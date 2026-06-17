from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.config import settings
from backend.api.middleware import RequestContextMiddleware
from backend.api.exceptions import (
    ResearchMindException,
    global_exception_handler,
    researchmind_exception_handler,
    validation_exception_handler,
    custom_http_exception_handler
)

from backend.api.routes import (
    system,
    auth,
    query,
    review,
    graph,
    documents,
    dashboard,
    monitoring
)

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc"
    )

    from fastapi.middleware.cors import CORSMiddleware
    from backend.api.middleware import (
        RequestContextMiddleware,
        SecurityHeadersMiddleware,
        RequestSizeLimitMiddleware,
        RateLimitMiddleware
    )

    # Note: Middlewares are executed in reverse order of how they are added.
    # The last one added is the outermost wrapper.
    
    app.add_middleware(RequestContextMiddleware)
    
    # Optional limits
    rate_limit_store = None
    if settings.REDIS_URL:
        try:
            from backend.api.rate_limiter import RedisCounterStore
            rate_limit_store = RedisCounterStore(settings.REDIS_URL)
        except ImportError:
            pass
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=settings.RATE_LIMIT_REQUESTS,
        window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        store=rate_limit_store
    )
    app.add_middleware(RequestSizeLimitMiddleware, max_upload_size=5_000_000)
    
    app.add_middleware(SecurityHeadersMiddleware)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception Handlers
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(ResearchMindException, researchmind_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, custom_http_exception_handler)

    # Routes
    app.include_router(system.router, prefix=settings.API_V1_STR, tags=["System"])
    app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
    app.include_router(query.router, prefix=f"{settings.API_V1_STR}/query", tags=["Query Engine"])
    app.include_router(review.router, prefix=f"{settings.API_V1_STR}/reviews", tags=["Synthesis Engine"])
    app.include_router(graph.router, prefix=f"{settings.API_V1_STR}/graph", tags=["Corpus Graph"])
    app.include_router(documents.router, prefix=f"{settings.API_V1_STR}/documents", tags=["Documents"])
    app.include_router(dashboard.router, prefix=f"{settings.API_V1_STR}/dashboard", tags=["Dashboard"])
    app.include_router(monitoring.router, prefix=f"{settings.API_V1_STR}/monitoring", tags=["Monitoring"])

    return app

app = create_app()
