# Phase 5 — Architecture Review Report

**Generated:** 2026-06-16
**Type:** Pre-implementation audit (independent verification)
**HEAD:** `5c0aa94` (Phase 4B baseline — Phase 4C/4D changes uncommitted)

---

## 1. Repository State

| Check | Status | Detail |
|-------|--------|--------|
| Branch | ✅ | `module5-development` |
| HEAD | ✅ | `5c0aa94` (chore: complete phase 4b remediation) |
| Worktrees | ✅ | None (1 worktree: D:/RM) |
| Working tree | ⚠️ | 18 modified files, 75+ untracked files (reports, audit docs, .env, .db) |
| Phase 4C/4D commits | ❌ | Changes are UNCOMMITTED — exist only as unstaged modifications |
| Migration applied | ⚠️ | Only `02cc7a4980ec` (Phase 4B). New `3a1b2c3d4e5f` migration exists as file but NOT applied to DB |

**Implication:** Phase 5 must commit all pending Phase 4C/4D changes before building on them.

---

## 2. Backend Architecture

### 2.1 Application Stack

| Layer | Component | Status | Notes |
|-------|-----------|--------|-------|
| Framework | FastAPI | ✅ | Async, with OpenAPI auto-docs |
| ORM | SQLAlchemy async | ✅ | 5 models, async session |
| Migration | Alembic | ✅ | Async-aware env.py |
| Auth | JWT + bcrypt | ✅ | OAuth2PasswordBearer, role-based |
| Rate Limiting | Fixed-window counter | ✅ | Pluggable store (memory/Redis) |

### 2.2 Middleware Stack (execution order: first added = innermost)

```
RequestContextMiddleware      — request ID, timing, logging
RateLimitMiddleware           — 1000 req/60s default
RequestSizeLimitMiddleware    — 5MB max
SecurityHeadersMiddleware     — HSTS, XSS, frame options
CORSMiddleware                — configurable origins
```

**Note:** Rate limit applied before CORS — preflight OPTIONS counted against limit. Acceptable for low-volume APIs.

### 2.3 Route Modules (25 endpoints total)

| Module | Endpoints | Auth | Admin | Mock Data |
|--------|-----------|------|-------|-----------|
| `auth` | 5 (register, login, refresh, me, logout) | Mixed | No | No |
| `system` | 2 (health, version) | No | No | No |
| `query` | 5 (parse, plan, route, answer, history) | Optional | No | No |
| `review` | 3 (generate, validate, history) | Optional | No | No |
| `graph` | 3 (graph_data, node_detail, data) | Yes | No | **Yes** (mock) |
| `dashboard` | 3 (summary, status, recent) | Yes | No | Mixed |
| `documents` | 2 (list, get_by_id) | Yes | No | **Yes** (CorpusManager) |
| `monitoring` | 2 (overview, metrics) | Yes | **Yes** (admin) | **Yes** (mock) |

### 2.4 Dependency Graph

```
app.py
  ├── config.py (settings, SECRET_KEY, RATE_LIMIT_*, REDIS_URL, CORS)
  ├── middleware.py (RequestContext, RateLimit, RequestSize, SecurityHeaders)
  ├── exceptions.py (error envelope, handlers)
  ├── routes/
  │   ├── auth.py ──── security.py (JWT, bcrypt, sha256)
  │   │                  └── dependencies.py (get_current_user, require_role)
  │   ├── query.py ──── dependencies.py
  │   │                  └── researchmind.query.* (parser, planner, router, engine)
  │   ├── review.py ─── dependencies.py
  │   │                  └── researchmind.synthesis.* (orchestrator, traceability)
  │   ├── graph.py ──── dependencies.py
  │   │                  └── mock_graph.py (DETERMINISTIC MOCK ONLY)
  │   ├── monitoring.py ── dependencies.py
  │   │                     └── mock_graph.py (DETERMINISTIC MOCK ONLY)
  │   ├── documents.py ── dependencies.py
  │   │                    └── CorpusManager (real store or mock)
  │   ├── dashboard.py ── dependencies.py
  │   │                    └── DB queries (SELECT COUNT(*))
  │   └── system.py
  └── rate_limiter.py (CounterStore, MemoryCounterStore, RedisCounterStore)
```

