# Phase 4D — Architecture Review Report

**Generated:** 2026-06-16
**Scope:** Full-stack architecture audit for Phase 4D implementation readiness
**Verdict:** GO FOR PHASE 4D IMPLEMENTATION (with documented remediations)

---

## 1. Backend Architecture

### 1.1 Application Stack (app.py)

| Layer | Component | Status | Notes |
|-------|-----------|--------|-------|
| Router | FastAPI APIRouter (8 modules) | ✅ Stable | auth, query, review, graph, monitoring, documents, dashboard, history |
| Middleware | RequestContextMiddleware | ✅ Active | Request ID + timing |
| Middleware | RateLimitMiddleware | ✅ Active | 1000 req/60s default, in-memory counters |
| Middleware | RequestSizeLimitMiddleware | ✅ Active | 5 MB max upload |
| Middleware | SecurityHeadersMiddleware | ✅ Active | XSS, CSP, HSTS headers |
| Middleware | CORSMiddleware | ✅ Active | Configurable origins, default empty |
| Exception | Unified exception handlers | ✅ Active | JSON error envelope |

### 1.2 Route Modules

| Route Prefix | Auth Required | Role Required | Status |
|-------------|--------------|---------------|--------|
| `/api/v1/auth/*` | No (register/login) / Yes (others) | None | ✅ |
| `/api/v1/query/*` | Optional (history) / Yes (execute) | None | ✅ |
| `/api/v1/reviews/*` | Optional (history) / Yes (execute) | None | ✅ |
| `/api/v1/graph/*` | Yes (most) / Optional (node detail?) | None | ✅ |
| `/api/v1/monitoring/*` | Yes | **admin** | ✅ W4 enforced |
| `/api/v1/documents/*` | Yes | None | ✅ |
| `/api/v1/dashboard/*` | Yes | None | ✅ |

### 1.3 Middleware Stack Order

```
RequestContextMiddleware (1)
RateLimitMiddleware (2)
RequestSizeLimitMiddleware (3)
SecurityHeadersMiddleware (4)
CORSMiddleware (5)
```

**Observation:** Rate limit is applied before CORS — preflight OPTIONS requests will be counted against the rate limit. This is acceptable for production but worth noting.

### 1.4 Database Layer

| Model | Table | Key Columns | Status |
|-------|-------|-------------|--------|
| User | users | id (UUID PK), email, hashed_password, role, is_active | ✅ |
| RefreshToken | refresh_tokens | id (UUID PK), user_id (FK), hashed_token, expires_at, is_revoked | ✅ |
| Document | documents | id (UUID PK), title, content, metadata | ✅ |
| Query | queries | id (UUID PK), question, answer, user_id (FK), created_at | ✅ |
| Review | reviews | id (UUID PK), request, response, user_id (FK), created_at | ✅ |

**Defect:** RefreshToken.hashed_token uses bcrypt — no index. Token lookup iterates all unexpired tokens per user (O(n) bcrypt verify). See `auth.py:111`.

### 1.5 Migration Chain

- `02cc7a4980ec_init_phase_4b_generic.py` — single migration creates all 5 tables
- No new migrations needed for Phase 4C (all tables existed from Phase 4B)
- Phase 4D may require: `admin_actions_log` table, `documents.content` storage for upload

---

## 2. Frontend Architecture

### 2.1 Route Structure

| Route | Component | Data Fetching | Auth Required |
|-------|-----------|--------------|---------------|
| `/login` | LoginPage | `apiClient.post('/auth/login')` | No |
| `/register` | RegisterPage | `apiClient.post('/auth/register')` | No |
| `/dashboard` | DashboardPage | `apiClient.get('/dashboard/summary')` | Yes |
| `/query` | QueryPage | `apiClient.post('/query')` + History | Yes |
| `/reviews` | ReviewsPage | History | Yes |
| `/graph` | GraphPage | `apiClient.get('/graph/*')` | Yes |
| `/monitoring` | MonitoringDashboard | `apiClient.get('/monitoring/metrics')` | Yes (admin required) |
| `/corpus` | CorpusPage | `apiClient.get('/documents')` | Yes |

### 2.2 State Management

| Store | Library | Purpose |
|-------|---------|---------|
| `auth-store.ts` | Zustand | Auth state (token, user) |
| `monitoring-store.ts` | Zustand | Monitoring filters, module selection, queue filter |
| `query-store.ts` | Zustand | Query state, results, history |
| `corpus-store.ts` | Zustand | Corpus data, filters |
| `ui-store.ts` | Zustand | UI preferences (sidebar, theme) |

### 2.3 API Client (`lib/api-client.ts`)

- Token storage: **localStorage** (W8 deferred — XSS risk)
- 401 handling: auto-refresh with token rotation, falls back to `/login` redirect
- **403 handling: NONE** — 403 will throw generic `ApiError(403, 'Forbidden')`
- Monitoring dashboard uses `apiClient.get()` which sets Bearer token
- **BREAKING CHANGE IDENTIFIED:** Monitoring route requires admin role (W4), but:

  **`services/monitoring.ts`** calls `apiClient.get()` which DOES send Bearer token (lines 4-6). However, if the user is not admin, the backend returns 403. The frontend monitoring dashboard (`monitoring-dashboard.tsx`, `monitoring-hooks.ts`) has **no error state handling** — `useMonitoringData` ignores query errors. Non-admin users get a broken page.

### 2.4 Test Coverage

| Area | Test Files | Coverage | Status |
|------|-----------|----------|--------|
| Dashboard | 5 test files | Good | ✅ |
| Query | 8 test files | Good | ✅ |
| Corpus | 3 test files | Moderate | ✅ |
| Shared | 5 test files | Good | ✅ |
| Monitoring | **0 test files** | **None** | ❌ |
| Auth (Login/Register) | **0 test files** | **None** | ❌ |
| API Client | **0 test files** | **None** | ❌ |
| E2E | **0 test files** | **None** | ❌ |

---

## 3. Determinism Audit

### 3.1 Engine Paths (M1–M6) — CLEAN

All engine paths (`src/researchmind/query/`, `src/researchmind/synthesis/`) verified: zero `uuid4`, `datetime.now()`, `random.*` calls.

### 3.2 Non-Engine Paths (Allowed)

| File | Violation | Justification |
|------|-----------|---------------|
| `backend/db/models/*` | `uuid.uuid4` for PK defaults | ORM model defaults |
| `backend/api/auth/security.py` | `datetime.now(timezone.utc)` | Token expiry timestamps |
| `backend/api/routes/auth.py` | `datetime.now(timezone.utc)` | Token expiry comparison |
| `src/researchmind/corpus/document_relations.py` | `uuid.uuid4().hex[:12]` | Data management, not engine |
| `src/researchmind/corpus/entity_resolution.py` | `uuid.uuid4()` | Data management |
| `src/researchmind/corpus/graph.py` | `uuid.uuid4()` | Data management |

All acceptable — determinism boundary is maintained.

---

## 4. Verification Summary

- **Backend tests:** 139/139 passing
- **Frontend tests:** 252/256 passing (4 pre-existing flaky in filters-panel.test.tsx)
- **Frontend build:** 12/12 static routes compiled
- **Migration:** Applied — no pending
- **CORS:** Configured via `CORS_ORIGINS` env var
- **Secret:** `SECRET_KEY` set in `.env` (testing_secret_key — needs production rotation)
