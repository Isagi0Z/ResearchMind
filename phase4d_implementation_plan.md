# Phase 4D — Implementation Plan

**Generated:** 2026-06-16
**Scope:** Phased implementation plan for Phase 4D workstreams
**Target:** Resolve all Critical and High risks, address Medium risks, document Low risks

---

## Workstream Overview

| ID | Name | Priority | Effort | Risk Addressed |
|----|------|----------|--------|----------------|
| D1 | Admin UI | P0 | 2 days | R02 (Critical) |
| D2 | Monitoring Auth Error Handling | P0 | 1 day | R01 (Critical) |
| D3 | Refresh Token Optimization | P1 | 1 day | R04 (High) |
| D4 | Rate Limiter Redis Backend | P1 | 2 days | R05 (High) |
| D5 | Cookie-Based Token Storage (W8) | P1 | 3 days | R03 (High) |
| D6 | Document Upload Endpoint | P2 | 2 days | R06 (Medium) |
| D7 | History Pagination | P2 | 1 day | R07 (Medium) |
| D8 | PostgreSQL Migration Verification | P2 | 1 day | R08 (Medium) |
| D9 | E2E Tests (Playwright) | P2 | 2 days | R09 (Medium) |
| D10 | SQL Push-Down for Documents | P3 | 1 day | R10 (Medium) |
| D11 | CSRF Token Endpoint | P3 | 1 day | R11 (Low) |

**Total estimated effort:** 17 days

---

## Workstream Details

### D1 — Admin UI (P0, 2 days)

**Risks:** R02 (Critical — no admin role management)

**Backend Changes:**
- New route: `backend/api/routes/admin.py`
  - `GET /api/v1/admin/users` — list users with roles (admin-only)
  - `PATCH /api/v1/admin/users/{user_id}/role` — update user role (admin-only)
  - Requires `require_role("admin")`
- Register route in `app.py`

**Frontend Changes:**
- New page: `frontend/app/admin/users/page.tsx`
  - User table (email, role, status, actions)
  - Role dropdown: user / admin
  - Confirm dialog on role change
- New feature component: `frontend/features/admin/user-management.tsx`
- Add admin link to sidebar (`app-shell.tsx`) — only for admin users

**Tests:**
- Backend: test admin routes (RBAC enforcement, user listing, role update)
- Frontend: test user management page renders, role change flow

**Migration:** None needed (role column exists in users table)

---

### D2 — Monitoring Auth Error Handling (P0, 1 day)

**Risks:** R01 (Critical — monitoring broken for non-admin)

**Frontend Changes:**
- `frontend/features/monitoring/monitoring-hooks.ts`:
  - Surface error from `useQuery` to callers
  - Return `{ data, isLoading, error }` instead of just data
- `frontend/features/monitoring/monitoring-dashboard.tsx`:
  - Add error state rendering:
    - 403: "Access Denied — Admin privileges required" with link
    - 401: Redirect to login page
    - Other errors: Generic error message with retry
- `frontend/features/monitoring/metrics-overview.tsx`:
  - Accept error prop, show disabled state on auth failure

**No backend changes needed** — RBAC already works correctly.

**Tests:**
- Frontend: mock 403 response, verify error state renders
- Frontend: mock 401 response, verify redirect

---

### D3 — Refresh Token Optimization (P1, 1 day)

**Risks:** R04 (High — O(n) bcrypt scan on refresh)

**Backend Changes:**
- `backend/db/models/refresh_token.py`:
  - Add column: `token_hash_sha256 = Column(String(64), index=True)`
- `backend/api/routes/auth.py`:
  - On token creation: compute SHA256(raw_token) and store in `token_hash_sha256`
  - On token refresh: look up by SHA256(raw_token) in O(1) instead of iterating all tokens
  - Keep bcrypt hashing for the primary `hashed_token` column (backward compat)
- `backend/api/auth/security.py`:
  - Add `sha256_hash(raw_token)` helper

**Migration:**
- New Alembic migration: add `token_hash_sha256` column (nullable, existing rows can backfill on first refresh)

