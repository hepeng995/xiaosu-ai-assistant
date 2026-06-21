"""管理后台鉴权测试：密码哈希、登录、JWT 守卫。

不依赖真实数据库与外部服务：登录与 token 校验均无需 DB。
默认走开发兜底（ADMIN_PASSWORD_HASH 未配置 → admin123；JWT_SECRET_KEY 未配置 → 进程内固定密钥）。
"""

import pytest
from fastapi.testclient import TestClient

from app.core.errors import AppException
from app.core.security import (
    _DEV_DEFAULT_PASSWORD,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.main import app

client = TestClient(app)


def _login(username: str = "admin", password: str = _DEV_DEFAULT_PASSWORD) -> str:
    """辅助：登录并返回 access_token。"""
    resp = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------- 密码哈希 ----------


def test_password_hash_roundtrip() -> None:
    """hash_password 后 verify_password 应校验通过；错误密码失败；随机盐使两次哈希不同。"""
    pwd = "S3cret-pa55!"
    stored = hash_password(pwd)
    assert verify_password(pwd, stored) is True
    assert verify_password("wrong", stored) is False
    assert hash_password(pwd) != stored


def test_verify_password_rejects_malformed_hash() -> None:
    """格式错误或算法不匹配的哈希串应安全返回 False（不抛异常）。"""
    assert verify_password("x", "not-a-valid-hash") is False
    assert verify_password("x", "bcrypt$1000$aa$bb") is False
    assert verify_password("x", "pbkdf2_sha256$abc$notb64$notb64") is False


# ---------- 登录 ----------


def test_login_success_returns_token() -> None:
    """默认密码 admin123 登录成功，返回 JWT 与用户名，token 可被解码。"""
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": _DEV_DEFAULT_PASSWORD},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["username"] == "admin"
    assert body["expires_in"] > 0
    assert decode_access_token(body["access_token"]) == "admin"


@pytest.mark.parametrize(
    "username,password",
    [("admin", "wrong"), ("wronguser", _DEV_DEFAULT_PASSWORD)],
)
def test_login_invalid_credentials_returns_401(username: str, password: str) -> None:
    """用户名或密码错误均返回 401 + 统一模糊文案（防用户名枚举）。"""
    resp = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False
    assert body["error_code"] == "AUTH_INVALID_CREDENTIALS"


# ---------- JWT 守卫 ----------


def test_admin_settings_rejects_missing_token() -> None:
    """无 token 访问管理后台应 401。"""
    resp = client.get("/api/admin/settings")
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "AUTH_TOKEN_INVALID"


def test_admin_settings_rejects_invalid_token() -> None:
    """错误 token 应 401。"""
    resp = client.get("/api/admin/settings", headers=_bearer("not.a.valid.token"))
    assert resp.status_code == 401


def test_admin_settings_accepts_valid_token() -> None:
    """正确 token 访问应 200，且响应含各模块配置状态。"""
    token = _login()
    resp = client.get("/api/admin/settings", headers=_bearer(token))
    assert resp.status_code == 200
    body = resp.json()
    assert "llm" in body
    assert "feishu" in body


def test_admin_documents_requires_admin() -> None:
    """文档管理无 token 应 401。"""
    resp = client.get("/api/admin/documents")
    assert resp.status_code == 401


def test_admin_messages_requires_admin() -> None:
    """对话日志（含员工隐私）无 token 应 401。"""
    resp = client.get("/api/admin/messages")
    assert resp.status_code == 401


def test_auth_me_returns_username() -> None:
    """GET /api/auth/me 带正确 token 返回当前管理员。"""
    token = _login()
    resp = client.get("/api/auth/me", headers=_bearer(token))
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"
    assert resp.json()["role"] == "admin"


def test_auth_me_rejects_missing_token() -> None:
    """GET /api/auth/me 无 token 应 401。"""
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_decode_token_rejects_tampered_token() -> None:
    """签名被篡改的 token 解码应抛 AUTH_TOKEN_INVALID。"""
    token, _ = create_access_token("admin")
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(AppException):
        decode_access_token(tampered)
