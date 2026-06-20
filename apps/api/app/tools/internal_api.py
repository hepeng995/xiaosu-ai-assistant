"""内部 Mock API 调用 helper：统一超时、重试与响应解析。"""

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings

_MAX_RETRIES = 1


@dataclass
class InternalApiResponse:
    """内部 API 响应（不把 4xx 作为异常抛出，交由工具生成友好文案）。"""

    status_code: int
    data: dict[str, Any]


async def request_internal_api(
    path: str,
    params: dict[str, str] | None = None,
) -> InternalApiResponse:
    """GET 调用内部 Mock API，对网络异常/超时/5xx 重试 1 次。"""
    base = f"http://localhost:{settings.APP_PORT}"
    url = f"{base}{path}"
    last_exc: Exception | None = None
    async with httpx.AsyncClient(timeout=settings.TOOL_TIMEOUT_SECONDS) as client:
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = await client.get(url, params=params)
                data = resp.json() if resp.content else {}
                if resp.status_code >= 500 and attempt < _MAX_RETRIES:
                    continue
                return InternalApiResponse(resp.status_code, data)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    continue
                break
    raise RuntimeError("内部系统暂时不可用") from last_exc
