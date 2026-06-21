"""纯问候语识别 + 角色化招呼回归测试（不依赖真实 LLM / 数据库）。"""

from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest

from app.agents import greeting
from app.services import chat_service


def test_is_greeting_matches_pure_hello() -> None:
    """纯问候短消息应被识别。"""
    assert greeting.is_greeting("你好")
    assert greeting.is_greeting("你好！")
    assert greeting.is_greeting("早上好")
    assert greeting.is_greeting("在吗")
    assert greeting.is_greeting("在吗？")
    assert greeting.is_greeting("hi")
    assert greeting.is_greeting("Hello")
    assert greeting.is_greeting("嗨～")
    assert greeting.is_greeting("晚安")


def test_is_greeting_rejects_with_substance() -> None:
    """含实质内容（问候+问题、非问候词、过长）一律放行给 Agent。"""
    assert not greeting.is_greeting("你好，报销流程怎么走？")
    assert not greeting.is_greeting("早期项目怎么安排")
    assert not greeting.is_greeting("早晨几点上班")
    assert not greeting.is_greeting("")
    assert not greeting.is_greeting("请帮我查员工001的部门")


def test_is_greeting_rejects_long() -> None:
    """超长消息即使以问候词开头也放行。"""
    assert not greeting.is_greeting("你好" * 10)


def test_build_greeting_reply_varies_by_period() -> None:
    """不同时段应从对应模板池挑选回复，且互不串池。"""
    morning = greeting.build_greeting_reply(datetime(2025, 1, 1, 8, 0))
    noon = greeting.build_greeting_reply(datetime(2025, 1, 1, 12, 30))
    late = greeting.build_greeting_reply(datetime(2025, 1, 1, 23, 30))

    assert morning in greeting._GREETING_TEMPLATES["morning"]
    assert noon in greeting._GREETING_TEMPLATES["noon"]
    assert late in greeting._GREETING_TEMPLATES["late_night"]
    assert morning not in greeting._GREETING_TEMPLATES["late_night"]


@pytest.mark.asyncio
async def test_chat_greeting_short_circuits_before_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """纯问候应跳过 Agent 直接返回小苏式招呼，且 assistant 落库 success=True。"""
    conv = SimpleNamespace(id="conv-id")
    saved: list[tuple[str, str, dict[str, Any]]] = []

    async def fake_get_or_create_conversation(*_args: object) -> Any:
        return conv

    async def fake_save_message(*args: object, **extra: object) -> Any:
        saved.append((str(args[1]), str(args[2]), dict(extra)))
        return SimpleNamespace(id="msg-id")

    async def fake_agent_run(*_args: object, **_kwargs: object) -> Any:
        raise AssertionError("问候语不应进入 Agent")

    monkeypatch.setattr(chat_service, "get_or_create_conversation", fake_get_or_create_conversation)
    monkeypatch.setattr(chat_service, "save_message", fake_save_message)
    monkeypatch.setattr(chat_service, "agent_run", fake_agent_run)

    result = await chat_service.chat("web", "c1", "u1", "你好", object())

    assert result["refused"] is False
    assert result["tool_calls"] == []
    assert "小苏" in result["answer"]
    assistant = next(item for item in saved if item[0] == "assistant")
    assert assistant[2]["success"] is True


@pytest.mark.asyncio
async def test_stream_chat_greeting_emits_done(monkeypatch: pytest.MonkeyPatch) -> None:
    """流式路径下纯问候也应短路：输出 token + references + done。"""
    conv = SimpleNamespace(id="conv-id")

    async def fake_get_or_create_conversation(*_args: object) -> Any:
        return conv

    async def fake_save_message(*_args: object, **_kwargs: object) -> Any:
        return SimpleNamespace(id="msg-id")

    async def fake_prepare_response_stream(*_args: object, **_kwargs: object) -> Any:
        raise AssertionError("问候语不应进入 prepare_response_stream")
        yield {}  # pragma: no cover - 仅用于维持 async generator 语义

    monkeypatch.setattr(chat_service, "get_or_create_conversation", fake_get_or_create_conversation)
    monkeypatch.setattr(chat_service, "save_message", fake_save_message)
    monkeypatch.setattr(chat_service, "prepare_response_stream", fake_prepare_response_stream)

    events = [e async for e in chat_service.stream_chat("web", "c1", "u1", "早上好", object())]
    types = [e["event"] for e in events]

    assert "token" in types
    assert "references" in types
    assert types[-1] == "done"
