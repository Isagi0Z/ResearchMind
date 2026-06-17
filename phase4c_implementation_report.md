# Phase 4C — Implementation Report

## Scope Executed

| # | Workstream | Status | Files Modified | Files Created |
|---|---|---|---|---|
| W1 | Rate Limiting | ✅ Complete | `config.py`, `middleware.py`, `app.py` | `rate_limiter.py` |
| W2 | Documents Search, Pagination & Sort | ✅ Complete | `routes/documents.py` | — |
| W3 | User History Endpoints | ✅ Complete | `routes/query.py`, `routes/review.py`, `schemas/query.py`, `schemas/review.py` | — |
| W4 | RBAC (Monitoring Routes) | ✅ Complete | `routes/monitoring.py` | — |
| W5 | Monitoring Filter Parameters | ✅ Complete | `routes/monitoring.py` | — |
| W6 | Graph Node Detail Endpoint | ✅ Complete | `routes/graph.py` | — |
| W7 | Dashboard DB-Backed Counts | ✅ Complete | `routes/dashboard.py` | — |
| W8 | Token Cookie Security | ⏭️ Deferred | — | — |

## Files Changed

**12 files modified**, **1 file created**:

| File | Change |
|---|---|
| `backend/api/rate_limiter.py` | **NEW** — Sliding-window rate limiter with LRU eviction, fixed-window boundaries |
| `backend/api/config.py` | Added `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS` env vars |
| `backend/api/middleware.py` | Activated `RateLimitMiddleware` with real `RateLimiter` using `X-Forwarded-For` |
| `backend/api/app.py` | Passes `settings.RATE_LIMIT_*` to middleware constructor |
| `backend/api/routes/documents.py` | Added `searchQuery`, `sortBy`, `sortDirection` query params with in-memory filter/sort |
| `backend/api/routes/query.py` | Added `GET /query/history` endpoint; fixed `model_dump(mode='json')` for serialization |
| `backend/api/routes/review.py` | Added `GET /reviews/history` endpoint; fixed `request.topic` → `request.title` bug |
| `backend/api/routes/graph.py` | Real `GET /graph/node/{id}` — returns node data or 404 |
| `backend/api/routes/monitoring.py` | Added `timeRange` query param; applied `require_role("admin")` to both endpoints |
| `backend/api/routes/dashboard.py` | `GET /dashboard/summary` now queries DB for `SELECT COUNT(*)` from documents/reviews |
| `backend/api/schemas/query.py` | Added `QueryHistoryResponse` schema |
| `backend/api/schemas/review.py` | Added `ReviewHistoryResponse` schema |
| `backend/api/tests/test_stubs.py` | +17 new tests covering all 7 workstreams |

## Bugs Fixed

Two pre-existing bugs discovered and fixed during implementation:

1. **Query persistence serialization** (`routes/query.py:74-80`): `model_dump()` produced non-JSON-serializable `datetime` objects when persisting query results. Fixed by adding `mode='json'` to all `model_dump()` calls in `result_dump`.

2. **Review route field mismatch** (`routes/review.py:35-38`): Route used `request.topic` and `request.target_audience` which don't exist on `ReviewRequest` model (`researchmind/synthesis/models.py`). Fixed to use `request.title` and `request.metadata` respectively. This bug only manifested when an authenticated user generated a review (the auth-persist code path was never previously exercised by tests).

## Implementation Details

### W1 — Rate Limiter
- **Algorithm**: Fixed-window counter with LRU eviction at 10,000 keys
- **Key**: `X-Forwarded-For` header, falling back to `request.client.host`
- **Response**: HTTP 429 with JSON body `{"detail": "Rate limit exceeded. Try again later."}`
- **No non-determinism**: Uses `time.time() // window_seconds` for window boundary (deterministic per request within the same window)

### W2 — Documents Search
- In-memory filtering on `title` and `author full_name` (case-insensitive substring match)
- Supports `sortBy` `title`/`year`/`created_at` with `sortDirection` `asc`/`desc`

### W3 — History Endpoints
- `GET /api/v1/query/history` — Returns last 50 queries for authenticated user, ordered by `created_at` DESC
- `GET /api/v1/reviews/history` — Returns last 50 reviews for authenticated user, ordered by `created_at` DESC
- Both require `get_current_active_user` — 401 if not authenticated

### W4 — Monitoring RBAC
- Both `GET /api/v1/monitoring` and `GET /api/v1/monitoring/metrics` now require `require_role("admin")`
- Standard users get 403; unauthenticated get 401
- All other routes remain unchanged (query/review remain optional-auth per R07)

### W5 — Monitoring Filters
- `timeRange` query param (default `"24h"`) is passed through to `generate_mock_monitoring()`
- Different timeRange values produce different deterministic snapshots (CRC32-seeded)

### W6 — Graph Node Detail
- Looks up node by `id` in freshly generated mock graph
- Returns full `GraphNodeResponse` or 404

### W7 — Dashboard Counts
- Queries `SELECT COUNT(*) FROM documents` and `SELECT COUNT(*) FROM reviews` from the database
- Falls back to hardcoded values on error
- Entity clusters still use `CorpusManager.statistics` with fallback
