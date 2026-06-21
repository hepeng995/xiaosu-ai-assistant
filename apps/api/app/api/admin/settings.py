"""管理后台：系统设置 API + 管理员认证 API。

为何与 auth 路由同文件：``app/api/`` 目录已踩 8 文件红线边缘，不能再新增文件；
二者同属「管理后台域」，合并于此不破坏红线，且文件行数仍远低于 500。
- ``router``（/api/admin/settings）：展示模型/IM/DB 配置状态（不回显密钥）+ 运行时切换模型。
- ``auth_router``（/api/auth）：管理员登录 / 当前用户，签发 JWT。
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.errors import AppException, ErrorCode
from app.core.security import (
    create_access_token,
    get_admin_password_hash,
    require_admin,
    verify_password,
)
from app.db.session import check_db_connection
from app.schemas.auth import LoginRequest, LoginResponse, UserInfo
from app.services import setting_service

router = APIRouter(prefix="/api/admin/settings", tags=["admin-settings"])
auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------- 系统设置 ----------


class ModelSwitchRequest(BaseModel):
    """切换模型请求：仅模型名（不接收 base_url / api_key，防注入）。"""

    model: str = Field(..., min_length=1, max_length=100)


@router.get("", dependencies=[Depends(require_admin)])
async def get_settings_status() -> dict:
    """返回各配置项的就绪状态（敏感值只显示已配置/未配置）。"""
    rag_runtime = await setting_service.get_rag_params()
    return {
        "llm": {
            "provider": settings.LLM_PROVIDER,
            "model": settings.LLM_MODEL,
            "base_url": settings.LLM_BASE_URL,
            "api_key_configured": settings.is_secret_configured(settings.LLM_API_KEY),
        },
        "embedding": {
            "model": settings.EMBEDDING_MODEL,
            "dimension": settings.EMBEDDING_DIMENSION,
            "api_key_configured": settings.is_secret_configured(settings.EMBEDDING_API_KEY),
        },
        "rag": {
            "top_k": rag_runtime.get("top_k", settings.RAG_TOP_K),
            "score_threshold": rag_runtime.get(
                "score_threshold", settings.RAG_SCORE_THRESHOLD
            ),
            "chunk_size": settings.RAG_CHUNK_SIZE,
        },
        "dingtalk": {
            "app_key_configured": settings.is_secret_configured(settings.DINGTALK_APP_KEY),
            "app_secret_configured": settings.is_secret_configured(settings.DINGTALK_APP_SECRET),
            "robot_code_configured": settings.is_secret_configured(settings.DINGTALK_ROBOT_CODE),
        },
        "feishu": {
            "app_id_configured": settings.is_secret_configured(settings.FEISHU_APP_ID),
            "app_secret_configured": settings.is_secret_configured(settings.FEISHU_APP_SECRET),
            "verification_token_configured": settings.is_secret_configured(
                settings.FEISHU_VERIFICATION_TOKEN
            ),
            "encrypt_key_configured": settings.is_secret_configured(settings.FEISHU_ENCRYPT_KEY),
        },
        "agent": {
            "max_tool_rounds": settings.MAX_TOOL_ROUNDS,
            "tool_timeout": settings.TOOL_TIMEOUT_SECONDS,
        },
        "observability": {
            "langfuse_enabled": settings.langfuse_enabled,
            "host_configured": bool(settings.LANGFUSE_HOST),
        },
    }


@router.get("/health", dependencies=[Depends(require_admin)])
async def system_health() -> dict:
    """系统组件健康状态。"""
    db_ok = await check_db_connection()
    return {"database": "ok" if db_ok else "unavailable", "service": "xiaosu-api"}


@router.get("/model", dependencies=[Depends(require_admin)])
async def get_active_model() -> dict:
    """返回当前激活模型与环境变量默认模型。"""
    return {
        "active_model": await setting_service.get_active_model(),
        "default_model": settings.LLM_MODEL,
    }


@router.put("/model", dependencies=[Depends(require_admin)])
async def switch_model(req: ModelSwitchRequest) -> dict:
    """设置运行时激活模型（校验后持久化），未配置 key 时亦可设置（待 key 就绪后生效）。"""
    saved = await setting_service.set_active_model(req.model)
    return {"active_model": saved, "default_model": settings.LLM_MODEL}


class RagParamsRequest(BaseModel):
    """RAG 检索参数（运行时可调，立即对后续检索生效）。"""

    top_k: int = Field(..., ge=1, le=50)
    score_threshold: float = Field(..., ge=0, le=1)


@router.put("/params", dependencies=[Depends(require_admin)])
async def update_rag_params(req: RagParamsRequest) -> dict:
    """更新运行时 RAG 参数（top_k / score_threshold），校验后持久化并立即生效。"""
    saved = await setting_service.set_rag_params(req.top_k, req.score_threshold)
    return {"rag": saved}


# ---------- 管理员认证 ----------


@auth_router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest) -> LoginResponse:
    """管理员登录：校验用户名+密码，签发 JWT。用户名或密码错误均返回同一模糊文案（防枚举）。"""
    username_ok = req.username == settings.ADMIN_USERNAME
    password_ok = verify_password(req.password, get_admin_password_hash())
    if not (username_ok and password_ok):
        raise AppException(ErrorCode.AUTH_INVALID_CREDENTIALS, "用户名或密码错误", 401)
    token, expires_in = create_access_token(req.username)
    return LoginResponse(
        access_token=token,
        expires_in=expires_in,
        username=req.username,
    )


@auth_router.get("/me", response_model=UserInfo)
async def current_user(username: str = Depends(require_admin)) -> UserInfo:
    """返回当前登录管理员（token 校验失败抛 401）。"""
    return UserInfo(username=username)
