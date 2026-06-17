# Phase 4C — Complete Dependency Map

## 1. Frontend → Backend API Call Matrix

| Frontend File | Feature | API Call | Backend Route | Auth Required | Backend Service/Engine |
|---|---|---|---|---|---|
| `app/login/page.tsx` | Login form | `POST /api/v1/auth/login` (x-www-form-urlencoded) | `auth.py:login` | No | bcrypt verify, JWT create, DB |
| `app/login/page.tsx` | Login → redirect | `apiClient.setTokens()` → `localStorage` | (client only) | — | — |
| `app/register/page.tsx` | Register form | `POST /api/v1/auth/register` (JSON) | `auth.py:register` | No | bcrypt hash, DB |
| `lib/api-client.ts` | Refresh token | `POST /api/v1/auth/refresh` | `auth.py:refresh_token` | No (refresh token) | JWT decode, bcrypt verify, rotate, DB |
| `lib/api-client.ts` | Logout | `POST /api/v1/auth/logout` | `auth.py:logout` | No (refresh token) | bcrypt verify, revoke, DB |
| `components/layout/app-shell.tsx` | Profile check | `GET /api/v1/auth/me` | `auth.py:get_me` | Yes (Bearer) | JWT decode, DB read |
| `features/query/query-workspace.tsx` | Run query | `POST /api/v1/query/answer` | `query.py:answer_query` | Optional (Bearer) | M5 QueryEngine (parse→plan→route→execute), DB write if auth'd |
| `features/review/review-page-client.tsx` | Generate review | `POST /api/v1/reviews/generate` | `review.py:generate_review` | Optional (Bearer) | M6 ReviewOrchestrator, DB write if auth'd |
| `features/review/` | Validate review | `POST /api/v1/reviews/validate` | `review.py:validate_review` | No | M6 TraceabilityVerifier |
| `features/dashboard/use-dashboard-data.ts` | Summary cards | `GET /api/v1/dashboard/summary` | `dashboard.py:get_dashboard_summary` | No | CorpusManager stats (fallback hardcoded) |
| `features/dashboard/use-dashboard-data.ts` | Recent documents | `GET /api/v1/documents?pageIndex=0&pageSize=10` | `documents.py:get_documents` | No | InMemoryDocumentStore |
| `features/dashboard/use-dashboard-data.ts` | System status | `GET /api/v1/dashboard/status` | `dashboard.py:get_dashboard_status` | No | Hardcoded mock |
| `features/dashboard/use-dashboard-data.ts` | Recent reviews | `GET /api/v1/dashboard/recent` | `dashboard.py:get_dashboard_recent` | No | Mock data |
| `features/corpus/use-corpus-data.ts` | Document list | `GET /api/v1/documents?pageIndex=N&pageSize=N` | `documents.py:get_documents` | No | InMemoryDocumentStore |
| `features/graph/graph-hooks.ts` | Graph data | `GET /api/v1/graph` | `graph.py:get_graph` | No | DeterministicLCG mock |
| `features/monitoring/monitoring-hooks.ts` | Monitoring data | `GET /api/v1/monitoring/metrics?timeRange=X` | `monitoring.py:get_monitoring_metrics` | No | DeterministicLCG mock |
| — | Health check | `GET /api/v1/health` | `system.py:health_check` | No | None |
| — | Version | `GET /api/v1/version` | `system.py:get_version` | No | Config read |
| — | Graph node detail | `GET /api/v1/graph/node/{id}` | `graph.py:get_graph_node` | No | Stub (not implemented) |

---

## 2. Backend → Database Dependency Map

