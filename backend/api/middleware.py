import binascii
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
        # Respect externally supplied deterministic request ID, otherwise generate one
        req_id = request.headers.get("X-Request-ID") or generate_request_id(request.method, request.url.path)
        
        request.state.request_id = req_id
        
        # Log request start
        logger.info(f"Request started: {request.method} {request.url.path} (ID: {req_id})")
        
        try:
            response = await call_next(request)
        except Exception as e:
            # We catch here primarily to log, the exception handler will format it
            logger.error(f"Request failed: {request.method} {request.url.path} (ID: {req_id})")
            raise e
            
        response.headers["X-Request-ID"] = req_id
        
        logger.info(f"Request completed: {request.method} {request.url.path} - Status: {response.status_code} (ID: {req_id})")
        
        return response
