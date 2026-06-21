"""健康检查测试（不依赖真实 API Key 与外部服务）。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mcp.http import McpHttpAuthApp


def test_health_returns_ok() -> None:
    """GET /health 应返回 status=ok 且响应头携带 trace_id。"""
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "xiaosu-api"
    # trace_id 中间件应回写响应头
    assert response.headers["x-trace-id"].startswith("trace_")


def test_trace_id_passthrough() -> None:
    """请求自带 x-trace-id 时应原样透传。"""
    client = TestClient(app)
    custom = "trace_custom_12345"
    response = client.get("/health", headers={"x-trace-id": custom})
    assert response.headers["x-trace-id"] == custom


async def _call_asgi(app_obj: McpHttpAuthApp, headers: list[tuple[bytes, bytes]]) -> list[dict]:
    sent: list[dict] = []

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict) -> None:
        sent.append(message)

    scope = {"type": "http", "method": "POST", "path": "/", "headers": headers}
    await app_obj(scope, receive, send)
    return sent


@pytest.mark.asyncio
async def test_mcp_http_auth_rejects_missing_token_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """生产环境启用 HTTP MCP 但未配置 token 时应拒绝访问。"""

    async def inner_app(*_args: object) -> None:
        raise AssertionError("未鉴权请求不应进入 MCP app")

    monkeypatch.setattr("app.mcp.http.settings.APP_ENV", "production")
    monkeypatch.setattr("app.mcp.http.settings.MCP_HTTP_AUTH_TOKEN", "replace_me")
    sent = await _call_asgi(McpHttpAuthApp(inner_app), [])

    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 403


@pytest.mark.asyncio
async def test_mcp_http_auth_accepts_configured_bearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """配置 token 后，Bearer 匹配才放行到 MCP app。"""
    called: list[bool] = []

    async def inner_app(_scope: object, _receive: object, send: object) -> None:
        called.append(True)
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    monkeypatch.setattr("app.mcp.http.settings.APP_ENV", "production")
    monkeypatch.setattr("app.mcp.http.settings.MCP_HTTP_AUTH_TOKEN", "test-token")
    sent = await _call_asgi(
        McpHttpAuthApp(inner_app),
        [(b"authorization", b"Bearer test-token")],
    )

    assert called == [True]
    assert sent[0]["status"] == 204
