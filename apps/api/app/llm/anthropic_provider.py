"""Anthropic 供应商（LLM_PROVIDER=anthropic）：Claude messages API 适配。

真实模式：调用 Anthropic ``/v1/messages``，工具调用走原生 tool_use，
内部完成 OpenAI ⇄ Anthropic 消息/工具格式互转（主链路仍用 OpenAI 风格 tool_calls）。
mock 模式：未配置 ANTHROPIC_API_KEY 时委托 LLMService 的 mock（复用工具选择启发式），
保证无 key 也能跑通流程验证。
"""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from loguru import logger

from app.core.config import settings
from app.core.observability import llm_span
from app.llm.openai_compatible import LLMService
from app.services import setting_service

_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider:
    """Claude（Anthropic messages API）供应商实现。"""

    def __init__(self) -> None:
        self._api_key = settings.ANTHROPIC_API_KEY
        self._base_url = settings.ANTHROPIC_BASE_URL
        self._model = settings.ANTHROPIC_MODEL
        self._client = httpx.AsyncClient(timeout=float(settings.LLM_TIMEOUT_SECONDS))
        # mock 模式下复用 OpenAI 兼容实现的工具选择启发式（不重复造轮子）
        self._mock_helper = LLMService()

    @property
    def use_mock(self) -> bool:
        return not settings.is_secret_configured(self._api_key)

    async def _effective_model(self) -> str:
        """运行时激活模型覆盖默认（与 openai_compatible 行为一致）。"""
        active = await setting_service.get_active_model()
        return active or self._model

    # ---------- 工具对话 ----------

    async def chat_with_tools(
        self, messages: list[dict], tools_schema: list[dict]
    ) -> tuple[str, list[dict], dict]:
        if self.use_mock:
            return self._mock_helper._mock_chat_with_tools(messages)
        return await self._chat_with_tools_api(messages, tools_schema)

    async def _chat_with_tools_api(
        self, messages: list[dict], tools_schema: list[dict]
    ) -> tuple[str, list[dict], dict]:
        effective_model = await self._effective_model()
        system, anthropic_msgs = self._convert_messages(messages)
        url = f"{self._base_url.rstrip('/')}/v1/messages"
        payload: dict[str, Any] = {
            "model": effective_model,
            "max_tokens": 2048,
            "system": system,
            "messages": anthropic_msgs,
        }
        if tools_schema:
            payload["tools"] = self._convert_tools(tools_schema)
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        with llm_span("llm_chat_with_tools", model=effective_model) as state:
            resp = await self._client.post(url, json=payload, headers=headers)
            if resp.status_code in (401, 403):
                raise RuntimeError("LLM_AUTH_ERROR")
            resp.raise_for_status()
            data = resp.json()
            content, tool_calls = self._parse_content(data)
            usage_in = data.get("usage", {})
            usage = {
                "prompt_tokens": usage_in.get("input_tokens", 0),
                "completion_tokens": usage_in.get("output_tokens", 0),
                "total_tokens": usage_in.get("input_tokens", 0)
                + usage_in.get("output_tokens", 0),
            }
            state["output"] = content
            state["usage"] = {
                "input": usage["prompt_tokens"],
                "output": usage["completion_tokens"],
                "unit": "TOKENS",
            }
            return content, tool_calls, usage

    # ---------- 流式 ----------

    async def chat_stream(
        self, messages: list[dict], temperature: float = 0.3
    ) -> AsyncIterator[str]:
        if self.use_mock:
            content = self._mock_helper._mock_chat(messages).content
            for i in range(0, len(content), 6):
                yield content[i : i + 6]
            return
        effective_model = await self._effective_model()
        system, anthropic_msgs = self._convert_messages(messages)
        url = f"{self._base_url.rstrip('/')}/v1/messages"
        payload = {
            "model": effective_model,
            "max_tokens": 2048,
            "system": system,
            "messages": anthropic_msgs,
            "temperature": temperature,
            "stream": True,
        }
        headers = {"x-api-key": self._api_key, "anthropic-version": _ANTHROPIC_VERSION}
        async with self._client.stream("POST", url, json=payload, headers=headers) as resp:
            if resp.status_code in (401, 403):
                raise RuntimeError("LLM_AUTH_ERROR")
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line.removeprefix("data:").strip()
                if not raw:
                    continue
                try:
                    chunk = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if chunk.get("type") == "content_block_delta":
                    delta = chunk.get("delta", {}) or {}
                    if delta.get("type") == "text_delta":
                        token = delta.get("text")
                        if token:
                            yield token

    # ---------- 格式互转 ----------

    def _convert_messages(self, messages: list[dict]) -> tuple[str, list[dict]]:
        """OpenAI 风格消息 → Anthropic（system 提取到顶层，tool → tool_result）。"""
        system_parts: list[str] = []
        anthropic_msgs: list[dict] = []
        for m in messages:
            role = m.get("role")
            if role == "system":
                system_parts.append(str(m.get("content", "")))
            elif role == "user":
                anthropic_msgs.append({"role": "user", "content": str(m.get("content", ""))})
            elif role == "assistant":
                blocks: list[dict] = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for tc in m.get("tool_calls") or []:
                    fn = tc.get("function", {})
                    raw_args = fn.get("arguments", "{}")
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except json.JSONDecodeError:
                        args = {}
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id", ""),
                            "name": fn.get("name", ""),
                            "input": args,
                        }
                    )
                anthropic_msgs.append({"role": "assistant", "content": blocks})
            elif role == "tool":
                anthropic_msgs.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.get("tool_call_id", ""),
                                "content": str(m.get("content", "")),
                            }
                        ],
                    }
                )
        return "\n\n".join(system_parts), anthropic_msgs

    @staticmethod
    def _convert_tools(tools_schema: list[dict]) -> list[dict]:
        """OpenAI tools_schema → Anthropic tools（input_schema）。"""
        out: list[dict] = []
        for t in tools_schema:
            fn = t.get("function", {})
            out.append(
                {
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                }
            )
        return out

    @staticmethod
    def _parse_content(data: dict) -> tuple[str, list[dict]]:
        """Anthropic 响应 content blocks → (text, OpenAI 风格 tool_calls)。"""
        blocks = data.get("content", []) or []
        text_parts = [str(b.get("text", "")) for b in blocks if b.get("type") == "text"]
        tool_calls: list[dict] = []
        for b in blocks:
            if b.get("type") == "tool_use":
                tool_calls.append(
                    {
                        "id": b.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": b.get("name", ""),
                            "arguments": json.dumps(b.get("input", {}), ensure_ascii=False),
                        },
                    }
                )
        return "".join(text_parts), tool_calls


logger.debug("Anthropic provider 已注册（LLM_PROVIDER=anthropic 时启用）")
