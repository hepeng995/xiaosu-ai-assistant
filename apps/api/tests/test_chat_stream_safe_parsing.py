"""chat_stream 流式 chunk 安全解析回归测试。

复现 bug：mimo-v2.5 等 provider 流末尾发 usage-only chunk（``choices: []``），
旧实现 ``chunk.get("choices", [{}])[0]`` 触发 IndexError，导致流式中断、
飞书卡片内容降级为兜底文案。修复后空 choices 安全跳过。
"""

from app.llm.openai_compatible import LLMService


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
