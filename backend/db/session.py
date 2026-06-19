import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Primary source: backend config (reads .env + env vars), fallback to os.environ
from backend.api.config import settings as _config

DATABASE_URL = _config.DATABASE_URL or os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

_engine_kwargs = {
    "echo": False,
    "future": True,
}

# Apply connection pooling for PostgreSQL
if "postgresql" in DATABASE_URL:
    _engine_kwargs.update({
        "pool_size": 5,
        "max_overflow": 10,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    })

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

async def get_db():
    async with async_session_factory() as session:
        yield session
