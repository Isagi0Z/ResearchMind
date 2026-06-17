# Phase 4D — Risk Assessment Report

**Generated:** 2026-06-16
**Scope:** Ranked risk register for Phase 4D implementation, with mitigations

---

## Risk Register (Ranked)

### 🔴 CRITICAL

#### R01 — Monitoring Dashboard Broken for Non-Admin Users
- **ID:** R01
- **Category:** Functionality
- **Probability:** High
- **Impact:** Critical
- **Affected:** All non-admin users (100% of new users)
- **Description:** Monitoring frontend (`monitoring-hooks.ts`, `monitoring-dashboard.tsx`) calls `/api/v1/monitoring/metrics` and sends Bearer token via `apiClient.get()`. If the user is not admin, backend returns 403. The frontend `useMonitoringData` hook (React Query `useQuery`) catches the error but **never renders it** — the monitoring dashboard shows an empty/loading state indefinitely.
- **Root Cause:** Phase 4C W4 (RBAC) applied `require_role("admin")` to monitoring routes (per R06/R07) but frontend monitoring was not updated to handle 403 responses.
- **Trigger:** Any non-admin user navigates to `/monitoring`.
- **Mitigation (Phase 4D):** Add error state rendering to `MonitoringDashboard` that shows "Access Denied — Admin privileges required" when 403 is received. Redirect to login on 401.

#### R02 — No Admin Role Management UI
- **ID:** R02
- **Category:** Administration
- **Probability:** High
- **Impact:** Critical
- **Affected:** System administrators
- **Description:** There is no UI to assign or revoke admin roles. The only way to make a user admin is via raw SQL or the test helper `_make_admin`. Phase 4C added RBAC but provided no admin management interface.
- **Mitigation (Phase 4D):** Create an admin management page (route: `/admin/users`) with user list, role dropdown, and assign/revoke admin action. Add backend endpoint `PATCH /api/v1/admin/users/{id}/role`.

---

### 🟠 HIGH

#### R03 — Token Storage in localStorage (W8 Carryover)
- **ID:** R03
- **Category:** Security
- **Probability:** Medium
- **Impact:** High
- **Affected:** All authenticated users
- **Description:** Access and refresh tokens stored in `localStorage` (W8 deferred from Phase 4C). Any XSS vulnerability can exfiltrate tokens. `localStorage` is accessible to any JavaScript on the same origin.
- **Mitigation (Phase 4D):** Migrate to httpOnly secure cookies for refresh tokens. Access tokens can remain in memory (Zustand store) or short-lived cookies. Carry-over from Phase 4C deferred workstream.

#### R04 — Refresh Token bcrypt O(n) Lookup
- **ID:** R04
- **Category:** Performance
- **Probability:** Medium
- **Impact:** High
- **Affected:** All users during token refresh
- **Description:** `auth.py:111-126` iterates all unexpired refresh tokens for a user and calls `verify_password()` (bcrypt) on each. With 100 users × 3 tokens each = 300 bcrypt verifies per refresh. bcrypt is deliberately slow (~100ms per verify) → 30 seconds for a single refresh.
- **Root Cause:** Refresh tokens stored as bcrypt hashes (for security) but no SHA256 hash column for fast lookup.
- **Trigger:** Every token refresh (every 15 minutes per user).
- **Mitigation (Phase 4D):** Add `token_hash_sha256` column to `refresh_tokens` table. Store SHA256(raw_token) at creation. Look up by SHA256 in O(1) instead of iterating all tokens.

#### R05 — Rate Limiter In-Memory Only
- **ID:** R05
- **Category:** Scalability
- **Probability:** Medium
- **Impact:** High
- **Affected:** Multi-worker deployments
- **Description:** `RateLimiter` class stores counters in an in-memory `dict`. When running multiple gunicorn workers (or multiple processes), each worker has its own counter — 1000 req/min per worker instead of globally. HTTP 429 can be bypassed by spraying across workers.
- **Mitigation (Phase 4D):** Add optional Redis backend for shared counter state. Fall back to in-memory when Redis is unavailable (graceful degradation).

---

### 🟡 MEDIUM

#### R06 — No Document Upload Endpoint
- **ID:** R06
- **Category:** Functionality
- **Probability:** High
- **Impact:** Medium
- **Affected:** Corpus feature users
- **Description:** Documents are entirely mock data (`documents.py` route generates placeholder `DocumentSchema`). There is no endpoint to upload, store, or retrieve real documents. The document table exists but is never written to by any endpoint.
- **Mitigation (Phase 4D):** Create `POST /api/v1/documents/upload` endpoint (file upload), `GET /api/v1/documents/{id}` for retrieval, and connect to the existing `documents` table.