| Route / Operation | Table(s) | Read/Write | Keys Used | Indexes |
|---|---|---|---|---|
| Register | `users` | INSERT | username, email (unique checks) | `ix_users_username`, `ix_users_email` |
| Login | `users`, `refresh_tokens` | SELECT users, INSERT refresh_tokens | username, user_id | `ix_users_username`, `ix_refresh_tokens_user_id` |
| Refresh | `refresh_tokens`, `users` | SELECT tokens, SELECT user, UPDATE revoke, INSERT new token | user_id, is_revoked, expires_at | `ix_refresh_tokens_user_id` |
| Logout | `refresh_tokens` | SELECT, UPDATE is_revoked | user_id | `ix_refresh_tokens_user_id` |
| GET /me | `users` | SELECT | id (from JWT) | Primary key |
| POST query/answer | `queries` | INSERT (if auth'd) | user_id, raw_query | `ix_queries_user_id` |
| POST review/generate | `reviews` | INSERT (if auth'd) | user_id | `ix_reviews_user_id` |
| (future) GET query/history | `queries` | SELECT | user_id, created_at DESC | `ix_queries_user_id` |
| (future) GET review/history | `reviews` | SELECT | user_id, created_at DESC | `ix_reviews_user_id` |
| (future) dashboard count | `documents`, `reviews` | SELECT COUNT(*) | — | None needed |

---

## 3. Backend → Engine Dependency Map

| Route | Engine Components | Deterministic? | File Path |
|---|---|---|---|
| `POST /api/v1/query/parse` | `QueryParser` | Yes (CRC32 IDs, no random) | `src/researchmind/query/parser.py` |
| `POST /api/v1/query/plan` | `QueryPlanner` | Yes (cached templates) | `src/researchmind/query/planner.py` |
| `POST /api/v1/query/route` | `StepDispatcher` | Yes (input-output mapping) | `src/researchmind/query/router.py` |
| `POST /api/v1/query/answer` | `QueryEngine` (parser→planner→dispatcher→execute) | Yes (no uuid4/datetime.now) | `src/researchmind/query/engine.py` |
| `POST /api/v1/reviews/generate` | `ReviewOrchestrator` | Yes (deterministic prompts) | `src/researchmind/synthesis/orchestrator.py` |
| `POST /api/v1/reviews/validate` | `TraceabilityVerifier` | Yes (pure function) | `src/researchmind/synthesis/traceability.py` |
| `GET /api/v1/graph` | Mock `DeterministicLCG` | Yes (fixed seed 12345, pure math) | `backend/api/mock_graph.py` |
| `GET /api/v1/monitoring/metrics` | Mock `DeterministicLCG` | Yes (CRC32 seed from timeRange string) | `backend/api/mock_graph.py` |
| `GET /api/v1/documents` | `InMemoryDocumentStore` | Yes (pre-computed mock docs, LCG) | `backend/api/mock_data.py` |

---

## 4. Frontend → Store/State Dependency Map

| Store | Type | Used By | Persistence |
|---|---|---|---|
| `stores/ui-store.ts` | Zustand | `app-shell.tsx` (sidebar) | Memory only |
| `features/query/query-store.ts` | Zustand | `query-workspace.tsx`, `query-history.tsx`, `query-results.tsx`, `evidence-panel.tsx`, `trace-viewer.tsx` | Memory only |
| `features/review/review-store.ts` | Zustand | `review-page-client.tsx`, `review-generator-form.tsx`, `review-viewer.tsx`, `findings-panel.tsx`, `traceability-panel.tsx` | Memory only |
| `features/corpus/corpus-store.ts` | Zustand | `corpus-manager.tsx`, `filters-panel.tsx` | Memory only |
| `features/monitoring/monitoring-store.ts` | Zustand | `monitoring-hooks.ts`, `monitoring-filters.tsx` | Memory only |
| `features/graph/graph-store.ts` | Zustand | `graph-explorer.tsx`, `graph-search.tsx`, `graph-sidebar.tsx` | Memory only |

---

## 5. Data Flow Diagrams (Text)

### 5.1 Query Execution Flow
```
User Input
    ↓
query-workspace.tsx (CRC32 id)
    ↓
services/query.ts → generateAnswer()
    ↓
apiClient.post('/api/v1/query/answer')  ←  Bearer token (if logged in)
    ↓
query.py:answer_query
    ├─ QueryEngine.execute() [parse→plan→route→execute]
    ├─ db add + commit (if current_user)
    └─ return result_dump
    ↓
services/query.ts: response validation
    ↓
query-store.ts: setCurrentAnswer()
    ↓
query-results.tsx, evidence-panel.tsx, trace-viewer.tsx (render)
```

### 5.2 Auth Flow
```
Login Page (x-www-form-urlencoded)
    ↓
POST /api/v1/auth/login
    ├─ bcrypt verify password
    ├─ JWT create (access + refresh)
    ├─ bcrypt hash refresh token → DB insert
    └─ return tokens
    ↓
frontend: apiClient.setTokens() → localStorage
    ↓
AppShell: apiClient.getTokens().access → !null → isAuthenticated=true
    ↓
API calls: handleFetchWithAuth → Bearer header
    ↓
401 response → /auth/refresh → retry or redirect /login
```

### 5.3 Database Entity Relationships
```
users (PK: id UUID)
  ├── refresh_tokens (FK: user_id → users.id, CASCADE)
  ├── documents (FK: user_id → users.id, CASCADE)
  ├── queries (FK: user_id → users.id, CASCADE)
  └── reviews (FK: user_id → users.id, CASCADE)
```

---

## 6. Critical Dependency Chain

```
Auth (Phase 4B) ─→ W3 (History) ─→ W4 (RBAC)
                        ↑
                    W2 (Documents search/sort) ─→ frontend corpus-manager.tsx
                        ↑
                    W1 (Rate limiting) ─→ all routes protected
```

**Key observation:** No circular dependencies. W8 (cookies) depends on Auth but does not block anything else. All workstreams except W3/W4 can be implemented in parallel.
