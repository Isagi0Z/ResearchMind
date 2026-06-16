# Phase 4B Database Alignment Report

**Date:** 2026-06-16

## Decision

**SQLite for local development; PostgreSQL for production.**

The `.env` file uses `sqlite+aiosqlite:///./test.db` which is appropriate for development. PostgreSQL is intended for production (via `DATABASE_URL` environment variable override).

## Changes Made

### `backend/db/session.py`
- Changed default from `postgresql+asyncpg://postgres:postgres@localhost:5432/postgres` to `sqlite+aiosqlite:///./test.db`
- Removed `pool_size=5, max_overflow=10` (these are PostgreSQL-specific pool settings; SQLite doesn't support them)
- Added comment documenting how to override for PostgreSQL (production)

### `migrations/env.py`
- Changed default from `postgresql+asyncpg://...` to `sqlite+aiosqlite:///./test.db`
- This ensures `alembic upgrade head` works out of the box without a PostgreSQL server

### `backend/db/__init__.py`
- Created (empty) to make `backend.db` a proper Python package

## Database Configuration Matrix

| Environment | Database | Driver | Config Source |
|-------------|----------|--------|---------------|
| **Runtime (dev)** | SQLite (test.db) | aiosqlite | `.env` → `sqlite+aiosqlite:///./test.db` |
| **Migrations (dev)** | SQLite (test.db) | aiosqlite | `.env` → `alembic upgrade head` reads from `DATABASE_URL` |
| **Tests** | SQLite (in-memory via test.db) | aiosqlite | `.env` + `conftest.py` creates tables via `Base.metadata.create_all` |
| **Production** | PostgreSQL | asyncpg | `DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname` env var override |

## Migration Verification

```bash
$ alembic upgrade head
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 02cc7a4980ec, init phase 4b generic
```

Migration created 5 tables: `users`, `documents`, `queries`, `refresh_tokens`, `reviews`.

## How to Switch to PostgreSQL

```bash
# Set environment variable to override .env
set DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/researchmind
# Run migration against PostgreSQL
alembic upgrade head
# Start application
uvicorn backend.api.app:app
```

## Conclusion

Database configuration is internally consistent. SQLite is used for development/testing, PostgreSQL for production. Both session.py and migrations/env.py now default to the same development URL.
