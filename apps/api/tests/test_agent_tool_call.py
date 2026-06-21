"""Mock LLM 工具调用测试（不依赖真实 API Key / 数据库）。

验证：无 key 时走 mock，且工具选择逻辑（模拟 LLM）能正确选工具 + 工具 Schema 合法。
真实模式下工具选择由 LLM 按 Tool Schema 自主决定（function calling）。
"""
from typing import Any

import pytest

from app.agents.prompts import SENSITIVE_KEYWORDS
from app.core.config import settings
from app.llm.openai_compatible import llm_service
from app.mcp import runtime
from app.tools.attendance_tool import AttendanceTool
from app.tools.base import ToolResult
from app.tools.employee_tool import EmployeeTool
from app.tools.orders_tool import OrdersTool
from app.tools.time_tool import CurrentTimeTool


def test_rag_score_threshold_default_matches_spec() -> None:
    """默认 RAG 阈值应与笔试题/开发规范一致。"""
    assert settings.RAG_SCORE_THRESHOLD == 0.72


def test_llm_uses_mock_without_key() -> None:
    """key=replace_me 时应启用 mock 模式（不调真实 API）。"""
    assert llm_service.use_mock is True


def test_mock_plan_selects_employee_tool() -> None:
    """问员工部门 → mock 选 get_employee。"""
    calls = llm_service._mock_plan("员工 001 是哪个部门的？")
    names = [c["function"]["name"] for c in calls]
    assert "get_employee" in names


def test_mock_plan_selects_orders_tool() -> None:
    """问订单 → mock 选 get_orders。"""
    calls = llm_service._mock_plan("上周一共多少订单？")
    names = [c["function"]["name"] for c in calls]
    assert "get_orders" in names


def test_mock_plan_sales_target_uses_knowledge_base() -> None:
    """问未来销售目标 → mock 应检索知识库，不能误走订单工具。"""
    calls = llm_service._mock_plan("2030 年的销售目标是多少？")
    names = [c["function"]["name"] for c in calls]
    assert names == ["search_knowledge_base"]


def test_salary_detail_keywords_are_sensitive() -> None:
    """工资明细类问题应走隐私拒答前置。"""
    assert "工资明细" in SENSITIVE_KEYWORDS
    assert "薪资明细" in SENSITIVE_KEYWORDS
    assert "所有员工工资" in SENSITIVE_KEYWORDS


def test_mock_plan_selects_time_tool() -> None:
    """问时间 → mock 选 get_current_time。"""
    calls = llm_service._mock_plan("现在几点？")
    names = [c["function"]["name"] for c in calls]
    assert "get_current_time" in names


def test_tool_schemas_are_valid() -> None:
    """工具 Schema 应符合 OpenAI function-calling 格式。"""
    for tool in (EmployeeTool(), AttendanceTool(), OrdersTool(), CurrentTimeTool()):
        schema = tool.schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == tool.name
        assert "parameters" in schema["function"]


@pytest.mark.asyncio
async def test_time_tool_runs() -> None:
    """当前时间工具应返回有效时间数据（不依赖外部 API）。"""
    result = await CurrentTimeTool().run({"timezone": "Asia/Shanghai"})
    assert result.success
    assert isinstance(result.data, dict)
    assert "datetime" in result.data


@pytest.mark.asyncio
async def test_mcp_chat_uses_mcp_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    """MCP 聊天入口应复用 chat_service，并固定 platform=mcp。"""
    captured: dict[str, Any] = {}

    class FakeSession:
        async def __aenter__(self) -> str:
            return "session"

        async def __aexit__(self, *_args: object) -> None:
            return None

    async def fake_chat(*args: object) -> dict[str, Any]:
        captured["args"] = args
        return {
            "answer": "ok",
            "references": [],
            "tool_calls": [],
            "usage": {},
            "refused": False,
        }

    monkeypatch.setattr(runtime, "AsyncSessionLocal", lambda: FakeSession())
    monkeypatch.setattr(runtime.chat_service, "chat", fake_chat)

    result = await runtime.chat("你好", "conv", "u1", "张三")

    assert result["success"] is True
    assert result["answer"] == "ok"
    assert captured["args"][:5] == ("mcp", "conv", "u1", "你好", "session")
    assert captured["args"][5] == "张三"


