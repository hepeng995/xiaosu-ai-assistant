"""健康检查路由。"""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """健康检查端点：``GET /health``。

    返回 ``{"status": "ok", "service": "xiaosu-api"}``，
    用于 Docker 健康检查与面试现场快速验证。
    """
    return {"status": "ok", "service": "xiaosu-api"}
