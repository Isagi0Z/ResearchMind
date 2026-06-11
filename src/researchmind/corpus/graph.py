"""Corpus-level graph models and builder for RUOCorpus.

Represents a corpus of documents as a directed multi-graph where:
- Each :class:`RUODocument` becomes a :class:`CorpusGraphNode`
- Each :class:`DocumentRelation` becomes a :class:`CorpusGraphEdge`
- Query, traverse, and analyse the graph through these models.
"""

from __future__ import annotations

import re
import uuid
from collections import defaultdict, deque
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from researchmind.corpus.entity_resolution import ResolutionResult
from researchmind.models.ruo import DocumentRelation, RUOClaim, RUODocument, RUOEntity
from researchmind.models.ruo_enums import RelationType

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_NODE_TYPES = frozenset({
    "document",
    "author",
    "entity_cluster",
    "claim",
    "concept",
})

_EDGE_TYPE_PATTERN = re.compile(r"^[a-z][a-z_]*$")


# ---------------------------------------------------------------------------
# CorpusGraphNode
# ---------------------------------------------------------------------------


class CorpusGraphNode(BaseModel):
    """A single node in the corpus-level document graph.

    Each node typically wraps a single :class:`RUODocument`, but the model
        is general enough to represent other node types
    (entity clusters, authors, concepts) for future extension.
    """

    model_config = ConfigDict(frozen=True)

    node_id: str
    """Unique node identifier (e.g. the document ``ruo_id``)."""

    node_type: str = "document"
    """Semantic type of the node: ``document``, ``author``,
    ``entity_cluster``, ``claim``, ``concept``."""

    label: str
    """Human-readable label (e.g. the document title)."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Arbitrary key-value payload attached to the node.

    For document nodes typical keys include:
        - ``ruo_id`` (str)
        - ``doi`` (str | None)
        - ``year`` (int | None)
        - ``authors`` (list[str])
        - ``entity_count`` (int)
        - ``claim_count`` (int)
        - ``triple_count`` (int)
        - ``overall_confidence`` (float)
        - ``research_field`` (str | None)
    """

    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    """Node importance weight (default 1.0)."""

    created_at: datetime | None = None
    """When the underlying document / entity was created in the corpus."""

    @field_validator("node_type")
    @classmethod
    def _validate_node_type(cls, v: str) -> str:
        if v not in VALID_NODE_TYPES:
            raise ValueError(
                f"node_type must be one of {sorted(VALID_NODE_TYPES)}, "
                f"got {v!r}"
            )
        return v


# ---------------------------------------------------------------------------
# CorpusGraphEdge
# ---------------------------------------------------------------------------


class CorpusGraphEdge(BaseModel):
    """A directed edge between two :class:`CorpusGraphNode` instances.

    Edges are typed by :class:`RelationType` and carry a confidence score
    and optional evidence identifiers for traceability.
    """

    model_config = ConfigDict(frozen=True)

    edge_id: str
    """Unique edge identifier."""

    source_id: str
    """``node_id`` of the source (from) node."""

    target_id: str
    """``node_id`` of the target (to) node."""

    relation_type: RelationType
    """The semantic relation type (cites, supports, contradicts, …)."""

    confidence: float = Field(ge=0.0, le=1.0)
    """Aggregate confidence for this edge in ``[0, 1]``."""

    evidence_ids: list[str] = Field(default_factory=list)
    """References to :class:`RelationEvidence` identifiers from the
    Document Relation Engine output."""

    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    """Edge weight used by graph algorithms (default 1.0)."""

    is_directed: bool = True
    """Whether the edge represents a directional relationship."""

    detected_at: datetime | None = None
    """When the relation was detected."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Additional key-value payload (e.g. ``{"citation_count": 5}``)."""


# ---------------------------------------------------------------------------
# CorpusGraphPath
# ---------------------------------------------------------------------------


