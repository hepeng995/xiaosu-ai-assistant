"""多轮 RAG 回归测试：防止 LLM 复述历史不调工具导致 references 空 → 误判拒答。

复现场景：同一问题第二次问，LLM 看到 history 已有完整答案会直接复述而不调
search_knowledge_base，导致 references 为空被 chat_service 判定为拒答。
修复：Agent 主循环第一轮空 tool_calls 时追加 RETRIEVAL_NUDGE 提醒重新检索。
"""

from typing import Any

import pytest

from app.agents import agent
from app.agents.prompts import RETRIEVAL_NUDGE
from app.tools.base import ToolResult


class _FakeTool:
    """测试用工具占位：仅提供 name 供 find_tool 匹配。

    execute_tool 已被 monkeypatch，工具本身的 run 不会被调用；
    真实 default_tools(session=None) 不含 KnowledgeSearchTool，故此处手动注入。
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def schema(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": self.name, "parameters": {}}}


def _kb_tool_patch(monkeypatch: pytest.MonkeyPatch) -> None:
    """让 find_tool 能命中 search_knowledge_base（绕过 session=None 的工具注册限制）。"""
    monkeypatch.setattr(
        agent, "default_tools", lambda _session=None: [_FakeTool("search_knowledge_base")]
    )


@pytest.mark.asyncio
async def test_prepare_response_nudges_when_first_round_no_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """第一轮空 tool_calls（模拟复述历史）应触发 nudge，第二轮重新检索拿回 references。"""
    _kb_tool_patch(monkeypatch)
    call_count = [0]
    captured_conversations: list[list[dict]] = []

    async def fake_chat_with_tools(
        conversation: list[dict], _schemas: list[dict]
    ) -> tuple[str, list[dict], dict]:
        call_count[0] += 1
        captured_conversations.append([dict(m) for m in conversation])
        if call_count[0] == 1:
            # 模拟多轮陷阱：LLM 复述历史答案，不调工具
            return "竞业限制最长 24 个月。", [], {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            }
        if call_count[0] == 2:
            # nudge 后：调用 search_knowledge_base
            return "", [
                {
                    "id": "c1",
                    "function": {
                        "name": "search_knowledge_base",
                        "arguments": '{"query":"竞业限制"}',
                    },
                }
            ], {"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1}
        # 第三轮：基于检索结果给出最终答案（带引用），不再调工具
        return "根据《保密协议》，竞业限制最长 24 个月。", [], {
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "total_tokens": 3,
        }

    async def fake_execute_tool(
        _tool: object, _args: dict[str, Any], _message_id: object = None
    ) -> ToolResult:
        return ToolResult(
            success=True,
            data={
                "results": [
                    {
                        "filename": "保密协议.md",
                        "chunk_id": "ck1",
                        "score": 0.9,
                        "quote": "竞业限制最长 24 个月",
                    }
                ]
            },
        )

    monkeypatch.setattr(agent.llm_service, "chat_with_tools", fake_chat_with_tools)
    monkeypatch.setattr(agent, "execute_tool", fake_execute_tool)

    result = await agent.prepare_response([], "竞业限制有多久", session=None)

    # nudge 被追加到第二轮的 conversation
    second_conv = captured_conversations[1]
    user_msgs = [m["content"] for m in second_conv if m["role"] == "user"]
    assert any(RETRIEVAL_NUDGE in c for c in user_msgs)
    # 最终拿到了 references（修复后不再误判拒答）
    assert len(result.references) == 1
    assert result.references[0]["filename"] == "保密协议.md"
    assert result.tool_calls[0]["name"] == "search_knowledge_base"
    assert result.draft_answer.startswith("根据《保密协议》")


@pytest.mark.asyncio
async def test_prepare_response_no_nudge_when_tool_called_first_round(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """第一轮就调工具时不应触发 nudge（避免误伤正常流程 + 节省 token）。"""
    _kb_tool_patch(monkeypatch)
    captured_conversations: list[list[dict]] = []

    async def fake_chat_with_tools(
        conversation: list[dict], _schemas: list[dict]
    ) -> tuple[str, list[dict], dict]:
        captured_conversations.append([dict(m) for m in conversation])
        if len(captured_conversations) == 1:
            # 第一轮就调工具
            return "", [
                {
                    "id": "c1",
                    "function": {
                        "name": "search_knowledge_base",
                        "arguments": '{"query":"竞业"}',
                    },
                }
            ], {"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1}
        # 第二轮：最终答案
        return "根据知识库，竞业限制最长 24 个月。", [], {
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "total_tokens": 3,
        }

    async def fake_execute_tool(
        _tool: object, _args: dict[str, Any], _message_id: object = None
    ) -> ToolResult:
        return ToolResult(
            success=True,
            data={"results": [{"filename": "保密协议.md", "chunk_id": "ck1", "score": 0.9}]},
        )

    monkeypatch.setattr(agent.llm_service, "chat_with_tools", fake_chat_with_tools)
    monkeypatch.setattr(agent, "execute_tool", fake_execute_tool)

    result = await agent.prepare_response([], "竞业限制有多久", session=None)

    # 任何一次 conversation 都不应含 nudge
    for conv in captured_conversations:
        user_msgs = [m.get("content", "") for m in conv if m.get("role") == "user"]
        assert not any(RETRIEVAL_NUDGE in c for c in user_msgs)
    assert len(result.references) == 1


@pytest.mark.asyncio
async def test_prepare_response_nudge_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """nudge 后第二轮仍空 tool_calls 时，直接返回（不二次 nudge、不死循环）。"""
    call_count = [0]

    async def fake_chat_with_tools(
        _conv: list[dict], _schemas: list[dict]
    ) -> tuple[str, list[dict], dict]:
        call_count[0] += 1
        # 两轮都空 tool_calls（LLM 坚持不调工具）
        return f"答案{call_count[0]}", [], {
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "total_tokens": 2,
        }

    monkeypatch.setattr(agent.llm_service, "chat_with_tools", fake_chat_with_tools)

    result = await agent.prepare_response([], "竞业限制有多久", session=None)

    # 只调用 2 次 LLM（第一轮 + nudge 后第二轮），第二轮 _round==1 直接返回
    assert call_count[0] == 2
    assert result.draft_answer == "答案2"
    assert result.references == []
