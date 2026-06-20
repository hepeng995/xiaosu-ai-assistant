"""Redis 客户端：用于 IM 事件幂等去重等场景。

项目已集成 redis 容器（docker-compose）；此模块提供懒加载的异步客户端。
IM 回调（飞书/钉钉）因平台超时重试机制会重复推送同一消息，
用幂等键（message_id / event_id）去重，避免重复回复。

Redis 不可用时降级为放行（优先保证消息能回复，极端情况下可能重复）。
"""

from __future__ import annotations

from loguru import logger
from redis.asyncio import Redis, from_url

from app.core.config import settings

# 幂等键 TTL：覆盖飞书最长 6 小时重试窗口 + 缓冲
IDEMPOTENT_TTL_SECONDS = 28800  # 8 小时

_redis: Redis | None = None


def get_redis() -> Redis:
    """懒加载单例 Redis 异步客户端。"""
    global _redis
    if _redis is None:
        _redis = from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def acquire_idempotent(key: str, ttl_seconds: int = IDEMPOTENT_TTL_SECONDS) -> bool:
    """抢占幂等键（SET NX EX）。

    - 首次写入成功返回 ``True``（可处理）
    - 键已存在返回 ``False``（重复事件，应跳过）
    - Redis 异常时降级返回 ``True``（放行，优先保证消息回复）

    Args:
        key: 幂等键，建议 ``<platform>:msg:<message_id>``。
        ttl_seconds: 过期时间，默认覆盖飞书 6 小时重试窗口。
    """
    try:
        redis = get_redis()
        return bool(await redis.set(key, "1", nx=True, ex=ttl_seconds))
    except Exception as exc:  # Redis 不可用时降级放行，不阻断消息处理
        logger.bind(module="im", event="idempotent").warning(
            "Redis 幂等检查失败，降级放行 key={} err={}", key, exc
        )
        return True