**Tests:**
- Backend: verify refresh uses SHA256 lookup
- Backend: verify backward compatibility with existing bcrypt tokens

---

### D4 — Rate Limiter Redis Backend (P1, 2 days)

**Risks:** R05 (High — in-memory only, not shared across workers)

**Backend Changes:**
- `backend/api/rate_limiter.py`:
  - Abstract `CounterStore` interface (get/set/delete with TTL)
  - `MemoryCounterStore` (existing dict-based implementation)
  - `RedisCounterStore` (new, using `redis-py` or `aioredis`)
  - `RateLimiter` accepts `CounterStore` via dependency injection
- `backend/api/config.py`:
  - Add `REDIS_URL: Optional[str] = None`
- `backend/api/app.py`:
  - If `REDIS_URL` is set, use `RedisCounterStore`; else fall back to `MemoryCounterStore`

**Tests:**
- Backend: unit test `MemoryCounterStore`
- Backend: unit test `RateLimiter` with mock store
- Backend: integration test with Redis (if available)

---

### D5 — Cookie-Based Token Storage (W8) (P1, 3 days)

**Risks:** R03 (High — localStorage XSS vulnerability)

**Note:** This is the deferred W8 from Phase 4C.

**Backend Changes:**
- `backend/api/routes/auth.py`:
  - Login endpoint: set refresh token as httpOnly secure cookie
  - Refresh endpoint: read refresh token from cookie instead of request body
  - Logout endpoint: clear refresh token cookie
- `backend/api/auth/security.py`:
  - Cookie settings: `HttpOnly=True`, `Secure=True` (prod), `SameSite='Strict'`, `Path='/api/v1/auth'`

**Frontend Changes:**
- `frontend/lib/api-client.ts`:
  - Remove `localStorage` for refresh token
  - Access token can remain in memory (Zustand store) or short-lived cookie
  - Remove `refresh_token` from request body on refresh call (read from cookie instead)
- `frontend/features/auth/auth-store.ts`:
  - Store access token in Zustand state (cleared on page refresh)
  - Check `/api/v1/auth/me` on app load to restore session

**Tests:**
- Backend: verify refresh token is set as cookie
- Frontend: verify token refresh works without localStorage
- Security: verify cookie is httpOnly (not accessible via JavaScript)

---

### D6 — Document Upload Endpoint (P2, 2 days)

**Risks:** R06 (Medium — no document upload)

**Backend Changes:**
- `backend/api/routes/documents.py`:
  - `POST /api/v1/documents/upload` — multipart file upload
    - Accept file + metadata (title, description)
    - Store file content in `documents.content` field
    - Return created document
  - `GET /api/v1/documents/{id}` — retrieve single document by ID
  - Remove or reduce mock data generation (replace with actual DB queries)

**Migration:** None needed (content field exists).

**Tests:**
- Backend: test file upload with various file types
- Backend: test document retrieval

---

### D7 — History Pagination (P2, 1 day)

**Risks:** R07 (Medium — hardcoded limit 50)

**Backend Changes:**
- `backend/api/routes/query.py`:
  - `GET /query/history`: add `skip: int = Query(0, ge=0)` and `limit: int = Query(50, ge=1, le=200)` params
  - Apply to SQL query: `.offset(skip).limit(limit)`
- `backend/api/routes/review.py`:
  - Same change for `GET /reviews/history`
- Return total count header or field: `X-Total-Count` or `{"items": [...], "total": N}`

**Tests:**
- Backend: verify pagination works correctly
- Backend: verify bounds (skip < 0 rejected, limit > 200 capped)

---

### D8 — PostgreSQL Migration Verification (P2, 1 day)

**Risks:** R08 (Medium — untested PostgreSQL path)

**Tasks:**
- Create `docker-compose.yml` or CI job with PostgreSQL service
- Run all Alembic migrations against PostgreSQL
- Run all backend tests with `DATABASE_URL=postgresql+asyncpg://...`
- Fix any dialect-specific compatibility issues:
  - SQLite `BOOLEAN` → PostgreSQL `BOOLEAN` (should be fine)
  - SQLite `UUID` → PostgreSQL `UUID` type
  - SQLite `DATETIME` → PostgreSQL `TIMESTAMP WITH TIME ZONE`
