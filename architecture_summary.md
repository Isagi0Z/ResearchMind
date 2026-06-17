# Architecture Summary

**Date:** 2026-06-16
**Branch:** `module5-development`

---

## 1. Overall Architecture

ResearchMind is a deterministic research synthesis platform with:

- **Backend**: Python FastAPI application with PostgreSQL (via SQLAlchemy async) and in-memory deterministic processing engines (M1–M6)
- **Frontend**: Next.js 14+ (App Router) with TypeScript, Tailwind CSS, TanStack Query, Zustand
- **Database**: PostgreSQL with SQLAlchemy async ORM + Alembic migrations

## 2. Backend Architecture

### API Layer (`backend/api/`)
```
FastAPI App
├── app.py                    — App factory, middleware stack, route registration
├── config.py                 — Pydantic Settings (SECRET_KEY, CORS, DB URL)
├── dependencies.py           — DI: auth, query/review engines, corpus manager
├── middleware.py              — RequestContextMiddleware (CRC32 request IDs)
│                               SecurityHeadersMiddleware
│                               RequestSizeLimitMiddleware
│                               RateLimitMiddleware (deferred)
├── exceptions.py             — Global, domain, validation, HTTP exception handlers
├── auth/security.py          — JWT creation/verification (HS256), bcrypt hashing
├── routes/                   — 8 route modules
│   ├── system.py             — /health, /version
│   ├── auth.py               — /register, /login, /refresh, /logout
│   ├── query.py              — /parse, /plan, /route, /answer
│   ├── review.py             — /generate, /validate
│   ├── graph.py              — (minimal)
│   ├── documents.py          — GET list, GET by id (paginated)
│   ├── dashboard.py          — /summary, /recent, /status (uses mock data)
│   └── monitoring.py         — (minimal)
└── schemas/                  — Pydantic request/response schemas
```

### Database Layer (`backend/db/`)
```
SQLAlchemy Async Models
├── User                      — id, username, email, password_hash, role, is_active, timestamps
├── RefreshToken              — id, user_id (FK), hashed_token, expires_at, is_revoked, created_at
├── Document                  — id, user_id (FK), fingerprint, title, metadata, created_at
├── Query                     — id, user_id (FK), raw_query, query_type, result, created_at
└── Review                    — id, user_id (FK), title, review_result, metadata, created_at
```

### Deterministic Engine Layer (`src/researchmind/`) — from M1–M6
- `researchmind.query.*` — QueryParser, QueryPlanner, StepDispatcher, QueryEngine
- `researchmind.synthesis.*` — ReviewOrchestrator, TraceabilityVerifier
- `researchmind.storage.corpus` — CorpusManager, InMemoryDocumentStore

## 3. Frontend Architecture

### Next.js App Router (`frontend/app/`)
```
Routes
├── /                         — Landing page (static)
├── /login                    — Login form (OAuth2 form-urlencoded)
├── /register                 — Registration form
├── /dashboard                — Dashboard (stats, recent items, system status)
├── /corpus                   — Corpus manager (virtualized table, search, filters)
├── /corpus/[id]              — Corpus detail
├── /graph                    — Graph explorer
├── /query                    — Query interface
├── /reviews                  — Review list/generator
└── /monitoring               — System monitoring
```

### State Management
| Category | Tool | Details |
|----------|------|---------|
| UI State | Zustand | sidebarCollapsed, mobileDrawerOpen |
| Server State | TanStack Query | API data fetching with caching |
| Auth State | localStorage tokens | access_token + refresh_token in localStorage |

### Key Components
- **app-shell.tsx**: Sidebar navigation + top bar with theme toggle, user info, logout
- **api-client.ts**: Fetch wrapper with Bearer auth, 401 auto-refresh with subscriber pattern, timeout, error sanitization

### Token Flow (current implementation)
```
Login → POST /auth/login (form-urlencoded)
       ← { access_token, refresh_token, token_type }
       → localStorage.setItem('access_token', ...)
       → localStorage.setItem('refresh_token', ...)

Every API call:
  → Read access_token from localStorage
  → Set Authorization: Bearer <token> header
  → If 401: POST /auth/refresh with refresh_token
    → Success: update tokens in localStorage, retry request
    → Failure: clear tokens, redirect to /login
```

## 4. Authentication Architecture

### Backend
- **Registration**: POST `/api/v1/auth/register` — creates User with bcrypt-hashed password
- **Login**: POST `/api/v1/auth/login` — OAuth2 form, returns JWT access + refresh tokens
- **Refresh**: POST `/api/v1/auth/refresh` — validates refresh token, rotates (revokes old, issues new pair)
- **Logout**: POST `/api/v1/auth/logout` — revokes the specific refresh token
- **Missing**: `GET /api/v1/auth/me` — no endpoint to validate session and return user profile

### Frontend
- Login page at `/login` — form-urlencoded POST to `/auth/login`, stores tokens in localStorage
- Register page at `/register` — JSON POST to `/auth/register`
- API client handles 401 → refresh → retry transparently
- On refresh failure: clears tokens, redirects to `/login`

## 5. Persistence Architecture

- **Relational**: PostgreSQL via SQLAlchemy async (models for User, Document, Query, Review, RefreshToken)
- **Deterministic engine state**: In-memory (InMemoryDocumentStore, DummyGraph)
- **Migrations**: Alembic with 1 migration version (initial schema creation)
- **Current DB**: SQLite (`test.db`) for development — `DATABASE_URL=sqlite+aiosqlite:///./test.db`

## 6. Known Architectural Issues

1. **localStorage token storage**: Security architecture specifies httpOnly cookies. Current implementation uses localStorage, vulnerable to XSS.
2. **Missing `/auth/me`**: Frontend's `AuthProvider` calls `GET /auth/me` on mount but this endpoint does not exist on the backend.
3. **Python 3.9 syntax issue**: `config.py` uses `str | List[str]` which is Python 3.10+ only.
4. **`auth_service.py` is a stub**: Service layer not implemented despite functional routes.
5. **Rate limiting deferred**: RateLimitMiddleware passes through without enforcement.
6. **Mock data dependency**: Dashboard, graph, and document routes fall back to mock data.
7. **Uncommitted state**: All Phase 4B work is uncommitted — implementation is not in git history.
