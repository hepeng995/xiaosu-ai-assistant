"""数据库会话管理（SQLAlchemy 2.x async + psycopg 3）。"""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# DATABASE_URL 为 postgresql+psycopg://，psycopg 3 原生支持 async
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.is_dev,
    pool_pre_ping=True,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：提供一个异步数据库会话，异常时自动回滚。"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def check_db_connection() -> bool:
    """启动时轻量 ping，返回数据库是否连通（不阻断启动）。"""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