class CorpusGraphPath(BaseModel):
    """A path through the corpus graph — a sequence of edges connecting
    a source node to a target node."""

    edges: list[CorpusGraphEdge]
    """Ordered list of edges forming the path."""

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    """Aggregate path confidence (e.g. minimum edge confidence)."""

    total_weight: float = Field(default=0.0, ge=0.0)
    """Sum of edge weights along the path."""

    length: int = Field(default=0, ge=0)
    """Number of edges in the path."""

    @field_validator("length")
    @classmethod
    def _length_matches_edges(cls, v: int, info: Any) -> int:
        edges = info.data.get("edges", [])
        if v != len(edges):
            raise ValueError(
                f"length ({v}) must equal len(edges) ({len(edges)})"
            )
        return v

    def source_id(self) -> str | None:
        """Return the ``node_id`` of the first node in the path."""
        if not self.edges:
            return None
        return self.edges[0].source_id

    def target_id(self) -> str | None:
        """Return the ``node_id`` of the last node in the path."""
        if not self.edges:
            return None
        return self.edges[-1].target_id

    def node_ids(self) -> list[str]:
        """Return all unique node IDs visited along the path, in order."""
        if not self.edges:
            return []
        ids: list[str] = [self.edges[0].source_id]
        for e in self.edges:
            if ids[-1] != e.source_id:
                ids.append(e.source_id)
            ids.append(e.target_id)
        return ids


# ---------------------------------------------------------------------------
# CorpusGraphStatistics
# ---------------------------------------------------------------------------


class CorpusGraphStatistics(BaseModel):
    """Aggregate metrics computed over a corpus graph."""

    total_nodes: int = Field(default=0, ge=0)
    total_edges: int = Field(default=0, ge=0)

    node_type_counts: dict[str, int] = Field(default_factory=dict)
    """Distribution of nodes by ``node_type``."""

    edge_type_counts: dict[str, int] = Field(default_factory=dict)
    """Distribution of edges by ``RelationType`` value."""

    average_degree: float = Field(default=0.0, ge=0.0)
    """Mean (in-degree + out-degree) across all nodes."""

    average_out_degree: float = Field(default=0.0, ge=0.0)
    """Mean out-degree across all nodes."""

    average_in_degree: float = Field(default=0.0, ge=0.0)
    """Mean in-degree across all nodes."""

    density: float = Field(default=0.0, ge=0.0, le=1.0)
    """Graph density: ``edges / (nodes * (nodes - 1))`` for directed graphs."""

    connected_components: int = Field(default=0, ge=0)
    """Number of weakly connected components."""

    largest_component_size: int = Field(default=0, ge=0)
    """Number of nodes in the largest weakly connected component."""

    largest_component_edges: int = Field(default=0, ge=0)
    """Number of edges in the largest weakly connected component."""

    self_loops: int = Field(default=0, ge=0)
    """Number of edges whose ``source_id == target_id`` (should be 0)."""

    avg_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    """Mean confidence across all edges."""

    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    """Minimum edge confidence."""

    max_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    """Maximum edge confidence."""


# ---------------------------------------------------------------------------
# CorpusGraphQuery
# ---------------------------------------------------------------------------


class CorpusGraphQuery(BaseModel):
    """A filter / traversal specification for querying the corpus graph."""

    node_ids: list[str] | None = None
    """If set, restrict to these specific node IDs."""

    source_id: str | None = None
    """If set, only consider edges originating from this node."""

    target_id: str | None = None
    """If set, only consider edges terminating at this node."""

    node_type: str | None = None
    """Filter nodes by ``node_type`` (e.g. ``document``)."""

    relation_types: list[RelationType] | None = None
    """If set, only consider edges with one of these relation types."""

    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    """Minimum edge / path confidence threshold."""

    min_weight: float = Field(default=0.0, ge=0.0)
    """Minimum edge weight threshold."""

    max_depth: int = Field(default=3, ge=1, le=100)
    """Maximum path length (edges) for path-finding queries."""

    max_results: int = Field(default=100, ge=1, le=10000)
    """Maximum number of results to return."""

    label_contains: str | None = None
    """If set, filter nodes whose ``label`` contains this substring
    (case-insensitive)."""

    metadata_filter: dict[str, Any] | None = None
    """If set, only include nodes/edges whose ``metadata`` contains
    all specified key-value pairs."""

    include_paths: bool = False
    """If ``True``, path-finding results include the full edge sequence."""


# ---------------------------------------------------------------------------
# CorpusGraphResult
# ---------------------------------------------------------------------------


