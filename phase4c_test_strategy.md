# Phase 4C — Test Strategy

## 1. Current Test Baseline

| Suite | Files | Test Functions | Lines |
|---|---|---|---|
| Backend (`backend/api/tests/`) | 10 test files + 1 conftest | 48 `def test_*` | 380 |
| Frontend (`frontend/tests/`) | 22 test files + 1 setup | ~256 (estimated) | 1,557 |
| **Total** | **32 test files** | **~304** | **1,937** |

### Backend Coverage by Area

| Area | Tests | Coverage Depth |
|---|---|---|
| Auth (register/login/refresh/logout/me) | 11 (in test_stubs.py) | Full E2E flow |
| Security (password hash, JWT) | 3 | Unit |
| Dependencies (token decode, expired token) | 2 | Unit |
| Middleware (request ID, headers, determinism) | 6 | Parametric + fuzz |
| Exceptions (base, auth, 404, 405, 422) | 7 + 10 fuzz = 17 | Parametric + fuzz |
| Schemas (auth, common, fuzz) | 8 + 15 fuzz = 23 | Parametric + fuzz |
| Config (defaults, overrides, fuzz) | 3 + 10 fuzz = 13 | Parametric + fuzz |
| App (health, version, OpenAPI) | 5 | Smoke |
| E2E (query flow determinism, review flow) | 2 | Full pipeline determinism |
| Route stubs (graph, documents, dashboard, monitoring) | ~7 | Status code only |

### Frontend Coverage by Area

| Area | Test Files | Coverage Depth |
|---|---|---|
| Query (workspace, history, results, evidence, trace, metrics, store, suggestions) | 8 | Component + store + service |
| Corpus (manager, store, filters, use-corpus-data) | 4 | Component + store + hook |
| Dashboard (summary, documents, reviews, status, use-dashboard-data) | 5 | Component + hook |
| Monitoring (no dedicated tests — covered via integration) | 0 | None |
| Graph (no dedicated tests — covered via integration) | 0 | None |
| Shared (status badge, error, empty, loading, ui-store) | 5 | Component + store |
| Auth (login, register pages — no frontend tests) | 0 | None |
| Layout/AppShell (no tests) | 0 | None |

---

## 2. Coverage Gaps

### Critical Gaps (Must Fix in Phase 4C)

| Gap | Current State | Risk |
|---|---|---|
| **Monitoring frontend tests (W5)** | 0 tests for `monitoring-dashboard.tsx`, `monitoring-hooks.ts`, `monitoring-store.ts` | Breaking changes to monitoring filter params undetected |
| **Graph frontend tests (W6)** | 0 tests for `graph-explorer.tsx`, `graph-hooks.ts`, `graph-store.ts` | Graph node detail endpoint errors undetected |
| **RBAC integration tests (W4)** | No test verifying 403 for insufficient role | RBAC changes could silently fail |
| **Rate limiter tests (W1)** | No rate limiting tests (middleware is no-op) | Rate limit logic untested |
| **Documents search/filter tests (W2)** | No search/filter/pagination tests | W2 code path untested on backend |
| **History endpoint tests (W3)** | No history endpoint tests | New endpoints untested |

### Moderate Gaps (Should Fix)

| Gap | Current State | Risk |
|---|---|---|
| **Auth frontend component tests** | Login/register pages have no component tests | Auth UI regressions undetected |
| **AppShell layout tests** | No tests for sidebar, theme toggle, auth state | Layout regressions could break UX |
| **API client tests** | `api-client.ts` has no dedicated unit tests | Refresh logic / error handling untested |
| **Graph node detail tests (W6)** | Route stub currently returns 501 — no existing test | New endpoint behavior untested |
| **Dashboard DB-backed test (W7)** | No test with populated vs empty DB | Real count logic untested |

### Low Priority (Can Defer)

| Gap | Current State | Risk |
|---|---|---|
| **E2E full-stack tests** | No Playwright/Cypress tests | Manual testing only |
| **Stress/load tests** | No load testing | Performance regressions undetected |
| **Security penetration tests** | No automated security scanning | Deployment risk only |

