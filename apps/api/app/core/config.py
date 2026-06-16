"""应用配置：全部通过环境变量读取（Pydantic Settings）。

字段与根目录 ``.env.example`` 一一对应。敏感值用 ``replace_me`` 占位，
生产环境通过环境变量覆盖。
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER = "replace_me"


class Settings(BaseSettings):
    """应用配置（单例，由 get_settings 缓存）。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- 应用 ----------
    APP_NAME: str = "xiaosu-ai-assistant"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # ---------- 数据库 / 缓存 ----------
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/xiaosu"
    REDIS_URL: str = "redis://localhost:6379/0"

    # ---------- LLM ----------
    LLM_PROVIDER: str = "openai_compatible"
    LLM_BASE_URL: str = "https://api.example.com/v1"
    LLM_API_KEY: str = _PLACEHOLDER
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TIMEOUT_SECONDS: int = 30
    LLM_MAX_RETRIES: int = 2

    # ---------- Embedding ----------
    EMBEDDING_PROVIDER: str = "openai_compatible"
    EMBEDDING_BASE_URL: str = "https://api.example.com/v1"
    EMBEDDING_API_KEY: str = _PLACEHOLDER
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536

    # ---------- RAG ----------
    RAG_TOP_K: int = 5
    RAG_SCORE_THRESHOLD: float = 0.72
    RAG_CHUNK_SIZE: int = 800
    RAG_CHUNK_OVERLAP: int = 120

    # ---------- Agent 工具调用 ----------
    MAX_TOOL_ROUNDS: int = 3
    TOOL_TIMEOUT_SECONDS: int = 10

    # ---------- 存储 / 日志 ----------
    STORAGE_DIR: str = "storage/uploads"
    LOG_DIR: str = "logs"
    UPLOAD_MAX_SIZE_BYTES: int = 10_485_760

    # ---------- 钉钉机器人 ----------
    DINGTALK_APP_KEY: str = _PLACEHOLDER
    DINGTALK_APP_SECRET: str = _PLACEHOLDER
    DINGTALK_ROBOT_CODE: str = _PLACEHOLDER
    DINGTALK_CALLBACK_TOKEN: str = _PLACEHOLDER

    # ---------- IM / 会话 ----------
    IM_DEFAULT_TIMEOUT_SECONDS: int = 45
    CONVERSATION_MAX_TURNS: int = 10

    @property
    def is_dev(self) -> bool:
        """是否为开发环境。"""
        return self.APP_ENV == "development"

    def is_secret_configured(self, value: str) -> bool:
        """判断敏感配置是否已真正配置（非空且非占位）。"""
        return bool(value) and value != _PLACEHOLDER


@lru_cache
def get_settings() -> Settings:
    """返回单例配置（lru_cache 保证全局唯一）。"""
    return Settings()


# 模块级单例，便于各处直接 ``from app.core.config import settings``
settings = get_settings()
