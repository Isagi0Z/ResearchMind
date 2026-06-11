# Corpus Graph -- Architecture & Design

> **Version:** 1.0  
> **Module:** M3-4  
> **Date:** 2026-06-10  

---

## 1. Overview

The Corpus Graph models the entire document corpus as a **directed multi-graph**:

- **Nodes** (`CorpusGraphNode`) represent individual `RUODocument` instances (or, in future, entity clusters, authors, or concepts).
- **Edges** (`CorpusGraphEdge`) represent semantic relationships (`DocumentRelation`) between nodes -- citation links, entity overlap, methodological dependence, claim support/contradiction, etc.
- **Paths** (`CorpusGraphPath`) encode ordered sequences of edges for provenance tracing and literature review workflows.

This module provides **schema only** -- the data models that define graph elements, query parameters, and result shapes. Builder logic, traversal algorithms, and graph construction from `CorpusManager` belong in the engine layer (not part of this document).

**Deterministic only** -- no LLMs, embeddings, vector databases, or external APIs.

---

## 2. Graph Model

### 2.1 Node Types

| `node_type`    | Semantics | Future Use |
|----------------|-----------|------------|
| `document`     | A single `RUODocument` -- the default and primary node type | -- |
| `author`       | An author entity aggregated across documents | Cross-document author disambiguation |
| `entity_cluster` | An `EntityCluster` (M3-2 output) spanning documents | Concept-level subgraph |
| `claim`        | A `RUOClaim` that appears in multiple documents | Claim-centric navigation |
| `concept`      | A higher-level topic or research direction | Topic modelling integration |

### 2.2 Edge Types

Edges use the existing `RelationType` enum (`ruo_enums.py`):

| `relation_type`    | Direction | Description |
|--------------------|-----------|-------------|
| `cites`            | Directed  | Document A cites Document B |
| `cited_by`         | Directed  | Inverse of `cites` |
| `supports`         | Directed  | A's claims/methods support B's findings |
| `contradicts`      | Directed  | A's findings contradict B's |
| `extends`          | Directed  | A extends B's methodology |
| `supersedes`       | Directed  | A supersedes B (newer/ more comprehensive) |
| `reproduces`       | Undirected | A reproduces B's results |
| `uses_method`      | Directed  | A uses a method described in B |
| `uses_dataset`     | Directed  | A uses a dataset introduced in B |
| `compares_with`    | Undirected | A and B are compared (shared entities / methods) |
| `reviews`          | Directed  | A is a review of B |
| `meta_analysis_includes` | Directed | A is a meta-analysis that includes B |
| `unknown`          | Undirected | Detected relation, type unclear |

---

## 3. Data Models

### 3.1 `CorpusGraphNode`

```python
class CorpusGraphNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    node_id: str
    node_type: str = "document"
    label: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: datetime | None = None
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `node_id` | `str` | Unique identifier (usually the document `ruo_id`) |
| `node_type` | `str` | One of `document`, `author`, `entity_cluster`, `claim`, `concept` |
| `label` | `str` | Human-readable label (e.g. document title) |
| `metadata` | `dict[str, Any]` | Arbitrary payload. Common keys for `document` nodes: `ruo_id`, `doi`, `year`, `authors`, `entity_count`, `claim_count`, `triple_count`, `overall_confidence`, `research_field` |
| `weight` | `float [0, 1]` | Node importance weight (default 1.0). Used by traversal algorithms for prioritisation |
| `created_at` | `datetime \| None` | When the underlying entity was created in the corpus |

**Valid `node_type` values** are enforced by a validator -- any value outside the known set raises `ValueError`.

### 3.2 `CorpusGraphEdge`

```python
class CorpusGraphEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    edge_id: str
    source_id: str
    target_id: str
    relation_type: RelationType
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    is_directed: bool = True
    detected_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `edge_id` | `str` | Unique edge identifier |
| `source_id` | `str` | `node_id` of the source node |
| `target_id` | `str` | `node_id` of the target node |
| `relation_type` | `RelationType` | The semantic type of the relation |
| `confidence` | `float [0, 1]` | Aggregate confidence for this edge |
| `evidence_ids` | `list[str]` | References to `RelationEvidence` identifiers from the Document Relation Engine |
| `weight` | `float [0, 1]` | Edge weight for graph algorithms (default 1.0) |
| `is_directed` | `bool` | Whether the edge is directional (default `True`) |
| `detected_at` | `datetime \| None` | When the relation was detected |
| `metadata` | `dict[str, Any]` | Additional payload (e.g. `{"citation_count": 5}`) |

### 3.3 `CorpusGraphPath`