class CorpusGraphResult(BaseModel):
    """The result of executing a :class:`CorpusGraphQuery`."""

    nodes: list[CorpusGraphNode] = Field(default_factory=list)
    """Nodes matching the query filters."""

    edges: list[CorpusGraphEdge] = Field(default_factory=list)
    """Edges matching the query filters."""

    paths: list[CorpusGraphPath] = Field(default_factory=list)
    """Paths found (only populated when :attr:`CorpusGraphQuery.include_paths`
    is ``True``)."""

    total_nodes_found: int = Field(default=0, ge=0)
    """Total number of matching nodes (may exceed ``len(nodes)`` if
    paginated)."""

    total_edges_found: int = Field(default=0, ge=0)
    """Total number of matching edges (may exceed ``len(edges)`` if
    paginated)."""

    total_paths_found: int = Field(default=0, ge=0)
    """Total number of matching paths."""

    query: CorpusGraphQuery | None = None
    """The query that produced this result (for audit / re-execution)."""

    statistics: CorpusGraphStatistics | None = None
    """Optional graph statistics computed over the result subgraph."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _node_dict(self) -> dict[str, CorpusGraphNode]:
        return {n.node_id: n for n in self.nodes}

    def _edge_dict(self) -> dict[str, CorpusGraphEdge]:
        return {e.edge_id: e for e in self.edges}

    def _build_adjacency(
        self,
    ) -> dict[str, list[tuple[str, CorpusGraphEdge]]]:
        """Build an undirected adjacency list from the edge list."""
        adj: dict[str, list[tuple[str, CorpusGraphEdge]]] = defaultdict(list)
        for e in self.edges:
            adj[e.source_id].append((e.target_id, e))
            adj[e.target_id].append((e.source_id, e))
        return dict(adj)

    # ------------------------------------------------------------------
    # get_neighbors
    # ------------------------------------------------------------------

    def get_neighbors(
        self, node_id: str, depth: int = 1
    ) -> CorpusGraphResult:
        """BFS outward from *node_id* up to *depth* hops."""
        if node_id not in self._node_dict():
            return CorpusGraphResult(nodes=[], edges=[])
        depth = max(1, depth)
        adj = self._build_adjacency()
        nd = self._node_dict()
        ed = self._edge_dict()
        visited_nodes: set[str] = {node_id}
        visited_edges: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])
        while queue:
            current, d = queue.popleft()
            if d >= depth:
                continue
            for neighbor, edge in adj.get(current, []):
                if edge.edge_id not in visited_edges:
                    visited_edges.add(edge.edge_id)
                if neighbor not in visited_nodes:
                    visited_nodes.add(neighbor)
                    queue.append((neighbor, d + 1))
        return CorpusGraphResult(
            nodes=[nd[nid] for nid in visited_nodes if nid in nd],
            edges=[ed[eid] for eid in visited_edges if eid in ed],
            total_nodes_found=len(visited_nodes),
            total_edges_found=len(visited_edges),
        )

    # ------------------------------------------------------------------
    # shortest_path
    # ------------------------------------------------------------------

    def shortest_path(
        self, source_id: str, target_id: str
    ) -> CorpusGraphPath | None:
        """BFS for the shortest (fewest edges) undirected path."""
        nd = self._node_dict()
        if source_id not in nd or target_id not in nd:
            return None
        if source_id == target_id:
            return CorpusGraphPath(edges=[], total_weight=0.0)
        adj = self._build_adjacency()
        visited: set[str] = {source_id}
        parent: dict[str, tuple[str | None, CorpusGraphEdge | None]] = {
            source_id: (None, None),
        }
        queue: deque[str] = deque([source_id])
        while queue:
            current = queue.popleft()
            for neighbor, edge in adj.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    parent[neighbor] = (current, edge)
                    if neighbor == target_id:
                        edges: list[CorpusGraphEdge] = []
                        node = target_id
                        while node != source_id:
                            _p, e = parent[node]
                            if e is not None:
                                edges.append(e)
                            node = _p if _p is not None else source_id
                        edges.reverse()
                        total_w = sum(e.weight for e in edges)
                        return CorpusGraphPath(
                            edges=edges, total_weight=total_w,
                            length=len(edges),
                        )
                    queue.append(neighbor)
        return None

    # ------------------------------------------------------------------
    # find_paths
    # ------------------------------------------------------------------

    def find_paths(
        self, source_id: str, target_id: str, max_depth: int = 5
    ) -> list[CorpusGraphPath]:
        """DFS enumeration of all paths up to *max_depth*."""
        nd = self._node_dict()
        if source_id not in nd or target_id not in nd:
            return []
        if source_id == target_id:
            return [CorpusGraphPath(edges=[], total_weight=0.0)]
        adj = self._build_adjacency()
        paths: list[CorpusGraphPath] = []
        visited: set[str] = set()

        def _dfs(
            current: str,
            target: str,
            path_edges: list[CorpusGraphEdge],
            depth: int,
        ) -> None:
            if depth > max_depth:
                return
            if current == target and path_edges:
                total_w = sum(e.weight for e in path_edges)
                paths.append(
                    CorpusGraphPath(
                        edges=list(path_edges),
                        total_weight=total_w,
                        length=len(path_edges),
                    )
                )
                return
            visited.add(current)
            for neighbor, edge in adj.get(current, []):
                if neighbor not in visited:
                    path_edges.append(edge)
                    _dfs(neighbor, target, path_edges, depth + 1)
                    path_edges.pop()
            visited.discard(current)

        _dfs(source_id, target_id, [], 0)
        paths.sort(key=lambda p: (len(p.edges), -p.confidence))
        return paths

    # ------------------------------------------------------------------
    # connected_components
    # ------------------------------------------------------------------

    def connected_components(self) -> list[CorpusGraphResult]:
        """Return each weakly connected component as a separate result."""
        adj = self._build_adjacency()
        nd = self._node_dict()
        ed = self._edge_dict()
        visited: set[str] = set()
        components: list[CorpusGraphResult] = []
        for nid in self._node_dict():
            if nid in visited:
                continue
            comp_nodes: set[str] = set()
            comp_edge_ids: set[str] = set()
            queue: deque[str] = deque([nid])
            while queue:
                current = queue.popleft()
                if current in visited:
                    continue
                visited.add(current)
                comp_nodes.add(current)
                for neighbor, edge in adj.get(current, []):
                    comp_edge_ids.add(edge.edge_id)
                    if neighbor not in visited:
                        queue.append(neighbor)
            if not comp_nodes:
                comp_nodes.add(nid)
            components.append(
                CorpusGraphResult(
                    nodes=[nd[n] for n in comp_nodes if n in nd],
                    edges=[ed[e] for e in comp_edge_ids if e in ed],
                    total_nodes_found=len(comp_nodes),
                    total_edges_found=len(comp_edge_ids),
                )
            )
        components.sort(key=lambda c: len(c.nodes), reverse=True)
        return components

    # ------------------------------------------------------------------
    # subgraph
    # ------------------------------------------------------------------

    def subgraph(self, node_ids: set[str]) -> CorpusGraphResult:
        """Extract the induced subgraph for a set of node IDs."""
        nd = self._node_dict()
        nodes = [nd[nid] for nid in node_ids if nid in nd]
        edge_ids: set[str] = set()
        for e in self.edges:
            if e.source_id in node_ids and e.target_id in node_ids:
                edge_ids.add(e.edge_id)
        ed = self._edge_dict()
        return CorpusGraphResult(
            nodes=nodes,
            edges=[ed[eid] for eid in edge_ids],
            total_nodes_found=len(nodes),
            total_edges_found=len(edge_ids),
        )

    # ------------------------------------------------------------------
    # query_nodes
    # ------------------------------------------------------------------

    def query_nodes(self, query: CorpusGraphQuery) -> CorpusGraphResult:
        """Filter nodes by query criteria, include touching edges."""
        nodes = list(self.nodes)
        if query.node_ids:
            idset = set(query.node_ids)
            nodes = [n for n in nodes if n.node_id in idset]
        if query.node_type is not None:
            nodes = [n for n in nodes if n.node_type == query.node_type]
        if query.label_contains is not None:
            pat = query.label_contains.lower()
            nodes = [n for n in nodes if pat in n.label.lower()]
        if query.metadata_filter:
            nodes = [
                n for n in nodes
                if all(
                    n.metadata.get(k) == v
                    for k, v in query.metadata_filter.items()
                )
            ]
        if query.min_confidence > 0.0:
            nodes = [n for n in nodes if n.weight >= query.min_confidence]
        nodes = sorted(
            nodes, key=lambda n: n.weight, reverse=True
        )[: query.max_results]
        node_ids = {n.node_id for n in nodes}
        edges = [
            e for e in self.edges
            if e.source_id in node_ids or e.target_id in node_ids
        ]
        return CorpusGraphResult(
            nodes=nodes,
            edges=edges,
            total_nodes_found=len(nodes),
            total_edges_found=len(edges),
            query=query,
        )

    # ------------------------------------------------------------------
    # query_edges
    # ------------------------------------------------------------------

    def query_edges(self, query: CorpusGraphQuery) -> CorpusGraphResult:
        """Filter edges by query criteria, include endpoint nodes."""
        edges = list(self.edges)
        if query.relation_types is not None:
            rset = set(query.relation_types)
            edges = [e for e in edges if e.relation_type in rset]
        if query.source_id is not None:
            edges = [e for e in edges if e.source_id == query.source_id]
        if query.target_id is not None:
            edges = [e for e in edges if e.target_id == query.target_id]
        if query.min_confidence > 0.0:
            edges = [e for e in edges if e.confidence >= query.min_confidence]
        if query.min_weight > 0.0:
            edges = [e for e in edges if e.weight >= query.min_weight]
        if query.metadata_filter:
            edges = [
                e for e in edges
                if all(
                    e.metadata.get(k) == v
                    for k, v in query.metadata_filter.items()
                )
            ]
        edges = sorted(
            edges, key=lambda e: e.confidence, reverse=True
        )[: query.max_results]
        edge_node_ids: set[str] = set()
        for e in edges:
            edge_node_ids.add(e.source_id)
            edge_node_ids.add(e.target_id)
        nd = self._node_dict()
        nodes = [nd[nid] for nid in edge_node_ids if nid in nd]
        return CorpusGraphResult(
            nodes=nodes,
            edges=edges,
            total_nodes_found=len(nodes),
            total_edges_found=len(edges),
            query=query,
        )


    # ------------------------------------------------------------------
    # compute_statistics
    # ------------------------------------------------------------------

    def compute_statistics(self) -> CorpusGraphStatistics:
        """Compute and return graph statistics over this result's nodes and edges."""
        return compute_graph_statistics(self.nodes, self.edges)

    # ------------------------------------------------------------------
    # top_entities
    # ------------------------------------------------------------------

    def top_entities(self, n: int = 10) -> list[CorpusGraphNode]:
        """Return top *n* entity-cluster nodes sorted by weight descending."""
        entities = sorted(
            (n for n in self.nodes if n.node_type == "entity_cluster"),
            key=lambda nd: nd.weight,
            reverse=True,
        )
        return entities[:n]

    # ------------------------------------------------------------------
    # top_documents
    # ------------------------------------------------------------------

    def top_documents(self, n: int = 10) -> list[CorpusGraphNode]:
        """Return top *n* document nodes sorted by weight descending."""
        docs = sorted(
            (n for n in self.nodes if n.node_type == "document"),
            key=lambda nd: nd.weight,
            reverse=True,
        )
        return docs[:n]

    # ------------------------------------------------------------------
    # top_predicates
    # ------------------------------------------------------------------

    def top_predicates(self, n: int = 10) -> list[tuple[str, int]]:
        """Return top *n* ``(relation_type_value, count)`` sorted by count descending."""
        counts: dict[str, int] = defaultdict(int)
        for e in self.edges:
            counts[e.relation_type.value] += 1
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_counts[:n]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def compute_graph_statistics(
    nodes: list[CorpusGraphNode],
    edges: list[CorpusGraphEdge],
) -> CorpusGraphStatistics:
    """Compute aggregate statistics over a list of nodes and edges."""
    n = len(nodes)
    e = len(edges)

    node_type_counts: dict[str, int] = defaultdict(int)
    for node in nodes:
        node_type_counts[node.node_type] += 1

    edge_type_counts: dict[str, int] = defaultdict(int)
    total_conf = 0.0
    min_conf = 1.0
    max_conf = 0.0
    self_loops = 0
    out_degree: dict[str, int] = defaultdict(int)
    in_degree: dict[str, int] = defaultdict(int)

    for edge in edges:
        edge_type_counts[edge.relation_type.value] += 1
        total_conf += edge.confidence
        min_conf = min(min_conf, edge.confidence)
        max_conf = max(max_conf, edge.confidence)
        if edge.source_id == edge.target_id:
            self_loops += 1
        out_degree[edge.source_id] += 1
        in_degree[edge.target_id] += 1

    avg_deg = (sum(out_degree.values()) + sum(in_degree.values())) / max(n, 1)
    avg_out = sum(out_degree.values()) / max(n, 1)
    avg_in = sum(in_degree.values()) / max(n, 1)
    density = min(e / max(n * (n - 1), 1), 1.0)
    avg_conf = total_conf / max(e, 1)
    if e == 0:
        min_conf = 0.0

    # Weakly connected components via union-find
    parent: dict[str, str] = {}
    def _find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x
    def _union(x: str, y: str) -> None:
        rx, ry = _find(x), _find(y)
        if rx != ry:
            parent[ry] = rx

    for node in nodes:
        parent[node.node_id] = node.node_id
    for edge in edges:
        _union(edge.source_id, edge.target_id)

    comp_sizes: dict[str, int] = defaultdict(int)
    for node in nodes:
        root = _find(node.node_id)
        comp_sizes[root] += 1

    components = len(comp_sizes)
    largest_size = max(comp_sizes.values()) if comp_sizes else 0

    if components > 0 and largest_size > 0:
        largest_root = max(comp_sizes, key=comp_sizes.get)
        largest_edges = sum(
            1 for edge in edges
            if _find(edge.source_id) == largest_root
        )
    else:
        largest_edges = 0

    return CorpusGraphStatistics(
        total_nodes=n,
        total_edges=e,
        node_type_counts=dict(node_type_counts),
        edge_type_counts=dict(edge_type_counts),
        average_degree=round(avg_deg, 4),
        average_out_degree=round(avg_out, 4),
        average_in_degree=round(avg_in, 4),
        density=round(density, 6),
        connected_components=components,
        largest_component_size=largest_size,
        largest_component_edges=largest_edges,
        self_loops=self_loops,
        avg_confidence=round(avg_conf, 4),
        min_confidence=round(min_conf, 4),
        max_confidence=round(max_conf, 4),
    )


