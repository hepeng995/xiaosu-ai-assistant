"""钉钉 IM 适配器：验签 + 解析 webhook + 通过 sessionWebhook 回复。"""

import base64
import hashlib
import hmac
import json
import os
import struct
from typing import Literal

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from loguru import logger

from app.core.config import settings
from app.im.base import IMMessage

_IM_REPLY_RETRIES = 1


def verify_sign(timestamp: str, sign: str) -> bool:
    """校验钉钉回调签名：HMAC-SHA256(timestamp + '\\n' + app_secret) → base64。

    未配置 secret 时（开发环境）放行并告警，生产环境必须配置真实 secret。
    """
    secret = settings.DINGTALK_APP_SECRET
    if not settings.is_secret_configured(secret):
        logger.bind(module="im", event="dingtalk_signature").warning(
            "DINGTALK_APP_SECRET 未配置，跳过验签（仅开发环境允许）"
        )
        return True
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(
        secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256
    ).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, sign)


def verify_event_signature(
    timestamp: str, nonce: str, encrypt: str, msg_signature: str
) -> bool:
    """钉钉事件订阅加密回调验签：``SHA1(sort(token, timestamp, nonce, encrypt))``。

    签名 token 取 ``DINGTALK_CALLBACK_TOKEN``；未配置时开发环境放行并告警。
    """
    token = settings.DINGTALK_CALLBACK_TOKEN
    if not settings.is_secret_configured(token):
        logger.bind(module="im", event="dingtalk_event_sign").warning(
            "DINGTALK_CALLBACK_TOKEN 未配置，跳过事件验签（仅开发环境允许）"
        )
        return True
    items = sorted([token, timestamp, nonce, encrypt])
    calc = hashlib.sha1("".join(items).encode("utf-8")).hexdigest()
    return hmac.compare_digest(calc, msg_signature)


def decrypt_event(encrypt: str) -> tuple[dict, str]:
    """钉钉事件订阅 AES-256-CBC 解密，返回 ``(事件字典, receiveId)``。

    - key = ``base64decode(aes_key + '=')``（32 字节）；iv = key[:16]
    - 明文结构：16 字节随机 + 4 字节网络序长度 + 消息 JSON + receiveId
    - 直接按长度字段截取消息，不依赖 PKCS7 去填充（receiveId 段长度可变）
    """
    aes_key = settings.DINGTALK_AES_KEY
    if not settings.is_secret_configured(aes_key):
        raise RuntimeError("DINGTALK_AES_KEY 未配置，无法解密钉钉加密事件")
    key = base64.b64decode(aes_key + "=")
    iv = key[:16]
    ciphertext = base64.b64decode(encrypt)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    pad_len = padded[-1]
    plain = padded[:-pad_len] if 1 <= pad_len <= 32 else padded
    msg_len = struct.unpack("!I", plain[16:20])[0]
    msg = plain[20 : 20 + msg_len].decode("utf-8", errors="replace")
    receive_id = plain[20 + msg_len :].decode("utf-8", errors="replace")
    return json.loads(msg), receive_id


def encrypt_event(msg: str, receive_id: str) -> str:
    """钉钉事件订阅 AES-256-CBC 加密响应（与 :func:`decrypt_event` 互逆）。

    明文 = 16 随机 + 4 网络序长度 + msg + receiveId，PKCS7(32 块) 填充后加密。
    钉钉校验回调时要求「1200ms 内返回包含 success 的加密字符串」。
    """
    aes_key = settings.DINGTALK_AES_KEY
    if not settings.is_secret_configured(aes_key):
        raise RuntimeError("DINGTALK_AES_KEY 未配置，无法加密钉钉响应")
    key = base64.b64decode(aes_key + "=")
    iv = key[:16]
    msg_bytes = msg.encode("utf-8")
    plain = (
        os.urandom(16)
        + struct.pack("!I", len(msg_bytes))
        + msg_bytes
        + receive_id.encode("utf-8")
    )
    pad_len = 32 - (len(plain) % 32)
    plain += bytes([pad_len]) * pad_len
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    return base64.b64encode(encryptor.update(plain) + encryptor.finalize()).decode("utf-8")


def sign_event(timestamp: str, nonce: str, encrypt: str) -> str:
    """计算事件响应签名：``SHA1(sort(token, timestamp, nonce, encrypt))``。

    用于加密响应体的 ``msg_signature`` 字段，钉钉据此验签响应。
    """
    token = settings.DINGTALK_CALLBACK_TOKEN
    items = sorted([token, timestamp, nonce, encrypt])
    return hashlib.sha1("".join(items).encode("utf-8")).hexdigest()


def parse_webhook(payload: dict) -> IMMessage:
    """解析钉钉 webhook payload 为统一 IMMessage。"""
    conv_type_raw = str(payload.get("conversationType", "1"))
    conversation_type: Literal["group", "private"] = "group" if conv_type_raw == "2" else "private"
    text = ((payload.get("text") or {}).get("content") or "").strip()
    return IMMessage(
        platform="dingtalk",
        message_id=payload.get("msgId", ""),
        conversation_id=payload.get("conversationId", ""),
        conversation_type=conversation_type,
        user_id=payload.get("senderStaffId") or payload.get("senderId") or "",
        user_name=payload.get("senderNick"),
        text=text,
        raw=payload,
    )


async def reply_via_webhook(session_webhook: str, text: str, markdown: str | None = None) -> bool:
    """通过钉钉 sessionWebhook 回复（Markdown 优先）。"""
    if not session_webhook:
        logger.bind(module="im", event="dingtalk_reply").info(
            "无 sessionWebhook，跳过钉钉回复（可能为本地/mock 测试）"
        )
        return False
    # 标题取回答摘要用于会话列表预览（不再固定"小苏"，避免每条消息开头都带前缀）
    title = (text or "").strip().replace("\n", " ")[:30] or "回复"
    body = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": markdown or text},
    }
    reply_logger = logger.bind(module="im", event="dingtalk_reply")
    async with httpx.AsyncClient(timeout=float(settings.IM_DEFAULT_TIMEOUT_SECONDS)) as client:
        for attempt in range(_IM_REPLY_RETRIES + 1):
            try:
                resp = await client.post(session_webhook, json=body)
                if resp.status_code == 200:
                    return True
                if resp.status_code < 500:
                    reply_logger.warning("钉钉回复失败 status={}", resp.status_code)
                    return False
                reply_logger.warning(
                    "钉钉回复 5xx attempt={}/{} status={}",
                    attempt + 1,
                    _IM_REPLY_RETRIES + 1,
                    resp.status_code,
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                reply_logger.warning(
                    "钉钉回复异常 attempt={}/{} err={}",
                    attempt + 1,
                    _IM_REPLY_RETRIES + 1,
                    exc,
                )
            if attempt < _IM_REPLY_RETRIES:
                continue
            return False
    return False
