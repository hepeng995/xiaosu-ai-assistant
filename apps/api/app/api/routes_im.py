"""IM 回调路由集中：钉钉 + 飞书（避免 api 目录超 8 文件红线，便于多平台维护）。

各平台回调统一流程：验签/握手 → 解析为 IMMessage → 调用 chat_service（异常兜底）
→ 格式化 → 平台回复。聊天/检索/Agent/落库链路完全复用，零重复。
"""

import asyncio
import json
import secrets
import time
from io import BytesIO
from typing import Any

from fastapi import APIRouter, Request, UploadFile
from loguru import logger

from app.core.config import settings
from app.core.errors import AppException, ErrorCode
from app.core.redis_client import acquire_idempotent
from app.db.session import AsyncSessionLocal
from app.im import feishu_stream
from app.im.base import IMAttachment, IMMessage
from app.im.dingtalk import (
    decrypt_event,
    encrypt_event,
    parse_webhook,
    reply_via_webhook,
    sign_event,
    verify_event_signature,
)
from app.im.feishu import (
    decrypt_payload,
    download_message_file,
    is_message_receive_event,
    is_url_verification,
    parse_event,
    reply_message,
    verify_signature,
    verify_token,
)
from app.im.formatter import format_feishu_post, format_reply
from app.parsers import SUPPORTED_EXTENSIONS
from app.services import chat_service, document_service
from app.services.indexing_service import index_document

# chat 处理异常时的统一兜底文案（不暴露技术细节，IM 端必有回复）
_CHAT_FALLBACK = {
    "answer": "小苏遇到了一点问题，已记录日志，请稍后再试。",
    "references": [],
    "tool_calls": [],
    "refused": True,
}
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()

dingtalk_router = APIRouter(prefix="/api/im/dingtalk", tags=["im"])


@dingtalk_router.get("/callback")
async def dingtalk_callback_probe(request: Request) -> dict:
    """钉钉消息接收地址校验：钉钉以 GET 探测，记录请求详情用于排查，返回 200。"""
    try:
        body = (await request.body()).decode("utf-8", "replace")[:500]
    except Exception:
        body = ""
    logger.bind(module="im", event="dingtalk_probe").warning(
        "钉钉GET校验 query=[{}] body=[{}] headers={}",
        str(request.query_params),
        body,
        dict(request.headers),
    )
    return {"success": True}


@dingtalk_router.post("/callback")
async def dingtalk_callback(request: Request) -> dict:
    """钉钉事件订阅加密回调：验签 → AES 解密 → check_url 校验/消息处理 → sessionWebhook 回复。

    钉钉企业内部应用以「事件订阅 + AES 加密」推送消息：
    query 带 ``msg_signature``/``timestamp``/``nonce``，body 为 ``{"encrypt": "AES 密文"}``。
    """
    msg_signature = request.query_params.get("msg_signature", "")
    timestamp = request.query_params.get("timestamp", "")
    nonce = request.query_params.get("nonce", "")
    try:
        payload = await request.json()
    except ValueError:
        payload = {}
    encrypt = payload.get("encrypt", "") if isinstance(payload, dict) else ""

    # 1) 验签（SHA1 sort(token, timestamp, nonce, encrypt)）
    if not verify_event_signature(timestamp, nonce, encrypt, msg_signature):
        logger.bind(module="im", event="verify", platform="dingtalk").warning("钉钉事件验签失败")
        raise AppException(ErrorCode.IM_VERIFY_ERROR, "验签失败", 401)

    # 2) AES 解密
    try:
        event, receive_id = decrypt_event(encrypt) if encrypt else ({}, "")
    except Exception as exc:  # 解密失败统一转 IM 校验错误
        logger.bind(module="im", event="decrypt", platform="dingtalk").warning(
            "钉钉事件解密失败: {}", exc
        )
        raise AppException(ErrorCode.IM_VERIFY_ERROR, "解密失败", 400) from exc

    # 3) check_url 地址校验请求 → 返回包含 success 的加密响应（钉钉要求 1200ms 内）
    if event.get("EventType") == "check_url":
        logger.bind(module="im", event="check_url", platform="dingtalk").info(
            "钉钉回调地址校验通过"
        )
        encrypted = encrypt_event("success", receive_id)
        resp_ts = str(int(time.time() * 1000))
        resp_nonce = secrets.token_hex(8)
        return {
            "msg_signature": sign_event(resp_ts, resp_nonce, encrypted),
            "timeStamp": resp_ts,
            "nonce": resp_nonce,
            "encrypt": encrypted,
        }

    # 4) 消息事件 → 解析 → 幂等去重 → 后台处理（chat 主链路耗时数秒，避免网关超时与重试）
    im_msg = parse_webhook(event)
    if not im_msg.text:
        return {"success": False, "message": "空消息"}
    logger.bind(module="im", event="message_received", platform="dingtalk").info(
        "钉钉消息 user={} conv={} text={}",
        im_msg.user_id,
        im_msg.conversation_id,
        im_msg.text[:50],
    )

    # 5) 幂等去重：钉钉网络异常会重试同一消息，用 msgId 去重避免重复回复
    idem_key = f"dingtalk:msg:{im_msg.message_id}"
    if not await acquire_idempotent(idem_key):
        logger.bind(module="im", event="dedup", platform="dingtalk").info(
            "钉钉重复事件已忽略 msgId={}", im_msg.message_id
        )
        return {"success": True, "deduplicated": True}

    # 6) 立即返回 200，后台异步处理（占位消息 + 最终答案，IM 端必有回复）
    session_webhook = event.get("sessionWebhook", "")
    task = asyncio.create_task(
        _handle_dingtalk_message(
            im_msg, session_webhook, logger.bind(module="im", platform="dingtalk")
        )
    )
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return {"success": True, "accepted": True}


