"""钉钉 IM 适配器：验签 + 解析 webhook + 通过 sessionWebhook 回复。"""

import base64
import hashlib
import hmac
from typing import Literal

import httpx
from loguru import logger

from app.core.config import settings
from app.im.base import IMMessage


def verify_sign(timestamp: str, sign: str) -> bool:
    """校验钉钉回调签名：HMAC-SHA256(timestamp + '\\n' + app_secret) → base64。

    未配置 secret 时（开发环境）放行并告警，生产环境必须配置真实 secret。
    """
    secret = settings.DINGTALK_APP_SECRET
    if not settings.is_secret_configured(secret):
        logger.warning("DINGTALK_APP_SECRET 未配置，跳过验签（仅开发环境允许）")
        return True
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(
        secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256
    ).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, sign)


def parse_webhook(payload: dict) -> IMMessage:
    """解析钉钉 webhook payload 为统一 IMMessage。"""
    conv_type_raw = str(payload.get("conversationType", "1"))
    conversation_type: Literal["group", "private"] = (
        "group" if conv_type_raw == "2" else "private"
    )
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
        logger.info("无 sessionWebhook，跳过钉钉回复（可能为本地/mock 测试）")
        return False
    body = {
        "msgtype": "markdown",
        "markdown": {"title": "小苏", "text": markdown or text},
    }
    try:
        async with httpx.AsyncClient(timeout=float(settings.IM_DEFAULT_TIMEOUT_SECONDS)) as client:
            resp = await client.post(session_webhook, json=body)
        return resp.status_code == 200
    except Exception as exc:
        logger.warning("钉钉回复失败: {}", exc)
        return False
