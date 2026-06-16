"""聊天服务：编排 检索 → RAG Prompt → LLM → 引用 + 拒答 + 落库。"""

import time

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import (
    RAG_PROMPT_TEMPLATE,
    REFUSAL_NO_RESULT,
    REFUSAL_PRIVACY,
    SENSITIVE_KEYWORDS,
    SYSTEM_PROMPT,
)
from app.llm.openai_compatible import llm_service
from app.services.conversation_service import (
    get_or_create_conversation,
    get_recent_messages,
    save_message,
)
from app.services.retrieval_service import search_knowledge


def _format_chunks(items: list[dict]) -> str:
    """将检索片段格式化为 Prompt 输入。"""
    parts: list[str] = []
    for i, it in enumerate(items, 1):
        if it.get("heading_path"):
            loc = it["heading_path"]
        elif it.get("page_number") is not None:
            loc = f"第 {it['page_number']} 页"
        else:
            loc = f"第 {it.get('paragraph_index', '?')} 段"
        parts.append(f"[{i}] {it['filename']}｜{loc}\n{it['content']}")
    return "\n\n".join(parts)


async def chat(
    platform: str,
    conversation_id: str,
    user_id: str,
    message: str,
    session: AsyncSession,
    user_name: str | None = None,
) -> dict:
    """主流程：敏感过滤 → 检索 → RAG → LLM → 引用 → 落库。"""
    start = time.time()
    conv = await get_or_create_conversation(platform, conversation_id, user_id, user_name, session)

    # 基础安全：敏感关键词拒答（非工具选择硬编码）
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

    # 检索知识库
    items = await search_knowledge(message, session)
    if not items:
        # 无结果或全部低于阈值 → 拒答（绝不编造）
        await save_message(conv.id, "user", message, session)
        await save_message(conv.id, "assistant", REFUSAL_NO_RESULT, session)
        return {
            "answer": REFUSAL_NO_RESULT,
            "references": [],
            "tool_calls": [],
            "usage": {},
            "refused": True,
        }

    # 组装上下文（历史 + 当前 RAG prompt）
    history = await get_recent_messages(conv.id, session)
    history_msgs = [
        {"role": m.role, "content": m.content} for m in history if m.role in ("user", "assistant")
    ]
    rag_prompt = RAG_PROMPT_TEMPLATE.format(chunks=_format_chunks(items), question=message)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history_msgs,
        {"role": "user", "content": rag_prompt},
    ]

    # LLM 生成（失败兜底）
    try:
        resp = await llm_service.chat(messages)
        answer = resp.content
        usage = {
            "prompt_tokens": resp.prompt_tokens,
            "completion_tokens": resp.completion_tokens,
            "total_tokens": resp.prompt_tokens + resp.completion_tokens,
        }
    except Exception as exc:
        logger.exception("LLM 生成失败，使用兜底文案: {}", exc)
        answer = "小苏的模型服务暂时不可用，请稍后再试。"
        usage = {}

    references = [
        {
            "document_id": it["document_id"],
            "chunk_id": it["chunk_id"],
            "filename": it["filename"],
            "heading_path": it["heading_path"],
            "page_number": it["page_number"],
            "paragraph_index": it["paragraph_index"],
            "quote": it["quote"],
            "score": it["score"],
        }
        for it in items
    ]

    latency_ms = int((time.time() - start) * 1000)
    await save_message(conv.id, "user", message, session)
    await save_message(
        conv.id,
        "assistant",
        answer,
        session,
        references=references,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
        success=True,
        latency_ms=latency_ms,
    )

    return {
        "answer": answer,
        "references": references,
        "tool_calls": [],
        "usage": usage,
        "refused": False,
    }