---

## 3. Frontend Architecture

### 3.1 Route Structure (8 pages)

| Route | Component | Auth | Key Dependencies |
|-------|-----------|------|-----------------|
| `/login` | LoginPage | No | apiClient, localStorage |
| `/register` | RegisterPage | No | apiClient |
| `/dashboard` | DashboardPage | Yes | apiClient.get('/dashboard/*') |
| `/query` | QueryPage | Yes | apiClient, query store |
| `/reviews` | ReviewsPage | Yes | apiClient, review store |
| `/graph` | GraphPage | Yes | apiClient.get('/graph/*') |
| `/monitoring` | MonitoringDashboard | Yes (admin) | useMonitoringData, 11 sub-components |
| `/corpus` | CorpusPage | Yes | apiClient.get('/documents') |

### 3.2 Auth Flow

```
LoginPage → POST /auth/login (x-www-form-urlencoded)
                ↓
         access_token + refresh_token → localStorage
                ↓
         AppShell checks apiClient.getTokens().access
                ↓
         Sidebar uses useAuth() → GET /auth/me → isAdmin
```

**Critical flows:**
- 401 in api-client: auto-refresh (fetch /auth/refresh), fallback to /login
- 403 in monitoring: shows "Access Restricted" view
- Monitoring nav link: hidden for non-admin users

### 3.3 State Management

| Store | Type | Purpose |
|-------|------|---------|
| `ui-store` | Zustand | Sidebar, theme |
| `monitoring-store` | Zustand | Time range, module selection, queue filter |
| `query-store` | Zustand | Query text, state, results, history |
| `corpus-store` | Zustand | Search, filters, sort, pagination, selection |
| `review-store` | Zustand | Review state |
| `graph-store` | Zustand | Graph state |

### 3.4 Test Coverage by Area

| Area | Test Files | Coverage | Status |
|------|-----------|----------|--------|
| Dashboard | 5 | Good | ✅ |
| Query | 8 | Good | ✅ |
| Corpus | 4 | Good | ✅ |
| Shared | 5 | Good | ✅ |
| Auth (pages, hooks) | **0** | **None** | ❌ |
| Monitoring | **0** | **None** | ❌ |
| Graph | **0** | **None** | ❌ |
| Review | **0** | **None** | ❌ |
| API Client | **0** | **None** | ❌ |
| E2E | **0** | **None** | ❌ |

---

## 4. Database Architecture

### 4.1 Models (5 tables)

| Table | Columns | Key Indexes |
|-------|---------|-------------|
| users | 8 (id, username, email, password_hash, role, is_active, created_at, updated_at) | ix_users_username (unique), ix_users_email (unique) |
| refresh_tokens | 7 (id, user_id, hashed_token, token_hash_sha256, expires_at, is_revoked, created_at) | ix_refresh_tokens_user_id, ix_refresh_tokens_token_hash_sha256 |
| documents | 6 (id, user_id, fingerprint, title, metadata, created_at) | ix_documents_fingerprint (unique), ix_documents_user_id |
| queries | 6 (id, user_id, raw_query, query_type, result, created_at) | ix_queries_user_id |
| reviews | 6 (id, user_id, title, review_result, metadata, created_at) | ix_reviews_user_id |

### 4.2 Migration Chain

```
[Base] 02cc7a4980ec — init phase 4b generic (creates all 5 tables)
  ↓
[New]  3a1b2c3d4e5f — add token_hash_sha256 column (NOT APPLIED)
```

### 4.3 Persistence Flow

```
Register → INSERT user
Login    → SELECT user + INSERT refresh_token
Refresh  → SELECT refresh_token (SHA256 O(1)) + INSERT new + UPDATE revoke
Query    → INSERT query (if user authenticated)
Review   → INSERT review (if user authenticated)
Logout   → UPDATE refresh_token SET is_revoked
Dashboard → SELECT COUNT(*) FROM documents, reviews
```
