"""聊天服务：编排 Agent（LLM 自主选工具/检索）→ 引用 + 拒答 + 落库 + 异常兜底。"""

import time
from collections.abc import AsyncIterator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.agent import prepare_response
from app.agents.agent import run as agent_run
from app.agents.prompts import REFUSAL_NO_RESULT, REFUSAL_PRIVACY, SENSITIVE_KEYWORDS
from app.core.errors import ErrorCode
from app.core.pricing import estimate_cost
from app.llm.base import llm_service
from app.services.conversation_service import (
    get_or_create_conversation,
    get_recent_messages,
    save_message,
    update_message,
)

# 模型不可用兜底文案（不暴露技术细节）
_LLM_UNAVAILABLE = "小苏的模型服务暂时不可用，请稍后再试。"
_STREAM_CHUNK_SIZE = 6


def _classify_agent_error(exc: Exception) -> str:
    """将 Agent/LLM 异常映射到统一错误码，避免自由发挥。"""
    text = str(exc)
    if ErrorCode.LLM_AUTH_ERROR in text:
        return ErrorCode.LLM_AUTH_ERROR
    if ErrorCode.LLM_TIMEOUT in text or "timeout" in text.lower() or "timed out" in text.lower():
        return ErrorCode.LLM_TIMEOUT
    return ErrorCode.UNKNOWN_ERROR


def _chunk_text(text: str) -> list[str]:
    """将普通文本降级切片为 SSE token。"""
    return [text[i : i + _STREAM_CHUNK_SIZE] for i in range(0, len(text), _STREAM_CHUNK_SIZE)]


async def _emit_text(text: str) -> AsyncIterator[dict]:
    """输出 token 事件。"""
    for piece in _chunk_text(text):
        yield {"event": "token", "data": {"content": piece}}


async def chat(
    platform: str,
    conversation_id: str,
    user_id: str,
    message: str,
    session: AsyncSession,
    user_name: str | None = None,
) -> dict:
    """主流程：敏感过滤 → Agent（自主选工具/检索）→ 引用 + 拒答 + 兜底 → 落库。"""
    start = time.time()
    conv = await get_or_create_conversation(platform, conversation_id, user_id, user_name, session)

    # 基础安全：敏感关键词拒答
    if any(kw in message for kw in SENSITIVE_KEYWORDS):
        await save_message(conv.id, "user", message, session)
        await save_message(
            conv.id,
            "assistant",
            REFUSAL_PRIVACY,
            session,
            success=False,
            error_code=ErrorCode.UNKNOWN_ERROR,
            error_message="命中隐私/敏感问题拒答",
        )
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
    await save_message(conv.id, "user", message, session)
    assistant_msg = await save_message(
        conv.id,
        "assistant",
        "小苏正在处理这个问题...",
        session,
        success=True,
    )

    # Agent：LLM 自主决定调用哪个工具（含知识库检索），无 if-else 路由
    # 任何异常（含 LLM 认证失败/超时）都走兜底，保证 IM/Web 端必有友好回复
    try:
        result = await agent_run(history_msgs, message, session, message_id=assistant_msg.id)
    except Exception as exc:
        agent_error_code = _classify_agent_error(exc)
        logger.exception("Agent 执行失败，使用兜底文案: {}", exc)
        latency_ms = int((time.time() - start) * 1000)
        await update_message(
            assistant_msg,
            session,
            content=_LLM_UNAVAILABLE,
            success=False,
            error_code=agent_error_code,
            error_message="模型服务暂时不可用",
            latency_ms=latency_ms,
        )
        return {
            "answer": _LLM_UNAVAILABLE,
            "references": [],
            "tool_calls": [],
            "usage": {},
            "refused": False,
        }

    # 拒答判断：仅知识库检索且无命中 → 拒答（绝不编造）
    has_external_tool = any(tc.get("name") != "search_knowledge_base" for tc in result.tool_calls)
    answer: str
    refused: bool
    error_code: str | None
    error_message: str | None
    if not has_external_tool and not result.references:
        answer = REFUSAL_NO_RESULT
        refused = True
        error_code = ErrorCode.UNKNOWN_ERROR
        error_message = "知识库无可引用结果"
    else:
        answer = result.answer
        refused = result.refused
        error_code = None
        error_message = None

    latency_ms = int((time.time() - start) * 1000)
    await update_message(
        assistant_msg,
        session,
        content=answer,
        references=result.references,
        tool_calls=result.tool_calls,
        prompt_tokens=result.usage.get("prompt_tokens", 0),
        completion_tokens=result.usage.get("completion_tokens", 0),
        total_tokens=result.usage.get("total_tokens", 0),
        estimated_cost=estimate_cost(
            result.usage.get("prompt_tokens", 0), result.usage.get("completion_tokens", 0)
        ),
        success=not refused,
        error_code=error_code,
        error_message=error_message,
        latency_ms=latency_ms,
    )

    return {
        "answer": answer,
        "references": result.references,
        "tool_calls": result.tool_calls,
        "usage": result.usage,
        "refused": refused,
    }


