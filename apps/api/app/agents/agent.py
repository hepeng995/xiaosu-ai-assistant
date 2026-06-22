"""Agent 编排：LLM 按 Tool Schema 自主选择工具 → 执行 → 回填 → 最终回答。

工具选择完全由 LLM 决定（真实模式 function calling），本模块不含任何 if-else 工具路由。
"""

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import RETRIEVAL_NUDGE, SYSTEM_PROMPT
from app.agents.tool_registry import (
    default_tools,
    execute_tool,
    find_tool,
    status_label_for,
    tools_schema,
)
from app.core.config import settings
from app.llm.base import llm_service


@dataclass
class AgentResult:
    answer: str
    references: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    refused: bool = False


@dataclass
class PreparedAgentResult:
    """工具执行后的最终回答上下文，供 ChatService 选择普通/流式生成。"""

    conversation: list[dict]
    draft_answer: str
    references: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    refused: bool = False
    needs_final_generation: bool = True


def _merge_usage(total: dict, usage: dict) -> dict:
    """合并多轮 LLM usage。"""
    merged = dict(total)
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        merged[key] = int(merged.get(key, 0) or 0) + int(usage.get(key, 0) or 0)
    return merged


def _compact_tool_payload(payload: Any, limit: int = 1500) -> str:
    """序列化工具结果回填 LLM；含 ``summary`` 的结构把汇总前置，避免 items 过长截断汇总。

    orders/attendance 等 mock_api 返回 ``{items:[...], summary:{...}}``，summary 排在末尾。
    当 items 较多时整体序列化在 ``limit`` 处截断会丢掉末尾的聚合数据（net_amount / work_days）。
    这里把 summary 重排到最前，保证即使截断也先损失明细尾部而非关键汇总。
    """
    if isinstance(payload, dict) and isinstance(payload.get("summary"), (dict, list)):
        ordered: dict[str, Any] = {"summary": payload["summary"]}
        for key, value in payload.items():
            if key != "summary":
                ordered[key] = value
        return json.dumps(ordered, ensure_ascii=False, default=str)[:limit]
    return json.dumps(payload, ensure_ascii=False, default=str)[:limit]


# RETRIEVAL_NUDGE 触发阈值：上一问与当前问的 2-gram Jaccard 相似度 ≥ 此值才认为「同问题复述」。
# 经验值——完全相同/微调措辞的二次追问通常 > 0.6，新话题/元问题通常 < 0.2，0.5 为安全分界。
_NUDGE_SIMILARITY_THRESHOLD = 0.5


def _bigrams(text: str) -> set[str]:
    """中文友好的 2-gram 集合（无需分词/向量，粗粒度相似度足够区分「新话题」与「复述」）。"""
    text = (text or "").strip()
    if len(text) < 2:
        return {text} if text else set()
    return {text[i : i + 2] for i in range(len(text) - 1)}


def _text_similarity(a: str, b: str) -> float:
    """2-gram Jaccard 相似度，∈ [0, 1]。"""
    ga, gb = _bigrams(a), _bigrams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def _last_user_content(history: list[dict]) -> str:
    """会话历史中最近一条 user 消息内容（无则空串）。"""
    for msg in reversed(history):
        if msg.get("role") == "user":
            return msg.get("content", "") or ""
    return ""


def _should_nudge(history: list[dict], current_user: str) -> bool:
    """第一轮无 tool_calls 时是否追加 :data:`RETRIEVAL_NUDGE`。

    nudge 的初衷是破解「LLM 复述历史答案而不重新检索」导致 references 空 → 误判拒答。
    但 LLM 对【新话题 / 元问题 / 能力问询 / 闲聊】合理选择不调工具时，nudge 反而会
    强迫检索，且检索 query 易被历史污染、答非所问（见 trace_5507d6e9f1914324：
    「你可以帮我做什么」被逼检索「年假天数规定」）。

    触发策略：
      - 无历史：保留 nudge（兼容首轮 LLM 偷懒不检索的知识库问题）；
      - 有历史且上一问与当前问高度相似（疑似同问题二次问）：nudge；
      - 有历史且上一问与当前问差异显著（新话题/元问题）：尊重 LLM 决策，不 nudge。
    """
    last_user = _last_user_content(history)
    if not last_user:
        return True
    return _text_similarity(last_user, current_user) >= _NUDGE_SIMILARITY_THRESHOLD


