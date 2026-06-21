"""波次 A 测试：运行时模型切换（setting_service 读写 + LLM 模型覆盖 + 路由）。

不依赖真实数据库与真实 API Key：用 FakeSession 模拟 settings 表，并校验模型名防注入。
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.errors import AppException
from app.core.security import create_access_token
from app.llm.openai_compatible import llm_service
from app.main import app
from app.services import setting_service


def _admin_auth_header() -> dict[str, str]:
    """生成管理后台鉴权头（直接签发 token，不依赖登录兜底密码）。"""
    token, _ = create_access_token("admin")
    return {"Authorization": f"Bearer {token}"}


class _FakeResult:
    def __init__(self, scalar: Any) -> None:
        self._scalar = scalar

    def scalar_one_or_none(self) -> Any:
        return self._scalar


class _FakeSetting:
    def __init__(self, key: str, value: dict[str, Any]) -> None:
        self.key = key
        self.value = value
        self.description: str | None = None


class _FakeSession:
    """模拟单条 setting 记录的 async session（支持 upsert 语义）。"""

    def __init__(self) -> None:
        self.record: _FakeSetting | None = None
        self._pending: _FakeSetting | None = None

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, _stmt: object) -> _FakeResult:
        return _FakeResult(self.record)

    def add(self, obj: _FakeSetting) -> None:
        self._pending = obj

    async def commit(self) -> None:
        if self._pending is not None:
            self.record = self._pending
            self._pending = None


def _bind_fake_session(monkeypatch: pytest.MonkeyPatch) -> _FakeSession:
    fake = _FakeSession()
    monkeypatch.setattr(setting_service, "AsyncSessionLocal", lambda: fake)
    setting_service.invalidate_cache()
    return fake


def test_validate_model_name_rejects_invalid() -> None:
    """模型名校验：拒绝空、超长、含注入字符；接受常规模型名。"""
    with pytest.raises(AppException):
        setting_service._validate_model_name("")
    with pytest.raises(AppException):
        setting_service._validate_model_name("gpt;rm -rf /")
    with pytest.raises(AppException):
        setting_service._validate_model_name("a$b")
    with pytest.raises(AppException):
        setting_service._validate_model_name("x" * 101)
    assert setting_service._validate_model_name("  gpt-4o-mini  ") == "gpt-4o-mini"
    assert setting_service._validate_model_name("deepseek-chat-v3") == "deepseek-chat-v3"


@pytest.mark.asyncio
async def test_get_active_model_defaults_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """未设置时返回 None（由调用方回退默认）。"""
    _bind_fake_session(monkeypatch)
    assert await setting_service.get_active_model() is None


@pytest.mark.asyncio
async def test_set_and_get_active_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """写入后能读回，且规范化空白。"""
    _bind_fake_session(monkeypatch)
    saved = await setting_service.set_active_model("  gpt-4o  ")
    assert saved == "gpt-4o"
    setting_service.invalidate_cache()
    assert await setting_service.get_active_model() == "gpt-4o"


@pytest.mark.asyncio
async def test_set_active_model_rejects_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """写入非法模型名应抛 400。"""
    _bind_fake_session(monkeypatch)
    with pytest.raises(AppException):
        await setting_service.set_active_model("bad;model")


@pytest.mark.asyncio
async def test_effective_model_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """无运行时覆盖时，LLM 使用环境变量默认模型。"""
    _bind_fake_session(monkeypatch)
    assert await llm_service._effective_model() == llm_service._model


@pytest.mark.asyncio
async def test_effective_model_uses_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """设置运行时模型后，LLM 真实请求改用该模型（mock 分支不受影响）。"""
    _bind_fake_session(monkeypatch)
    await setting_service.set_active_model("deepseek-chat")
    setting_service.invalidate_cache()
    assert await llm_service._effective_model() == "deepseek-chat"
    # 清理：避免影响其他测试
    setting_service.invalidate_cache()


def test_get_model_endpoint_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/admin/settings/model 路由可达（需鉴权），返回 active/default。"""

    async def fake_get() -> None:
        return None

    monkeypatch.setattr(
        "app.api.admin.settings.setting_service.get_active_model", fake_get
    )
    client = TestClient(app)
    resp = client.get("/api/admin/settings/model", headers=_admin_auth_header())
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_model"] is None
    assert "default_model" in body


def test_switch_model_endpoint_validates(monkeypatch: pytest.MonkeyPatch) -> None:
    """PUT /api/admin/settings/model 需鉴权；带 token 后非法模型名应返回 400 友好结构。"""
    client = TestClient(app)
    # 无 token 应先被鉴权拦截（401）
    assert (
        client.put("/api/admin/settings/model", json={"model": "bad;model"}).status_code
        == 401
    )
    resp = client.put(
        "/api/admin/settings/model",
        json={"model": "bad;model"},
        headers=_admin_auth_header(),
    )
    assert resp.status_code == 400
    assert resp.json()["success"] is False
