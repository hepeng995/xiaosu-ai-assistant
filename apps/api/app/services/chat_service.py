"""聊天服务：编排 Agent（LLM 自主选工具/检索）→ 引用 + 拒答 + 落库。"""

import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.agent import run as agent_run
from app.agents.prompts import REFUSAL_NO_RESULT, REFUSAL_PRIVACY, SENSITIVE_KEYWORDS
from app.services.conversation_service import (
    get_or_create_conversation,
    get_recent_messages,
    save_message,
)


async def chat(
    platform: str,
    conversation_id: str,
    user_id: str,
    message: str,
    session: AsyncSession,
    user_name: str | None = None,
) -> dict:
    """主流程：敏感过滤 → Agent（自主选工具/检索）→ 引用 + 拒答 → 落库。"""
    start = time.time()
    conv = await get_or_create_conversation(platform, conversation_id, user_id, user_name, session)

    # 基础安全：敏感关键词拒答
    if any(kw in message for kw in SENSITIVE_KEYWORDS):
        await save_message(conv.id, "user", message, session)
        await save_message(conv.id, "assistant", REFUSAL_PRIVACY, session)
        return {
            "answer": REFUSAL_PRIVACY,
            "references": [],
            "tool_calls": [],
            "usage": {},
            "refused": True,
        }

    # 历史上下文
    history = await get_recent_messages(conv.id, session)
    history_msgs = [
        {"role": m.role, "content": m.content} for m in history if m.role in ("user", "assistant")
    ]

    # Agent：LLM 自主决定调用哪个工具（含知识库检索），无 if-else 路由
    result = await agent_run(history_msgs, message, session)

    # 拒答判断：仅知识库检索且无命中 → 拒答（绝不编造）
    has_external_tool = any(tc.get("name") != "search_knowledge_base" for tc in result.tool_calls)
    if not has_external_tool and not result.references:
        answer, refused = REFUSAL_NO_RESULT, True
    else:
        answer, refused = result.answer, result.refused

    latency_ms = int((time.time() - start) * 1000)
    await save_message(conv.id, "user", message, session)
    await save_message(
        conv.id,
        "assistant",
        answer,
        session,
        references=result.references,
        tool_calls=result.tool_calls,
        prompt_tokens=result.usage.get("prompt_tokens", 0),
        completion_tokens=result.usage.get("completion_tokens", 0),
        total_tokens=result.usage.get("total_tokens", 0),
        success=not refused,
        latency_ms=latency_ms,
    )

    return {
        "answer": answer,
        "references": result.references,
        "tool_calls": result.tool_calls,
        "usage": result.usage,
        "refused": refused,
    }
