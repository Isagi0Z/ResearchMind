# Phase 5B Graph Audit — Data Source & Correctness

## Audit Scope

Verify that every graph endpoint returns data derived solely from the persisted corpus, with no synthetic or mock graph generation remaining in the request path.

## Endpoint Audit

### `GET /api/v1/graph`

| Aspect | Status | Detail |
|---|---|---|
| Real data | ✅ | Reads from `CorpusManager.get_documents()` → `InMemoryDocumentStore.get_batch()` |
| No mock fallback | ✅ | `generate_mock_graph()` removed; no conditional fallback |
| Node types | ✅ | `document` (from `RUOHeader.title/authors/publication_date`), `entity` (from `RUOEntity.text/confidence`) |
| Edge types | ✅ | `CO_OCCURS` (entity → parent document) |
| Filtering | ✅ | `nodeType` filter, `search` (title case-insensitive) |
| Pagination | ✅ | `offset`/`limit` (default 200, max 500, min 1) |
| Deterministic | ✅ | Grid-based position (col=index%10, row=index//10) |

### `GET /api/v1/graph/data`

| Aspect | Status | Detail |
|---|---|---|
| Real data | ✅ | Same `GraphService.get_graph()` as `/graph` |
| Redundant? | ⚠️ | Duplicate of `/graph`; kept for backward compatibility |

### `GET /api/v1/graph/node/{id}`

| Aspect | Status | Detail |
|---|---|---|
| Real data | ✅ | `GraphService.get_node()` reads real doc/entity by index |
| Doc nodes (`doc-{i}`) | ✅ | Returns title, authors, year from `RUOHeader` |
| Entity nodes (`ent-{i}-{j}`) | ✅ | Returns text, confidence, relatedDocuments from `RUOEntity` |
| 404 handling | ✅ | Unknown ID → `HTTPException(404)` |

## Data Correctness

### Document Nodes
- **ID format**: `doc-{index}` (index into `get_documents()` list)
- **Label**: `doc.header.title` (real title)
- **Authors**: `doc.header.authors[].full_name` (real author names)
- **Year**: Extracted from `doc.header.publication_date[:4]` (first 4 chars)
- **Position**: Deterministic grid (col = idx % 10, row = idx // 10)

### Entity Nodes
- **ID format**: `ent-{doc_idx}-{ent_idx}`
- **Label**: `entity.text` (real extracted entity text)
- **Confidence**: `entity.confidence` (real confidence score)
- **RelatedDocuments**: `1` (entity belongs to exactly one document)
- **Blank filter**: Entities with `text.strip() == ""` are skipped
- **Position**: Offset grid relative to parent document

### Edges
- **Type**: `CO_OCCURS` (entity co-occurs within a document)
- **Direction**: entity → document
- **Confidence**: Copied from entity's confidence score

## Remaining Concerns

| Issue | Severity | Note |
|---|---|---|
| No `theme` or `cluster` node types | Low | No persisted data source exists for these in current schema; custom renderers still present in frontend but never used |
| Dashboard graph stat counts still hardcoded | Low | `dashboard.py` has `graphNodes=89000`, `graphEdges=215000` — these are monitoring display numbers, not graph endpoint data |
| No total-count header in paginated responses | Medium | The API returns paginated slices but no `X-Total-Count` or total field; frontend pagination uses estimate |
| `limit=0` returns 422 | Low | Expected behavior (min 1), but could be more user-friendly |
