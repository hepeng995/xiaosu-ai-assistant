"""聊天服务：编排 Agent（LLM 自主选工具/检索）→ 引用 + 拒答 + 落库 + 异常兜底。"""

import re
import time
from collections.abc import AsyncIterator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.agent import PreparedAgentResult, prepare_response_stream
from app.agents.agent import run as agent_run
from app.agents.greeting import build_greeting_reply, is_greeting
from app.agents.prompts import REFUSAL_NO_RESULT, REFUSAL_PRIVACY, SENSITIVE_KEYWORDS
from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.observability import trace_span
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
# 最终回答被工具调用格式泄漏过滤殆尽时的兜底（避免飞书空卡片）
_BAD_OUTPUT_FALLBACK = "小苏刚才的回答好像出了点格式问题，能换种方式再问一次吗？"
_STREAM_CHUNK_SIZE = 6

# 部分 OpenAI-compatible 模型（如 mimo-v2.5）在多轮 tool use 后，可能在最终回答里把
# <tool_call>...</tool_call> 当正文输出（本应走结构化 tool_calls 字段），向用户泄露内部
# 协议。System Prompt 铁律 9 已从源头禁止；以下为工程兜底。
_TOOL_CALL_OPEN = "<tool_call>"
_TOOL_CALL_CLOSE = "</tool_call>"
_TOOL_CALL_BLOCK = re.compile(r"<tool_call>.*?</tool_call>", re.DOTALL | re.IGNORECASE)


def _trailing_prefix_len(buffer: str, marker: str) -> int:
    """``buffer`` 末尾与 ``marker`` 前缀匹配的最大长度（用于跨 token 的标签检测）。"""
    max_check = min(len(marker) - 1, len(buffer))
    for length in range(max_check, 0, -1):
        if buffer.endswith(marker[:length]):
            return length
    return 0


def _sanitize_answer(text: str) -> str:
    """清洗正文里误输出的 ``<tool_call>...</tool_call>`` 块（非流式场景）。"""
    if not text:
        return text
    return _TOOL_CALL_BLOCK.sub("", text).strip()


async def _filter_tool_call_leak(tokens: AsyncIterator[str]) -> AsyncIterator[str]:
    """流式 token 级过滤 ``<tool_call>`` 泄漏（飞书流式卡片的关键防御）。

    状态机：
      - 正常态：``<tool_call>`` 之前的内容正常 yield，末尾若是其前缀则保留缓冲；
      - 抑制态：进入 ``<tool_call>`` 后吞掉一切，直到 ``</tool_call>`` 闭合；
      - 标签可能跨 token，靠 ``_trailing_prefix_len`` 避免把不完整标签当正文输出。
    """
    buffer = ""
    inside = False
    async for token in tokens:
        buffer += token
        while True:
            if inside:
                close_idx = buffer.find(_TOOL_CALL_CLOSE)
                if close_idx == -1:
                    keep = _trailing_prefix_len(buffer, _TOOL_CALL_CLOSE)
                    buffer = buffer[len(buffer) - keep :] if keep else ""
                    break
                buffer = buffer[close_idx + len(_TOOL_CALL_CLOSE) :]
                inside = False
            else:
                open_idx = buffer.find(_TOOL_CALL_OPEN)
                if open_idx == -1:
                    prefix_len = _trailing_prefix_len(buffer, _TOOL_CALL_OPEN)
                    safe = len(buffer) - prefix_len
                    if safe > 0:
                        yield buffer[:safe]
                        buffer = buffer[safe:]
                    break
                if open_idx > 0:
                    yield buffer[:open_idx]
                buffer = buffer[open_idx + len(_TOOL_CALL_OPEN) :]
                inside = True
    # 流结束收尾：仍在 <tool_call> 内或残留其不完整前缀 → 丢弃，杜绝部分标签泄漏
    if not inside and buffer:
        prefix_len = _trailing_prefix_len(buffer, _TOOL_CALL_OPEN)
        if prefix_len:
            buffer = buffer[:-prefix_len]
        if buffer:
            yield buffer


