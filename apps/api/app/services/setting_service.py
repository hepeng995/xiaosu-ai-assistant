"""运行时设置服务：基于 settings 表的非敏感配置读写（含运行时模型切换）。

设计要点：
- **只存非敏感配置**（如当前激活的模型名），绝不存放 API Key / Base URL，防止注入与泄漏。
- LLM 在每次真实请求时读取激活模型覆盖环境变量默认值；未设置或为空时回退默认（保持降级哲学）。
- 进程内带 TTL 缓存，避免每条请求都查库；写入时清除对应缓存。
"""

import re
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppException, ErrorCode
from app.db.session import AsyncSessionLocal
from app.models import Setting

_ACTIVE_MODEL_KEY = "llm_active_model"
# 模型名仅允许字母、数字与常见分隔符（. _ - : / 空格），长度 1~100，防止注入
_MODEL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._\-:/ ]{1,100}$")
_CACHE_TTL_SECONDS = 30.0

# 模块级缓存：key -> (monotonic 时间戳, 值)
_cache: dict[str, tuple[float, Any]] = {}


def invalidate_cache(key: str | None = None) -> None:
    """清除缓存（写入设置或测试时调用）。"""
    if key is None:
        _cache.clear()
    else:
        _cache.pop(key, None)


def _validate_model_name(model: str) -> str:
    """校验模型名合法性，返回去除首尾空白的规范值；非法时抛 400。"""
    if not isinstance(model, str) or not _MODEL_NAME_PATTERN.match(model):
        raise AppException(
            ErrorCode.UNKNOWN_ERROR,
            "模型名不合法（仅允许字母、数字及 . _ - : / 空格，长度 1~100）",
            400,
        )
    return model.strip()


async def get_setting(session: AsyncSession, key: str) -> dict[str, Any] | None:
    """读取一条运行时设置；命中未过期缓存时跳过 DB。"""
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]  # type: ignore[return-value]
    result = await session.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    value = setting.value if setting else None
    _cache[key] = (now, value)
    return value


async def upsert_setting(
    session: AsyncSession, key: str, value: dict[str, Any], description: str | None = None
) -> None:
    """写入或更新一条运行时设置，并清除该 key 缓存。"""
    result = await session.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if setting is None:
        setting = Setting(key=key, value=value, description=description)
        session.add(setting)
    else:
        setting.value = value
        if description is not None:
            setting.description = description
    await session.commit()
    invalidate_cache(key)


async def get_active_model() -> str | None:
    """读取运行时激活模型；未设置或为空返回 None（由调用方回退默认）。"""
    async with AsyncSessionLocal() as session:
        value = await get_setting(session, _ACTIVE_MODEL_KEY)
    if not isinstance(value, dict):
        return None
    model = value.get("model")
    if not isinstance(model, str) or not model.strip():
        return None
    return model.strip()


async def set_active_model(model: str) -> str:
    """设置运行时激活模型（校验后持久化），返回规范化后的模型名。"""
    model = _validate_model_name(model)
    async with AsyncSessionLocal() as session:
        await upsert_setting(
            session,
            _ACTIVE_MODEL_KEY,
            {"model": model},
            "运行时激活的 LLM 模型名（覆盖 LLM_MODEL 默认值）",
        )
    return model


_RAG_PARAMS_KEY = "rag_params"


async def get_rag_params() -> dict[str, Any]:
    """读取运行时 RAG 参数（top_k/score_threshold）；未设置返回空 dict，调用方回退默认。"""
    async with AsyncSessionLocal() as session:
        value = await get_setting(session, _RAG_PARAMS_KEY)
    return value if isinstance(value, dict) else {}


async def set_rag_params(top_k: int, score_threshold: float) -> dict[str, Any]:
    """写入运行时 RAG 参数（校验后持久化），立即对后续检索生效。"""
    if not 1 <= top_k <= 50:
        raise AppException(ErrorCode.UNKNOWN_ERROR, "top_k 须在 1~50 之间", 400)
    if not 0 <= score_threshold <= 1:
        raise AppException(ErrorCode.UNKNOWN_ERROR, "score_threshold 须在 0~1 之间", 400)
    merged = {"top_k": top_k, "score_threshold": score_threshold}
    async with AsyncSessionLocal() as session:
        await upsert_setting(session, _RAG_PARAMS_KEY, merged, "运行时 RAG 检索参数")
    return merged
