"""波次 D 测试：多模型适配（工厂选择 + Anthropic mock 降级 + 格式互转）。

不依赖真实 API Key：Anthropic 未配置 key 时降级为 mock（委托 LLMService 启发式）。
"""

import json

import pytest

from app.core import config
from app.core.config import settings
from app.llm import base
from app.llm.anthropic_provider import AnthropicProvider


def test_get_llm_provider_defaults_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认 LLM_PROVIDER=openai_compatible → 返回 LLMService。"""
    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "openai_compatible")
    provider = base.get_llm_provider()
    assert provider.__class__.__name__ == "LLMService"


def test_get_llm_provider_selects_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM_PROVIDER=anthropic → 返回 AnthropicProvider。"""
    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "anthropic")
    provider = base.get_llm_provider()
    assert isinstance(provider, AnthropicProvider)


def test_anthropic_provider_mock_without_key() -> None:
    """未配置 ANTHROPIC_API_KEY 时为 mock 模式。"""
    assert settings.is_secret_configured(settings.ANTHROPIC_API_KEY) is False
    assert AnthropicProvider().use_mock is True


@pytest.mark.asyncio
async def test_anthropic_mock_delegates_tool_selection() -> None:
    """mock 模式委托 LLMService 启发式选工具（复用，不重复造轮子）。"""
    provider = AnthropicProvider()
    _content, calls, _usage = await provider.chat_with_tools(
        [{"role": "user", "content": "员工 001 是哪个部门的？"}], []
    )
    names = [c["function"]["name"] for c in calls]
    assert "get_employee" in names


def test_anthropic_message_conversion() -> None:
    """OpenAI ⇄ Anthropic 消息格式互转正确（system 提取、tool_result 还原）。"""
    provider = AnthropicProvider()
    system, msgs = provider._convert_messages(
        [
            {"role": "system", "content": "你是小苏"},
            {"role": "user", "content": "你好"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {
                            "name": "get_employee",
                            "arguments": json.dumps({"employee_id": "001"}),
                        },
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "c1", "content": '{"name":"张三"}'},
        ]
    )
    assert system == "你是小苏"
    assert msgs[0] == {"role": "user", "content": "你好"}
    # assistant 的 tool_use 还原
    assistant_block = msgs[1]["content"][0]
    assert assistant_block["type"] == "tool_use"
    assert assistant_block["name"] == "get_employee"
    assert assistant_block["input"] == {"employee_id": "001"}
    # tool 结果转 tool_result
    assert msgs[2]["content"][0]["type"] == "tool_result"


def test_anthropic_parse_content_to_openai_tool_calls() -> None:
    """Anthropic 响应 content blocks → OpenAI 风格 tool_calls。"""
    provider = AnthropicProvider()
    text, calls = provider._parse_content(
        {
            "content": [
                {"type": "text", "text": "查询结果："},
                {"type": "tool_use", "id": "u1", "name": "get_orders", "input": {"limit": 5}},
            ]
        }
    )
    assert text == "查询结果："
    assert calls[0]["function"]["name"] == "get_orders"
    assert json.loads(calls[0]["function"]["arguments"]) == {"limit": 5}


@pytest.mark.asyncio
async def test_anthropic_post_messages_retries_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    """Anthropic 非流式请求遇到 5xx 应按 LLM 策略重试。"""
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 1)
    provider = AnthropicProvider()

    class FakeResponse:
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError("server error")

        def json(self) -> dict:
            return {"content": [{"type": "text", "text": "ok"}], "usage": {}}

    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        async def post(self, *_args: object, **_kwargs: object) -> FakeResponse:
            self.calls += 1
            return FakeResponse(500 if self.calls == 1 else 200)

    fake_client = FakeClient()
    provider._client = fake_client  # type: ignore[assignment]

    data = await provider._post_messages(
        "http://anthropic.test", {"model": "m", "messages": []}, {}
    )

    assert data["content"][0]["text"] == "ok"
    assert fake_client.calls == 2


@pytest.mark.asyncio
async def test_anthropic_post_messages_auth_error_no_retry() -> None:
    """Anthropic 401/403 应直接抛 LLM_AUTH_ERROR，不消耗重试次数。"""
    provider = AnthropicProvider()

    class FakeResponse:
        status_code = 401

        def raise_for_status(self) -> None:
            raise AssertionError("认证错误不应进入 raise_for_status")

    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        async def post(self, *_args: object, **_kwargs: object) -> FakeResponse:
            self.calls += 1
            return FakeResponse()

    fake_client = FakeClient()
    provider._client = fake_client  # type: ignore[assignment]

    with pytest.raises(RuntimeError, match="LLM_AUTH_ERROR"):
        await provider._post_messages("http://anthropic.test", {"model": "m", "messages": []}, {})
    assert fake_client.calls == 1