async def _handle_dingtalk_message(
    im_msg: IMMessage,
    session_webhook: str,
    bind: Any,
) -> None:
    """后台处理钉钉消息：先发占位消息消除黑盒等待 → 跑 chat 主链路 → 发最终答案。

    钉钉 sessionWebhook 不支持流式更新单条消息，故采用双消息方案（占位 + 答案）。
    任一阶段失败均有兜底（占位失败不阻塞主链路；chat 异常用 _CHAT_FALLBACK），保证 IM 端必有回复。
    """
    # 1) 占位消息（best-effort：失败只告警，不阻塞主链路）
    if settings.DINGTALK_PLACEHOLDER_ENABLED and session_webhook:
        try:
            await reply_via_webhook(
                session_webhook, text=settings.DINGTALK_PLACEHOLDER_TEXT, markdown=None
            )
        except Exception as exc:
            bind.warning("钉钉占位消息发送失败（已忽略，继续主链路）: {}", exc)

    # 2) chat 主链路（异常兜底 _CHAT_FALLBACK）
    try:
        async with AsyncSessionLocal() as session:
            result = await chat_service.chat(
                platform="dingtalk",
                conversation_id=im_msg.conversation_id,
                user_id=im_msg.user_id,
                message=im_msg.text,
                session=session,
                user_name=im_msg.user_name,
            )
    except Exception as exc:
        bind.exception("钉钉后台 chat 异常: {}", exc)
        result = _CHAT_FALLBACK

    # 3) 格式化 + 回复最终答案（Markdown 优先，用 sessionWebhook 被动回复）
    text, markdown = format_reply(
        result.get("answer", ""), result.get("references", []), result.get("tool_calls", [])
    )
    if await reply_via_webhook(session_webhook, text, markdown):
        bind.info("钉钉后台回复完成")
    else:
        bind.error("钉钉最终答案发送失败 sessionWebhook={}", session_webhook)


feishu_router = APIRouter(prefix="/api/im/feishu", tags=["im"])


