from fastapi import APIRouter
from backend.api.config import settings
from sqlalchemy import text, inspect
from backend.db.session import async_session_factory

router = APIRouter()

ALEMBIC_HEAD = "3a1b2c3d4e5f"

@router.get("/health")
async def health_check():
    return {"status": "healthy"}

@router.get("/health/live")
async def health_live():
    return {"status": "alive"}

@router.get("/health/ready")
async def health_ready():
    checks = {"database": False, "redis": False, "migration": False}
    all_ok = True

    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        all_ok = False

    if settings.REDIS_URL:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
            await r.ping()
            await r.aclose()
            checks["redis"] = True
        except Exception:
            all_ok = False
    else:
        checks["redis"] = None

    try:
        async with async_session_factory() as session:
            result = await session.execute(text("SELECT version_num FROM alembic_version"))
            row = result.scalar_one_or_none()
            if row == ALEMBIC_HEAD:
                checks["migration"] = True
            else:
                checks["migration"] = False
                all_ok = False
    except Exception:
        checks["migration"] = None
        all_ok = False

    return {"status": "ready" if all_ok else "degraded", "checks": checks}

@router.get("/version")
async def get_version():
    return {"version": settings.VERSION}
