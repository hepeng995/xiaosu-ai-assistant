"""可观测性：Langfuse 追踪（未配置时 noop，不破坏主链路）。

降级原则：
- ``LANGFUSE_*`` 未配置 → 所有 span 为 noop，零开销、不影响 mock/业务。
- SDK 调用失败 → best-effort 忽略，绝不向上抛出。
已配置时，在 LLM / Embedding 调用节点记录 generation（model/output/usage），
trace 关联中间件注入的 trace_id（贯穿 IM→Chat→Agent→LLM 全链路）。
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from loguru import logger

from app.core.config import settings

# 中间件注入的 trace_id，供 span 关联（贯穿全链路）
trace_id_var: ContextVar[str] = ContextVar("obs_trace_id", default="-")

_client: Any = None
_init_attempted = False


def get_client() -> Any | None:
    """惰性返回 langfuse client；未配置返回 None。"""
    global _client, _init_attempted
    if _init_attempted:
        return _client
    _init_attempted = True
    if not settings.langfuse_enabled:
        return None
    try:
        from langfuse import Langfuse  # type: ignore[import-not-found]

        _client = Langfuse(
            host=settings.LANGFUSE_HOST or None,
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
        )
        logger.info("Langfuse 可观测性已启用 host={}", settings.LANGFUSE_HOST or "(默认)")
    except Exception as exc:
        logger.warning("Langfuse 初始化失败，可观测性降级 noop: {}", exc)
        _client = None
    return _client


def _reset_for_test() -> None:
    """测试重置单例（避免跨用例污染）。"""
    global _client, _init_attempted
    _client = None
    _init_attempted = False


@contextmanager
def trace_span(name: str, *, metadata: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    """记录一次通用链路 span；未配置 Langfuse 时为 noop。

    调用方可在 yield 的 state 中回填 ``output``/``metadata``，SDK 异常会被忽略。
    """
    state: dict[str, Any] = {}
    if metadata:
        state["metadata"] = metadata
    client = get_client()
    span: Any = None
    if client is not None:
        try:
            trace = client.trace(id=trace_id_var.get())
            span = trace.span(name=name, metadata=metadata)
        except Exception as exc:
            logger.debug("langfuse span 创建失败（已忽略）: {}", exc)
    yield state
    if span is not None:
        try:
            end_kwargs = {k: v for k, v in state.items() if k in ("output", "metadata")}
            span.end(**end_kwargs)
        except Exception as exc:
            logger.debug("langfuse span 结束失败（已忽略）: {}", exc)


@contextmanager
def llm_span(name: str, *, model: str | None = None) -> Iterator[dict[str, Any]]:
    """记录一次 LLM/Embedding generation；yield state dict 供调用方回填 output/usage。

    用法::

        with llm_span("llm_chat", model=m) as state:
            resp = await call(...)
            state["output"] = resp.content
            state["usage"] = {"input": p, "output": c, "unit": "TOKENS"}
    """
    state: dict[str, Any] = {}
    client = get_client()
    generation: Any = None
    if client is not None:
        try:
            trace = client.trace(id=trace_id_var.get())
            generation = trace.generation(name=name, model=model)
        except Exception as exc:
            logger.debug("langfuse span 创建失败（已忽略）: {}", exc)
    yield state
    if generation is not None:
        try:
            end_kwargs = {
                k: v for k, v in state.items() if k in ("output", "usage", "metadata")
            }
            generation.end(**end_kwargs)
        except Exception as exc:
            logger.debug("langfuse span 结束失败（已忽略）: {}", exc)