@feishu_router.post("/callback")
async def feishu_callback(request: Request) -> dict:
    """飞书事件回调：握手 → 验签 → 解密 → 解析 → 幂等去重 → 后台异步处理。

    飞书要求 3 秒内返回 HTTP 200，否则判定超时并重试（最多 4 次，间隔 15s/5min/1h/6h）。
    而 chat 主链路（LLM + RAG + Agent）通常耗时较长，因此：
    - 收到消息后**立即返回 200**，实际处理放入后台任务；
    - 用 ``message_id`` 做幂等去重，避免重试导致重复回复。
    """
    raw_body = (await request.body()).decode("utf-8", errors="ignore")
    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError as exc:
        raise AppException(ErrorCode.IM_VERIFY_ERROR, "非法请求体", 400) from exc

    # 0) url_verification 握手 —— 必须最先返回，否则飞书不接受 Request URL
    if is_url_verification(payload):
        verify_token(payload.get("token", ""))
        return {"challenge": payload.get("challenge", "")}

    # 1) 解密（配置了 Encrypt Key 时回调体为 {"encrypt": "base64..."}）
    #    飞书握手与事件推送均用 Encrypt Key 加密；其中【握手请求不带 X-Lark-Signature】，
    #    靠 Encrypt Key 解密成功即可证明请求来源，因此先解密识别握手，再对事件验签。
    event_payload = decrypt_payload(payload["encrypt"]) if "encrypt" in payload else payload

    # 2) 加密模式握手：解密后识别 url_verification 并回传 challenge（飞书握手不验签）
    if is_url_verification(event_payload):
        verify_token(event_payload.get("token", ""))
        return {"challenge": event_payload.get("challenge", "")}

    # 3) 真实事件验签（X-Lark-Signature = SHA256(timestamp + nonce + encrypt_key + body)）
    timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
    nonce = request.headers.get("X-Lark-Request-Nonce", "")
    sign = request.headers.get("X-Lark-Signature", "")
    if not verify_signature(timestamp, nonce, raw_body, sign):
        logger.bind(module="im", event="verify", platform="feishu").warning("飞书验签失败")
        raise AppException(ErrorCode.IM_VERIFY_ERROR, "验签失败", 401)

    # 4) 仅处理接收消息事件
    if not is_message_receive_event(event_payload):
        return {"success": False, "message": "忽略非消息事件"}

    im_msg = parse_event(event_payload)
    if not im_msg.text and not im_msg.attachments:
        return {"success": False, "message": "空消息"}
    logger.bind(module="im", event="message_received", platform="feishu").info(
        "飞书消息 user={} conv={} text={}", im_msg.user_id, im_msg.conversation_id, im_msg.text[:50]
    )

    # 5) 幂等去重：飞书因 3 秒超时会重试同一消息，用 message_id 去重避免重复回复
    idem_key = f"feishu:msg:{im_msg.message_id}"
    if not await acquire_idempotent(idem_key):
        logger.bind(module="im", event="dedup", platform="feishu").info(
            "飞书重复事件已忽略 message_id={}", im_msg.message_id
        )
        return {"success": True, "deduplicated": True}

    # 6) 立即返回 200，后台异步处理（chat 主链路可能耗时数秒，避免飞书超时重试）
    task = asyncio.create_task(_handle_feishu_message(im_msg))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return {"success": True, "accepted": True}


async def _handle_feishu_message(im_msg: IMMessage) -> None:
    """后台处理飞书消息：流式卡片（开启且创建成功）或一次性 post（降级）。

    流式路径复用 chat_service.stream_chat，逐 token 攒批更新卡片（打字机效果）；
    stream_chat 内部已落库与异常兜底。任一阶段失败自动降级为一次性 post，保证 IM 必有回复。
    """
    bind = logger.bind(
        module="im",
        event="feishu_async",
        platform="feishu",
        conversation_id=im_msg.conversation_id,
        user_id=im_msg.user_id,
    )
    if im_msg.attachments:
        handled = await _handle_feishu_file_message(im_msg, bind)
        if handled:
            return

    card_id: str | None = None
    if settings.FEISHU_STREAMING_ENABLED:
        card_id = await feishu_stream.create_streaming_card(im_msg.conversation_id)

    if card_id is not None:
        await _feishu_stream_reply(im_msg, card_id, bind)
        return

    # 降级：一次性 post 富文本回复（含引用与工具调用）
    try:
        async with AsyncSessionLocal() as session:
            result = await chat_service.chat(
                platform="feishu",
                conversation_id=im_msg.conversation_id,
                user_id=im_msg.user_id,
                message=im_msg.text,
                session=session,
                user_name=im_msg.user_name,
            )
    except Exception as exc:  # 后台任务异常兜底，IM 端必有回复
        bind.exception("飞书后台 chat 异常: {}", exc)
        result = _CHAT_FALLBACK

    post_content = format_feishu_post(
        result.get("answer", ""),
        result.get("references", []),
        result.get("tool_calls", []),
        mentions=im_msg.mentions,
    )
    await reply_message(im_msg.conversation_id, post_content, msg_type="post")
    bind.info("飞书后台回复完成（一次性）")


