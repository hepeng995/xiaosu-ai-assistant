"""系统设置 API：展示模型/IM/DB 配置状态（不回显密钥）+ 运行时切换模型。"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import settings
from app.db.session import check_db_connection
from app.services import setting_service

router = APIRouter(prefix="/api/admin/settings", tags=["admin-settings"])


class ModelSwitchRequest(BaseModel):
    """切换模型请求：仅模型名（不接收 base_url / api_key，防注入）。"""

    model: str = Field(..., min_length=1, max_length=100)


@router.get("")
async def get_settings_status() -> dict:
    """返回各配置项的就绪状态（敏感值只显示已配置/未配置）。"""
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
            "top_k": settings.RAG_TOP_K,
            "score_threshold": settings.RAG_SCORE_THRESHOLD,
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


@router.get("/health")
async def system_health() -> dict:
    """系统组件健康状态。"""
    db_ok = await check_db_connection()
    return {"database": "ok" if db_ok else "unavailable", "service": "xiaosu-api"}


@router.get("/model")
async def get_active_model() -> dict:
    """返回当前激活模型与环境变量默认模型。"""
    return {
        "active_model": await setting_service.get_active_model(),
        "default_model": settings.LLM_MODEL,
    }


@router.put("/model")
async def switch_model(req: ModelSwitchRequest) -> dict:
    """设置运行时激活模型（校验后持久化），未配置 key 时亦可设置（待 key 就绪后生效）。"""
    saved = await setting_service.set_active_model(req.model)
    return {"active_model": saved, "default_model": settings.LLM_MODEL}
