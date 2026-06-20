"""系统设置 API：展示模型/IM/DB 配置状态（不回显密钥）。"""

from fastapi import APIRouter

from app.core.config import settings
from app.db.session import check_db_connection

router = APIRouter(prefix="/api/admin/settings", tags=["admin-settings"])


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
