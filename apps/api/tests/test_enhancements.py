"""增强项回归测试：软删除、审计、错误码、SSE 降级、成本估算、可观测性 noop。"""

import asyncio
import uuid
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agents import tool_registry
from app.api import routes_chat
from app.api.routes_admin_logs import list_messages
from app.core import observability, pricing
from app.core.errors import ErrorCode
from app.main import app
from app.services import chat_service, retrieval_service
from app.tools import internal_api
from app.tools.base import ToolResult


def test_retrieval_sql_excludes_deleted_chunks() -> None:
    """真实/Mock 检索 SQL 都应排除已软删除 chunk。"""
    assert "c.deleted_at IS NULL" in str(retrieval_service._VECTOR_SQL)
    assert "c.deleted_at IS NULL" in str(retrieval_service._LIST_SQL)


@pytest.mark.asyncio
async def test_execute_tool_links_message_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """工具调用日志应关联 assistant message_id，便于后台审计追踪。"""
    captured: list[Any] = []

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        def add(self, obj: object) -> None:
            captured.append(obj)

        async def commit(self) -> None:
            return None

    class FakeTool:
        name = "fake_tool"

        async def run(self, _arguments: dict[str, Any]) -> ToolResult:
            return ToolResult(success=True, data={"ok": True})

    monkeypatch.setattr(tool_registry, "AsyncSessionLocal", lambda: FakeSession())
    message_id = uuid.uuid4()

    result = await tool_registry.execute_tool(FakeTool(), {"x": 1}, message_id)

    assert result.success
    assert captured[0].message_id == message_id
    assert captured[0].tool_name == "fake_tool"


@pytest.mark.asyncio
async def test_execute_tool_timeout_maps_error_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """工具超时应映射为 TOOL_TIMEOUT，并记录失败日志。"""
    captured: list[Any] = []

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        def add(self, obj: object) -> None:
            captured.append(obj)

        async def commit(self) -> None:
            return None

    class SlowTool:
        name = "slow_tool"

        async def run(self, _arguments: dict[str, Any]) -> ToolResult:
            await asyncio.sleep(0.05)
            return ToolResult(success=True, data={"late": True})

    monkeypatch.setattr(tool_registry, "AsyncSessionLocal", lambda: FakeSession())
    monkeypatch.setattr(tool_registry.settings, "TOOL_TIMEOUT_SECONDS", 0.001)

    result = await tool_registry.execute_tool(SlowTool(), {}, uuid.uuid4())

    assert result.success is False
    assert result.error_code == ErrorCode.TOOL_TIMEOUT
    assert captured[0].success is False