# ---------------------------------------------------------------------------
# CorpusGraphBuilder
# ---------------------------------------------------------------------------


class CorpusGraphBuilder:
    """Builds a :class:`CorpusGraphResult` from documents, entity resolution,
    and document relations across 8 stages.

    Stages:
        1. Document nodes
        2. Canonical entity cluster nodes
        3. Document → entity-cluster edges
        4. Document → document relation edges
        5. Entity-cluster → entity-cluster co-occurrence edges
        6. Claim nodes
        7. Document → claim edges + cross-document claim-relation edges
        8. Deduplication
    """

    def __init__(
        self,
        resolution_result: ResolutionResult | None = None,
    ) -> None:
        self._resolution = resolution_result
        self._nodes: dict[str, CorpusGraphNode] = {}
        self._edges: dict[str, CorpusGraphEdge] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        documents: list[RUODocument],
        relations: list[DocumentRelation] | None = None,
    ) -> CorpusGraphResult:
        """Execute all 8 builder stages and return the result."""
        self._nodes.clear()
        self._edges.clear()
        self._documents = documents
        self._relations = relations or []

        self._stage_1_document_nodes()
        self._stage_2_entity_cluster_nodes()
        self._stage_3_document_entity_edges()
        self._stage_4_document_relation_edges()
        self._stage_5_entity_entity_edges()
        self._stage_6_claim_nodes()
        self._stage_7_claim_relation_edges()
        self._stage_8_deduplicate()

        stats = self._compute_statistics()
        return CorpusGraphResult(
            nodes=list(self._nodes.values()),
            edges=list(self._edges.values()),
            total_nodes_found=len(self._nodes),
            total_edges_found=len(self._edges),
            statistics=stats,
        )

    # ------------------------------------------------------------------
    # Stage 1: Document nodes
    # ------------------------------------------------------------------

    def _stage_1_document_nodes(self) -> None:
        for doc in self._documents:
            meta = doc.meta
            header = doc.header
            authors = [
                a.full_name if hasattr(a, "full_name") else str(a)
                for a in header.authors
            ] if header.authors else []
            year: int | None = None
            if header.publication_date:
                try:
                    year = int(str(header.publication_date)[:4])
                except (ValueError, TypeError):
                    year = None
            node = CorpusGraphNode(
                node_id=meta.ruo_id,
                node_type="document",
                label=header.title or meta.ruo_id,
                metadata={
                    "ruo_id": meta.ruo_id,
                    "doi": header.doi,
                    "year": year,
                    "authors": authors,
                    "entity_count": len(doc.entities),
                    "claim_count": len(doc.claims),
                    "triple_count": len(doc.triples),
                    "overall_confidence": (
                        doc.quality.overall_confidence
                        if doc.quality else 0.0
                    ),
                    "research_field": (
                        meta.research_fields[0]
                        if meta.research_fields else None
                    ),
                },
                weight=(
                    doc.quality.overall_confidence
                    if doc.quality else 1.0
                ),
                created_at=meta.created_at if hasattr(meta, "created_at") else None,
            )
            self._add_node(node)

    # ------------------------------------------------------------------
    # Stage 2: Canonical entity cluster nodes
    # ------------------------------------------------------------------

    def _stage_2_entity_cluster_nodes(self) -> None:
        if not self._resolution:
            return
        for cluster in self._resolution.clusters:
            ce = cluster.canonical_entity
            node = CorpusGraphNode(
                node_id=cluster.cluster_id,
                node_type="entity_cluster",
                label=ce.canonical_text,
                metadata={
                    "canonical_text": ce.canonical_text,
                    "label": ce.label.value if hasattr(ce.label, "value") else str(ce.label),
                    "confidence": ce.confidence,
                    "cluster_size": cluster.size,
                    "resolution_method": ce.resolution_method,
                    "entity_ids": ce.entity_ids,
                    "variants": ce.variants,
                },
                weight=ce.confidence,
            )
            self._add_node(node)

        # Build entity_id → cluster_node_id lookup for stage 3
        self._eid_to_cluster: dict[str, str] = {}
        for cluster in self._resolution.clusters:
            node_id = cluster.cluster_id
            for eid in cluster.canonical_entity.entity_ids:
                self._eid_to_cluster[eid] = node_id

    # ------------------------------------------------------------------
    # Stage 3: Document → entity-cluster edges
    # ------------------------------------------------------------------

    def _stage_3_document_entity_edges(self) -> None:
        if not self._resolution or not hasattr(self, "_eid_to_cluster"):
            return
        for doc in self._documents:
            doc_id = doc.meta.ruo_id
            for ent in doc.entities:
                cluster_id = self._eid_to_cluster.get(ent.entity_id)
                if cluster_id is None:
                    continue
                edge = CorpusGraphEdge(
                    edge_id=f"de_{uuid.uuid4().hex[:12]}",
                    source_id=doc_id,
                    target_id=cluster_id,
                    relation_type=RelationType.EXTENDS,
                    confidence=ent.confidence,
                    weight=ent.confidence,
                    is_directed=True,
                    metadata={"edge_kind": "doc_contains_entity", "entity_label": (
                        ent.label.value if hasattr(ent.label, "value") else str(ent.label)
                    )},
                )
                self._add_edge(edge)

    # ------------------------------------------------------------------
    # Stage 4: Document → document relation edges
    # ------------------------------------------------------------------

    def _stage_4_document_relation_edges(self) -> None:
        for rel in self._relations:
            edge = CorpusGraphEdge(
                edge_id=rel.relation_id,
                source_id=rel.source_ruo_id,
                target_id=rel.target_ruo_id,
                relation_type=rel.relation_type,
                confidence=rel.confidence,
                evidence_ids=list(rel.evidence_ids),
                weight=rel.confidence,
                is_directed=rel.is_directed,
                detected_at=rel.detected_at,
                metadata={"edge_kind": "doc_relation"},
            )
            self._add_edge(edge)

    # ------------------------------------------------------------------
    # Stage 5: Entity-cluster → entity-cluster co-occurrence edges
    # ------------------------------------------------------------------

    def _stage_5_entity_entity_edges(self) -> None:
        if not self._resolution or not hasattr(self, "_eid_to_cluster"):
            return
        # Build cluster_ids per document
        doc_clusters: dict[str, set[str]] = defaultdict(set)
        for doc in self._documents:
            doc_id = doc.meta.ruo_id
            for ent in doc.entities:
                cluster_id = self._eid_to_cluster.get(ent.entity_id)
                if cluster_id:
                    doc_clusters[doc_id].add(cluster_id)

        # For each doc with ≥2 clusters, create edges between all pairs
        seen_pairs: set[tuple[str, str]] = set()
        for doc_id, cluster_ids in doc_clusters.items():
            cids = sorted(cluster_ids)
            for i in range(len(cids)):
                for j in range(i + 1, len(cids)):
                    pair = (cids[i], cids[j])
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    edge = CorpusGraphEdge(
                        edge_id=f"ee_{uuid.uuid4().hex[:12]}",
                        source_id=cids[i],
                        target_id=cids[j],
                        relation_type=RelationType.COMPARES_WITH,
                        confidence=1.0,
                        weight=1.0,
                        is_directed=False,
                        metadata={
                            "edge_kind": "entity_co_occur",
                            "doc_id": doc_id,
                        },
                    )
                    self._add_edge(edge)

    # ------------------------------------------------------------------
    # Stage 6: Claim nodes
    # ------------------------------------------------------------------

    def _stage_6_claim_nodes(self) -> None:
        for doc in self._documents:
            doc_id = doc.meta.ruo_id
            for claim in doc.claims:
                node_id = f"cl_{doc_id}_{claim.claim_id}"
                node = CorpusGraphNode(
                    node_id=node_id,
                    node_type="claim",
                    label=claim.sentence[:120],
                    metadata={
                        "doc_id": doc_id,
                        "claim_id": claim.claim_id,
                        "claim_type": claim.claim_type.value if hasattr(claim.claim_type, "value") else str(claim.claim_type),
                        "confidence": claim.confidence,
                        "chunk_id": claim.chunk_id,
                        "section_id": claim.section_id,
                        "page": claim.page,
                        "normalized_statement": claim.normalized_statement,
                    },
                    weight=claim.confidence,
                )
                self._add_node(node)

    # ------------------------------------------------------------------
    # Stage 7: Document → claim + cross-document claim-relation edges
    # ------------------------------------------------------------------

    def _stage_7_claim_relation_edges(self) -> None:
        # Build doc_id → set of claim node_ids for quick lookup
        doc_claim_nodes: dict[str, dict[str, str]] = defaultdict(dict)
        for doc in self._documents:
            doc_id = doc.meta.ruo_id
            for claim in doc.claims:
                node_id = f"cl_{doc_id}_{claim.claim_id}"
                doc_claim_nodes[doc_id][claim.claim_id] = node_id

        # 7a: Document → claim edges
        for doc in self._documents:
            doc_id = doc.meta.ruo_id
            for claim in doc.claims:
                claim_node_id = f"cl_{doc_id}_{claim.claim_id}"
                edge = CorpusGraphEdge(
                    edge_id=f"dc_{uuid.uuid4().hex[:12]}",
                    source_id=doc_id,
                    target_id=claim_node_id,
                    relation_type=RelationType.SUPPORTS,
                    confidence=claim.confidence,
                    weight=claim.confidence,
                    is_directed=True,
                    metadata={"edge_kind": "doc_has_claim"},
                )
                self._add_edge(edge)

        # 7b: Cross-document claim → claim edges from DocumentRelation
        for rel in self._relations:
            if not rel.source_claim_id or not rel.target_claim_id:
                continue
            src_doc = rel.source_ruo_id
            tgt_doc = rel.target_ruo_id
            src_claim_node = doc_claim_nodes.get(src_doc, {}).get(rel.source_claim_id)
            tgt_claim_node = doc_claim_nodes.get(tgt_doc, {}).get(rel.target_claim_id)
            if src_claim_node is None or tgt_claim_node is None:
                continue
            edge = CorpusGraphEdge(
                edge_id=f"cc_{uuid.uuid4().hex[:12]}",
                source_id=src_claim_node,
                target_id=tgt_claim_node,
                relation_type=rel.relation_type,
                confidence=rel.confidence,
                evidence_ids=list(rel.evidence_ids),
                weight=rel.confidence,
                is_directed=rel.is_directed,
                detected_at=rel.detected_at,
                metadata={"edge_kind": "claim_relation"},
            )
            self._add_edge(edge)

    # ------------------------------------------------------------------
    # Stage 8: Deduplication
    # ------------------------------------------------------------------

    def _stage_8_deduplicate(self) -> None:
        # Node dedup: if two nodes share the same node_id, keep the one
        # with higher weight (first seen wins for equal weight).
        seen_nodes: dict[str, CorpusGraphNode] = {}
        for nid, node in self._nodes.items():
            existing = seen_nodes.get(nid)
            if existing is None or node.weight > existing.weight:
                seen_nodes[nid] = node
        self._nodes = seen_nodes

        # Edge dedup: if two edges share the same edge_id, keep the more
        # confident one.
        seen_edges: dict[str, CorpusGraphEdge] = {}
        for eid, edge in self._edges.items():
            existing = seen_edges.get(eid)
            if existing is None or edge.confidence > existing.confidence:
                seen_edges[eid] = edge
        self._edges = seen_edges

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_node(self, node: CorpusGraphNode) -> None:
        self._nodes[node.node_id] = node

    def _add_edge(self, edge: CorpusGraphEdge) -> None:
        self._edges[edge.edge_id] = edge

    def _compute_statistics(self) -> CorpusGraphStatistics:
        return compute_graph_statistics(
            list(self._nodes.values()),
            list(self._edges.values()),
        )
