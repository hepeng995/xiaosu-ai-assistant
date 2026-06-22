"""Embedding 服务：OpenAI-compatible API；未配置 key 时用确定性 mock 向量。

mock 仅用于无 API Key 环境下的流程验证（入库/检索路径），
真实语义检索需在 .env 配置有效的 EMBEDDING_API_KEY。
"""

import hashlib
import math

import httpx
from loguru import logger

from app.core.config import settings
from app.core.observability import llm_span

# 单次 embedding 请求的文本条数上限：部分 OpenAI 兼容接口（如阿里 dashscope
# text-embedding-v4）单次 input 上限 10 条，超出返回 400，故按此分批。
EMBEDDING_BATCH_SIZE = 10


class EmbeddingService:
    """文本向量化服务（批量 + 单条）。"""

    def __init__(self) -> None:
        self._base_url = settings.EMBEDDING_BASE_URL
        self._api_key = settings.EMBEDDING_API_KEY
        self._model = settings.EMBEDDING_MODEL
        self._dim = settings.EMBEDDING_DIMENSION
        self._client = httpx.AsyncClient(timeout=float(settings.LLM_TIMEOUT_SECONDS))

    @property
    def use_mock(self) -> bool:
        """是否使用 mock（API key 未真正配置时）。"""
        return not settings.is_secret_configured(self._api_key)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量生成 embedding（自动分批，避免超过 API 单次批量上限）。"""
        if not texts:
            return []
        if self.use_mock:
            logger.warning("EMBEDDING_API_KEY 未配置，使用 mock 向量（仅流程验证，非真实语义）")
            return [self._mock_vector(t) for t in texts]
        # 分批请求，规避部分接口（如 dashscope text-embedding-v4）单次 input 条数上限
        result: list[list[float]] = []
        for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            result.extend(await self._embed_via_api(texts[i : i + EMBEDDING_BATCH_SIZE]))
        return result

    async def embed_query(self, text: str) -> list[float]:
        """单条查询向量。"""
        result = await self.embed_texts([text])
        return result[0]

    async def _embed_via_api(self, texts: list[str]) -> list[list[float]]:
        with llm_span("embedding", model=self._model) as state:
            url = f"{self._base_url.rstrip('/')}/embeddings"
            headers = {"Authorization": f"Bearer {self._api_key}"}
            last_exc: Exception | None = None
            emb_logger = logger.bind(module="llm", event="embedding", model=self._model)
            # dimensions 参数并非所有模型都支持：bge-m3 等原生定长模型传了会 400。
            # 先尝试带 dimensions，遇 400 自动降级为不传（走原生维度），兼容两类模型。
            send_dimensions = True
            for attempt in range(1, settings.LLM_MAX_RETRIES + 2):
                payload: dict[str, object] = {"model": self._model, "input": texts}
                if send_dimensions:
                    payload["dimensions"] = self._dim
                try:
                    emb_logger.info(
                        "embedding 请求开始 attempt={} count={} dim={}",
                        attempt,
                        len(texts),
                        payload.get("dimensions"),
                    )
                    resp = await self._client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    emb_logger.info("embedding 请求成功 count={}", len(texts))
                    result = [item["embedding"] for item in data["data"]]
                    state["output"] = f"{len(result)} vectors"
                    state["usage"] = {"input": len(texts), "unit": "CHARS"}
                    return result
                except httpx.HTTPStatusError as exc:
                    last_exc = exc
                    if exc.response.status_code == 400 and send_dimensions:
                        send_dimensions = False
                        logger.warning(
                            "embedding 返回 400，模型可能不支持 dimensions 参数，"
                            "已降级为原生维度重试"
                        )
                        continue
                    logger.warning(
                        "embedding 调用失败 attempt={}/{} status={} err={}",
                        attempt,
                        settings.LLM_MAX_RETRIES + 1,
                        exc.response.status_code,
                        exc,
                    )
                except Exception as exc:
                    last_exc = exc
                    logger.warning(
                        "embedding 调用失败 attempt={}/{} err={}",
                        attempt,
                        settings.LLM_MAX_RETRIES + 1,
                        exc,
                    )
            raise RuntimeError(f"embedding 调用失败: {last_exc}")

    def _mock_vector(self, text: str) -> list[float]:
        """基于文本 SHA256 生成确定性伪向量（归一化，仅流程验证）。"""
        seed = hashlib.sha256(text.encode("utf-8")).digest()
        raw = bytearray()
        block = seed
        while len(raw) < self._dim:
            raw.extend(block)
            block = hashlib.sha256(block).digest()
        vec = [(b - 128) / 128.0 for b in raw[: self._dim]]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


embedding_service = EmbeddingService()