@pytest.mark.asyncio
async def test_mcp_search_returns_references(monkeypatch: pytest.MonkeyPatch) -> None:
    """MCP 知识库检索应直接返回引用结构，不生成编造答案。"""

    class FakeSession:
        async def __aenter__(self) -> str:
            return "session"

        async def __aexit__(self, *_args: object) -> None:
            return None

    async def fake_search(query: str, session: object, top_k: int | None = None) -> list[dict]:
        assert query == "年假"
        assert session == "session"
        assert top_k == 2
        return [{"filename": "员工手册.md", "chunk_id": "c1", "quote": "年假", "score": 0.9}]

    monkeypatch.setattr(runtime, "AsyncSessionLocal", lambda: FakeSession())
    monkeypatch.setattr(runtime, "search_knowledge", fake_search)

    result = await runtime.search_knowledge_base("年假", top_k=2)

    assert result["success"] is True
    assert result["results"][0]["filename"] == "员工手册.md"
    assert "answer" not in result


@pytest.mark.asyncio
async def test_mcp_tool_failure_is_friendly(monkeypatch: pytest.MonkeyPatch) -> None:
    """MCP 原子工具失败时应归一为友好错误，不暴露底层异常。"""

    class BrokenTool:
        name = "get_employee"

    async def fake_execute_tool(_tool: object, _arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(success=False, error_message="连接失败: ECONNREFUSED")

    monkeypatch.setattr(runtime, "execute_tool", fake_execute_tool)
    result = await runtime.run_tool(BrokenTool(), {"employee_id": "001"})

    assert result["success"] is False
    assert result["error_code"] == "TOOL_ERROR"
    assert result["message"] == "小苏暂时无法连接内部系统，请稍后再试。"


def test_mcp_server_imports_when_sdk_available() -> None:
    """安装官方 mcp SDK 后，server 模块应可导入并完成注册。"""
    pytest.importorskip("mcp")
    from app.mcp.server import mcp_server

    assert mcp_server is not None


@pytest.mark.asyncio
async def test_prepare_response_stream_yields_status_and_prepared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """prepare_response_stream 应 yield 工具进度事件，末尾 yield 字段完整的 prepared。"""
    from app.agents import agent

    call_count = [0]

    async def fake_chat_with_tools(
        _conv: list[dict], _schemas: list[dict]
    ) -> tuple[str, list[dict], dict]:
        call_count[0] += 1
        if call_count[0] == 1:
            return "", [
                {
                    "id": "c1",
                    "function": {
                        "name": "get_employee",
                        "arguments": '{"employee_id":"001"}',
                    },
                }
            ], {"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1}
        return "张三在销售部", [], {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}

    async def fake_execute_tool(
        _tool: object, _args: dict[str, Any], _message_id: object = None
    ) -> ToolResult:
        return ToolResult(success=True, data={"name": "张三", "department": "销售部"})

    monkeypatch.setattr(agent.llm_service, "chat_with_tools", fake_chat_with_tools)
    monkeypatch.setattr(agent, "execute_tool", fake_execute_tool)

    events = [
        e async for e in agent.prepare_response_stream([], "张三在哪个部门", session=None)
    ]

    statuses = [e for e in events if e["type"] == "status"]
    prepared_events = [e for e in events if e["type"] == "prepared"]

    # 两轮 thinking + 一次 tool_call（label 来自 tool_registry 元数据，非硬编码路由）
    assert [s["stage"] for s in statuses] == ["thinking", "tool_call", "thinking"]
    assert statuses[1]["tool_name"] == "get_employee"
    assert statuses[1]["label"] == "正在查询员工信息..."

    # 末尾 prepared 字段完整，与同步版 prepare_response 一致
    assert len(prepared_events) == 1
    prepared = prepared_events[0]["data"]
    assert prepared.draft_answer == "张三在销售部"
    assert len(prepared.tool_calls) == 1
    assert prepared.tool_calls[0]["name"] == "get_employee"
    assert prepared.usage["total_tokens"] == 4
    assert prepared.needs_final_generation is True
