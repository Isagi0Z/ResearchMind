# Phase 4C — Execution Plan

## 1. Scope Definition

Phase 4C targets **8 implementation workstreams** derived from architecture gaps and deferred items identified during Phase 4A/4B remediation:

| # | Workstream | Priority | Est. Effort |
|---|-----------|----------|-------------|
| W1 | Rate Limiting — activate `RateLimitMiddleware` | High | 1 day |
| W2 | Pagination, Search & Sort on `/api/v1/documents` | High | 2 days |
| W3 | User history endpoints — `/api/v1/query/history`, `/api/v1/reviews/history` | High | 2 days |
| W4 | Role-Based Access Control (RBAC) on existing routes | High | 1.5 days |
| W5 | Monitoring `/api/v1/monitoring/metrics` — filter parameter support | Medium | 1 day |
| W6 | Graph `/api/v1/graph/node/{id}` — real detail endpoint | Medium | 1 day |
| W7 | Dashboard `/api/v1/dashboard/summary` — DB-backed real counts | Medium | 1.5 days |
| W8 | Token security — migrate `localStorage` → `httpOnly` cookie | Low | 2 days |

Total estimated: **12 days** (sequential) or **8 days** (parallel W2/W3/W4/W5).

---

## 2. W1 — Rate Limiting (High Priority)

**Current State:** `RateLimitMiddleware` at `backend/api/middleware.py:61-69` is a no-op pass-through with a stub comment.

**Implementation:**
- Add an in-memory sliding-window rate limiter keyed on `X-Forwarded-For` (or `request.client.host`).
- Configurable via `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS` env vars (default: 1000 req / 60s).
- Store the window counter in `request.state` to avoid module-level mutable globals.
- Must be deterministic: do NOT use `time.monotonic()` as primary key — use a fixed-window boundary (floor division of timestamp by window size).

**Files to modify:** `backend/api/middleware.py`, `backend/api/config.py`
**Files to create:** `backend/api/rate_limiter.py`
**Tests:** Add 5+ tests in `test_middleware.py` for rate limit exceeded, reset, config variations.

**Risk:** Low — isolated, no upstream/downstream dependencies.

---

## 3. W2 — Documents Search, Pagination & Sort (High Priority)

**Current State:** `GET /api/v1/documents` at `backend/api/routes/documents.py:9-39` returns all docs from `CorpusManager.store().list_all()` with client-side pagination. The backend **does not** support `searchQuery`, `sortBy`, or `filters` parameters.

**Implementation:**
- Add `searchQuery`, `sortBy`, `sortDirection`, `filters[yearRange,authors,source,status]` as optional query parameters.
- Perform filtering/sorting in-memory since `InMemoryDocumentStore` is the current store.
- Preserve the `PaginatedDocumentsResponse` schema shape.
- Log the search/filter params for observability.

**Files to modify:** `backend/api/routes/documents.py`, `backend/api/schemas/documents.py`
**Files to create:** None
**Tests:** 8+ tests in `test_routes.py` (or a new `test_documents.py`) for filter, sort, pagination edge cases.

**Risk:** Low — isolated route change.

---

## 4. W3 — User History Endpoints (High Priority)

**Current State:** No dedicated history endpoints exist. Query and Review persistence is already implemented in `POST /api/v1/query/answer` (`query.py:83-91`) and `POST /api/v1/reviews/generate` (`review.py:32-39`) — they write to `queries` and `reviews` tables when a user is authenticated.

**Implementation:**
- Add `GET /api/v1/query/history` returning paginated queries for the current user (descending by `created_at`).
- Add `GET /api/v1/reviews/history` returning paginated reviews for the current user (descending by `created_at`).
- Both require `get_current_active_user` dependency (not optional).
- Response schemas: `QueryHistoryResponse`, `ReviewHistoryResponse`.

**Files to modify:** `backend/api/routes/query.py`, `backend/api/routes/review.py`, `backend/api/schemas/query.py`, `backend/api/schemas/review.py`
**Files to create:** None
**Tests:** 6+ tests exercising history with various user states.

**Risk:** Medium — depends on auth being fully operational (confirmed in Phase 4B).

---

## 5. W4 — Role-Based Access Control (RBAC) (High Priority)

**Current State:** `require_role()` dependency exists at `backend/api/dependencies.py:92-97` but is not applied to any route. All routes use `get_current_user` or `get_current_user_optional`.

**Implementation:**
- Apply `require_role("admin")` to:
  - `GET /api/v1/monitoring` (all monitoring endpoints)
  - `GET /api/v1/monitoring/metrics`
- Apply `require_role("user")` to:
  - `POST /api/v1/query/answer` (write operations)
  - `POST /api/v1/reviews/generate`
  - `POST /api/v1/documents` (future)
