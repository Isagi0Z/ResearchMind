# Phase 5C Documents Audit — Data Source & Correctness

## Audit Scope

Verify that every document endpoint returns data from the SQLAlchemy-persisted `corpus_documents` table, with no remaining in-memory mock data leaks.

## Endpoint Audit

### `GET /api/v1/documents`

| Aspect | Status | Detail |
|---|---|---|
| Persistence | ✅ | SQLAlchemy query on `corpus_documents` table |
| No mock fallback | ✅ | `store.list_all()` removed; `try/except` that masked the bug removed |
| Search | ✅ | `ILIKE` on title (case-insensitive) |
| Sort | ✅ | `title`, `year`, `status`, `entity_count` — asc/desc |
| Pagination | ✅ | `pageIndex`/`pageSize` with offset/limit |
| Response shape | ✅ | Typed `DocumentListItem[]` with all required fields |
| Default page size | ✅ | 10 |
| Max page size | ✅ | 1000 |

### `GET /api/v1/documents/{id}`

| Aspect | Status | Detail |
|---|---|---|
| Persistence | ✅ | Queries `corpus_documents` table for metadata |
| Full detail | ✅ | Merges `pipeline_stages` and `abstract` from `CorpusManager.store.get(ruo_id)` |
| 404 handling | ✅ | Returns `HTTPException(404)` when not found |

## Data Correctness

### DocumentListItem fields

| Field | Source | Description |
|---|---|---|
| `ruo_id` | `RUODocument.meta.ruo_id` | Primary identifier |
| `title` | `RUODocument.header.title` | Document title |
| `authors` | `RUODocument.header.authors[].full_name` | List of author names |
| `year` | `RUODocument.header.publication_date[:4]` | Publication year |
| `status` | `RUODocument.meta.pipeline_stages[-1]` | Final pipeline stage status |
| `entity_count` | `len(RUODocument.entities)` | Number of extracted entities |
| `source` | `RUODocument.header.venue` | Publication venue |

### Seeding Behavior

- First call to `list_documents()` triggers `_ensure_seeded()`
- Checks if `corpus_documents` table has rows
- If empty, loads all documents from `CorpusManager.get_documents()` and bulk-inserts
- Subsequent calls skip seeding
- If `CorpusManager` is unavailable, returns empty results

## Issues Found & Fixed

| Issue | Severity | Fix |
|---|---|---|
| `store.list_all()` called on `DocumentStore` ABC (doesn't exist) | **Critical** | Replaced with proper SQLAlchemy queries |
| Empty `DocumentService` placeholder | **High** | Full implementation with seeding + CRUD |
| `List[Any]` in response schema | **Medium** | Typed `DocumentListItem` + `DocumentDetail` |
| Frontend silently dropped search/sort params | **Medium** | All params now serialized to query string |
| Pydantic `class Config` deprecation | **Low** | Migrated to `ConfigDict` |