```python
class CorpusGraphPath(BaseModel):
    edges: list[CorpusGraphEdge]
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    total_weight: float = Field(default=0.0, ge=0.0)
    length: int = Field(default=0, ge=0)
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `edges` | `list[CorpusGraphEdge]` | Ordered edge sequence forming the path |
| `confidence` | `float [0, 1]` | Aggregate path confidence (computed by traversal -- e.g. minimum or product of edge confidences) |
| `total_weight` | `float` | Sum of edge weights along the path |
| `length` | `int` | Number of edges (validated against `len(edges)`) |

**Convenience methods:**

- `source_id() -> str | None` -- `node_id` of the first node
- `target_id() -> str | None` -- `node_id` of the last node
- `node_ids() -> list[str]` -- All unique node IDs in traversal order

**Validation:**
- `length` must equal `len(edges)`.

### 3.4 `CorpusGraphStatistics`

```python
class CorpusGraphStatistics(BaseModel):
    total_nodes: int = Field(default=0, ge=0)
    total_edges: int = Field(default=0, ge=0)
    node_type_counts: dict[str, int] = Field(default_factory=dict)
    edge_type_counts: dict[str, int] = Field(default_factory=dict)
    average_degree: float = Field(default=0.0, ge=0.0)
    average_out_degree: float = Field(default=0.0, ge=0.0)
    average_in_degree: float = Field(default=0.0, ge=0.0)
    density: float = Field(default=0.0, ge=0.0, le=1.0)
    connected_components: int = Field(default=0, ge=0)
    largest_component_size: int = Field(default=0, ge=0)
    largest_component_edges: int = Field(default=0, ge=0)
    self_loops: int = Field(default=0, ge=0)
    avg_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    max_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
```

**Metrics:**

| Metric | Derivation |
|--------|-----------|
| `total_nodes` | `len(nodes)` |
| `total_edges` | `len(edges)` |
| `node_type_counts` | Counter over `node_type` values |
| `edge_type_counts` | Counter over `relation_type` values |
| `average_degree` | `2 * edges / nodes` (undirected) or `edges / nodes` (directed average) |
| `average_out_degree` | Mean out-degree across all nodes |
| `average_in_degree` | Mean in-degree across all nodes |
| `density` | `edges / (nodes * (nodes - 1))` for directed graphs |
| `connected_components` | Weakly connected components (BFS/union-find) |
| `largest_component_size` | Node count of the largest component |
| `largest_component_edges` | Edge count of the largest component |
| `self_loops` | Edges where `source_id == target_id` |
| `avg_confidence` | Mean of all edge `confidence` values |
| `min_confidence` | Minimum edge `confidence` |
| `max_confidence` | Maximum edge `confidence` |

### 3.5 `CorpusGraphQuery`

```python
class CorpusGraphQuery(BaseModel):
    node_ids: list[str] | None = None
    source_id: str | None = None
    target_id: str | None = None
    node_type: str | None = None
    relation_types: list[RelationType] | None = None
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    min_weight: float = Field(default=0.0, ge=0.0)
    max_depth: int = Field(default=3, ge=1, le=100)
    max_results: int = Field(default=100, ge=1, le=10000)
    label_contains: str | None = None
    metadata_filter: dict[str, Any] | None = None
    include_paths: bool = False
```

**Filter semantics:**

| Filter | Behaviour |
|--------|-----------|
| `node_ids` | Restrict to specific node IDs (exact match) |
| `source_id` | Only edges originating from this node |
| `target_id` | Only edges terminating at this node |
| `node_type` | Only nodes matching this type |
| `relation_types` | Only edges with one of the specified `RelationType` values |
| `min_confidence` | Exclude edges / paths below this confidence |
| `min_weight` | Exclude edges below this weight |
| `max_depth` | Maximum path length in edges (path-finding queries) |
| `max_results` | Cap on returned results |
| `label_contains` | Substring match on node `label` (case-insensitive) |
| `metadata_filter` | Key-value pairs that must be present in node/edge `metadata` |
| `include_paths` | If `True`, populate the `paths` field in the result |

### 3.6 `CorpusGraphResult`

```python
class CorpusGraphResult(BaseModel):
    nodes: list[CorpusGraphNode] = Field(default_factory=list)
    edges: list[CorpusGraphEdge] = Field(default_factory=list)
    paths: list[CorpusGraphPath] = Field(default_factory=list)
    total_nodes_found: int = Field(default=0, ge=0)
    total_edges_found: int = Field(default=0, ge=0)
    total_paths_found: int = Field(default=0, ge=0)
    query: CorpusGraphQuery | None = None
    statistics: CorpusGraphStatistics | None = None
