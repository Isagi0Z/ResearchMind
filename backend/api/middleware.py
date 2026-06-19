import binascii
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger("researchmind.api")

def generate_request_id(method: str, path: str) -> str:
    """Generate a deterministic CRC32 request ID (No UUIDs allowed)"""
    data = f"{method}:{path}".encode('utf-8')
    crc = binascii.crc32(data) & 0xFFFFFFFF
    return f"req-{crc:08x}"

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        req_id = request.headers.get("X-Request-ID") or generate_request_id(request.method, request.url.path)
        request.state.request_id = req_id

        start = time.monotonic()
        logger.info(f"Request started: {request.method} {request.url.path} (ID: {req_id})")

        try:
            response = await call_next(request)
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            logger.error(f"Request failed after {elapsed:.0f}ms: {request.method} {request.url.path} (ID: {req_id})")
            raise e

        elapsed = (time.monotonic() - start) * 1000
        response.headers["X-Response-Time-Ms"] = f"{elapsed:.0f}"
        logger.info(f"Request completed in {elapsed:.0f}ms: {request.method} {request.url.path} - Status: {response.status_code} (ID: {req_id})")

        return response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["X-Request-ID"] = getattr(request.state, "request_id", "unknown")
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # Content-Security-Policy: restrict to same-origin by default
        if request.url.scheme == "https":
            response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_upload_size: int = 5_000_000):
        super().__init__(app)
        self.max_upload_size = max_upload_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.max_upload_size:
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=413, content={"detail": "Payload Too Large"})
        return await call_next(request)

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 1000, window_seconds: int = 60, store=None):
        super().__init__(app)
        from backend.api.rate_limiter import RateLimiter, MemoryCounterStore
        self.limiter = RateLimiter(max_requests, window_seconds, store=store or MemoryCounterStore())

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")
        key = forwarded or client_ip

        if not self.limiter.is_allowed(key):
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."}
            )

        return await call_next(request)
