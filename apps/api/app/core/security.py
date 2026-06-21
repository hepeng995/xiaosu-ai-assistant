"""管理后台鉴权工具：PBKDF2 密码哈希 + JWT 签发/校验 + FastAPI 依赖。

设计要点：
- 密码哈希用标准库 ``hashlib.pbkdf2_hmac``（SHA256，20 万次迭代），格式自包含盐与迭代次数，
  形如 ``pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>``（Django 风格，便于离线生成与迁移）。
- JWT 用 PyJWT（HS256），payload 含 ``sub`` / ``role`` / ``exp`` / ``iat``。
- 未配置 ``ADMIN_PASSWORD_HASH`` 时回退开发默认密码 ``admin123``（启动告警，仅限开发联调），
  与 IM 密钥未配时「开发放行 + 告警」的降级哲学一致。
- 未配置 ``JWT_SECRET_KEY`` 时开发环境随机生成（重启后已签发 token 全部失效），生产必须配置。

CLI：``uv run python -m app.core.security [密码]`` 生成 PBKDF2 哈希，填入 ``ADMIN_PASSWORD_HASH``。
"""

import base64
import hashlib
import hmac
import secrets
import sys
import time
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Header
from loguru import logger

from app.core.config import settings
from app.core.errors import AppException, ErrorCode

# ---------- PBKDF2 参数 ----------
_PBKDF2_ALGORITHM = "sha256"
_PBKDF2_ITERATIONS = 200_000
_HASH_FORMAT = "pbkdf2_sha256"

# 开发兜底（仅 ADMIN_PASSWORD_HASH 未配置时启用，启动时告警）
_DEV_DEFAULT_PASSWORD = "admin123"
_DEV_DEFAULT_SALT = b"xiaosu-dev-default-salt-v1"
# 未配置 JWT_SECRET_KEY 时，进程内固定的开发兜底密钥（import 时生成一次，重启后变化）。
# 用模块级常量而非每次随机，确保同一进程内签发与校验密钥一致。
_DEV_JWT_SECRET = secrets.token_hex(32)


# ---------- 密码哈希 ----------


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str, salt: bytes | None = None) -> str:
    """生成密码的 PBKDF2 哈希串；未指定 salt 时随机生成 16 字节盐。"""
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(
        _PBKDF2_ALGORITHM, password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return f"{_HASH_FORMAT}${_PBKDF2_ITERATIONS}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    """校验密码是否匹配哈希串；用 ``hmac.compare_digest`` 防时序攻击。"""
    try:
        algo, iter_str, salt_b64, hash_b64 = stored.split("$")
        if algo != _HASH_FORMAT:
            return False
        iterations = int(iter_str)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False
    dk = hashlib.pbkdf2_hmac(
        _PBKDF2_ALGORITHM, password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(dk, expected)


@lru_cache(maxsize=1)
def _dev_default_hash() -> str:
    """开发兜底密码的确定哈希（盐固定，结果稳定可复现）。"""
    return hash_password(_DEV_DEFAULT_PASSWORD, _DEV_DEFAULT_SALT)


def get_admin_password_hash() -> str:
    """返回当前生效的管理员密码哈希：已配置用配置值，否则回退开发兜底。"""
    if settings.admin_password_configured:
        return settings.ADMIN_PASSWORD_HASH
    return _dev_default_hash()


# ---------- JWT ----------


def _jwt_secret() -> str:
    if settings.jwt_secret_configured:
        return settings.JWT_SECRET_KEY
    # 开发环境兜底：模块级常量，保证进程内签发/校验一致（重启后失效）
    return _DEV_JWT_SECRET


def create_access_token(username: str) -> tuple[str, int]:
    """签发 JWT，返回 (token, 有效期秒数)。"""
    now = int(time.time())
    expires_in = settings.JWT_EXPIRE_MINUTES * 60
    payload = {
        "sub": username,
        "role": "admin",
        "iat": now,
        "exp": now + expires_in,
    }
    token = jwt.encode(payload, _jwt_secret(), algorithm=settings.JWT_ALGORITHM)
    return token, expires_in


def decode_access_token(token: str) -> str:
    """校验并解码 JWT，返回管理员用户名；无效/过期/越权抛 401/403。"""
    try:
        payload = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub", "role"]},
        )
    except jwt.ExpiredSignatureError:
        raise AppException(ErrorCode.AUTH_TOKEN_INVALID, "登录已过期，请重新登录", 401) from None
    except jwt.InvalidTokenError:
        raise AppException(ErrorCode.AUTH_TOKEN_INVALID, "无效的登录凭证", 401) from None
    sub = payload.get("sub")
    role = payload.get("role")
    if not isinstance(sub, str) or role != "admin":
        raise AppException(ErrorCode.AUTH_PERMISSION_DENIED, "无权访问管理后台", 403)
    return sub


# ---------- FastAPI 依赖 ----------


def require_admin(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> str:
    """管理后台鉴权依赖：解析 ``Authorization: Bearer <token>`` 并校验，返回管理员用户名。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppException(ErrorCode.AUTH_TOKEN_INVALID, "请先登录", 401)
    token = authorization.split(" ", 1)[1].strip()
    return decode_access_token(token)


# ---------- 启动检查 ----------


def warn_if_insecure() -> None:
    """启动时检查鉴权配置；开发环境未配置给出告警（不阻断启动，遵循降级哲学）。"""
    insecure: list[str] = []
    if not settings.admin_password_configured:
        insecure.append("ADMIN_PASSWORD_HASH（回退默认密码 admin123）")
    if not settings.jwt_secret_configured:
        insecure.append("JWT_SECRET_KEY（开发环境随机生成，重启失效）")
    if insecure:
        logger.warning(
            "管理后台鉴权使用开发兜底配置：{}。生产环境务必通过环境变量配置固定值！",
            "、".join(insecure),
        )


# ---------- CLI：生成密码哈希 ----------

if __name__ == "__main__":
    pwd = sys.argv[1] if len(sys.argv) > 1 else _DEV_DEFAULT_PASSWORD
    print(f"密码 '{pwd}' 的 PBKDF2 哈希（填入 ADMIN_PASSWORD_HASH）：")
    print(hash_password(pwd))