def _should_refuse(tool_calls: list[dict], references: list[dict]) -> bool:
    """拒答判断：仅当调用了知识库检索却无命中（且无其他外部工具数据）时拒答。

    若 LLM 根本没调用任何工具（能力/身份/闲聊等无需知识库依据的问题），应采纳其
    回答，不判拒答——否则会把「我是小苏，可以帮你查制度…」误报成拒答（见
    trace_756d4ccf0a534508：职责 5 引导 LLM 对能力问题不调工具，却因 references 空
    被旧逻辑误判拒答）。
    """
    has_external_tool = any(tc.get("name") != "search_knowledge_base" for tc in tool_calls)
    searched_kb = any(tc.get("name") == "search_knowledge_base" for tc in tool_calls)
    # 必须真的调过 search 才考虑拒答；没调任何工具 → 采纳 LLM 回答
    return searched_kb and not has_external_tool and not references


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
    chat_span = trace_span(
        "chat", metadata={"platform": platform, "conversation_id": conversation_id}
    )
    span_state = chat_span.__enter__()
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
        span_state["metadata"] = {
            "platform": platform,
            "conversation_id": conversation_id,
            "refused": True,
            "reason": "privacy",
        }
        chat_span.__exit__(None, None, None)
        return {
            "answer": REFUSAL_PRIVACY,
            "references": [],
            "tool_calls": [],
            "usage": {},
            "refused": True,
        }

    # 基础前置：纯问候语直接角色化打招呼，跳过 Agent（省 token，Mock/真实行为一致）
    # 仅匹配「问候词 + 语气标点」整串；含实质内容（「你好，报销流程？」）一律放行
    if is_greeting(message):
        greeting = build_greeting_reply()
        await save_message(conv.id, "user", message, session)
        latency_ms = int((time.time() - start) * 1000)
        await save_message(
            conv.id,
            "assistant",
            greeting,
            session,
            success=True,
            latency_ms=latency_ms,
        )
        span_state["metadata"] = {
            "platform": platform,
            "conversation_id": conversation_id,
            "greeting": True,
            "latency_ms": latency_ms,
        }
        chat_span.__exit__(None, None, None)
        return {
            "answer": greeting,
            "references": [],
            "tool_calls": [],
            "usage": {},
            "refused": False,
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
        span_state["metadata"] = {
            "platform": platform,
            "conversation_id": conversation_id,
            "success": False,
            "error_code": agent_error_code,
            "latency_ms": latency_ms,
        }
        chat_span.__exit__(None, None, None)
        return {
            "answer": _LLM_UNAVAILABLE,
            "references": [],
            "tool_calls": [],
            "usage": {},
            "refused": False,
        }

    # 拒答判断：调了知识库检索却无命中 → 拒答（绝不编造）；
    # 但 LLM 对能力/身份/闲聊等本就不调工具的问题，应采纳其回答，不判拒答。
    answer: str
    refused: bool
    error_code: str | None
    error_message: str | None
    if _should_refuse(result.tool_calls, result.references):
        answer = REFUSAL_NO_RESULT
        refused = True
        error_code = ErrorCode.UNKNOWN_ERROR
        error_message = "知识库无可引用结果"
    else:
        answer = _sanitize_answer(result.answer) or _BAD_OUTPUT_FALLBACK
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

    response = {
        "answer": answer,
        "references": result.references,
        "tool_calls": result.tool_calls,
        "usage": result.usage,
        "refused": refused,
    }
    span_state["metadata"] = {
        "platform": platform,
        "conversation_id": conversation_id,
        "refused": refused,
        "references": len(result.references),
        "tool_calls": len(result.tool_calls),
        "latency_ms": latency_ms,
    }
    chat_span.__exit__(None, None, None)
    return response


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

    # 基础前置：纯问候语直接角色化打招呼，跳过 Agent（流式路径同步短路）
    if is_greeting(message):
        greeting = build_greeting_reply()
        await save_message(conv.id, "user", message, session)
        latency_ms = int((time.time() - start) * 1000)
        await save_message(
            conv.id,
            "assistant",
            greeting,
            session,
            success=True,
            latency_ms=latency_ms,
        )
        async for event in _emit_text(greeting):
            yield event
        yield {"event": "references", "data": {"references": []}}
        yield {"event": "done", "data": {"success": True, "refused": False}}
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
        prepared: PreparedAgentResult | None = None
        async for event in prepare_response_stream(
            history_msgs, message, session, message_id=assistant_msg.id
        ):
            if event["type"] == "status" and settings.FEISHU_TOOL_STATUS_ENABLED:
                yield {
                    "event": "status",
                    "data": {
                        "stage": event.get("stage", ""),
                        "tool_name": event.get("tool_name"),
                        "label": event.get("label", ""),
                    },
                }
            elif event["type"] == "prepared":
                prepared = event["data"]
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

    # prepare_response_stream 正常完成必 yield prepared；assert 收窄类型供 mypy
    assert prepared is not None
    answer = ""
    refused = prepared.refused
    error_code: str | None = None
    error_message: str | None = None

    if _should_refuse(prepared.tool_calls, prepared.references):
        answer = REFUSAL_NO_RESULT
        refused = True
        error_code = ErrorCode.UNKNOWN_ERROR
        error_message = "知识库无可引用结果"
        async for event in _emit_text(answer):
            yield event
    elif prepared.refused or not prepared.needs_final_generation or llm_service.use_mock:
        answer = _sanitize_answer(prepared.draft_answer) or _BAD_OUTPUT_FALLBACK
        async for event in _emit_text(answer):
            yield event
    else:
        answer_parts: list[str] = []
        try:
            async for token in _filter_tool_call_leak(
                llm_service.chat_stream(prepared.conversation)
            ):
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
            answer = "".join(answer_parts) or _sanitize_answer(prepared.draft_answer)

    # 防御：若最终回答被 <tool_call> 泄漏过滤殆尽（或本就为空），补发兜底，避免飞书空卡片
    if not answer:
        answer = _BAD_OUTPUT_FALLBACK
        async for event in _emit_text(answer):
            yield event

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
