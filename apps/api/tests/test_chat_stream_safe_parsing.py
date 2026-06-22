"""chat_stream 流式输出的安全解析与泄漏过滤回归测试。

两类 bug 的修复回归：
1. mimo-v2.5 等 provider 流末尾发 usage-only chunk（``choices: []``），旧实现
   ``chunk.get("choices", [{}])[0]`` 触发 IndexError，导致流式中断、飞书卡片降级
   为兜底文案。修复后空 choices 安全跳过。
2. mimo-v2.5 在多轮 tool use 后，最终回答可能把 ``<tool_call>...</tool_call>``
   当正文输出（本应走结构化 tool_calls），向用户泄露内部协议。修复 = System Prompt
   铁律 9（源头禁止）+ ``_filter_tool_call_leak``（流式 token 级兜底过滤）+
   ``_sanitize_answer``（非流式清洗）。见 trace_717839cc7e9b4d04。
"""

import pytest

from app.llm.openai_compatible import LLMService
from app.services.chat_service import _filter_tool_call_leak, _sanitize_answer


async def _aiter(seq: list[str]):
    """把同步序列包装成 async iterator，供 _filter_tool_call_leak 消费。"""
    for item in seq:
        yield item


async def _collect(seq: list[str]) -> str:
    """跑一遍过滤并拼接结果，便于断言。"""
    out: list[str] = []
    async for token in _filter_tool_call_leak(_aiter(seq)):
        out.append(token)
    return "".join(out)


def test_extract_delta_token_empty_choices_safe() -> None:
    """空 choices chunk（usage-only）应返回 None，不抛 IndexError（核心 bug 修复）。"""
    assert LLMService._extract_delta_token({"choices": []}) is None


def test_extract_delta_token_missing_choices_safe() -> None:
    """缺 choices key 的 chunk 应返回 None。"""
    assert LLMService._extract_delta_token({}) is None
    assert LLMService._extract_delta_token({"usage": {"prompt_tokens": 10}}) is None


def test_extract_delta_token_normal_chunk() -> None:
    """正常 chunk 应提取 delta.content。"""
    chunk = {"choices": [{"delta": {"content": "你好"}}]}
    assert LLMService._extract_delta_token(chunk) == "你好"


def test_extract_delta_token_empty_delta_safe() -> None:
    """choices 存在但 delta 为空时应返回 None。"""
    assert LLMService._extract_delta_token({"choices": [{"delta": {}}]}) is None
    assert LLMService._extract_delta_token({"choices": [{}]}) is None


def test_extract_delta_token_empty_string_content() -> None:
    """delta.content 为空字符串时应返回 None（falsy，不 yield 空串）。"""
    assert LLMService._extract_delta_token({"choices": [{"delta": {"content": ""}}]}) is None


@pytest.mark.asyncio
async def test_filter_tool_call_leak_passes_normal_text() -> None:
    """不含 <tool_call> 的正常文本应原样透传。"""
    assert await _collect(["你好", "我是小苏"]) == "你好我是小苏"


@pytest.mark.asyncio
async def test_filter_tool_call_leak_strips_whole_block() -> None:
    """整个 <tool_call>...</tool_call> 块在一个 token 时应被完整吞掉，保留前后正文。"""
    payload = (
        "前文<tool_call>\n<function=search_knowledge_base>\n"
        "<parameter=query>x</parameter>\n</function>\n</tool_call>后文"
    )
    assert await _collect([payload]) == "前文后文"


@pytest.mark.asyncio
async def test_filter_tool_call_leak_splits_across_tokens() -> None:
    """标签跨多个 token 时也应正确识别并吞掉（核心回归：mimo 分片输出）。"""
    tokens = ["前文<tool_", "call>", "<function=x/>", "</tool_", "call>后文"]
    assert await _collect(tokens) == "前文后文"


@pytest.mark.asyncio
async def test_filter_tool_call_leak_only_block_yields_empty() -> None:
    """若整段输出只是 <tool_call>（本案场景），过滤后为空，交由上层兜底补发。"""
    tokens = ["<tool_call>", "<function=x/>", "</tool_call>"]
    assert await _collect(tokens) == ""


@pytest.mark.asyncio
async def test_filter_tool_call_leak_trailing_partial_open_dropped() -> None:
    """流结束时缓冲区残留的 <tool_ 不完整前缀应被丢弃，杜绝部分标签泄漏。"""
    assert await _collect(["你好<tool_"]) == "你好"


@pytest.mark.asyncio
async def test_filter_tool_call_leak_multiple_blocks() -> None:
    """多次 <tool_call> 泄漏都应被分别吞掉，正文相连。"""
    tokens = ["a<tool_call>x</tool_call>b", "<tool_call>y</tool_call>c"]
    assert await _collect(tokens) == "abc"


def test_sanitize_answer_strips_block() -> None:
    """非流式清洗应去除 <tool_call> 块。"""
    text = "前文<tool_call>\n<function=x/>\n</tool_call>后文"
    assert _sanitize_answer(text) == "前文后文"


def test_sanitize_answer_keeps_normal_text() -> None:
    """正常文本与空串不受影响。"""
    assert _sanitize_answer("正常回答") == "正常回答"
    assert _sanitize_answer("") == ""