async def prepare_response(
    messages_history: list[dict],
    user_message: str,
    session: AsyncSession,
    message_id: uuid.UUID | None = None,
    max_rounds: int | None = None,
) -> PreparedAgentResult:
    """执行工具调用轮次，返回可用于最终生成的 conversation。"""
    max_rounds = max_rounds or settings.MAX_TOOL_ROUNDS
    tools = default_tools(session)
    schemas = tools_schema(tools)

    conversation: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *messages_history,
        {"role": "user", "content": user_message},
    ]
    executed: list[dict] = []
    references: list[dict] = []
    total_usage: dict = {}

    for _round in range(max_rounds):
        content, tool_calls_raw, usage = await llm_service.chat_with_tools(conversation, schemas)
        total_usage = _merge_usage(total_usage, usage)
        if not tool_calls_raw:
            # 多轮陷阱兜底（仅第一轮）：LLM 若复述历史答案而不调工具，references 会为空，
            # 进而被误判拒答（同问题第二次问必复现）。仅在疑似「同问题复述」时追加提醒
            # 重新检索，避免误伤 LLM 对新话题/元问题合理选择不调工具的场景（见 _should_nudge）。
            if _round == 0 and _should_nudge(messages_history, user_message):
                conversation.append({"role": "assistant", "content": content})
                conversation.append({"role": "user", "content": RETRIEVAL_NUDGE})
                continue
            return PreparedAgentResult(
                conversation=conversation,
                draft_answer=content,
                references=references,
                tool_calls=executed,
                usage=total_usage,
            )
        conversation.append({"role": "assistant", "content": content, "tool_calls": tool_calls_raw})
        for tc in tool_calls_raw:
            name = tc["function"]["name"]
            raw_args = tc["function"].get("arguments", "{}")
            try:
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except Exception:
                arguments = {}
            executed.append({"name": name, "arguments": arguments})
            tool = find_tool(tools, name)
            if tool is None:
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": f"工具 {name} 不存在",
                    }
                )
                continue
            result = await execute_tool(tool, arguments, message_id)
            if name == "search_knowledge_base" and result.success and isinstance(result.data, dict):
                references.extend(result.data.get("results", []))
            payload = result.data if result.success else {"error": result.error_message}
            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": _compact_tool_payload(payload),
                }
            )

    return PreparedAgentResult(
        conversation=conversation,
        draft_answer="这个问题需要较多外部查询，小苏暂时无法一次性完成。请拆成更具体的问题再试。",
        references=references,
        tool_calls=executed,
        usage=total_usage,
        refused=True,
        needs_final_generation=False,
    )


async def prepare_response_stream(
    messages_history: list[dict],
    user_message: str,
    session: AsyncSession,
    message_id: uuid.UUID | None = None,
    max_rounds: int | None = None,
) -> AsyncIterator[dict]:
    """流式版工具准备：与 :func:`prepare_response` 逻辑等价，额外在工具调用前后 yield 进度事件。

    供 ``stream_chat`` 透传给 IM 卡片，消除「空卡片黑盒等待」。事件类型：
      - ``{"type": "status", "stage": "thinking"|"tool_call", "tool_name": str, "label": str}``
      - ``{"type": "prepared", "data": PreparedAgentResult}``（末尾，字段与同步版完全一致）
    """
    max_rounds = max_rounds or settings.MAX_TOOL_ROUNDS
    tools = default_tools(session)
    schemas = tools_schema(tools)

    conversation: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *messages_history,
        {"role": "user", "content": user_message},
    ]
    executed: list[dict] = []
    references: list[dict] = []
    total_usage: dict = {}

    for _round in range(max_rounds):
        yield {"type": "status", "stage": "thinking", "label": "正在思考..."}
        content, tool_calls_raw, usage = await llm_service.chat_with_tools(conversation, schemas)
        total_usage = _merge_usage(total_usage, usage)
        if not tool_calls_raw:
            # 多轮陷阱兜底（仅第一轮）：与 prepare_response 同源，避免复述历史导致 references 空。
            # 仅在疑似「同问题复述」时触发，新话题/元问题放行（见 _should_nudge）。
            if _round == 0 and _should_nudge(messages_history, user_message):
                conversation.append({"role": "assistant", "content": content})
                conversation.append({"role": "user", "content": RETRIEVAL_NUDGE})
                continue
            yield {
                "type": "prepared",
                "data": PreparedAgentResult(
                    conversation=conversation,
                    draft_answer=content,
                    references=references,
                    tool_calls=executed,
                    usage=total_usage,
                    # 没调用任何工具（能力/身份/闲聊等）时，LLM 已给出回答，直接采纳，
                    # 不再走 chat_stream 二次生成——避免冗余 LLM 调用与多轮 nudge 上下文干扰。
                    needs_final_generation=bool(executed),
                ),
            }
            return
        conversation.append({"role": "assistant", "content": content, "tool_calls": tool_calls_raw})
        for tc in tool_calls_raw:
            name = tc["function"]["name"]
            raw_args = tc["function"].get("arguments", "{}")
            try:
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except Exception:
                arguments = {}
            executed.append({"name": name, "arguments": arguments})
            # 工具调用前推送进度事件（label 由 tool_registry 元数据决定，非硬编码路由）
            yield {
                "type": "status",
                "stage": "tool_call",
                "tool_name": name,
                "label": status_label_for(name),
            }
            tool = find_tool(tools, name)
            if tool is None:
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": f"工具 {name} 不存在",
                    }
                )
                continue
            result = await execute_tool(tool, arguments, message_id)
            if name == "search_knowledge_base" and result.success and isinstance(result.data, dict):
                references.extend(result.data.get("results", []))
            payload = result.data if result.success else {"error": result.error_message}
            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": _compact_tool_payload(payload),
                }
            )

    yield {
        "type": "prepared",
        "data": PreparedAgentResult(
            conversation=conversation,
            draft_answer="这个问题需要较多外部查询，小苏暂时无法一次性完成。请拆成更具体的问题再试。",
            references=references,
            tool_calls=executed,
            usage=total_usage,
            refused=True,
            needs_final_generation=False,
        ),
    }


async def run(
    messages_history: list[dict],
    user_message: str,
    session: AsyncSession,
    message_id: uuid.UUID | None = None,
    max_rounds: int | None = None,
) -> AgentResult:
    """Agent 主循环：最多 max_rounds 轮工具调用，由 LLM 决定何时停止。"""
    prepared = await prepare_response(
        messages_history, user_message, session, message_id, max_rounds
    )
    return AgentResult(
        answer=prepared.draft_answer,
        references=prepared.references,
        tool_calls=prepared.tool_calls,
        usage=prepared.usage,
        refused=prepared.refused,
    )
