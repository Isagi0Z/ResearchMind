# Phase 4D — Dependency & Coupling Analysis Report

**Generated:** 2026-06-16
**Scope:** Map all frontend→backend→DB→engine dependency paths; identify coupling risks and scalability bottlenecks

---

## 1. Complete Dependency Map

### 1.1 Auth Flow
```
Login Page ──POST──▶ /api/v1/auth/login ──▶ User table ──▶ bcrypt verify
                            │
                            ▼
                     JWT issued (access + refresh)
                            │
               ┌────────────┴────────────┐
               ▼                         ▼
        localStorage              RefreshToken table
        (access_token +           (bcrypt hashed)
         refresh_token)
                                    │
                        ┌───────────┴───────────┐
                        ▼                       ▼
                  Token refresh             Token rotation
                  (O(n) bcrypt scan)        (revoke old + insert new)
```

**Scalability Bottleneck:** Refresh token lookup is O(n * bcrypt_cost) — with n=100 users each having ~3 valid tokens, that's 300 bcrypt verifies per refresh. Acceptable at small scale but will degrade.

### 1.2 Query Flow
```
Query Page ──POST──▶ /api/v1/query/execute
                        │
                        ▼
                  researchmind.pipeline (M1-M6)
                        │
                        ▼
                  Answer + Traceability
                        │
                        ├──▶ Query table (persist)
                        └──▶ Response to frontend
```

**No coupling risk.** Query is self-contained.

### 1.3 Monitoring Flow (CRITICAL COUPLING)
```
Monitoring Dashboard
    │
    ├──▶ useMonitoringData() ──▶ getMonitoringData()
    │                                   │
    │                          apiClient.get('/api/v1/monitoring/metrics')
    │                                   │
    │                           Bearer token (from localStorage)
    │                                   │
    ▼                                   ▼
[No error handling]          backend/routes/monitoring.py
                                     │
                            require_role("admin")
                                     │
                              ┌──────┴──────┐
                              ▼             ▼
                          Admin user    Non-admin user
                              │             │
                              ▼             ▼
                         200 OK         403 Forbidden
                              │             │
                              ▼             ▼
                     [No 403 handler]  [Throws ApiError(403)]
                                             │
                                      useQuery error field
                                      (never rendered)
```

**BREAKING CHANGE:** Frontend monitoring dashboard has no error state rendering. Non-admin users (or unauthenticated users) will see either a spinner (loading) or stale data after error. The `useMonitoringData` hook in `monitoring-hooks.ts` does not surface errors to the UI.

### 1.4 Dashboard Flow
```
Dashboard Page ──GET──▶ /api/v1/dashboard/summary
                              │
                              ▼
                    SELECT COUNT(*) FROM documents
                    SELECT COUNT(*) FROM reviews
                              │
                              ▼
                    Response (doc_count, review_count)
```

No coupling risk.

### 1.5 Document Flow
```
Corpus Page ──GET──▶ /api/v1/documents
                           │
                     ┌─────┴─────┐
                     ▼           ▼
                 searchQuery   sortBy
                   filter     sortDirection
                     │           │
                     ▼           ▼
              In-memory filter   In-memory sort
              (Python list)     (Python sort)
```

**Scalability Bottleneck:** Documents are fetched in full then filtered/sorted in Python. With >10K documents, this will be slow. A proper SQL WHERE/ORDER BY is needed.

### 1.6 Graph Flow
```
Graph Page ──GET──▶ /api/v1/graph/node/{id}
                           │
                           ▼
                    SELECT FROM node table
                    (or 404)
```

No coupling risk.

### 1.7 History Flows
```
Query/Review Page ──GET──▶ /api/v1/query/history  (limit=50)
                           GET /api/v1/reviews/history (limit=50)
                              │
                              ▼
                    SELECT WHERE user_id = :uid
                    ORDER BY created_at DESC
                    LIMIT 50
```

**Missing:** No pagination (skip/offset params). Users with >50 history entries cannot access older records.

---

## 2. Coupling Risk Matrix

| ID | Dependency | Risk Level | Description |
|----|-----------|------------|-------------|
| C01 | Monitoring frontend → monitoring backend (RBAC) | **CRITICAL** | No 403 handling; non-admin users get broken page |
| C02 | Token storage → localStorage | **HIGH** | XSS vulnerability (W8 deferred) |
| C03 | Refresh token → bcrypt lookup | **MEDIUM** | O(n) scan per refresh; degrades with scale |
| C04 | Rate limiter → in-memory dict | **MEDIUM** | Not shared across workers; bypass with multiple processes |
| C05 | Documents filter/sort → Python list | **LOW** | Works for current scale; SQL push-down needed later |
| C06 | History → hardcoded LIMIT 50 | **LOW** | Missing pagination |
| C07 | CORS → config only (no CSRF) | **LOW** | No CSRF token endpoint for cookie-based auth |
| C08 | Admin management → raw SQL only | **HIGH** | No UI for role assignment; only `_make_admin` in test stubs |

---

## 3. Data Flow Integrity

### 3.1 Write Paths
```
Auth: Register → INSERT user
      Login → SELECT user + INSERT refresh_token
      Refresh → SELECT tokens (O(n)) + INSERT new + UPDATE revoked
      Logout → UPDATE refresh_token SET is_revoked

Query: Execute → pipeline call + INSERT query
Review: Execute → LLM call + INSERT review
```

### 3.2 Read Paths
```
Dashboard: SELECT COUNT(*) FROM documents, reviews
Documents: SELECT * FROM documents (+ Python filter/sort)
Graph: SELECT * FROM node WHERE id = :id
History: SELECT * FROM queries/reviews WHERE user_id = :uid LIMIT 50
Monitoring: SELECT * FROM monitoring_metrics WHERE time_range
```

### 3.3 Mock/Real Data Boundary

| Source | Type | Real Data? | Notes |
|--------|------|-----------|-------|
| Documents | Mock | No | `backend/api/routes/documents.py` generates mock data with `DocumentSchema` |
| Graph nodes | Mock | No | `backend/api/routes/graph.py` returns `graph_response` dict |
| Monitoring metrics | Mock | No | `backend/api/routes/monitoring.py` returns `MonitoringSnapshot` with placeholder values |
| Queries | Real | Yes | Persisted to `queries` table |
| Reviews | Real | Yes | Persisted to `reviews` table |
| Users | Real | Yes | Persisted to `users` table |

**Phase 4D should prioritize real data pipelines for documents and graph.**

---

## 4. Third-Party Dependencies

| Dependency | Version | Purpose | Risk |
|-----------|---------|---------|------|
| FastAPI | (latest) | Backend framework | Low |
| SQLAlchemy (async) | (latest) | ORM | Low |
| Alembic | (latest) | Migrations | Low |
| bcrypt | (latest) | Password/token hashing | Low (but O(n) issue) |
| PyJWT | (latest) | JWT encode/decode | Low |
| Next.js 14 | 14.x | Frontend framework | Low |
| React Query (TanStack) | (latest) | Data fetching | Low |
| Zustand | (latest) | State management | Low |
| Tailwind CSS | (latest) | Styling | Low |
| Vitest | (latest) | Testing | Low |

No dependency issues identified.
