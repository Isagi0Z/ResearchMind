"""In-memory Knowledge Graph for the Understanding Engine.

Builds a queryable graph from SemanticTriple, RUOEntity, RUOClaim, and
RUOChunk objects. Supports traversal, path finding, subgraph extraction,
and graph statistics — no LLMs, embeddings, or graph databases.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict, deque
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from researchmind.models.ruo import (
    RUOClaim,
    RUOEntity,
    RUOChunk,
    SemanticTriple,
)
from researchmind.understanding.fact_extractor import ExtractedFact

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_NODE_TYPES = frozenset({"entity", "claim", "chunk", "fact"})

# ---------------------------------------------------------------------------
# Graph element models
# ---------------------------------------------------------------------------


class GraphNode(BaseModel):
    node_id: str
    node_type: str
    label: str
    text: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("node_type")
    @classmethod
    def _validate_type(cls, v: str) -> str:
        if v not in VALID_NODE_TYPES:
            raise ValueError(f"node_type must be one of {sorted(VALID_NODE_TYPES)}")
        return v

    @field_validator("text")
    @classmethod
    def _text_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be empty or whitespace-only")
        return v


class GraphEdge(BaseModel):
    edge_id: str
    source_id: str
    target_id: str
    predicate: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_negated: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("predicate")
    @classmethod
    def _predicate_format(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z_]+", v):
            raise ValueError("predicate must be snake_case lowercase")
        return v


# ---------------------------------------------------------------------------
# Query models
# ---------------------------------------------------------------------------


class GraphPath(BaseModel):
    edges: list[GraphEdge]
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _compute_confidence(self) -> GraphPath:
        if self.edges:
            self.confidence = round(
                min(e.confidence for e in self.edges), 4
            )
        return self


class Subgraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphStatistics(BaseModel):
    total_nodes: int = 0
    total_edges: int = 0
    node_type_counts: dict[str, int] = Field(default_factory=dict)
    predicate_counts: dict[str, int] = Field(default_factory=dict)
    avg_degree: float = 0.0
    connected_components: int = 0
    density: float = 0.0
    entity_label_counts: dict[str, int] = Field(default_factory=dict)


class GraphQuery(BaseModel):
    node_type: str | None = None
    predicate: str | None = None
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    entity_label: str | None = None
    text_contains: str | None = None
    max_results: int = Field(default=100, ge=1, le=10000)


# ---------------------------------------------------------------------------
# Knowledge Graph
# ---------------------------------------------------------------------------


class KnowledgeGraph(BaseModel):
    nodes: dict[str, GraphNode] = Field(default_factory=dict)
    edges: dict[str, GraphEdge] = Field(default_factory=dict)

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        self.edges[edge.edge_id] = edge

    def has_node(self, node_id: str) -> bool:
        return node_id in self.nodes

    def get_node(self, node_id: str) -> GraphNode | None:
        return self.nodes.get(node_id)

    def get_edge(self, edge_id: str) -> GraphEdge | None:
        return self.edges.get(edge_id)

    def node_count(self) -> int:
        return len(self.nodes)

    def edge_count(self) -> int:
        return len(self.edges)

    def _build_adjacency(self) -> dict[str, list[tuple[str, str, GraphEdge]]]:
        adj: dict[str, list[tuple[str, str, GraphEdge]]] = defaultdict(list)
        for e in self.edges.values():
            adj[e.source_id].append((e.target_id, e.predicate, e))
            adj[e.target_id].append((e.source_id, e.predicate, e))
        return dict(adj)

    def get_neighbors(self, node_id: str, depth: int = 1) -> Subgraph:
        if node_id not in self.nodes:
            return Subgraph(nodes=[], edges=[])
        depth = max(1, depth)
        adj = self._build_adjacency()
        visited_nodes: set[str] = {node_id}
        visited_edges: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])
        while queue:
            current, d = queue.popleft()
            if d >= depth:
                continue
            for neighbor, _pred, edge in adj.get(current, []):
                if edge.edge_id not in visited_edges:
                    visited_edges.add(edge.edge_id)
                if neighbor not in visited_nodes:
                    visited_nodes.add(neighbor)
                    queue.append((neighbor, d + 1))
        return Subgraph(
            nodes=[self.nodes[nid] for nid in visited_nodes if nid in self.nodes],
            edges=[self.edges[eid] for eid in visited_edges if eid in self.edges],
        )

    def shortest_path(self, source_id: str, target_id: str) -> GraphPath | None:
        if source_id not in self.nodes or target_id not in self.nodes:
            return None
        if source_id == target_id:
            return GraphPath(edges=[])
        adj = self._build_adjacency()
        visited: set[str] = {source_id}
        parent: dict[str, tuple[str | None, GraphEdge | None]] = {
            source_id: (None, None)
        }
        queue: deque[str] = deque([source_id])
        while queue:
            current = queue.popleft()
            for neighbor, _pred, edge in adj.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    parent[neighbor] = (current, edge)
                    if neighbor == target_id:
                        edges: list[GraphEdge] = []
                        node = target_id
                        while node != source_id:
                            _p, e = parent[node]
                            if e is not None:
                                edges.append(e)
                            node = _p if _p is not None else source_id
                        edges.reverse()
                        return GraphPath(edges=edges)
                    queue.append(neighbor)
        return None

    def find_paths(
        self, source_id: str, target_id: str, max_depth: int = 5
    ) -> list[GraphPath]:
        if source_id not in self.nodes or target_id not in self.nodes:
            return []
        if source_id == target_id:
            return [GraphPath(edges=[])]
        adj = self._build_adjacency()
        paths: list[GraphPath] = []
        visited: set[str] = set()

        def _dfs(current: str, target: str, path_edges: list[GraphEdge], depth: int) -> None:
            if depth > max_depth:
                return
            if current == target and path_edges:
                paths.append(GraphPath(edges=list(path_edges)))
                return
            visited.add(current)
            for neighbor, _pred, edge in adj.get(current, []):
                if neighbor not in visited:
                    path_edges.append(edge)
                    _dfs(neighbor, target, path_edges, depth + 1)
                    path_edges.pop()
            visited.discard(current)

        _dfs(source_id, target_id, [], 0)
        paths.sort(key=lambda p: (len(p.edges), -p.confidence))
        return paths

    def get_subgraph(self, node_ids: set[str]) -> Subgraph:
        nodes = [self.nodes[nid] for nid in node_ids if nid in self.nodes]
        edge_ids: set[str] = set()
        for e in self.edges.values():
            if e.source_id in node_ids and e.target_id in node_ids:
                edge_ids.add(e.edge_id)
        return Subgraph(
            nodes=nodes,
            edges=[self.edges[eid] for eid in edge_ids],
        )

    def query(self, q: GraphQuery) -> Subgraph:
        nodes = list(self.nodes.values())
        if q.node_type is not None:
            nodes = [n for n in nodes if n.node_type == q.node_type]
        if q.entity_label is not None:
            nodes = [
                n for n in nodes
                if n.metadata.get("entity_label") == q.entity_label
            ]
        if q.text_contains is not None:
            pattern = q.text_contains.lower()
            nodes = [n for n in nodes if pattern in n.text.lower()]
        if q.min_confidence > 0.0:
            nodes = [n for n in nodes if n.confidence >= q.min_confidence]
        nodes = sorted(nodes, key=lambda n: n.confidence, reverse=True)[:q.max_results]
        node_ids = {n.node_id for n in nodes}
        edges = [
            e for e in self.edges.values()
            if e.source_id in node_ids or e.target_id in node_ids
        ]
        return Subgraph(nodes=nodes, edges=edges)

    def get_neighbor_edges(self, node_id: str) -> list[GraphEdge]:
        return [
            e for e in self.edges.values()
            if e.source_id == node_id or e.target_id == node_id
        ]

    def get_connected_components(self) -> list[Subgraph]:
        adj = self._build_adjacency()
        visited: set[str] = set()
        components: list[Subgraph] = []
        for nid in self.nodes:
            if nid in visited:
                continue
            component_nodes: set[str] = set()
            component_edge_ids: set[str] = set()
            queue: deque[str] = deque([nid])
            while queue:
                current = queue.popleft()
                if current in visited:
                    continue
                visited.add(current)
                component_nodes.add(current)
                for neighbor, _pred, edge in adj.get(current, []):
                    component_edge_ids.add(edge.edge_id)
                    if neighbor not in visited:
                        queue.append(neighbor)
            if not component_nodes:
                component_nodes.add(nid)
            components.append(Subgraph(
                nodes=[self.nodes[n] for n in component_nodes
                       if n in self.nodes],
                edges=[self.edges[e] for e in component_edge_ids
                       if e in self.edges],
            ))
        components.sort(key=lambda c: len(c.nodes), reverse=True)
        return components

    def get_statistics(self) -> GraphStatistics:
        total_nodes = len(self.nodes)
        total_edges = len(self.edges)
        node_type_counts: dict[str, int] = defaultdict(int)
        predicate_counts: dict[str, int] = defaultdict(int)
        entity_label_counts: dict[str, int] = defaultdict(int)
        for n in self.nodes.values():
            node_type_counts[n.node_type] += 1
            if n.node_type == "entity":
                lbl = n.metadata.get("entity_label", "unknown")
                entity_label_counts[lbl] += 1
        for e in self.edges.values():
            predicate_counts[e.predicate] += 1
        total_degree = 0
        adj = self._build_adjacency()
        for nid in self.nodes:
            total_degree += len(adj.get(nid, []))
        avg_degree = round(total_degree / total_nodes, 4) if total_nodes > 0 else 0.0
        components = self.get_connected_components()
        max_possible = total_nodes * (total_nodes - 1) / 2
        density = round(total_edges / max_possible, 6) if max_possible > 0 else 0.0
        return GraphStatistics(
            total_nodes=total_nodes,
            total_edges=total_edges,
            node_type_counts=dict(node_type_counts),
            predicate_counts=dict(predicate_counts),
            avg_degree=avg_degree,
            connected_components=len(components),
            density=density,
            entity_label_counts=dict(entity_label_counts),
        )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


class KnowledgeGraphBuilder:
    def __init__(self) -> None:
        self.graph = KnowledgeGraph()
        self._edge_counter = 0

    def _next_edge_id(self) -> str:
        self._edge_counter += 1
        return f"edge_{self._edge_counter:04d}"

    def add_entities(self, entities: list[RUOEntity]) -> None:
        for ent in entities:
            self.graph.add_node(GraphNode(
                node_id=ent.entity_id,
                node_type="entity",
                label=ent.label.value if hasattr(ent.label, "value") else str(ent.label),
                text=ent.text,
                confidence=ent.confidence,
                metadata={
                    "entity_label": ent.label.value if hasattr(ent.label, "value") else str(ent.label),
                    "chunk_id": ent.chunk_id,
                    "source": ent.source,
                    "normalized_id": ent.normalized_id,
                },
            ))

    def add_claims(self, claims: list[RUOClaim]) -> None:
        for claim in claims:
            self.graph.add_node(GraphNode(
                node_id=claim.claim_id,
                node_type="claim",
                label=claim.claim_type.value if hasattr(claim.claim_type, "value") else str(claim.claim_type),
                text=claim.sentence,
                confidence=claim.confidence,
                metadata={
                    "claim_type": claim.claim_type.value if hasattr(claim.claim_type, "value") else str(claim.claim_type),
                    "chunk_id": claim.chunk_id,
                    "section_id": claim.section_id,
                    "canonical_label": claim.canonical_label.value if hasattr(claim.canonical_label, "value") else str(claim.canonical_label),
                },
            ))

    def add_chunks(self, chunks: list[RUOChunk]) -> None:
        for chunk in chunks:
            display_text = chunk.text[:200] if len(chunk.text) > 200 else chunk.text
            self.graph.add_node(GraphNode(
                node_id=chunk.chunk_id,
                node_type="chunk",
                label="chunk",
                text=display_text,
                confidence=chunk.extraction_confidence,
                metadata={
                    "section_id": chunk.section_id,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "paragraph_index": chunk.paragraph_index,
                    "word_count": chunk.word_count,
                },
            ))

    def add_facts(self, facts: list[ExtractedFact]) -> None:
        for fact in facts:
            self.graph.add_node(GraphNode(
                node_id=fact.fact_id,
                node_type="fact",
                label=fact.fact_type.value if hasattr(fact.fact_type, "value") else str(fact.fact_type),
                text=fact.value,
                confidence=fact.confidence,
                metadata={
                    "fact_type": fact.fact_type.value if hasattr(fact.fact_type, "value") else str(fact.fact_type),
                    "source_type": fact.source_type,
                    "source_id": fact.source_id,
                    "section_id": fact.section_id,
                    "chunk_id": fact.chunk_id,
                },
            ))

    def add_triples_as_edges(self, triples: list[SemanticTriple]) -> None:
        for triple in triples:
            self.graph.add_edge(GraphEdge(
                edge_id=self._next_edge_id(),
                source_id=triple.subject_id,
                target_id=triple.object_id,
                predicate=triple.predicate,
                confidence=triple.confidence,
                is_negated=triple.is_negated,
                metadata={
                    "triple_id": triple.triple_id,
                    "chunk_id": triple.chunk_id,
                },
            ))

    def _add_entity_chunk_edges(
        self, entities: list[RUOEntity], chunks: list[RUOChunk],
    ) -> None:
        chunk_ids = {c.chunk_id for c in chunks}
        for ent in entities:
            if ent.chunk_id in chunk_ids:
                self.graph.add_edge(GraphEdge(
                    edge_id=self._next_edge_id(),
                    source_id=ent.entity_id,
                    target_id=ent.chunk_id,
                    predicate="appears_in",
                    confidence=ent.confidence,
                    metadata={"relation": "entity_in_chunk"},
                ))
                self.graph.add_edge(GraphEdge(
                    edge_id=self._next_edge_id(),
                    source_id=ent.chunk_id,
                    target_id=ent.entity_id,
                    predicate="contains_entity",
                    confidence=ent.confidence,
                    metadata={"relation": "chunk_has_entity"},
                ))

    def _add_claim_chunk_edges(
        self, claims: list[RUOClaim], chunks: list[RUOChunk],
    ) -> None:
        chunk_ids = {c.chunk_id for c in chunks}
        for claim in claims:
            if claim.chunk_id in chunk_ids:
                self.graph.add_edge(GraphEdge(
                    edge_id=self._next_edge_id(),
                    source_id=claim.claim_id,
                    target_id=claim.chunk_id,
                    predicate="appears_in",
                    confidence=claim.confidence,
                    metadata={"relation": "claim_in_chunk"},
                ))
                self.graph.add_edge(GraphEdge(
                    edge_id=self._next_edge_id(),
                    source_id=claim.chunk_id,
                    target_id=claim.claim_id,
                    predicate="contains_claim",
                    confidence=claim.confidence,
                    metadata={"relation": "chunk_has_claim"},
                ))

    def _add_entity_claim_edges(
        self, entities: list[RUOEntity], claims: list[RUOClaim],
    ) -> None:
        for claim in claims:
            claim_lower = claim.sentence.lower()
            for ent in entities:
                if (
                    ent.text.lower() in claim_lower
                    and ent.chunk_id == claim.chunk_id
                ):
                    self.graph.add_edge(GraphEdge(
                        edge_id=self._next_edge_id(),
                        source_id=ent.entity_id,
                        target_id=claim.claim_id,
                        predicate="mentioned_in",
                        confidence=round(ent.confidence * claim.confidence, 4),
                        metadata={"relation": "entity_in_claim"},
                    ))

    def _add_fact_entity_edges(
        self, facts: list[ExtractedFact], entities: list[RUOEntity],
    ) -> None:
        for fact in facts:
            fact_value_lower = fact.value.lower()
            for ent in entities:
                if ent.text.lower() in fact_value_lower:
                    self.graph.add_edge(GraphEdge(
                        edge_id=self._next_edge_id(),
                        source_id=fact.fact_id,
                        target_id=ent.entity_id,
                        predicate="references",
                        confidence=round(fact.confidence * ent.confidence, 4),
                        metadata={"relation": "fact_references_entity"},
                    ))

    def build(
        self,
        entities: list[RUOEntity] | None = None,
        claims: list[RUOClaim] | None = None,
        chunks: list[RUOChunk] | None = None,
        facts: list[ExtractedFact] | None = None,
        triples: list[SemanticTriple] | None = None,
    ) -> KnowledgeGraph:
        entities_list = entities or []
        claims_list = claims or []
        chunks_list = chunks or []
        facts_list = facts or []
        triples_list = triples or []

        self.add_entities(entities_list)
        self.add_claims(claims_list)
        self.add_chunks(chunks_list)
        self.add_facts(facts_list)
        self.add_triples_as_edges(triples_list)
        self._add_entity_chunk_edges(entities_list, chunks_list)
        self._add_claim_chunk_edges(claims_list, chunks_list)
        self._add_entity_claim_edges(entities_list, claims_list)
        self._add_fact_entity_edges(facts_list, entities_list)

        return self.graph


def build_knowledge_graph(
    entities: list[RUOEntity] | None = None,
    claims: list[RUOClaim] | None = None,
    chunks: list[RUOChunk] | None = None,
    facts: list[ExtractedFact] | None = None,
    triples: list[SemanticTriple] | None = None,
) -> KnowledgeGraph:
    builder = KnowledgeGraphBuilder()
    return builder.build(
        entities=entities,
        claims=claims,
        chunks=chunks,
        facts=facts,
        triples=triples,
    )
