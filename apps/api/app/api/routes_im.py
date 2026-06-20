"""IM 回调路由集中：钉钉 + 飞书（避免 api 目录超 8 文件红线，便于多平台维护）。

各平台回调统一流程：验签/握手 → 解析为 IMMessage → 调用 chat_service（异常兜底）
→ 格式化 → 平台回复。聊天/检索/Agent/落库链路完全复用，零重复。
"""

import asyncio
import json
import secrets
import time

from fastapi import APIRouter, Depends, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppException, ErrorCode
from app.core.redis_client import acquire_idempotent
from app.db.session import AsyncSessionLocal, get_db
from app.im.base import IMMessage
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
    is_message_receive_event,
    is_url_verification,
    parse_event,
    reply_message,
    verify_signature,
    verify_token,
)
from app.im.formatter import format_feishu_post, format_reply
from app.services import chat_service

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
async def dingtalk_callback(request: Request, session: AsyncSession = Depends(get_db)) -> dict:
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

    # 4) 消息事件 → 解析 → chat → 回复
    im_msg = parse_webhook(event)
    if not im_msg.text:
        return {"success": False, "message": "空消息"}
    logger.bind(module="im", event="message_received", platform="dingtalk").info(
        "钉钉消息 user={} conv={} text={}",
        im_msg.user_id,
        im_msg.conversation_id,
        im_msg.text[:50],
    )

    # 5) 调用 chat（异常兜底，IM 端必有回复）
    try:
        result = await chat_service.chat(
            platform="dingtalk",
            conversation_id=im_msg.conversation_id,
            user_id=im_msg.user_id,
            message=im_msg.text,
            session=session,
            user_name=im_msg.user_name,
        )
    except Exception as exc:  # IM 端兜底，保证必有回复
        logger.bind(module="im", event="chat_fallback", platform="dingtalk").exception(
            "chat 处理异常: {}", exc
        )
        result = _CHAT_FALLBACK

    # 6) 格式化 + 回复钉钉（Markdown 优先，用 sessionWebhook 被动回复）
    text, markdown = format_reply(
        result.get("answer", ""), result.get("references", []), result.get("tool_calls", [])
    )
    session_webhook = event.get("sessionWebhook", "")
    await reply_via_webhook(session_webhook, text, markdown)

    return {"success": True, "answer": text, "refused": result.get("refused", False)}


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
    if not im_msg.text:
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
    """后台处理飞书消息：chat 主链路 + 主动发消息回复（异常时发兜底消息）。

    在独立 DB 会话中执行（请求会话随响应结束而关闭）。
    """
    bind = logger.bind(
        module="im",
        event="feishu_async",
        platform="feishu",
        conversation_id=im_msg.conversation_id,
        user_id=im_msg.user_id,
    )
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

    # 格式化 + 主动回复飞书（post 富文本，含引用与工具调用）
    post_content = format_feishu_post(
        result.get("answer", ""), result.get("references", []), result.get("tool_calls", [])
    )
    await reply_message(im_msg.conversation_id, post_content, msg_type="post")
    bind.info("飞书后台回复完成")