async def _feishu_stream_reply(im_msg: IMMessage, card_id: str, bind: Any) -> None:
    """流式回复：stream_chat 攒批更新卡片文本，结束追加引用并关闭流式。

    stream_chat 内部已处理落库与异常兜底（update_message），此处仅负责卡片展示更新。
    """
    sequence = 1
    accumulated = ""
    status_lines: list[str] = []
    last_flush = time.monotonic()
    references: list[dict] = []
    flush_interval = settings.FEISHU_FLUSH_INTERVAL_MS / 1000.0  # 攒批间隔（可配置，默认 80ms）

    def _compose_card_text() -> str:
        """组合卡片正文：进度文案（markdown 引用块）+ 已累积 token。"""
        if status_lines:
            status_block = "\n".join(f"> {line}" for line in status_lines)
            return f"{status_block}\n\n{accumulated}".strip()
        return accumulated

    async def _flush() -> None:
        """攒批到达间隔时更新卡片文本（进度文案 + token）。"""
        nonlocal sequence, last_flush
        text = _compose_card_text()
        if text and await feishu_stream.update_card_text(card_id, text, sequence):
            sequence += 1
        last_flush = time.monotonic()

    async with AsyncSessionLocal() as session:
        try:
            async for event in chat_service.stream_chat(
                platform="feishu",
                conversation_id=im_msg.conversation_id,
                user_id=im_msg.user_id,
                message=im_msg.text,
                session=session,
                user_name=im_msg.user_name,
            ):
                ev = event.get("event")
                if ev == "status":
                    label = event.get("data", {}).get("label", "")
                    if label:
                        status_lines.append(label)
                        await _flush()  # 进度文案立即推送，消除空卡片黑盒等待
                elif ev == "token":
                    accumulated += event.get("data", {}).get("content", "")
                    if accumulated and time.monotonic() - last_flush >= flush_interval:
                        await _flush()
                elif ev == "references":
                    references = event.get("data", {}).get("references", []) or []
        except Exception as exc:  # stream_chat 内部已兜底；此处记日志，卡片尽量保留已累积内容
            bind.exception("飞书流式 stream_chat 异常: {}", exc)

    # 最终更新：累积全文 + 引用来源
    final_text = accumulated
    if references:
        ref_lines = "\n".join(
            f"{i + 1}. {r.get('filename', '')}" for i, r in enumerate(references)
        )
        final_text = f"{accumulated}\n\n---\n参考来源：\n{ref_lines}".strip()
    if im_msg.mentions:
        names = " ".join(f"@{m.name or m.open_id}" for m in im_msg.mentions)
        final_text = f"{final_text}\n\n{names}".strip()
    if final_text and await feishu_stream.update_card_text(card_id, final_text, sequence):
        sequence += 1
    await feishu_stream.close_streaming(card_id, sequence)  # best-effort 关闭
    bind.info("飞书流式回复完成")


async def download_feishu_file(message_id: str, attachment: IMAttachment) -> bytes:
    """下载飞书附件内容；单独包装便于测试替换。"""
    return await download_message_file(message_id, attachment.file_key)


async def _handle_feishu_file_message(im_msg: IMMessage, bind: Any) -> bool:
    """处理飞书文件消息：下载 → 上传知识库 → 同步索引 → 回复结果。"""
    if not im_msg.attachments:
        return False
    attachment = im_msg.attachments[0]
    ext = f".{attachment.file_type.lower().lstrip('.')}"
    if ext not in SUPPORTED_EXTENSIONS:
        post = format_feishu_post(
            f"这个文件暂时不能加入知识库。仅支持：{', '.join(sorted(SUPPORTED_EXTENSIONS))}。",
            [],
            [],
            mentions=im_msg.mentions,
        )
        await reply_message(im_msg.conversation_id, post, msg_type="post")
        return True
    if attachment.file_size > settings.UPLOAD_MAX_SIZE_BYTES:
        post = format_feishu_post(
            "文件超过大小限制，暂时不能加入知识库。", [], [], mentions=im_msg.mentions
        )
        await reply_message(im_msg.conversation_id, post, msg_type="post")
        return True
    try:
        content = await download_feishu_file(im_msg.message_id, attachment)
        upload = UploadFile(file=BytesIO(content), filename=attachment.filename)
        async with AsyncSessionLocal() as session:
            doc = await document_service.upload_document(upload, session)
            await index_document(doc.id)
            await session.refresh(doc)
        answer = f"文件「{attachment.filename}」已加入知识库，可以继续围绕它提问。"
        post = format_feishu_post(answer, [], [], mentions=im_msg.mentions)
        await reply_message(im_msg.conversation_id, post, msg_type="post")
        bind.info("飞书文件已加入知识库 filename={}", attachment.filename)
        return True
    except Exception as exc:
        bind.exception("飞书文件处理失败: {}", exc)
        post = format_feishu_post(
            "文件处理失败，请稍后再试或联系管理员。", [], [], mentions=im_msg.mentions
        )
        await reply_message(im_msg.conversation_id, post, msg_type="post")
        return True