async def stream_chat(
    platform: str,
    conversation_id: str,
    user_id: str,
    message: str,
    session: AsyncSession,
    user_name: str | None = None,
) -> AsyncIterator[dict]:
    """SSE 主流程：工具/检索准备后，最终回答阶段尽量使用 LLM 真流式输出。"""
    start = time.time()
    conv = await get_or_create_conversation(platform, conversation_id, user_id, user_name, session)

    if any(kw in message for kw in SENSITIVE_KEYWORDS):
        await save_message(conv.id, "user", message, session)
        await save_message(
            conv.id,
            "assistant",
            REFUSAL_PRIVACY,
            session,
            success=False,
            error_code=ErrorCode.UNKNOWN_ERROR,
            error_message="命中隐私/敏感问题拒答",
        )
        async for event in _emit_text(REFUSAL_PRIVACY):
            yield event
        yield {"event": "references", "data": {"references": []}}
        yield {"event": "done", "data": {"success": False, "refused": True}}
        return

    history = await get_recent_messages(conv.id, session)
    history_msgs = [
        {"role": m.role, "content": m.content} for m in history if m.role in ("user", "assistant")
    ]
    await save_message(conv.id, "user", message, session)
    assistant_msg = await save_message(
        conv.id,
        "assistant",
        "小苏正在处理这个问题...",
        session,
        success=True,
    )

    try:
        prepared = await prepare_response(
            history_msgs, message, session, message_id=assistant_msg.id
        )
    except Exception as exc:
        agent_error_code = _classify_agent_error(exc)
        logger.exception("Agent 流式准备失败，使用兜底文案: {}", exc)
        latency_ms = int((time.time() - start) * 1000)
        await update_message(
            assistant_msg,
            session,
            content=_LLM_UNAVAILABLE,
            success=False,
            error_code=agent_error_code,
            error_message="模型服务暂时不可用",
            latency_ms=latency_ms,
        )
        async for event in _emit_text(_LLM_UNAVAILABLE):
            yield event
        yield {"event": "references", "data": {"references": []}}
        yield {"event": "done", "data": {"success": False, "refused": False}}
        return

    has_external_tool = any(
        tc.get("name") != "search_knowledge_base" for tc in prepared.tool_calls
    )
    answer = ""
    refused = prepared.refused
    error_code: str | None = None
    error_message: str | None = None

    if not has_external_tool and not prepared.references:
        answer = REFUSAL_NO_RESULT
        refused = True
        error_code = ErrorCode.UNKNOWN_ERROR
        error_message = "知识库无可引用结果"
        async for event in _emit_text(answer):
            yield event
    elif prepared.refused or not prepared.needs_final_generation or llm_service.use_mock:
        answer = prepared.draft_answer
        async for event in _emit_text(answer):
            yield event
    else:
        answer_parts: list[str] = []
        try:
            async for token in llm_service.chat_stream(prepared.conversation):
                answer_parts.append(token)
                yield {"event": "token", "data": {"content": token}}
        except Exception as exc:
            error_code = _classify_agent_error(exc)
            error_message = "模型服务暂时不可用"
            logger.exception("LLM 流式生成失败，使用兜底文案: {}", exc)
            if not answer_parts:
                async for event in _emit_text(_LLM_UNAVAILABLE):
                    yield event
                answer = _LLM_UNAVAILABLE
            else:
                answer = "".join(answer_parts)
        else:
            answer = "".join(answer_parts) or prepared.draft_answer

    latency_ms = int((time.time() - start) * 1000)
    success = not refused and error_code is None
    await update_message(
        assistant_msg,
        session,
        content=answer,
        references=prepared.references,
        tool_calls=prepared.tool_calls,
        prompt_tokens=prepared.usage.get("prompt_tokens", 0),
        completion_tokens=prepared.usage.get("completion_tokens", 0),
        total_tokens=prepared.usage.get("total_tokens", 0),
        estimated_cost=estimate_cost(
            prepared.usage.get("prompt_tokens", 0), prepared.usage.get("completion_tokens", 0)
        ),
        success=success,
        error_code=error_code,
        error_message=error_message,
        latency_ms=latency_ms,
    )
    yield {"event": "references", "data": {"references": prepared.references}}
    yield {"event": "done", "data": {"success": success, "refused": refused}}