- Document PostgreSQL setup in README

**No code changes expected** — SQLAlchemy + Alembic handles dialect differences.

---

### D9 — E2E Tests (Playwright) (P2, 2 days)

**Risks:** R09 (Medium — no E2E coverage)

**Tasks:**
- Install Playwright: `npm install -D @playwright/test`
- Create `frontend/e2e/` directory
- Critical path tests:
  1. **Login/Register flow**: register user → login → verify redirect to dashboard
  2. **Query execution**: login → submit query → verify results render
  3. **Monitoring access (admin)**: login as admin → navigate to monitoring → verify data renders
  4. **Monitoring access (non-admin)**: login as non-admin → navigate to monitoring → verify "Access Denied" message
  5. **Token refresh**: idle until access token expires → verify auto-refresh works
  6. **Logout**: login → logout → verify redirect to login
- CI integration: add `npm run test:e2e` script

---

### D10 — SQL Push-Down for Documents (P3, 1 day)

**Risks:** R10 (Medium — in-memory filter/sort)

**Backend Changes:**
- `backend/api/routes/documents.py`:
  - Replace `filter()` and `sorted()` in Python with SQL WHERE/ORDER BY
  - `searchQuery` → `WHERE title LIKE :q OR content LIKE :q`
  - `sortBy`/`sortDirection` → `ORDER BY :col :dir`
  - Add SQLAlchemy full-text search or `ILIKE` for PostgreSQL compatibility

**Low priority** — acceptable for current scale.

---

### D11 — CSRF Token Endpoint (P3, 1 day)

**Risks:** R11 (Low — no CSRF protection for future cookie auth)

**Backend Changes:**
- `GET /api/v1/auth/csrf` — generate and return CSRF token
- Validate CSRF token on state-changing requests (POST/PUT/PATCH/DELETE)
- Only needed if cookie-based auth (D5) is implemented

**Low priority** — blocked on D5 decision.

---

## Implementation Sequence

```
Phase 4D = 17 days total
─────────────────────────────────────────────────────
Week 1 (Days 1-5):
  D1 Admin UI        ── 2 days ──┐
  D2 Monitoring Auth ── 1 day ───┤
  D3 Token Opt       ── 1 day ───┤
  D4 Redis Backend   ── 2 days ──┘ (parallel with D1)
                                   Total: 5 days

Week 2 (Days 6-11):
  D5 Cookie Tokens   ── 3 days ──┐
  D6 Upload Endpoint ── 2 days ──┤
  D7 Pagination      ── 1 day ───┤
                                   Total: 6 days

Week 3 (Days 12-17):
  D8 PostgreSQL      ── 1 day ──┐
  D9 E2E Tests       ── 2 days ──┤
  D10 SQL Push-Down  ── 1 day ───┤
  D11 CSRF Token     ── 1 day ───┤
  Buffer/QA          ── 1 day ───┘
                                   Total: 6 days
```

## Success Criteria

1. **Admin UI functional:** Admin can list users, assign/revoke admin roles via UI
2. **Monitoring dashboard handles auth errors:** Non-admin users see "Access Denied", admin users see data
3. **Token refresh O(1):** SHA256 lookup replaces O(n) bcrypt scan
4. **Rate limiter works across workers:** Optional Redis backend for multi-process deployments
5. **Tokens stored securely:** httpOnly cookies replace localStorage for refresh tokens
6. **Documents can be uploaded:** File upload endpoint functional
7. **History is paginated:** `skip`/`limit` parameters on history endpoints
8. **PostgreSQL verified:** All tests pass against PostgreSQL
9. **E2E tests passing:** Critical paths covered with Playwright
10. **All existing tests still pass:** Phase 4B, 4C, and new Phase 4D tests
11. **Determinism maintained:** Zero new violations in M1–M6 engine paths
12. **Frontend build succeeds:** `npm run build` produces 12+ routes
