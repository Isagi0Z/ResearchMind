# Phase 5 — Implementation Plan

**Generated:** 2026-06-16
**Based on:** Architecture Review, Dependency Analysis, & Production Readiness reports

---

## Executive Summary

Phase 5 is **real integration**. Every endpoint behind mock data must be wired to real sources. The pattern is consistent: remove `generate_mock_*()` calls and replace with actual DB queries or engine pipelines. Auth, Query, and Review are real already; the remaining 3 modules (Monitoring, Graph, Documents) plus the Admin UI gap are the core work.

---

## Work Streams

### WS1: Real Monitoring Pipeline (High Priority)

**Problem:** `/monitoring/metrics` and `/monitoring/overview` return deterministic mock data.

**Solution:**

| Step | File(s) | Description |
|------|---------|-------------|
| 1.1 | `backend/api/routes/monitoring.py` | Replace `generate_mock_monitoring()` with `MonitoringService.get_overview()` and `MonitoringService.get_metrics()` |
| 1.2 | `backend/api/services/monitoring_service.py` (new) | Real queries: SELECT COUNT, engine profiles from M1-M6 execution context, error rates from query/review tables, avg response times via middleware logs |
| 1.3 | `backend/api/routes/monitoring.py` | Accept `time_range` query param → apply SQL WHERE on `created_at` |
| 1.4 | `backend/api/dependencies.py` | Add `get_monitoring_service()` factory |
| 1.5 | `frontend/services/monitoring.ts` | Verify existing service signature matches new response schema |

**Risks:** Response shape must match. The 11 frontend sub-components consume specific keys (`metrics`, `health`, `charts`, `queue`, `recentErrors`, `corpus`). Schema must be stable.

---

### WS2: Real Graph Pipeline (High Priority)

**Problem:** `/graph/data` returns 1000 deterministic placeholder nodes. `/graph/node/:id` queries DB but has no real data.

**Solution:**

| Step | File(s) | Description |
|------|---------|-------------|
| 2.1 | `backend/api/routes/graph.py` | Replace `generate_mock_graph()` with `GraphService.get_graph()` |
| 2.2 | `backend/api/services/graph_service.py` (new) | Query `documents` → nodes (title, fingerprint, metadata), build edges from CorpusManager relations |
| 2.3 | `backend/api/services/graph_service.py` | Implement pagination, filtering by type/daterange |
| 2.4 | `backend/api/routes/graph.py` | `/graph/node/:id` — wire to real DB lookup with full metadata |
| 2.5 | `backend/api/routes/graph.py` | Remove `generate_mock_graph` import dependency |

**Risks:** Graph rendering performance at scale. If document count is high, consider lazy-loading sub-graphs.

---

### WS3: Document Upload & Server-Side Filter (Medium Priority)

**Problem:** No upload endpoint. Filter/sort happens in Python memory.

**Solution:**

| Step | File(s) | Description |
|------|---------|-------------|
| 3.1 | `backend/api/routes/documents.py` | Add `POST /documents/upload` — accept file, store via CorpusManager |
| 3.2 | `backend/api/routes/documents.py` | Move filter/sort to SQL (WHERE, ORDER BY) on `GET /documents` |
| 3.3 | `backend/api/routes/documents.py` | Add pagination with cursor-based offset |
| 3.4 | `backend/api/schemas/document.py` | Add upload request/response schemas |
| 3.5 | `frontend/features/corpus` | Wire upload UI to new endpoint |

---

### WS4: Admin User Promotion (Medium Priority)

**Problem:** No way to set `role=admin` without raw SQL or `_make_admin` helper.

**Solution:**

| Step | File(s) | Description |
|------|---------|-------------|
| 4.1 | `backend/api/routes/admin.py` (new) | Add `POST /admin/promote` — promote user by username (require existing admin) |
| 4.2 | `backend/api/routes/admin.py` | Add `GET /admin/users` — list all users |
| 4.3 | `backend/api/routes/admin.py` | Add `PUT /admin/users/:id` — update user role/status |
| 4.4 | `backend/api/app.py` | Register admin router |
| 4.5 | `backend/api/dependencies.py` | Ensure `require_role("admin")` is reusable |

---

### WS5: Security Hardening (Ongoing)

| Step | File(s) | Description |
|------|---------|-------------|
| 5.1 | `.env` | Ensure SECRET_KEY is an env var, not default |
| 5.2 | `backend/api/routes/auth.py` | Add failed-login tracking in redis/memory → rate limit per-IP |
| 5.3 | testing | Verify all endpoints reject unauthorized access |

---

### WS6: Test Coverage (Medium Priority)

| Step | Area | Current | Target |
|------|------|---------|--------|
| 6.1 | Auth pages | 0 tests | 2 tests (login, register flows) |
| 6.2 | Monitoring frontend | 0 tests | 5 tests (hooks, dashboard, filters, health panel) |
| 6.3 | Graph frontend | 0 tests | 2 tests (graph rendering, interaction) |
| 6.4 | Review frontend | 0 tests | 2 tests (generate, validate) |
| 6.5 | API client | 0 tests | 3 tests (auth refresh, error handling, timeout) |

---

## Implementation Order

```
Week 1: WS1 (Real Monitoring) + WS6 (Monitoring tests)
Week 2: WS2 (Real Graph) + WS6 (Graph/Review tests)
Week 3: WS3 (Document Upload) + WS6 (Auth page tests)
Week 4: WS4 (Admin UI) + WS5 (Security) + WS6 (API client tests)
```

## Verification Criteria

- [ ] `generate_mock_monitoring()` removed — data comes from real queries
- [ ] `generate_mock_graph()` removed — data comes from DB
- [ ] Document upload works end-to-end (frontend → upload → store → list)
- [ ] Admin user can be promoted via UI
- [ ] All backend tests still pass (target: 139+)
- [ ] All frontend tests still pass (target: 256+)
- [ ] No mock data in any endpoint response (unless explicitly temporary)
- [ ] SECRET_KEY not in source code
