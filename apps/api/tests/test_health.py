"""健康检查测试（不依赖真实 API Key 与外部服务）。"""

from fastapi.testclient import TestClient

from app.main import app


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
