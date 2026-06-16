"""LLM Chat 服务：OpenAI-compatible API；未配置 key 时用 mock。

mock 仅用于无 API Key 环境下的流程验证，真实回答需配置有效的 LLM_API_KEY。
"""

from dataclasses import dataclass

import httpx
from loguru import logger

from app.core.config import settings


@dataclass
class LLMResponse:
    """LLM 响应（内容 + token 用量）。"""

    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMService:
    """对话补全服务（OpenAI-compatible）。"""

    def __init__(self) -> None:
        self._base_url = settings.LLM_BASE_URL
        self._api_key = settings.LLM_API_KEY
        self._model = settings.LLM_MODEL
        self._client = httpx.AsyncClient(timeout=float(settings.LLM_TIMEOUT_SECONDS))

    @property
    def use_mock(self) -> bool:
        return not settings.is_secret_configured(self._api_key)

    async def chat(self, messages: list[dict], temperature: float = 0.3) -> LLMResponse:
        """生成对话回复。"""
        if self.use_mock:
            return self._mock_chat(messages)
        return await self._chat_via_api(messages, temperature)

    async def _chat_via_api(self, messages: list[dict], temperature: float) -> LLMResponse:
        url = f"{self._base_url.rstrip('/')}/chat/completions"
        payload = {"model": self._model, "messages": messages, "temperature": temperature}
        headers = {"Authorization": f"Bearer {self._api_key}"}
        last_exc: Exception | None = None
        for attempt in range(1, settings.LLM_MAX_RETRIES + 2):
            try:
                resp = await self._client.post(url, json=payload, headers=headers)
                if resp.status_code in (401, 403):
                    # 认证错误不重试，直接抛出（由上层兜底）
                    raise RuntimeError("LLM_AUTH_ERROR") from httpx.HTTPStatusError(
                        "auth error", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return LLMResponse(
                    content,
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                )
            except RuntimeError:
                raise
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "LLM 调用失败 attempt={}/{} err={}", attempt, settings.LLM_MAX_RETRIES + 1, exc
                )
        raise RuntimeError(f"LLM 调用失败: {last_exc}")

    def _mock_chat(self, messages: list[dict]) -> LLMResponse:
        """mock：从 system+user 提取片段摘要（仅流程验证）。"""
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break
        snippet = last_user[:160].replace("\n", " ")
        content = f"[mock] 已参考知识库片段回答：{snippet}…（配置 LLM_API_KEY 后由真实模型生成）"
        return LLMResponse(
            content=content,
            prompt_tokens=max(1, len(last_user) // 2),
            completion_tokens=60,
        )


llm_service = LLMService()