---

## 3. Phase 4C Test Implementation Plan

### Batch 1: W1 Rate Limiter (5 new tests)
| Test Name | Type | File | What It Verifies |
|---|---|---|---|
| `test_rate_limit_not_exceeded` | Integration | `test_middleware.py` | Normal request passes through |
| `test_rate_limit_exceeded` | Integration | `test_middleware.py` | After N requests within window, 429 returned |
| `test_rate_limit_resets_after_window` | Integration | `test_middleware.py` | After window expiry, requests allowed again |
| `test_rate_limit_configurable` | Unit | `test_config.py` | `RATE_LIMIT_REQUESTS` env var respected |
| `test_rate_limit_deterministic` | Integration | `test_integration_e2e.py` | Rate limiter does not introduce non-deterministic state |

### Batch 2: W2 Documents Search (8 new tests)
| Test Name | Type | File | What It Verifies |
|---|---|---|---|
| `test_documents_default_pagination` | Integration | `test_routes.py` | Default page 0, pageSize 10 returns 10 docs |
| `test_documents_search_query` | Integration | `test_routes.py` | `searchQuery="BERT"` filters results |
| `test_documents_sort_by_title` | Integration | `test_routes.py` | `sortBy=title&sortDirection=asc` orders correctly |
| `test_documents_filter_year` | Integration | `test_routes.py` | `filters[yearRange]=2020,2025` narrows results |
| `test_documents_filter_status` | Integration | `test_routes.py` | `filters[status]=success` filters by pipeline stage |
| `test_documents_pagination_offset` | Integration | `test_routes.py` | Page 1 returns different docs than page 0 |
| `test_documents_empty_result` | Integration | `test_routes.py` | Search for nonexistent term returns empty |
| `test_documents_fuzz` | Parametric | `test_routes.py` | 10 iterations of random params return 200 |

### Batch 3: W3 History Endpoints (6 new tests)
| Test Name | Type | File | What It Verifies |
|---|---|---|---|
| `test_query_history_returns_queries` | Integration | `test_stubs.py` | After answering a query, history returns it |
| `test_query_history_auth_required` | Integration | `test_stubs.py` | Without token, 401 |
| `test_query_history_cross_user` | Integration | `test_stubs.py` | User A cannot see User B's queries |
| `test_review_history_returns_reviews` | Integration | `test_stubs.py` | After generating review, history returns it |
| `test_review_history_auth_required` | Integration | `test_stubs.py` | Without token, 401 |
| `test_review_history_cross_user` | Integration | `test_stubs.py` | User A cannot see User B's reviews |

### Batch 4: W4 RBAC (4 new tests)
| Test Name | Type | File | What It Verifies |
|---|---|---|---|
| `test_monitoring_admin_required` | Integration | `test_stubs.py` | Normal user gets 403 on monitoring |
| `test_monitoring_admin_allowed` | Integration | `test_stubs.py` | Admin user gets 200 on monitoring |
| `test_rbac_default_role` | Integration | `test_stubs.py` | New user has default `role="user"` |
| `test_rbac_query_still_optional` | Integration | `test_stubs.py` | Query answer still works without auth |

### Batch 5: W5 Monitoring Filter (3 new tests)
| Test Name | Type | File | What It Verifies |
|---|---|---|---|
| `test_monitoring_time_range_accepted` | Integration | `test_stubs.py` | `?timeRange=1h` returns 200 |
| `test_monitoring_time_range_deterministic` | Integration | `test_stubs.py` | Same timeRange → same monitoring snapshot |
| `test_monitoring_time_range_different` | Integration | `test_stubs.py` | Different timeRange → different snapshots |