```

**Fields:**

| Field | Description |
|-------|-------------|
| `nodes` | Matching nodes (may be subset if paginated) |
| `edges` | Matching edges |
| `paths` | Matching paths (only when query `include_paths=True`) |
| `total_nodes_found` | Total count of matching nodes (for pagination) |
| `total_edges_found` | Total count of matching edges |
| `total_paths_found` | Total count of matching paths |
| `query` | The query that produced this result (audit trail) |
| `statistics` | Optional statistics computed over the result subgraph |

---

## 4. Relationship to Existing Modules

### 4.1 Input Sources

| Source Module | Produces | Consumed By |
|---------------|----------|-------------|
| M3-1 `CorpusManager` | `RUODocument` list, `corpus.indexes` | Node builder |
| M3-2 `EntityResolver` | `ResolutionResult` (clusters) | Entity-cluster nodes |
| M3-3 `DocumentRelationEngine` | `DocumentRelationResult` (relations + evidence) | Edge builder |

### 4.2 Layer Separation

```
┌──────────────────────────────────────────────────────────────┐
│                    Corpus Graph Engine                        │
│  (builder, traversal, query -- not part of this document)      │
├──────────────────────────────────────────────────────────────┤
│                    Corpus Graph Schema                        │
│  Node, Edge, Path, Statistics, Query, Result                  │
├──────────────────────┬───────────────────────┬────────────────┤
│  CorpusManager       │  EntityResolver       │  DocumentRel… │
│  (M3-1)              │  (M3-2)               │  (M3-3)        │
└──────────────────────┴───────────────────────┴────────────────┘
```

### 4.3 Data Flow

```
RUODocument[] ──→ CorpusGraphNode[] (one per document)
                       │
ResolutionResult ──────┤ (entity clusters → future node types)
                       │
DocumentRelation[] ────┼──→ CorpusGraphEdge[]
                       │
                       ▼
                  CorpusGraph
              (nodes + edges dicts)
                       │
                       ▼
              CorpusGraphQuery ──→ CorpusGraphResult
```

---

## 5. Edge Cases

| Case | Handling |
|------|----------|
| Empty corpus | `CorpusGraphStatistics` returns all zeros |
| Single document | No edges, one node, density = 0.0 |
| No relations between docs | Nodes present, edges empty |
| Duplicate edge (same source, target, type) | Deduplication by `edge_id`; builder layer can merge evidence |
| Self-loop edge | Counted in `self_loops` metric; allowed at schema level |
| Unknown `RelationType` | `relation_type` uses the existing enum -- no new values |
| Missing optional fields (`detected_at`, `created_at`) | `None` -- no validation failure |
| Very large metadata payload | No size limit enforced at schema level; builder should truncate |
| Case-insensitive `label_contains` | Implemented at query-execution layer |

---

## 6. Performance Considerations

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| Node lookup by ID | O(1) | Dict-backed |
| Edge lookup by ID | O(1) | Dict-backed |
| Filter by `source_id` / `target_id` | O(e) | Linear scan or adjacency index |
| BFS/DFS traversal | O(v + e) | Standard graph traversal |
| Shortest path (unweighted) | O(v + e) | BFS |
| Connected components | O(v + e) | Union-find or BFS |
| Graph statistics | O(v + e) | Single pass |
| Filter by `metadata_filter` | O(n · k) | k = keys per filter |

**For very large corpora (>10k nodes):**
- Pre-compute adjacency lists (in-edge and out-edge indexes)
- Store degree counts in node metadata to avoid recomputation
- Use indexed field scans for common filter patterns (by `relation_type`, by `confidence` threshold)

---

## 7. Future Extensions

| Feature | Required Model Changes |
|---------|----------------------|
| Author nodes | Add `"author"` to `VALID_NODE_TYPES`; populate from `RUOHeader.authors` |
| Entity-cluster nodes | Add `"entity_cluster"`; populate from `ResolutionResult.clusters` |
| Claim nodes | Add `"claim"`; populate from `RUOClaim` |
| Time-weighted edges | Add `temporal_weight` field to `CorpusGraphEdge` |
| Paginated results | Add `offset` / `limit` to `CorpusGraphQuery` |
| Aggregation queries | Add `aggregate` field to `CorpusGraphQuery` (count by type, etc.) |
| Subgraph export | Add `format` parameter (JSON, GraphML, CSV) |

---

## 8. File Locations

| Artifact | Path |
|----------|------|
| Data models | `src/researchmind/corpus/graph.py` |
| Module exports | `src/researchmind/corpus/__init__.py` |
| Architecture document | `architecture/corpus_graph.md` |
