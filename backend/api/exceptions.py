from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

class ResearchMindException(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code

class AuthException(ResearchMindException):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(code="AUTH_ERROR", message=message, status_code=401)

def _get_req_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")

def create_error_envelope(code: str, message: str, req_id: str) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": req_id
        }
    }

async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    req_id = _get_req_id(request)
    # Generic HTTP errors from FastAPI itself (like 404, 405)
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_envelope("HTTP_ERROR", str(exc.detail), req_id)
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    req_id = _get_req_id(request)
    return JSONResponse(
        status_code=422,
        content=create_error_envelope("VALIDATION_ERROR", "Request validation failed", req_id)
    )

async def researchmind_exception_handler(request: Request, exc: ResearchMindException) -> JSONResponse:
    req_id = _get_req_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_envelope(exc.code, exc.message, req_id)
    )

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    req_id = _get_req_id(request)
    # Unhandled server errors
    return JSONResponse(
        status_code=500,
        content=create_error_envelope("INTERNAL_ERROR", "An unexpected internal error occurred", req_id)
    )
