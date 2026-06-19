# Phase 5B Implementation Report — Graph Real Data

## Overview

Phase 5B replaces the remaining mock graph implementation with real, corpus-derived graph data. The graph is now built dynamically from persisted `RUODocument` data (titles, authors, entities, confidence scores) rather than from a deterministic synthetic generator.

## Backend Implementation

### Files Changed / Created

| File | Change |
|---|---|
| `backend/api/services/graph_service.py` | **New** — `GraphService` class that reads from `CorpusManager.get_documents()` and builds nodes/edges from real document and entity data |
| `backend/api/routes/graph.py` | Updated — All 3 endpoints (`GET /graph`, `GET /graph/data`, `GET /graph/node/{id}`) now use `GraphService` with `Depends(get_corpus_manager)` instead of `generate_mock_graph()` |
| `backend/api/dependencies.py` | Fixed — Removed invalid `store=` kwarg from `CorpusManager.from_documents()` call; removed unused `InMemoryDocumentStore` import |
| `backend/api/mock_data.py` | Fixed — Added valid `ComponentConfidence` entry to `RUOQuality.confidence.components`; added minimal `RUOSection` and `RUOChunk` to body to satisfy Pydantic `min_length=1` constraints |
| `backend/api/routes/documents.py` | Fixed — `corpus.store()` → `corpus.store` (property, not method) |
| `backend/api/mock_graph.py` | **Deleted** — No longer imported or used; `generate_mock_graph()` and `generate_mock_monitoring()` replaced by real services |

### Architecture

```
GET /api/v1/graph
  → GraphService.get_graph(nodeType, search, offset, limit)
    → CorpusManager.get_documents()   // returns all real RUODocuments
      → DocumentStore.get_batch(ids)  // lazy-loads from InMemoryDocumentStore
    → Builds nodes (document + entity types)
    → Builds edges (CO_OCCURS entity→document relationships)
    → Applies filters (nodeType, search)
    → Paginates (offset/limit, max 500)
```

### Graph Node Types

| Type | Source | Fields |
|---|---|---|
| `document` | `RUOHeader` | label, title, year, authors |
| `entity` | `RUOEntity` | label, confidence, relatedDocuments |

### Edge Types

| Type | Source | Description |
|---|---|---|
| `CO_OCCURS` | entity → parent document | Links each entity to its containing document |

### Deterministic Layout

Node positions are derived from an index-based grid (col = index % 10, row = index // 10). Entity nodes are offset slightly from their parent document. This ensures fully deterministic output — no random seeds or sunflower spirals.

## Frontend Implementation

### Files Changed / Created

| File | Change |
|---|---|
| `frontend/services/graph.ts` | Updated — `getGraphData()` now accepts optional `GraphQueryParams` (nodeType, search, offset, limit); added `getGraphNode()` |
| `frontend/features/graph/graph-hooks.ts` | Updated — `useGraphData()` forwards params to query key; added `useGraphNode()` |
| `frontend/features/graph/graph-store.ts` | Updated — Added `nodeTypeFilter`, `page`, and their setters;
| `frontend/features/graph/graph-explorer.tsx` | Rewritten — Server-side pagination + filtering; proper `LoadingState`, `ErrorState` (with retry button), `EmptyState` components; type filter dropdown; pagination bar |
| `frontend/features/graph/graph-search.tsx` | Updated — Server-side via store (no longer takes `data` prop or does client-side highlighting) |
| `frontend/features/graph/custom-nodes.tsx` | Updated — Removed client-side dimming/highlighting logic (search is now server-side) |

### State Handling

| State | UX |
|---|---|
| Loading | Full-height centered spinner with "Loading graph data..." text |
| Error | Centered error message with "Retry" button |
| Empty (no results) | "No graph data available" with suggestion to adjust filters |
| Empty (initial, no data) | Same empty state with search bar and filter visible |
| Success | Full graph canvas + sidebar + stats + pagination |

### Pagination

- Server-side: `offset`/`limit` params (default 200, max 500)
- Frontend: Page size 500, prev/next pagination bar at bottom center
- Filter type resets page to 0

### Filtering

- Server-side: `nodeType` (`document`/`entity`) and `search` (text, case-insensitive)
- Frontend: Debounced search bar (300ms) + type dropdown
- Reset page on filter change

## Mock Removal

- `backend/api/mock_graph.py` — Deleted entirely (no remaining imports)
- `backend/api/routes/graph.py` — No longer imports `generate_mock_graph`
- `frontend/` — No graph mock files exist (frontend always hits real backend)

## Files Not Modified

- Backend schemas (`graph.py`, `monitoring.py`) — unchanged
- Dashboard routes — unchanged (but note: `graphNodes`/`graphEdges` are still hardcoded in `dashboard.py`)
- Query and review systems — unchanged
- Auth and middleware — unchanged
