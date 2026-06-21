"""对话日志 API（管理后台查看员工提问/AI 回答/工具调用/Token）。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin
from app.db.session import get_db
from app.models import Conversation, Message

# router 级鉴权：对话日志含员工隐私与 Token 成本，仅管理员可查
router = APIRouter(
    prefix="/api/admin/messages",
    tags=["admin-logs"],
    dependencies=[Depends(require_admin)],
)


@router.get("")
async def list_messages(
    session: AsyncSession = Depends(get_db), limit: int = Query(50, le=200)
) -> dict:
    """列出最近的对话消息（倒序）。"""
    result = await session.execute(
        select(Message, Conversation)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    items = [
        {
            "id": str(m.id),
            "conversation_id": str(m.conversation_id),
            "platform": c.platform,
            "user_id": c.user_id,
            "user_name": c.user_name,
            "conversation_key": c.conversation_key,
            "role": m.role,
            "content": m.content,
            "references": m.references,
            "tool_calls": m.tool_calls,
            "prompt_tokens": m.prompt_tokens,
            "completion_tokens": m.completion_tokens,
            "total_tokens": m.total_tokens,
            "estimated_cost": float(m.estimated_cost),
            "success": m.success,
            "error_code": m.error_code,
            "latency_ms": m.latency_ms,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m, c in result.all()
    ]
    return {"items": items, "total": len(items)}
