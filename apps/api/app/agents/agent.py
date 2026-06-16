"""Agent 编排：LLM 按 Tool Schema 自主选择工具 → 执行 → 回填 → 最终回答。

工具选择完全由 LLM 决定（真实模式 function calling），本模块不含任何 if-else 工具路由。
"""

import json
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import SYSTEM_PROMPT
from app.agents.tool_registry import default_tools, execute_tool, find_tool, tools_schema
from app.core.config import settings
from app.llm.openai_compatible import llm_service


@dataclass
class AgentResult:
    answer: str
    references: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    refused: bool = False


async def run(
    messages_history: list[dict],
    user_message: str,
    session: AsyncSession,
    message_id: uuid.UUID | None = None,
    max_rounds: int | None = None,
) -> AgentResult:
    """Agent 主循环：最多 max_rounds 轮工具调用，由 LLM 决定何时停止。"""
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

    for _round in range(max_rounds):
        content, tool_calls_raw, usage = await llm_service.chat_with_tools(conversation, schemas)
        if not tool_calls_raw:
            return AgentResult(
                answer=content, references=references, tool_calls=executed, usage=usage
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
                    "content": json.dumps(payload, ensure_ascii=False, default=str)[:1500],
                }
            )

    return AgentResult(
        answer="这个问题需要较多外部查询，小苏暂时无法一次性完成。请拆成更具体的问题再试。",
        references=references,
        tool_calls=executed,
        refused=True,
    )
