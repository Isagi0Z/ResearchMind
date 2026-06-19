import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

_sync_url = DATABASE_URL
if _sync_url.startswith("sqlite+aiosqlite"):
    _sync_url = _sync_url.replace("+aiosqlite", "")
elif _sync_url.startswith("postgresql+asyncpg"):
    _sync_url = _sync_url.replace("+asyncpg", "+psycopg2")

_engine = create_engine(_sync_url, echo=False, future=True)
_Session = sessionmaker(bind=_engine)


def get_sync_db():
    db = _Session()
    try:
        return db
    finally:
        db.close()
