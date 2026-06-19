# Phase 5C Implementation Report — Documents Real Data

## Overview

Phase 5C replaces the remaining in-memory document mock implementation with real SQLAlchemy-persisted documents. Document listing, search, sort, and pagination now query the `corpus_documents` SQLAlchemy table instead of calling `store.list_all()` (which never existed on `DocumentStore` ABC).

## Backend Implementation

### New Files

| File | Description |
|---|---|
| `backend/db/models/corpus_document.py` | New SQLAlchemy model with columns: `ruo_id` (PK), `title`, `authors_json` (JSON list), `year`, `status`, `entity_count`, `source`, `created_at` |
| `backend/api/tests/test_documents.py` | 21 new tests covering listing, search, sort, pagination, detail |

### Modified Files

| File | Change |
|---|---|
| `backend/api/services/document_service.py` | **Rewritten** — `DocumentService` with SQLAlchemy-backed `list_documents()`, `get_document()`, `get_full_document()` methods. Seeds DB from `CorpusManager` on first query via `_ensure_seeded()`. Search uses `ILIKE` on title. Sort supports title, year, status, entity_count. Pagination via offset/limit. |
| `backend/api/routes/documents.py` | **Rewritten** — Both endpoints use `DocumentService` via `Depends(_get_document_service)` which injects `AsyncSession` + `CorpusManager`. No more `store.list_all()` (which was buggy). Detail endpoint merges `DocumentDetail` from DB with full `RUODocument` from CorpusManager. |
| `backend/api/schemas/documents.py` | **Rewritten** — `DocumentListItem` schema with typed fields (`ruo_id`, `title`, `authors: List[str]`, `year: Optional[int]`, `status`, `entity_count`, `source`). `DocumentDetail` schema with additional `abstract` and `pipeline_stages`. Both use `ConfigDict(from_attributes=True)`. |
| `backend/db/models/__init__.py` | Added `CorpusDocument` import |

### Architecture

```
Document List (GET /api/v1/documents)
  → DocumentService.list_documents()
    → _ensure_seeded() — lazy-seeds corpus_documents table from CorpusManager on first call
    → SQLAlchemy query: SELECT + WHERE (search) + ORDER BY (sort) + OFFSET/LIMIT (pagination)
    → Returns PaginatedDocumentsResponse with typed DocumentListItem[]

Document Detail (GET /api/v1/documents/{id})
  → DocumentService.get_document(id) — queries corpus_documents table
  → DocumentService.get_full_document(id) — fetches full RUODocument from CorpusManager store
  → Merges pipeline_stages and abstract into DocumentDetail
```

### Key Fixes

| Bug | Status |
|---|---|
| `store.list_all()` called on `DocumentStore` ABC which has no such method | ✅ Replaced with SQLAlchemy query |
| `PaginatedDocumentsResponse` used `List[Any]` | ✅ Replaced with `List[DocumentListItem]` |
| `DocumentService` was empty placeholder | ✅ Full implementation |
| Frontend `corpus.ts` dropped search/sort/filter params | ✅ All params now serialized |
| Pydantic class-based config deprecation | ✅ `ConfigDict(from_attributes=True)` |

## Frontend Implementation

### New Files

| File | Description |
|---|---|
| `frontend/types/document-list-item.ts` | `DocumentListItem` type matching backend schema |
| `frontend/tests/corpus/corpus-service.test.ts` | 5 tests for document service URL construction |

### Modified Files

| File | Change |
|---|---|
| `frontend/services/corpus.ts` | `getDocuments()` now sends `searchQuery`, `sortBy`, `sortDirection` params. Type changed from `RUODocument` to `DocumentListItem`. |
| `frontend/services/dashboard.ts` | `getRecentDocuments()` uses `DocumentListItem` instead of `RUODocument` |
| `frontend/features/corpus/corpus-manager.tsx` | Updated to use flat `DocumentListItem` fields (`ruo_id`, `title`, `authors[]`, `year`, `status`, `entity_count`) instead of nested RUODocument |
| `frontend/features/dashboard/recent-documents.tsx` | Updated to use flat `DocumentListItem` fields |
| `frontend/tests/corpus/corpus-manager.test.tsx` | Updated mock data to use flat shape |
| `frontend/tests/dashboard/recent-documents.test.tsx` | Updated mock data to use flat shape |

### Data Flow

```
CorpusManager.tsx  →  useDocuments(params)  →  getDocuments(params)
                                                   ↓
                                              GET /api/v1/documents?pageIndex=0&pageSize=50&searchQuery=...&sortBy=title&sortDirection=asc
                                                   ↓
                                              DocumentService → SQLAlchemy → corpus_documents table
                                                   ↓
                                              JSON: { data: [{ ruo_id, title, authors, year, status, entity_count, source }], total }
```

## Impact Analysis

| System | Affected? | Notes |
|---|---|---|
| Graph | ❌ No | Still uses `CorpusManager.get_documents()` via `GraphService` |
| Monitoring | ❌ No | Still uses direct SQLAlchemy aggregation queries |
| Auth | ❌ No | Unchanged |
| RBAC | ❌ No | Unchanged |
| Query | ❌ No | Still uses `CorpusManager` via `QueryEngine` |
| Reviews | ❌ No | Still uses `CorpusManager` via `ReviewOrchestrator` |
| Dashboard | ✅ Yes | Document summary cards now use new flat API response — tests updated |
