from typing import Optional
from fastapi import Response
from backend.api.config import settings

ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"


def _cookie_kwargs() -> dict:
    return {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "domain": settings.AUTH_COOKIE_DOMAIN or None,
    }


def set_auth_cookies(response: Optional[Response], access_token: str, refresh_token: str) -> None:
    if response is None:
        return
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        **_cookie_kwargs(),
    )
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
        **_cookie_kwargs(),
    )


def clear_auth_cookies(response: Optional[Response]) -> None:
    if response is None:
        return
    kwargs = _cookie_kwargs()
    response.delete_cookie(key=ACCESS_TOKEN_COOKIE, path="/", **kwargs)
    response.delete_cookie(key=REFRESH_TOKEN_COOKIE, path="/api/v1/auth", **kwargs)
