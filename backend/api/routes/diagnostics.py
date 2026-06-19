"""
Diagnostics endpoint for observability and health introspection.
Returns configuration metadata, environment info, and runtime state.
"""
import os
import sys
import time
from fastapi import APIRouter, Request
from backend.api.config import settings

router = APIRouter()


@router.get("/diagnostics")
async def get_diagnostics(request: Request):
    return {
        "application": {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
        },
        "runtime": {
            "python_version": sys.version,
            "platform": sys.platform,
            "pid": os.getpid(),
        },
        "request": {
            "id": getattr(request.state, "request_id", None),
            "method": request.method,
            "path": str(request.url.path),
            "client_host": request.client.host if request.client else None,
        },
        "config": {
            "cors_origins": settings.cors_origins_list,
            "rate_limit_requests": settings.RATE_LIMIT_REQUESTS,
            "rate_limit_window_seconds": settings.RATE_LIMIT_WINDOW_SECONDS,
            "access_token_expire_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            "refresh_token_expire_days": settings.REFRESH_TOKEN_EXPIRE_DAYS,
            "cookie_secure": settings.cookie_secure,
            "cookie_samesite": settings.AUTH_COOKIE_SAMESITE,
            "redis_configured": bool(settings.REDIS_URL),
        },
        "uptime_seconds": time.monotonic(),
    }
