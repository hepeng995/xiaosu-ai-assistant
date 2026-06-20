"""会话管理：维度隔离（platform:conversation:user）+ 多轮上下文。"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Conversation, Message


def make_conversation_key(platform: str, conversation_id: str, user_id: str) -> str:
    """统一会话 key：platform:conversation_id:user_id。"""
    return f"{platform}:{conversation_id}:{user_id}"


async def get_or_create_conversation(
    platform: str,
    conversation_id: str,
    user_id: str,
    user_name: str | None,
    session: AsyncSession,
) -> Conversation:
    """获取或创建会话（按平台+会话+用户唯一）。"""
    conv_key = make_conversation_key(platform, conversation_id, user_id)
    result = await session.execute(
        select(Conversation).where(
            Conversation.platform == platform,
            Conversation.conversation_key == conv_key,
            Conversation.user_id == user_id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        conv = Conversation(
            platform=platform, conversation_key=conv_key, user_id=user_id, user_name=user_name
        )
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
    return conv


async def save_message(
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    session: AsyncSession,
    **extra: object,
) -> Message:
    """保存一轮消息（含 token/引用/工具调用等附加字段）。"""
    msg = Message(conversation_id=conversation_id, role=role, content=content, **extra)  # type: ignore[arg-type]
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


async def update_message(
    message: Message,
    session: AsyncSession,
    **fields: object,
) -> Message:
    """更新已保存消息（用于先落 assistant 占位，再回填结果/错误）。"""
    for key, value in fields.items():
        setattr(message, key, value)
    await session.commit()
    await session.refresh(message)
    return message


async def get_recent_messages(
    conversation_id: uuid.UUID, session: AsyncSession, limit: int | None = None
) -> list[Message]:
    """取最近若干条消息（倒序取再正序返回，用于上下文）。"""
    limit = limit or settings.CONVERSATION_MAX_TURNS * 2
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    msgs = list(result.scalars().all())
    msgs.reverse()
    return msgs
