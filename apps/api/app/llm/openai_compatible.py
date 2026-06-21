"""LLM 服务：OpenAI-compatible（chat + function calling）；未配置 key 时用 mock。

真实模式：function calling，工具选择由模型按 Tool Schema 自主决定（无 if-else 路由）。
mock 模式：用启发式模拟模型的工具选择与最终回答，仅用于无 key 环境的流程验证。
"""

import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger

from app.core.config import settings
from app.core.observability import llm_span
from app.services import setting_service


@dataclass
class LLMResponse:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMService:
    def __init__(self) -> None:
        self._base_url = settings.LLM_BASE_URL
        self._api_key = settings.LLM_API_KEY
        self._model = settings.LLM_MODEL
        self._client = httpx.AsyncClient(timeout=float(settings.LLM_TIMEOUT_SECONDS))

    @property
    def use_mock(self) -> bool:
        return not settings.is_secret_configured(self._api_key)

    async def _effective_model(self) -> str:
        """真实请求使用的模型：运行时激活模型覆盖默认（未设置则回退环境变量值）。"""
        active = await setting_service.get_active_model()
        return active or self._model

    async def chat(self, messages: list[dict], temperature: float = 0.3) -> LLMResponse:
        if self.use_mock:
            return self._mock_chat(messages)
        return await self._chat_via_api(messages, temperature)

    async def chat_with_tools(
        self, messages: list[dict], tools_schema: list[dict], temperature: float = 0.0
    ) -> tuple[str, list[dict], dict]:
        """带工具的对话，返回 (content, tool_calls, usage)。

        工具选择阶段默认 temperature=0.0 保证确定性（相同问题选相同工具），
        避免同一问题多次回答不一致；最终回答阶段（chat_stream）仍用 0.3 保留丰富度。
        """
        if self.use_mock:
            return self._mock_chat_with_tools(messages)
        return await self._chat_with_tools_api(messages, tools_schema, temperature)

    async def chat_stream(
        self, messages: list[dict], temperature: float = 0.3
    ) -> AsyncIterator[str]:
        """流式输出最终回答 token；mock 模式按小片段降级。"""
        if self.use_mock:
            content = self._mock_chat(messages).content
            for i in range(0, len(content), 6):
                yield content[i : i + 6]
            return

        effective_model = await self._effective_model()
        url = f"{self._base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": effective_model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        llm_logger = logger.bind(module="llm", event="chat_stream", model=effective_model)
        llm_logger.info("LLM 流式请求开始 messages={}", len(messages))
        async with self._client.stream("POST", url, json=payload, headers=headers) as resp:
            if resp.status_code in (401, 403):
                raise RuntimeError("LLM_AUTH_ERROR")
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                token = self._extract_delta_token(chunk)
                if token:
                    yield token
        llm_logger.info("LLM 流式请求结束")

    async def _chat_via_api(self, messages: list[dict], temperature: float) -> LLMResponse:
        effective_model = await self._effective_model()
        url = f"{self._base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": effective_model,
            "messages": messages,
            "temperature": temperature,
        }
        with llm_span("llm_chat", model=effective_model) as state:
            resp = self._parse_chat_response(await self._post(url, payload))
            state["output"] = resp.content
            state["usage"] = {
                "input": resp.prompt_tokens,
                "output": resp.completion_tokens,
                "unit": "TOKENS",
            }
            return resp

    async def _chat_with_tools_api(
        self, messages: list[dict], tools_schema: list[dict], temperature: float = 0.0
    ) -> tuple[str, list[dict], dict]:
        effective_model = await self._effective_model()
        url = f"{self._base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": effective_model,
            "messages": messages,
            "tools": tools_schema,
            "temperature": temperature,
        }
        with llm_span("llm_chat_with_tools", model=effective_model) as state:
            resp_data = await self._post(url, payload)
            msg = resp_data["choices"][0]["message"]
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls") or []
            usage = resp_data.get("usage", {})
            state["output"] = content
            state["usage"] = {
                "input": usage.get("prompt_tokens", 0),
                "output": usage.get("completion_tokens", 0),
                "unit": "TOKENS",
            }
            return content, tool_calls, usage

    async def _post(self, url: str, payload: dict) -> dict:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        last_exc: Exception | None = None
        llm_logger = logger.bind(module="llm", event="chat", model=payload.get("model"))
        for attempt in range(1, settings.LLM_MAX_RETRIES + 2):
            try:
                llm_logger.info(
                    "LLM 请求开始 attempt={} messages={}",
                    attempt,
                    len(payload.get("messages", [])),
                )
                resp = await self._client.post(url, json=payload, headers=headers)
                if resp.status_code in (401, 403):
                    raise RuntimeError("LLM_AUTH_ERROR")
                resp.raise_for_status()
                llm_logger.info("LLM 请求成功 status={}", resp.status_code)
                return resp.json()
            except RuntimeError:
                raise
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "LLM 调用失败 attempt={}/{} err={}", attempt, settings.LLM_MAX_RETRIES + 1, exc
                )
        raise RuntimeError(f"LLM 调用失败: {last_exc}")

    def _parse_chat_response(self, data: dict) -> LLMResponse:
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            content, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
        )

    @staticmethod
    def _extract_delta_token(chunk: dict) -> str | None:
        """从流式 chunk 安全提取 ``delta.content`` token。

        部分 OpenAI-compatible provider（含当前 mimo-v2.5）会在流末尾发 usage-only
        chunk（``choices`` 为空列表），旧实现 ``chunk.get("choices", [{}])[0]`` 会触发
        ``IndexError: list index out of range``，导致流式中断、整段回答降级为兜底文案、
        飞书卡片内容异常。空 choices 直接跳过即可。
        """
        choices = chunk.get("choices") or []
        if not choices:
            return None
        delta = choices[0].get("delta") or {}
        return delta.get("content") or None

    # ---------- mock 实现（无 key 时模拟模型行为）----------

    def _mock_chat(self, messages: list[dict]) -> LLMResponse:
        last_user = self._last_user(messages)
        snippet = last_user[:160].replace("\n", " ")
        content = f"[mock] 已参考知识库片段回答：{snippet}…（配置 LLM_API_KEY 后将由真实模型生成）"
        return LLMResponse(content, max(1, len(last_user) // 2), 60)

    def _mock_chat_with_tools(self, messages: list[dict]) -> tuple[str, list[dict], dict]:
        # 若已有工具结果，则生成最终摘要回答
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        if tool_msgs:
            parts = [str(m.get("content", ""))[:200] for m in tool_msgs]
            answer = (
                "[mock] 根据工具查询结果：\n"
                + "\n".join(parts)
                + "\n（配置 LLM_API_KEY 后将由真实模型生成自然语言回答）"
            )
            return answer, [], {"prompt_tokens": 100, "completion_tokens": 80}
        # 否则模拟模型的工具选择（含指代消解）
        user_msg = self._resolve_coreference(self._last_user(messages), messages)
        calls = self._mock_plan(user_msg)
        return "", calls, {"prompt_tokens": 50, "completion_tokens": 10}

    def _resolve_coreference(self, user_msg: str, messages: list[dict]) -> str:
        """指代消解：将"他/她"替换为历史最近提及的员工编号（模拟多轮理解）。"""
        if not any(p in user_msg for p in ("他", "她")):
            return user_msg
        for m in reversed(messages):
            if m.get("role") == "user":
                match = re.search(r"(\d{3})", m.get("content", ""))
                if match:
                    emp = f"员工{match.group(1)}"
                    return user_msg.replace("他", emp).replace("她", emp)
        return user_msg

    def _mock_plan(self, user_msg: str) -> list[dict]:
        """模拟 LLM function calling 的工具选择（真实模式由模型按 Schema 自主决定）。"""
        calls: list[dict] = []
        emp_match = re.search(r"(\d{3})", user_msg)
        emp_id: str | None = emp_match.group(1) if emp_match else None
        if any(k in user_msg for k in ("销售目标", "销售计划", "未来规划", "经营目标", "2030")):
            calls.append(self._tool_call("search_knowledge_base", {"query": user_msg}))
        elif any(k in user_msg for k in ("几点", "现在时间", "今天几号", "日期", "现在")):
            calls.append(self._tool_call("get_current_time", {"timezone": "Asia/Shanghai"}))
        elif any(k in user_msg for k in ("订单", "销售额", "订单数量")):
            calls.append(
                self._tool_call(
                    "get_orders", {"start_date": "2026-06-08", "end_date": "2026-06-14"}
                )
            )
        elif any(k in user_msg for k in ("考勤", "上班", "迟到")) and emp_id:
            calls.append(
                self._tool_call(
                    "get_attendance",
                    {"employee_id": emp_id, "start_date": "2026-06-08", "end_date": "2026-06-14"},
                )
            )
        elif emp_id and any(
            k in user_msg for k in ("员工", "部门", "职级", "主管", "是谁", "叫什么")
        ):
            calls.append(self._tool_call("get_employee", {"employee_id": emp_id}))
        else:
            calls.append(self._tool_call("search_knowledge_base", {"query": user_msg}))
        return calls

    @staticmethod
    def _tool_call(name: str, args: dict[str, Any]) -> dict:
        return {
            "id": f"call_{name}",
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
        }

    @staticmethod
    def _last_user(messages: list[dict]) -> str:
        for m in reversed(messages):
            if m.get("role") == "user":
                return m.get("content", "")
        return ""


llm_service = LLMService()
