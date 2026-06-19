# Phase 6 — Pre-Implementation Dependency Analysis

**Date:** 2026-06-19  
**Type:** Static analysis of import graph, circular dependency risk, and external coupling

---

## 1. Package Dependency Graph

```
backend.api.app
  ├── backend.api.config          (settings, env_file=_env_path)
  ├── backend.api.middleware      (RequestContext, SecurityHeaders, etc.)
  ├── backend.api.exceptions      (ResearchMindException, handlers)
  ├── backend.api.routes.*        (10 route modules)
  │
backend.api.routes.auth
  ├── backend.db.session          (get_db)                    → session.py
  ├── backend.db.models.user      (User ORM)
  ├── backend.db.models.refresh_token  (RefreshToken ORM)
  ├── backend.api.auth.security   (JWT create/decode, hash)
  ├── backend.api.auth.cookies    (set/clear cookies)          → [NEW 5E]
  ├── backend.api.dependencies    (get_current_user)
  └── backend.api.config          (settings)

backend.api.dependencies
  ├── backend.api.auth.security   (decode_access_token, JWT_ISSUER)
  ├── backend.api.auth.cookies    (ACCESS_TOKEN_COOKIE)       → [NEW 5E]
  ├── backend.db.session          (get_db)
  ├── backend.db.models.user      (User ORM)
  ├── backend.api.exceptions      (AuthException)
  ├── backend.api.mock_data       (generate_mock_documents)
  ├── researchmind.query.*        (Parser, Planner, Router, Engine)
  ├── researchmind.synthesis.*    (ReviewOrchestrator, TraceabilityVerifier)
  └── researchmind.storage.corpus (CorpusManager)

backend.api.config
  ├── os, sys
  ├── pydantic (BaseSettings, field_validator, SettingsConfigDict)
  └── .env (via _env_path resolver)

backend.db.session
  ├── os
  ├── sqlalchemy.ext.asyncio
  └── backend.api.config (settings as _config)                → [5E change — dependency INVERTED]

backend.api.middleware
  ├── fastapi, starlette (Request, Response, BaseHTTPMiddleware)
  ├── logging
  ├── backend.api.rate_limiter    (RateLimiter, MemoryCounterStore)
  └── time, binascii
```

## 2. Circular Dependency Risk Assessment

### Risk 1: `backend.db.session` → `backend.api.config`

**Status:** ⚠️ MONITORED

**Introduced in Phase 5E:** `session.py` now imports `settings as _config` from `backend.api.config`:

```python
from backend.api.config import settings as _config
DATABASE_URL = _config.DATABASE_URL or os.environ.get(...)
```

**Chain:**
- `db/session.py` ← `api/config.py` ← `pydantic, os, sys` (leaf — no further deps)

**Risk:** LOW. `backend.api.config` imports only stdlib (`os`, `sys`) and pydantic libraries — it does NOT import anything from `backend.db` or `backend.api`. No cycle exists.

**Mitigation:** If any future change causes `config.py` to import from `session.py`, this will break at import time. Keep `config.py` as a leaf module.

### Risk 2: Middleware ↔ App

**Chain:**
- `app.py` → `middleware.py` (imports classes)
- `middleware.py` → NO imports from `app.py`

**Risk:** NONE. One-way dependency.

### Risk 3: Routes ↔ Dependencies

**Chain:**
- `routes/auth.py` → `dependencies.py` (get_current_user)
- `dependencies.py` → NO imports from specific route modules

**Risk:** NONE. Dependencies module is a hub, not a cycle.

## 3. External Library Coupling

| Library | Version | Used By | Criticality | PG Compat |
|---------|---------|---------|-------------|-----------|
| fastapi | ≥0.110.0 | All routes, middleware, app | HIGH ✅ | N/A |
| pydantic | ≥2.5 | config, schemas, request/response models | HIGH ✅ | N/A |
| pydantic-settings | ≥2.2.0 | config.py Settings | HIGH ✅ | N/A |
| sqlalchemy[asyncio] | ≥2.0.0 | All DB models, session, services | HIGH ✅ | ✅ Uses asyncpg driver |
| python-jose[cryptography] | ≥3.3.0 | auth/security.py (JWT) | HIGH ✅ | N/A |
| passlib[bcrypt] | ≥1.7.4 | auth/security.py (password hashing) | HIGH ✅ | N/A |
| alembic | ≥1.13.0 | Migrations | HIGH ✅ | ✅ `compare_type=True` for PG |
| asyncpg | ≥0.29.0 | PG driver (listed in deps) | HIGH ⚠️ | ✅ Required for PG |
| aiosqlite | (transitive) | SQLite driver | LOW | Dev only |
| httpx | ≥0.27 | TestClient transport | LOW | N/A |
| google-genai | ≥1.0 | LLM integration | MEDIUM | N/A |

## 4. Configuration Dependency Graph

```
.env
 ├── DATABASE_URL           → backend.db.session
 ├── SECRET_KEY             → backend.api.auth.security → JWT
 ├── ENVIRONMENT            → backend.api.config → validate_environment()
 ├── CORS_ORIGINS           → backend.api.config → backend.api.app (CORSMiddleware)
 ├── AUTH_COOKIE_SECURE     → backend.api.auth.cookies (Secure flag)
 ├── AUTH_COOKIE_SAMESITE   → backend.api.auth.cookies (SameSite)
 ├── REFRESH_TOKEN_EXPIRE_DAYS → backend.api.auth.security → JWT
 ├── REDIS_URL              → backend.api.app (RateLimitMiddleware Redis)
 └── NEXT_PUBLIC_API_URL    → frontend/lib/api-client.ts
```

## 5. Test Dependencies

```
conftest.py (session scoped)
  ├── Creates all tables via Base.metadata.create_all
  ├── Drops all tables at session end
  └── No test-level isolation, no transaction rollback

test_*.py
  └── Uses `client = TestClient(app)` (function-scoped fixture)
  
Impact:
  - Data persists between test classes
  - Tests must use unique usernames/emails to avoid collisions
  - 4 pre-existing test_stubs.py failures (event loop issue, unrelated)
```

## 6. Module Boundaries (for Phase 6)

| Layer | Entry Points | Phase 6 Impact |
|-------|-------------|----------------|
| Deterministic Engines | `src/researchmind/` | **Zero-touch zone** — must not be modified |
| API Routes | `backend/api/routes/` | Safe to add/modify route handlers |
| Services | `backend/api/services/` | Safe to add service classes |
| DB Models | `backend/db/models/` | Safe to add models (requires migration) |
| Auth | `backend/api/auth/` | Safe to extend auth flows |
| Middleware | `backend/api/middleware.py` | Safe to add middleware in correct order |
| Config | `backend/api/config.py` | Safe to add validated settings |
| Frontend | `frontend/` | Independent of backend module structure |
