# Phase 5C Test Report — Document Testing

## Backend Tests

### New: `backend/api/tests/test_documents.py` (21 tests)

| Test Class | Tests | Description |
|---|---|---|
| `TestDocumentListing` | 5 | Default pagination, items returned, response shape, size ceiling, zero size |
| `TestDocumentSearch` | 4 | Title fragment, no results, empty query, case-insensitive |
| `TestDocumentSort` | 5 | Title asc/desc, year asc/desc, sort with search |
| `TestDocumentPagination` | 4 | Offset, page sizes, beyond total, consistency |
| `TestDocumentDetail` | 3 | By ID, not found (404), all fields present |

### Existing: `backend/api/tests/test_stubs.py` — document-related tests (6 tests)

| Test | Status | Notes |
|---|---|---|
| `test_implemented_routes[GET-/api/v1/documents]` | ✅ | Route returns 200 |
| `test_documents_default_pagination` | ✅ | Now returns real data (was previously masked by `list_all()` bug) |
| `test_documents_search_query` | ✅ | Real search via SQL |
| `test_documents_sort_by_title` | ✅ | Real sort via SQL |
| `test_documents_pagination_offset` | ✅ | Real pagination via SQL |
| `test_documents_search_no_results` | ✅ | 0 results for impossible query |

### Count
- Backend total: **189 tests** (was 168 prior to Phase 5C)
- Document coverage: **27 tests** (21 new + 6 existing)

## Frontend Tests

### New: `frontend/tests/corpus/corpus-service.test.ts` (5 tests)

| Test | Description |
|---|---|
| URL construction with page params | `/api/v1/documents?pageIndex=0&pageSize=10` |
| Search query parameter | `searchQuery=biology` appended |
| Sort parameters | `sortBy=title&sortDirection=asc` appended |
| Response shape | `data` and `total` properties |
| DocumentListItem shape | `ruo_id`, `title`, `authors`, `year`, `status`, `entity_count` |

### Updated Tests

| File | Tests | Change |
|---|---|---|
| `corpus-manager.test.tsx` | 9 | Mock data changed from nested RUODocument to flat DocumentListItem |
| `recent-documents.test.tsx` | 2 | Mock data changed to flat shape |

### Count
- Frontend total: **290 tests** (was 285 prior to Phase 5C)
- New document coverage: **5 tests**

## Test Summary

```
Backend:  189 tests — all passed (including 21 new document tests)
Frontend: 290 tests — all passed (including 5 new document service tests)
Build:    npm run build — compiled successfully
DB:       alembic current — 3a1b2c3d4e5f (head)
```