#### R07 — No Pagination on History Endpoints
- **ID:** R07
- **Category:** Functionality
- **Probability:** High
- **Impact:** Medium
- **Affected:** Users with >50 queries or reviews
- **Description:** `GET /api/v1/query/history` and `GET /api/v1/reviews/history` both have a hardcoded `LIMIT 50` with no `skip`/`offset` or `limit` parameters. Users with extensive history cannot access older entries.
- **Mitigation (Phase 4D):** Add `skip` and `limit` query parameters to both endpoints. Default `limit=50`, max `limit=200`.

#### R08 — No PostgreSQL Migration Path Verified
- **ID:** R08
- **Category:** Operations
- **Probability:** Low
- **Impact:** Medium
- **Affected:** Production deployment
- **Description:** SQLite is the default database. PostgreSQL is supported by SQLAlchemy but the migration path is untested. No PostgreSQL-specific types or optimizations.
- **Mitigation (Phase 4D):** Create a PostgreSQL migration test (CI job), update `DATABASE_URL` docs, verify all queries work with PostgreSQL dialect.

#### R09 — No E2E Test Coverage
- **ID:** R09
- **Category:** Quality
- **Probability:** High
- **Impact:** Medium
- **Affected:** Release confidence
- **Description:** Zero E2E tests (no Playwright, no Cypress). All testing is unit/integration via Vitest (frontend) and pytest (backend). Breaking changes like R01 go undetected until manual testing.
- **Mitigation (Phase 4D):** Add Playwright for critical paths: login flow, query execution, monitoring access.

#### R10 — Documents Filter/Sort In-Memory
- **ID:** R10
- **Category:** Performance
- **Probability:** Low
- **Impact:** Medium
- **Affected:** Large document sets
- **Description:** `documents.py` fetches all documents, then filters/sorts in Python memory. Works for demo scale but degrades with 10K+ documents.
- **Mitigation (Phase 4D):** Push `searchQuery`, `sortBy`, `sortDirection` down to SQL WHERE/ORDER BY.

---

### 🟢 LOW

#### R11 — No CSRF Token Endpoint
- **ID:** R11
- **Category:** Security
- **Probability:** Low
- **Impact:** Low
- **Affected:** Cookie-based auth (future)
- **Description:** No CSRF token generation or validation. Currently mitigated by Bearer token auth (not cookie-based). If cookie-based auth is added later (W8), CSRF protection will be required.
- **Mitigation:** Document as known limitation. No action in Phase 4D unless W8 is implemented.

#### R12 — Pre-Existing Non-Determinism in Corpus Layer
- **ID:** R12
- **Category:** Determinism
- **Probability:** Low
- **Impact:** Low
- **Affected:** Corpus data management
- **Description:** `document_relations.py`, `entity_resolution.py`, `graph.py` in `src/researchmind/corpus/` use `uuid.uuid4()` and `datetime.now()`. These are outside the deterministic M1–M6 engine boundary.
- **Mitigation:** None needed. Boundary is respected. Acceptable for data management layer.

#### R13 — CORS Origins Default Empty
- **ID:** R13
- **Category:** Configuration
- **Probability:** Low
- **Impact:** Low
- **Affected:** Initial deployment
- **Description:** `CORS_ORIGINS` defaults to `[]` (empty list) in config.py. If not set in `.env`, CORS will block all browser requests. The config parser expects `AnyHttpUrl` type which rejects `*` wildcard.
- **Mitigation:** Document that `CORS_ORIGINS` must be set in `.env` for deployed environments.

---

## Risk Summary

| Severity | Count | IDs |
|----------|-------|-----|
| 🔴 Critical | 2 | R01, R02 |
| 🟠 High | 3 | R03, R04, R05 |
| 🟡 Medium | 5 | R06, R07, R08, R09, R10 |
| 🟢 Low | 3 | R11, R12, R13 |
| **Total** | **13** | |

## Risk Trend (vs Phase 4C Baseline)

- Phase 4C identified 18 risks, resolved 7, carried 11 forward
- Phase 4D adds 2 new critical risks (R01 from W4 RBAC, R02 from missing admin UI)
- Phase 4D carries 3 high risks from Phase 4C (W8, bcrypt, rate limiter)
- Total open risks: 13 (trending downward from 18 at Phase 4C start)