### Batch 6: W6 Graph Node Detail (3 new tests)
| Test Name | Type | File | What It Verifies |
|---|---|---|---|
| `test_graph_node_detail_found` | Integration | `test_stubs.py` | `GET /graph/node/node-0` returns node data |
| `test_graph_node_detail_not_found` | Integration | `test_stubs.py` | `GET /graph/node/nonexistent` returns 404 |
| `test_graph_node_determinism` | Integration | `test_integration_e2e.py` | Same node id always returns same data |

### Batch 7: W7 Dashboard Counts (2 new tests)
| Test Name | Type | File | What It Verifies |
|---|---|---|---|
| `test_dashboard_summary_db_backed` | Integration | `test_stubs.py` | After inserting documents, summary reflects count |
| `test_dashboard_summary_empty_db` | Integration | `test_stubs.py` | Empty DB returns all zeros |

---

## 4. Frontend Test Gaps to Fill in Phase 4C

| Test File | Tests to Add | Priority |
|---|---|---|
| `frontend/tests/monitoring/monitoring-hooks.test.tsx` | Hook with timeRange param variations | High (W5) |
| `frontend/tests/graph/graph-hooks.test.tsx` | Hook with loading/success/error states | High (W6) |
| `frontend/tests/auth/login-page.test.tsx` | Login form submit, error display, token storage | Medium |
| `frontend/tests/layout/app-shell.test.tsx` | Sidebar nav items, theme toggle, auth state rendering | Medium |
| `frontend/tests/lib/api-client.test.ts` | Token refresh subscriber pattern, 401 retry, error sanitization | Medium |
| `frontend/tests/monitoring/monitoring-dashboard.test.tsx` | Component rendering with mock data | Medium |

---

## 5. Test Execution Plan

### Phase 4C CI Gates
```
Gate 1: pytest backend/api/tests/   → 122/122 + ~31 new = 153/153
Gate 2: vitest run                   → 256/256 + ~XX new = ~280+/280+
Gate 3: grep -r "uuid4\|datetime.now" src/researchmind/query/ src/researchmind/synthesis/
         → ZERO matches
Gate 4: Manual determinism check:
         POST /api/v1/query/answer (same input, same output)
         POST /api/v1/reviews/generate (same input, same output)
```

### Testing Tools
- **Backend:** pytest 8.x with `pytest-asyncio` for async route tests
- **Frontend:** vitest + jsdom + `@testing-library/react`
- **Determinism:** Manual + CI grep gate (no automated deterministic output assertion — E2E test `test_integration_e2e.py` covers this)

---

## 6. Total Backend Test Count Projection

| Area | Current | New | Total |
|---|---|---|---|
| App | 5 | 0 | 5 |
| Config | 13 (3 base + 10 fuzz) | 1 | 14 |
| Dependencies | 2 | 0 | 2 |
| Exceptions | 17 (7 base + 10 fuzz) | 0 | 17 |
| Integration E2E | 2 | 2 | 4 |
| Middleware | 6 | 5 | 11 |
| Routes | 1 | 8 | 9 |
| Schemas | 23 (8 base + 15 fuzz) | 0 | 23 |
| Security | 3 | 0 | 3 |
| Stubs | 19 (11 base + 8 fuzz) | 15 | 34 |
| **Total** | **48 + 43 fuzz = 91** | **31** | **122** |

*Actual pass count: 122 tests (includes fuzz parametrizations). With 31 new tests: ~153 passing tests.*

---

## 7. Risk-Based Testing Priorities

| Priority | Workstream | Tests | Rationale |
|---|---|---|---|
| P1 | W4 RBAC | 4 integration | Breaking auth changes affect all endpoints |
| P2 | W3 History | 6 integration | New routes, auth-sensitive, data isolation critical |
| P3 | W1 Rate Limiter | 5 integration | New infrastructure, determinism risk |
| P4 | W2 Search/Filter | 8 integration | Many edge cases (empty, pagination, sort order) |
| P5 | W5 Monitoring | 3 integration | Simple parameter pass-through |
| P6 | W6 Graph Detail | 3 integration | Isolated, low complexity |
| P7 | W7 Dashboard | 2 integration | Simple COUNT queries |
