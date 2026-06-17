# Repository State Audit

**Date:** 2026-06-16
**Branch:** `module5-development`
**Auditor:** Automated

---

## 1. Git State

| Property | Value |
|----------|-------|
| Current branch | `module5-development` |
| Ahead of remote | 3 commits |
| Uncommitted changes | 16 modified files, 50+ untracked files |
| Local branches | `implement-dashboard-corpus-manager`, `main`, `module4-development`, `module5-development` |
| Remote branches | `origin/main`, `origin/module4-development`, `origin/module5-development` |
| Worktrees | 1: `D:/RM` at `module5-development` (the primary) |
| Latest commit | `e09f7cf` — "chore: complete phase 3b implementation" |

## 2. Uncommitted Changes

### Modified files (16):
```
backend/api/app.py                  — routes, middleware, CORS config
backend/api/auth/security.py        — JWT + bcrypt implementation
backend/api/config.py               — Settings class with SECRET_KEY, CORS, etc.
backend/api/dependencies.py         — DI for auth, query engine, review orchestrator
backend/api/middleware.py           — RequestContext, SecurityHeaders, RateLimit
backend/api/routes/auth.py          — /register, /login, /refresh, /logout
backend/api/routes/query.py         — /parse, /plan, /route, /answer
backend/api/routes/review.py        — /generate, /validate
frontend/.env.example               — updated env template
frontend/components/layout/app-shell.tsx — sidebar, navigation, theme toggle
frontend/lib/api-client.ts          — fetch wrapper with Bearer auth, 401 refresh
frontend/tests/corpus/filters-panel.test.tsx
frontend/tests/query/query-metrics.test.tsx
frontend/tests/services/corpus.test.ts — DELETED (143 lines)
frontend/tests/services/dashboard.test.ts — DELETED (71 lines)
pyproject.toml                      — project config
```

### Untracked directories/files (key):
```
.env, test.db, test_db.py, test_db2.py
migrations/                         — Alembic migrations (1 version + env.py)
backend/db/                         — SQLAlchemy models + session + repositories
backend/.env.example
frontend/app/login/                 — Login page
frontend/app/register/              — Register page
audit/phase4a_*.md                  — 18 Phase 4A audit documents
audit/phase4b_*.md                  — 7 Phase 4B planning documents
audit/module8_phase3b_*.md          — 4 Phase 3B audit documents
audit/module9_*.md                  — 10 Phase 9 planning documents
```

## 3. Repository Structure

### Backend (`backend/`)
```
backend/
├── api/
│   ├── app.py                      — FastAPI app factory
│   ├── config.py                   — Pydantic Settings (SECRET_KEY, CORS, etc.)
│   ├── dependencies.py             — DI: auth, query engine, review orchestrator, corpus
│   ├── middleware.py                — RequestContext, SecurityHeaders, RequestSizeLimit, RateLimit
│   ├── exceptions.py               — Global exception handlers
│   ├── mock_data.py                — Mock documents for testing
│   ├── auth/
│   │   └── security.py             — JWT create/decode, bcrypt hash/verify
│   ├── routes/                     — 8 route modules (system, auth, query, review, graph, documents, dashboard, monitoring)
│   ├── schemas/                    — 8 schema modules (auth, common, dashboard, documents, graph, monitoring, query, review)
│   └── services/                   — 7 service stubs (auth_service is a placeholder class)
├── db/
│   ├── base.py                     — SQLAlchemy DeclarativeBase
│   ├── session.py                  — Async engine + session factory
│   ├── models/                     — 5 models (User, Query, Review, Document, RefreshToken)
│   └── repositories/               — (empty directory)
```

### Frontend (`frontend/`)
```
frontend/
├── app/                            — Next.js App Router (dashboard, corpus, graph, query, reviews, login, register)
├── components/                     — UI components (shadcn/ui-style) + layout (app-shell)
├── lib/
│   └── api-client.ts               — Fetch wrapper with Bearer auth, 401 auto-refresh, token management
├── stores/
│   └── ui-store.ts                 — Zustand store (sidebarCollapsed, mobileDrawerOpen)
├── providers/                      — Theme + TanStack Query providers
├── tests/                          — 256 tests across 22 files
└── services/                       — Frontend service layer
```

### Migrations (`migrations/`)
- Alembic configuration (`alembic.ini`, `env.py`)
- 1 migration version: `02cc7a4980ec_init_phase_4b_generic.py` — creates users, documents, queries, refresh_tokens, reviews tables

### Audit Documents (`audit/`)
- 18 Phase 4A documents (security audit, determinism verification, remediation)
- 7 Phase 4B documents (architecture plan, auth design, database design, etc.)
- 4 Phase 3B documents (determinism audit, runtime validation, etc.)
- 10 Phase 9 documents (deployment, scalability, security, etc.)

## 4. Runtime Versions

| Component | Version |
|-----------|---------|
| Python | 3.9.13 |
| Node.js | 24.13.1 |
| npm | 11.8.0 |
| FastAPI | 0.128.8 |
| SQLAlchemy | 2.0.50 |
| Alembic | 1.16.5 |
| Pydantic | 2.12.5 |
| Next.js | 16.2.9 (frontend) |

## 5. Environment Configuration

- `.env`: `DATABASE_URL=sqlite+aiosqlite:///./test.db`, `SECRET_KEY=testing_secret_key`
- `backend/.env.example`: `SECRET_KEY=super_secret_temporary_key_change_in_prod`, `CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000`
- `frontend/.env.example`: Contains `NEXT_PUBLIC_API_URL` template
- `test.db` exists (SQLite database file)

## 6. Key Discrepancies Found

1. **Python 3.9 incompatibility**: `config.py` uses `str | List[str]` syntax which requires Python 3.10+. Current runtime is Python 3.9.13. This blocks `config.py` from loading and all backend tests/application from starting.

2. **Frontend token storage**: Architecture specifies httpOnly cookies for JWT tokens. Implementation uses `localStorage`. This is an XSS vulnerability.

3. **Missing `/auth/me` endpoint**: Frontend auth provider calls `GET /auth/me` to validate sessions. This route does not exist in the backend.

4. **Uncommitted implementation**: All Phase 4B implementation (auth routes, DB models, migrations, login/register pages) exists only as uncommitted/unstaged changes. These are NOT in the git history.

5. **Staged vs untracked dichotomy**: The core implementation files (auth routes, models, middleware) are modified but NOT staged. The DB layer, migrations, and auth pages are entirely untracked. No commit captures Phase 4B as a coherent unit.

6. **Detached lockfile warning**: Next.js build warns about multiple lockfiles (workspace root has `package-lock.json`, frontend has another).

7. **`auth_service.py` is a stub**: `class AuthService: pass` — the service layer is not implemented despite auth routes being functional.