- Leave read-only routes (dashboard, graph, health) as `get_current_user_optional`.

**Files to modify:** `backend/api/routes/monitoring.py`, `backend/api/routes/query.py`, `backend/api/routes/review.py`
**Tests:** 4+ tests verifying 403 on insufficient role.

**Risk:** Low-Medium — needs careful ordering to not break existing optional-auth patterns.

---

## 6. W5 — Monitoring Filter Parameters (Medium Priority)

**Current State:** `GET /api/v1/monitoring/metrics` at `monitoring.py:13-15` ignores query params. The frontend sends `timeRange` at `frontend/services/monitoring.ts:6` but it is discarded.

**Implementation:**
- Accept optional `timeRange` query param, pass it to `generate_mock_monitoring()` (already supports this: `mock_graph.py:92` uses `time_range_str` as CRC32 seed).
- Add optional `moduleId` filter to filter health status per module.

**Files to modify:** `backend/api/routes/monitoring.py`
**Tests:** 3+ tests verifying different timeRange values produce different deterministic snapshots.

**Risk:** Low — trivially isolated.

---

## 7. W6 — Graph Node Detail (Medium Priority)

**Current State:** `GET /api/v1/graph/node/{id}` at `graph.py:15-17` returns a stub "Not implemented detail" message.

**Implementation:**
- When a valid `id` (matching `node-{i}` pattern from mock data) is provided, search the mock graph and return the full `GraphNodeResponse`.
- Return 404 if not found.
- Since `generate_mock_graph()` regenerates on every call, cache or compute a lookup dict per request.

**Files to modify:** `backend/api/routes/graph.py`
**Tests:** 3+ tests for valid ID, invalid ID, edge cases.

**Risk:** Low — isolated.

---

## 8. W7 — Dashboard Real Counts (Medium Priority)

**Current State:** `GET /api/v1/dashboard/summary` at `dashboard.py:11-28` returns hardcoded fallback values (`graphNodes: 89000`, `graphEdges: 215000`). The real `corpus.corpus().statistics` is attempted but falls back to hardcoded values.

**Implementation:**
- Query `SELECT COUNT(*)` from `documents`, `reviews` tables for total documents and total reviews.
- For `entityClusters`, `graphNodes`, `graphEdges`, compute from the in-memory corpus store if available; otherwise fall back to current hardcoded values.

**Files to modify:** `backend/api/routes/dashboard.py`
**Tests:** 2+ tests verifying counts with populated vs empty DB.

**Risk:** Low — isolated.

---

## 9. W8 — Token Cookie Security (Low Priority)

**Current State:** `frontend/lib/api-client.ts` stores tokens in `localStorage` via `getTokens()`/`setTokens()`. The login page writes them; the API client reads them.

**Implementation:**
- Add a `POST /api/v1/auth/login/cookie` endpoint that sets `httpOnly`, `Secure`, `SameSite=Strict` cookies.
- Add a CSRF token endpoint `GET /api/v1/auth/csrf`.
- Frontend: create a new `cookie-api-client.ts` wrapper that sends credentials: 'include' and reads CSRF header.
- Phase 4C scope: **design + document only**; actual implementation deferred to Phase 5 unless explicitly requested.

**Files to modify (design only):** `backend/api/routes/auth.py`, `frontend/lib/api-client.ts`
**Tests:** Documented but not implemented.
**Decision: DEFER — document in risk register only.**

---

## 10. Sequence Dependencies

```
W1 ──┐
      ├── W4 ──┐
W2 ──┘        │
W3 ───────────┘
W5 ──┐
W6 ──┤
W7 ──┘
W8 — Deferred
```

- W1, W2, W5, W6, W7 are fully independent — can be implemented in parallel.
- W3 depends on auth flows being stable (confirmed in Phase 4B).
- W4 depends on W3 routes being finalized (to apply roles correctly).
- W8 is deferred.

**Recommended parallel tracks:**
- **Track A:** W1 + W2 + W5 (3 devs, ~2 days)
- **Track B:** W6 + W7 (1 dev, ~2 days)
- **Track C:** W3 (1 dev, ~2 days) → W4 (same dev, ~1.5 days)
- **Track D:** W8 design doc (1 dev, ~1 day — non-blocking)

---

## 11. Verification Gates

| Gate | Criteria | Exit |
|------|----------|------|
| G1 | All 8 workstreams implemented per spec | Code review sign-off |
| G2 | Backend `pytest` 122/122 + new tests all pass | CI pass |
| G3 | Frontend `vitest run` 256/256 + new tests all pass | CI pass |
| G4 | Manual smoke test of all 12 frontend routes | QA sign-off |
| G5 | Determinism sweep — no new `uuid4`/`datetime.now` in engine paths | Audit pass |
| G6 | No regressions in M1–M6 engine output | Determinism re-check |
