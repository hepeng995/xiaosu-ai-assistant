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


@pytest.mark.asyncio
async def test_prepare_response_no_nudge_for_new_topic(monkeypatch: pytest.MonkeyPatch) -> None:
    """上一问与当前问差异显著（新话题/元问题）时，LLM 不调工具是合理的，不应 nudge。

    回归 trace_5507d6e9f1914324：用户先问「我可以放多少天年假」，再问「你可以帮我做什么」。
    旧逻辑第一轮无 tool_calls 即无条件 nudge，文案「请重新回答我上一个问题」被 LLM 误解为
    历史里的年假问题 → 检索 query 污染成「年假天数规定」→ 答非所问。修复后新话题放行。
    """
    _kb_tool_patch(monkeypatch)
    history = [
        {"role": "user", "content": "我可以放多少天年假"},
        {"role": "assistant", "content": "正式员工每年 5 天年假，满 3 年递增。"},
    ]
    captured: list[list[dict]] = []

    async def fake_chat_with_tools(
        conversation: list[dict], _schemas: list[dict]
    ) -> tuple[str, list[dict], dict]:
        captured.append([dict(m) for m in conversation])
        # LLM 对能力/身份元问题合理地不调工具，直接回答
        return "我是小苏，可以帮你查公司制度、考勤、订单等。", [], {
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "total_tokens": 2,
        }

    monkeypatch.setattr(agent.llm_service, "chat_with_tools", fake_chat_with_tools)

    result = await agent.prepare_response(history, "你可以帮我做什么", session=None)

    # 不应追加 nudge，也不应多调一轮 LLM
    assert len(captured) == 1
    for conv in captured:
        user_msgs = [m.get("content", "") for m in conv if m.get("role") == "user"]
        assert not any(RETRIEVAL_NUDGE in c for c in user_msgs)
    # 直接采纳 LLM 的能力介绍，不去检索年假
    assert "小苏" in result.draft_answer
    assert result.references == []


@pytest.mark.asyncio
async def test_prepare_response_nudges_for_repeated_question_with_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """上一问与当前问高度相似（同问题二次问）时仍应 nudge，保留原始拒答修复。"""
    _kb_tool_patch(monkeypatch)
    history = [
        {"role": "user", "content": "员工每年有几天年假？"},
        {"role": "assistant", "content": "正式员工每年 5 天年假。"},
    ]
    call_count = [0]
    captured: list[list[dict]] = []

    async def fake_chat_with_tools(
        conversation: list[dict], _schemas: list[dict]
    ) -> tuple[str, list[dict], dict]:
        call_count[0] += 1
        captured.append([dict(m) for m in conversation])
        if call_count[0] == 1:
            # 第一轮复述历史，不调工具 → 触发 nudge
            return "正式员工每年 5 天年假。", [], {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            }
        if call_count[0] == 2:
            # nudge 后调 search_knowledge_base
            return "", [
                {
                    "id": "c1",
                    "function": {
                        "name": "search_knowledge_base",
                        "arguments": '{"query":"年假"}',
                    },
                }
            ], {"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1}
        # 第三轮：基于检索结果给出最终带引用答案，不再调工具
        return "根据《休假与福利政策》，正式员工每年 5 天年假。", [], {
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "total_tokens": 3,
        }

    async def fake_execute_tool(
        _tool: object, _args: dict[str, Any], _message_id: object = None
    ) -> ToolResult:
        return ToolResult(
            success=True,
            data={"results": [{"filename": "休假与福利政策.txt", "chunk_id": "ck1", "score": 0.9}]},
        )

    monkeypatch.setattr(agent.llm_service, "chat_with_tools", fake_chat_with_tools)
    monkeypatch.setattr(agent, "execute_tool", fake_execute_tool)

    result = await agent.prepare_response(history, "员工每年有几天年假", session=None)

    second_conv = captured[1]
    user_msgs = [m["content"] for m in second_conv if m["role"] == "user"]
    assert any(RETRIEVAL_NUDGE in c for c in user_msgs)
    assert len(result.references) == 1


def test_should_nudge_threshold() -> None:
    """_should_nudge 的相似度阈值：无历史→nudge；同问题→nudge；新话题→放行。"""
    # 无历史：兼容首轮 LLM 偷懒不检索，保留 nudge
    assert agent._should_nudge([], "竞业限制有多久") is True
    # 同问题二次问（高度相似）
    assert (
        agent._should_nudge(
            [{"role": "user", "content": "员工每年有几天年假？"}],
            "员工每年有几天年假",
        )
        is True
    )
    # 新话题/元问题（差异显著）——本案关键回归
    assert (
        agent._should_nudge(
            [{"role": "user", "content": "我可以放多少天年假"}],
            "你可以帮我做什么",
        )
        is False
    )
