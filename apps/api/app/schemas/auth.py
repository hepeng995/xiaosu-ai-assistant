"""鉴权相关入参/出参模型（Pydantic v2）。"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """管理员登录请求：用户名 + 密码（明文，仅用于本次校验，不落库不记日志）。"""

    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    """登录成功响应：JWT access token + 当前管理员信息。"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str


class UserInfo(BaseModel):
    """当前登录管理员信息（GET /api/auth/me 返回）。"""

    username: str
    role: str = "admin"