@pytest.mark.asyncio
async def test_chat_exception_updates_assistant_error_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agent 异常时应回填 assistant 消息 error_code，而不是只返回兜底文本。"""
    conv = SimpleNamespace(id=uuid.uuid4())
    assistant_msg = SimpleNamespace(id=uuid.uuid4())
    updates: dict[str, Any] = {}

    async def fake_get_or_create_conversation(*_args: object) -> Any:
        return conv

    async def fake_get_recent_messages(*_args: object) -> list[Any]:
        return []

    async def fake_save_message(*args: object, **_kwargs: object) -> Any:
        role = args[1]
        if role == "assistant":
            return assistant_msg
        return SimpleNamespace(id=uuid.uuid4())

    async def fake_update_message(_message: object, _session: object, **fields: object) -> Any:
        updates.update(fields)
        return assistant_msg

    async def fake_agent_run(*_args: object, **_kwargs: object) -> Any:
        raise RuntimeError("LLM_AUTH_ERROR")

    monkeypatch.setattr(chat_service, "get_or_create_conversation", fake_get_or_create_conversation)
    monkeypatch.setattr(chat_service, "get_recent_messages", fake_get_recent_messages)
    monkeypatch.setattr(chat_service, "save_message", fake_save_message)
    monkeypatch.setattr(chat_service, "update_message", fake_update_message)
    monkeypatch.setattr(chat_service, "agent_run", fake_agent_run)

    result = await chat_service.chat("web", "debug", "admin", "你好", object())

    assert result["answer"] == "小苏的模型服务暂时不可用，请稍后再试。"
    assert updates["success"] is False
    assert updates["error_code"] == ErrorCode.LLM_AUTH_ERROR


def test_chat_stream_mock_fallback_events(monkeypatch: pytest.MonkeyPatch) -> None:
    """SSE 降级路径仍应输出 token/references/done 三类事件。"""

    async def fake_stream_chat(*_args: object, **_kwargs: object):
        yield {"event": "token", "data": {"content": "测试"}}
        yield {"event": "references", "data": {"references": []}}
        yield {"event": "done", "data": {"success": True, "refused": False}}

    monkeypatch.setattr(routes_chat.chat_service, "stream_chat", fake_stream_chat)
    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={"platform": "web", "conversation_id": "debug", "user_id": "admin", "message": "hi"},
    )

    assert response.status_code == 200
    body = response.text
    assert "event: token" in body
    assert "event: references" in body
    assert "event: done" in body


@pytest.mark.asyncio
async def test_stream_chat_streams_tokens_and_updates_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """流式聊天应按 token/references/done 输出，并最终回填 assistant 消息。"""
    conv = SimpleNamespace(id=uuid.uuid4())
    assistant_msg = SimpleNamespace(id=uuid.uuid4())
    updates: dict[str, Any] = {}

    async def fake_get_or_create_conversation(*_args: object) -> Any:
        return conv

    async def fake_get_recent_messages(*_args: object) -> list[Any]:
        return []

    async def fake_save_message(*args: object, **_kwargs: object) -> Any:
        return assistant_msg if args[1] == "assistant" else SimpleNamespace(id=uuid.uuid4())

    async def fake_update_message(_message: object, _session: object, **fields: object) -> Any:
        updates.update(fields)
        return assistant_msg

    async def fake_prepare_response(*_args: object, **_kwargs: object) -> Any:
        return SimpleNamespace(
            conversation=[{"role": "user", "content": "hi"}],
            draft_answer="",
            references=[{"filename": "员工手册.md", "document_id": "d1", "chunk_id": "c1"}],
            tool_calls=[{"name": "get_employee", "arguments": {"employee_id": "001"}}],
            usage={"prompt_tokens": 2, "completion_tokens": 0, "total_tokens": 2},
            refused=False,
            needs_final_generation=True,
        )

    class FakeLLM:
        use_mock = False

        async def chat_stream(self, _conversation: list[dict]):
            yield "你"
            yield "好"

    monkeypatch.setattr(chat_service, "get_or_create_conversation", fake_get_or_create_conversation)
    monkeypatch.setattr(chat_service, "get_recent_messages", fake_get_recent_messages)
    monkeypatch.setattr(chat_service, "save_message", fake_save_message)
    monkeypatch.setattr(chat_service, "update_message", fake_update_message)
    monkeypatch.setattr(chat_service, "prepare_response", fake_prepare_response)
    monkeypatch.setattr(chat_service, "llm_service", FakeLLM())

    events = [
        item
        async for item in chat_service.stream_chat("web", "debug", "admin", "hi", object())
    ]

    assert [e["event"] for e in events] == ["token", "token", "references", "done"]
    assert updates["content"] == "你好"
    assert updates["success"] is True
    assert updates["references"][0]["chunk_id"] == "c1"


@pytest.mark.asyncio
async def test_admin_logs_include_conversation_identity() -> None:
    """日志 API 应返回平台和用户信息，便于后台审计“谁问的”。"""
    message = SimpleNamespace(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        role="user",
        content="问题",
        references=[],
        tool_calls=[],
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        estimated_cost=0,
        success=True,
        error_code=None,
        latency_ms=12,
        created_at=None,
    )
    conversation = SimpleNamespace(
        platform="dingtalk",
        user_id="u1",
        user_name="张三",
        conversation_key="dingtalk:c1:u1",
    )

    class FakeResult:
        def all(self) -> list[tuple[Any, Any]]:
            return [(message, conversation)]

    class FakeSession:
        async def execute(self, _stmt: object) -> FakeResult:
            return FakeResult()

    result = await list_messages(FakeSession(), limit=10)

    assert result["items"][0]["platform"] == "dingtalk"
    assert result["items"][0]["user_id"] == "u1"
    assert result["items"][0]["user_name"] == "张三"


@pytest.mark.asyncio
async def test_internal_api_retries_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    """内部 API 5xx 应重试一次后返回成功响应。"""
    calls: list[str] = []

    class FakeResponse:
        def __init__(self, status_code: int, data: dict[str, Any]) -> None:
            self.status_code = status_code
            self._data = data
            self.content = b"{}"

        def json(self) -> dict[str, Any]:
            return self._data

    class FakeClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.responses = [FakeResponse(500, {"error": "x"}), FakeResponse(200, {"ok": True})]

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, url: str, params: object = None) -> FakeResponse:
            calls.append(url)
            return self.responses.pop(0)

    monkeypatch.setattr(internal_api.httpx, "AsyncClient", FakeClient)

    response = await internal_api.request_internal_api("/mock-api/orders")

    assert len(calls) == 2
    assert response.status_code == 200
    assert response.data == {"ok": True}


@pytest.mark.asyncio
async def test_internal_api_does_not_retry_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """内部 API 4xx 不重试，由具体工具生成友好业务文案。"""
    calls: list[str] = []

    class FakeResponse:
        status_code = 404
        content = b"{}"

        def json(self) -> dict[str, Any]:
            return {"error": "not found"}

    class FakeClient:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, url: str, params: object = None) -> FakeResponse:
            calls.append(url)
            return FakeResponse()

    monkeypatch.setattr(internal_api.httpx, "AsyncClient", FakeClient)

    response = await internal_api.request_internal_api("/mock-api/employees/404")

    assert len(calls) == 1
    assert response.status_code == 404


# ---------- 波次 B：LLM 成本估算 ----------


def test_estimate_cost_zero_when_unconfigured() -> None:
    """单价默认 0 时返回 0（降级语义，不破坏无单价流程）。"""
    assert pricing.estimate_cost(1000, 500) == Decimal("0.000000")
    assert pricing.estimate_cost(0, 0) == Decimal("0.000000")


def test_estimate_cost_computes_with_prices(monkeypatch: pytest.MonkeyPatch) -> None:
    """配置单价后按 input/output 分别估算。"""
    monkeypatch.setattr(pricing.settings, "LLM_PRICE_INPUT_PER_M", 5.0)
    monkeypatch.setattr(pricing.settings, "LLM_PRICE_OUTPUT_PER_M", 15.0)
    assert pricing.estimate_cost(1000, 500) == Decimal("0.012500")


def test_estimate_cost_negative_inputs_guarded(monkeypatch: pytest.MonkeyPatch) -> None:
    """负数或空输入应被钳制为 0，不产生负成本。"""
    monkeypatch.setattr(pricing.settings, "LLM_PRICE_INPUT_PER_M", 10.0)
    assert pricing.estimate_cost(-100, None) == Decimal("0.000000")  # type: ignore[arg-type]


# ---------- 波次 C：可观测性 noop 降级 ----------


def test_observability_client_none_when_unconfigured() -> None:
    """未配置 LANGFUSE_* 时 client 为 None（noop）。"""
    observability._reset_for_test()
    assert observability.get_client() is None


def test_observability_llm_span_noop_when_unconfigured() -> None:
    """未配置时 llm_span 为 noop，回填 state 不报错。"""
    observability._reset_for_test()
    with observability.llm_span("test_span", model="gpt-4o-mini") as state:
        state["output"] = "hello"
        state["usage"] = {"input": 1, "output": 1, "unit": "TOKENS"}


def test_observability_trace_id_var_default() -> None:
    """trace_id_var 默认值为占位。"""
    assert observability.trace_id_var.get() == "-"
