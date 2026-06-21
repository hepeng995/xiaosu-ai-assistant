"""飞书 IM 适配器：握手 + AES 解密 + 签名校验 + token 换取 + 主动发消息。

与钉钉适配器不同，飞书回复需先用 ``app_id/app_secret`` 换取 ``tenant_access_token``，
再调用发消息接口；事件回调支持 Encrypt Key 加密与 ``X-Lark-Signature`` 验签。
未配置 ``FEISHU_ENCRYPT_KEY``/``FEISHU_APP_SECRET`` 时开发环境放行并告警（与钉钉一致）。
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Literal

import httpx
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from loguru import logger

from app.core.config import settings
from app.im.base import IMAttachment, IMMention, IMMessage

# tenant_access_token 本地缓存（模块级，asyncio 单进程内共享；多 worker 各自缓存）
_token_cache: dict[str, Any] = {"token": "", "expire_at": 0.0}

_EVENT_MESSAGE_RECEIVE = "im.message.receive_v1"
_IM_REPLY_RETRIES = 1


async def _post_json_with_retry(url: str, **kwargs: Any) -> httpx.Response:
    """IM 外呼 POST：对网络异常/超时/5xx 重试 1 次，4xx 不重试。"""
    last_exc: Exception | None = None
    async with httpx.AsyncClient(timeout=float(settings.IM_DEFAULT_TIMEOUT_SECONDS)) as client:
        for attempt in range(_IM_REPLY_RETRIES + 1):
            try:
                resp = await client.post(url, **kwargs)
                if resp.status_code < 500:
                    return resp
                logger.bind(module="im", event="feishu_http").warning(
                    "飞书外呼 5xx attempt={}/{} status={}",
                    attempt + 1,
                    _IM_REPLY_RETRIES + 1,
                    resp.status_code,
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                logger.bind(module="im", event="feishu_http").warning(
                    "飞书外呼异常 attempt={}/{} err={}",
                    attempt + 1,
                    _IM_REPLY_RETRIES + 1,
                    exc,
                )
            if attempt < _IM_REPLY_RETRIES:
                continue
            if last_exc is not None:
                raise RuntimeError("飞书外呼失败") from last_exc
            return resp
    raise RuntimeError("飞书外呼失败")


def is_url_verification(payload: dict) -> bool:
    """是否为飞书 Request URL 校验握手请求。"""
    return payload.get("type") == "url_verification"


def verify_token(token: str) -> bool:
    """校验回调事件的 Verification Token（飞书开放平台配置）。

    未配置时开发环境放行并告警。
    """
    expected = settings.FEISHU_VERIFICATION_TOKEN
    if not settings.is_secret_configured(expected):
        if not settings.is_dev:
            logger.bind(module="im", event="feishu_token").warning(
                "生产环境 FEISHU_VERIFICATION_TOKEN 未配置，拒绝 token 校验"
            )
            return False
        logger.bind(module="im", event="feishu_token").warning(
            "FEISHU_VERIFICATION_TOKEN 未配置，跳过 token 校验（仅开发环境允许）"
        )
        return True
    return hmac.compare_digest(expected, token)


def verify_signature(timestamp: str, nonce: str, raw_body: str, signature: str) -> bool:
    """校验 X-Lark-Signature：``SHA256(timestamp + nonce + encrypt_key + body)``。

    未配置 ``FEISHU_ENCRYPT_KEY`` 时开发环境放行并告警。
    ``raw_body`` 必须为解密前的原始请求体字符串。
    """
    encrypt_key = settings.FEISHU_ENCRYPT_KEY
    if not settings.is_secret_configured(encrypt_key):
        if not settings.is_dev:
            logger.bind(module="im", event="feishu_signature").warning(
                "生产环境 FEISHU_ENCRYPT_KEY 未配置，拒绝验签"
            )
            return False
        logger.bind(module="im", event="feishu_signature").warning(
            "FEISHU_ENCRYPT_KEY 未配置，跳过验签（仅开发环境允许）"
        )
        return True
    to_sign = f"{timestamp}{nonce}{encrypt_key}{raw_body}"
    expected = hashlib.sha256(to_sign.encode("utf-8")).hexdigest()
    return hmac.compare_digest(expected, signature)


def decrypt_payload(encrypt_b64: str) -> dict:
    """解密飞书加密事件：AES-256-CBC。

    key = ``SHA256(encrypt_key)`` 前 32 字节；IV = 密文前 16 字节；PKCS7 去填充。
    需已配置 ``FEISHU_ENCRYPT_KEY``。
    """
    key = hashlib.sha256(settings.FEISHU_ENCRYPT_KEY.encode("utf-8")).digest()  # 32 bytes
    ciphertext = base64.b64decode(encrypt_b64)
    iv, encrypted = ciphertext[:16], ciphertext[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(encrypted) + decryptor.finalize()
    unpadder = sym_padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    return json.loads(plaintext.decode("utf-8"))


def parse_event(event_payload: dict) -> IMMessage:
    """解析飞书 ``im.message.receive_v1`` 事件为统一 IMMessage。

    - ``chat_type`` ``p2p`` → private，其余 → group
    - 仅 ``message_type=text`` 提取文本，并剥离群聊 ``@机器人`` 占位符
    - 非文本消息 ``text`` 置空（路由层据此判空消息）
    """
    event = event_payload.get("event") or {}
    msg = event.get("message") or {}
    sender = (event.get("sender") or {}).get("sender_id") or {}

    chat_type = msg.get("chat_type", "p2p")
    conversation_type: Literal["group", "private", "web"] = (
        "private" if chat_type == "p2p" else "group"
    )

    message_type = msg.get("message_type")
    raw_mentions = msg.get("mentions") or []
    content_text = ""
    mentions: list[IMMention] = []
    attachments: list[IMAttachment] = []
    if message_type == "text":
        try:
            content_text = json.loads(msg.get("content") or "{}").get("text", "")
        except json.JSONDecodeError:
            content_text = ""
        content_text = " ".join(_strip_at_mention(content_text, raw_mentions).split())
        mentions = _extract_mentions(raw_mentions)
    elif message_type == "file":
        attachments = _extract_file_attachments(msg)

    return IMMessage(
        platform="feishu",
        message_id=msg.get("message_id", ""),
        conversation_id=msg.get("chat_id", ""),
        conversation_type=conversation_type,
        user_id=sender.get("open_id") or sender.get("user_id") or "",
        user_name=None,  # 飞书 v1 事件 sender 仅含 id，无名称
        text=content_text,
        raw=event_payload,
        mentions=mentions,
        attachments=attachments,
    )


def _strip_at_mention(text: str, mentions: list[dict]) -> str:
    """移除群聊消息中 @用户/机器人的占位符（如 ``@_user_1``）。"""
    cleaned = text
    for mention in mentions:
        key = mention.get("key")
        if key:
            cleaned = cleaned.replace(key, "")
    return cleaned


def _extract_mentions(mentions: list[dict]) -> list[IMMention]:
    """保留非机器人 @ 成员，用于飞书 post 的 at 富文本展示。"""
    items: list[IMMention] = []
    for mention in mentions:
        name = str(mention.get("name") or "")
        mention_id = mention.get("id") or {}
        open_id = str(mention_id.get("open_id") or "")
        if name == "小苏":
            continue
        items.append(
            IMMention(
                open_id=open_id,
                user_id=str(mention_id.get("user_id") or ""),
                name=name,
                key=str(mention.get("key") or ""),
            )
        )
    return items


def _extract_file_attachments(msg: dict) -> list[IMAttachment]:
    """从飞书 file 消息中提取附件元数据。"""
    try:
        content = json.loads(msg.get("content") or "{}")
    except json.JSONDecodeError:
        return []
    filename = str(content.get("file_name") or content.get("name") or "upload")
    file_type = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    file_key = str(content.get("file_key") or "")
    if not file_key:
        return []
    return [
        IMAttachment(
            file_key=file_key,
            filename=filename,
            file_size=int(content.get("file_size") or content.get("size") or 0),
            file_type=file_type,
        )
    ]


def is_message_receive_event(event_payload: dict) -> bool:
    """是否为接收消息事件（仅此事件进入聊天流程）。"""
    header = event_payload.get("header") or {}
    return header.get("event_type") == _EVENT_MESSAGE_RECEIVE


async def get_tenant_access_token() -> str:
    """获取 ``tenant_access_token``（本地缓存，提前 60s 过期）。

    失败时抛出 ``RuntimeError``，由调用方决定降级。
    """
    if _token_cache["token"] and time.time() < _token_cache["expire_at"] - 60:
        return _token_cache["token"]

    if not settings.is_secret_configured(settings.FEISHU_APP_SECRET):
        raise RuntimeError("FEISHU_APP_SECRET 未配置，无法获取 tenant_access_token")

    url = f"{settings.FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal"
    body = {"app_id": settings.FEISHU_APP_ID, "app_secret": settings.FEISHU_APP_SECRET}
    try:
        resp = await _post_json_with_retry(url, json=body)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # 顶层兜底，统一转 RuntimeError
        logger.bind(module="im", event="feishu_token").warning(
            "获取飞书 tenant_access_token 失败: {}", exc
        )
        raise RuntimeError("获取飞书 tenant_access_token 失败") from exc

    token = data.get("tenant_access_token", "")
    expire = int(data.get("expire", 7200))
    _token_cache.update(token=token, expire_at=time.time() + expire)
    return token


async def download_message_file(message_id: str, file_key: str) -> bytes:
    """下载飞书消息文件内容，供知识库文件上传问答使用。"""
    token = await get_tenant_access_token()
    url = f"{settings.FEISHU_BASE_URL}/im/v1/messages/{message_id}/resources/{file_key}"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"type": "file"}
    async with httpx.AsyncClient(timeout=float(settings.IM_DEFAULT_TIMEOUT_SECONDS)) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        return resp.content


async def reply_message(receive_id: str, content: dict, msg_type: str = "text") -> bool:
    """通过飞书发消息接口主动回复（``receive_id_type=chat_id``）。

    ``content`` 为飞书消息体（text: ``{"text": "..."}``；post: ``{"zh_cn": {...}}``），
    内部序列化为 content 字符串。失败记日志并返回 False（与钉钉一致，不抛出）。
    """
    if not receive_id:
        logger.bind(module="im", event="feishu_reply").info(
            "无 receive_id(chat_id)，跳过飞书回复（可能为本地/mock 测试）"
        )
        return False

    try:
        token = await get_tenant_access_token()
    except RuntimeError as exc:
        logger.bind(module="im", event="feishu_reply").warning("飞书回复跳过: {}", exc)
        return False

    url = f"{settings.FEISHU_BASE_URL}/im/v1/messages?receive_id_type=chat_id"
    headers = {"Authorization": f"Bearer {token}"}
    body = {
        "receive_id": receive_id,
        "msg_type": msg_type,
        "content": json.dumps(content, ensure_ascii=False),
    }
    try:
        resp = await _post_json_with_retry(url, json=body, headers=headers)
        return resp.status_code == 200
    except Exception as exc:  # IM 回复失败兜底，不抛出
        logger.bind(module="im", event="feishu_reply").warning("飞书回复失败: {}", exc)
        return False
