"""LLM 供应商抽象与工厂：统一接口支持多家供应商（OpenAI 兼容 / Anthropic）。

设计：
- ``LLMProvider`` Protocol 定义统一接口（工具调用 / 流式 / mock 开关）。
- 主链路（agent / chat_service）统一从本模块导入 ``llm_service``，由
  ``settings.LLM_PROVIDER`` 决定实例，新增供应商只需实现 Protocol 并在工厂注册。
- 各 provider 在对应 key 未配置时自行降级为 mock，保持「无 key 可跑全流程」。

注意：``openai_compatible`` 模块仍保留同名 ``llm_service``（LLMService 实例），
供 mock 相关单元测试直接使用；主链路使用本模块按配置选择的实例。
"""

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from app.core.config import settings


@runtime_checkable
class LLMProvider(Protocol):
    """LLM 供应商统一接口。"""

    @property
    def use_mock(self) -> bool: ...

    async def chat_with_tools(
        self, messages: list[dict], tools_schema: list[dict]
    ) -> tuple[str, list[dict], dict]:
        """带工具的对话，返回 (content, tool_calls, usage)；tool_calls 为 OpenAI 格式。"""
        ...

    def chat_stream(
        self, messages: list[dict], temperature: float = 0.3
    ) -> AsyncIterator[str]:
        """流式输出最终回答 token（async generator）。"""
        ...


def get_llm_provider() -> LLMProvider:
    """按 ``settings.LLM_PROVIDER`` 返回供应商实例（未知值回退 openai_compatible）。"""
    if settings.LLM_PROVIDER == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    from app.llm.openai_compatible import LLMService

    return LLMService()


# 主链路使用的 LLM 实例（按配置选择；默认 openai_compatible）
llm_service: LLMProvider = get_llm_provider()
