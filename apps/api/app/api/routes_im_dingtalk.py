"""钉钉机器人回调 API：验签 → 解析 → chat → 格式化 → 回复。"""

from fastapi import APIRouter, Depends, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppException, ErrorCode
from app.db.session import get_db
from app.im.dingtalk import parse_webhook, reply_via_webhook, verify_sign
from app.im.formatter import format_reply
from app.services import chat_service

router = APIRouter(prefix="/api/im/dingtalk", tags=["im"])


@router.post("/callback")
async def dingtalk_callback(request: Request, session: AsyncSession = Depends(get_db)) -> dict:
    """钉钉 Webhook 回调。"""
    payload = await request.json()
    timestamp = request.headers.get("timestamp", "")
    sign = request.headers.get("sign", "")

    # 1) 验签
    if not verify_sign(timestamp, sign):
        logger.warning("钉钉验签失败")
        raise AppException(ErrorCode.IM_VERIFY_ERROR, "验签失败", 401)

    # 2) 解析
    im_msg = parse_webhook(payload)
    if not im_msg.text:
        return {"success": False, "message": "空消息"}
    logger.info(
        "钉钉消息 user={} conv={} text={}",
        im_msg.user_id,
        im_msg.conversation_id,
        im_msg.text[:50],
    )

    # 3) 调用 chat（异常兜底，IM 端必有回复）
    try:
        result = await chat_service.chat(
            platform="dingtalk",
            conversation_id=im_msg.conversation_id,
            user_id=im_msg.user_id,
            message=im_msg.text,
            session=session,
            user_name=im_msg.user_name,
        )
    except Exception as exc:
        logger.exception("chat 处理异常: {}", exc)
        result = {
            "answer": "小苏遇到了一点问题，已记录日志，请稍后再试。",
            "references": [],
            "tool_calls": [],
            "refused": True,
        }

    # 4) 格式化 + 回复钉钉
    text, markdown = format_reply(
        result.get("answer", ""),
        result.get("references", []),
        result.get("tool_calls", []),
    )
    session_webhook = payload.get("sessionWebhook", "")
    await reply_via_webhook(session_webhook, text, markdown)

    return {"success": True, "answer": text, "refused": result.get("refused", False)}
