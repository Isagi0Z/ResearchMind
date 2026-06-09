"""Tests for the in-memory Knowledge Graph module.

Covers graph model validation, traversal (neighbors, paths, subgraph),
querying, statistics, builder integration, and edge cases.
Target: 50+ tests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from researchmind.models.enums import ClaimType, EntityLabel, ExtractionMethod
from researchmind.models.ruo import (
    RUOClaim,
    RUOEntity,
    RUOChunk,
    SemanticTriple,
)
from researchmind.understanding.fact_extractor import ExtractedFact, FactType
from researchmind.understanding.knowledge_graph import (
    GraphEdge,
    GraphNode,
    GraphPath,
    GraphQuery,
    GraphStatistics,
    KnowledgeGraph,
    KnowledgeGraphBuilder,
    Subgraph,
    VALID_NODE_TYPES,
    build_knowledge_graph,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 9, tzinfo=timezone.utc)


def _entity(
    eid: str = "ent_001",
    text: str = "GAN",
    label: EntityLabel = EntityLabel.METHOD,
    chunk_id: str = "chunk_001",
    conf: float = 0.85,
) -> RUOEntity:
    return RUOEntity(
        entity_id=eid,
        text=text,
        label=label,
        chunk_id=chunk_id,
        sentence=f"We use {text}.",
        confidence=conf,
        source="test",
    )


def _claim(
    cid: str = "claim_001",
    sentence: str = "GAN achieves state-of-the-art results.",
    chunk_id: str = "chunk_001",
    section_id: str = "sec_001",
    ctype: ClaimType = ClaimType.STATISTICAL,
    conf: float = 0.80,
) -> RUOClaim:
    return RUOClaim(
        claim_id=cid,
        sentence=sentence,
        chunk_id=chunk_id,
        section_id=section_id,
        canonical_label="results",
        claim_type=ctype,
        matched_patterns=["state_of_art"],
        confidence=conf,
        page=3,
        evidence_chain_id="ec_001",
    )


def _chunk(
    cid: str = "chunk_001",
    text: str = "GAN achieves state-of-the-art results on ImageNet.",
    section_id: str = "sec_001",
    conf: float = 0.90,
) -> RUOChunk:
    return RUOChunk(
        chunk_id=cid,
        text=text,
        word_count=len(text.split()),
        section_id=section_id,
        canonical_label="results",
        page_start=3,
        page_end=3,
        paragraph_index=0,
        reading_order=0,
        extraction_method=ExtractionMethod.GROBID,
        extraction_confidence=conf,
    )


def _fact(
    fid: str = "fact_001",
    ftype: FactType = FactType.METHOD,
    value: str = "GAN",
    conf: float = 0.85,
) -> ExtractedFact:
    return ExtractedFact(
        fact_id=fid,
        fact_type=ftype,
        value=value,
        confidence=conf,
        source_type="entity",
        source_id="ent_001",
        section_id="sec_001",
        chunk_id="chunk_001",
        context_sentence="We use GAN.",
        evidence_text="We use GAN.",
    )


def _triple(
    tid: str = "triple_001",
    subj_id: str = "ent_001",
    subj_text: str = "GAN",
    pred: str = "evaluated_on",
    obj_id: str = "ent_002",
    obj_text: str = "ImageNet",
    conf: float = 0.80,
    chunk_id: str = "chunk_001",
) -> SemanticTriple:
    return SemanticTriple(
        triple_id=tid,
        subject_id=subj_id,
        subject_text=subj_text,
        predicate=pred,
        object_id=obj_id,
        object_text=obj_text,
        confidence=conf,
        chunk_id=chunk_id,
    )


def _graph_node(
    nid: str = "n_001",
    ntype: str = "entity",
    label: str = "method",
    text: str = "GAN",
    conf: float = 1.0,
    meta: dict[str, Any] | None = None,
) -> GraphNode:
    return GraphNode(
        node_id=nid,
        node_type=ntype,
        label=label,
        text=text,
        confidence=conf,
        metadata=meta or {},
    )


def _graph_edge(
    eid: str = "e_001",
    src: str = "n_001",
    tgt: str = "n_002",
    pred: str = "uses",
    conf: float = 1.0,
) -> GraphEdge:
    return GraphEdge(
        edge_id=eid,
        source_id=src,
        target_id=tgt,
        predicate=pred,
        confidence=conf,
    )


def _small_graph() -> KnowledgeGraph:
    """A -> B -> C  and  A -> D"""
    g = KnowledgeGraph()
    for nid, text in [("A", "NodeA"), ("B", "NodeB"), ("C", "NodeC"), ("D", "NodeD")]:
        g.add_node(_graph_node(nid=nid, text=text))
    g.add_edge(_graph_edge(eid="e1", src="A", tgt="B", pred="connects"))
    g.add_edge(_graph_edge(eid="e2", src="B", tgt="C", pred="connects"))
    g.add_edge(_graph_edge(eid="e3", src="A", tgt="D", pred="connects"))
    return g


# ===================================================================
# GraphNode validation
# ===================================================================


class TestGraphNode:
    def test_valid_node(self):
        n = _graph_node()
        assert n.node_id == "n_001"
        assert n.node_type == "entity"
        assert n.text == "GAN"

    def test_invalid_node_type(self):
        with pytest.raises(ValidationError):
            _graph_node(ntype="invalid_type")

    def test_empty_text(self):
        with pytest.raises(ValidationError):
            _graph_node(text="   ")

    def test_whitespace_text(self):
        with pytest.raises(ValidationError):
            _graph_node(text="\t\n")

    def test_all_valid_node_types(self):
        for t in sorted(VALID_NODE_TYPES):
            n = _graph_node(ntype=t)
            assert n.node_type == t

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            _graph_node(conf=1.5)
        with pytest.raises(ValidationError):
            _graph_node(conf=-0.1)

    def test_metadata_roundtrip(self):
        meta = {"entity_label": "method", "source": "test", "count": 42}
        n = _graph_node(meta=meta)
        assert n.metadata["entity_label"] == "method"
        assert n.metadata["count"] == 42


# ===================================================================
# GraphEdge validation
# ===================================================================


class TestGraphEdge:
    def test_valid_edge(self):
        e = _graph_edge()
        assert e.edge_id == "e_001"
        assert e.predicate == "uses"

    def test_invalid_predicate_format(self):
        with pytest.raises(ValidationError):
            _graph_edge(pred="Uses")

    def test_predicate_with_hyphen(self):
        with pytest.raises(ValidationError):
            _graph_edge(pred="uses-dataset")

    def test_predicate_with_spaces(self):
        with pytest.raises(ValidationError):
            _graph_edge(pred="uses dataset")

    def test_predicate_with_numbers(self):
        with pytest.raises(ValidationError):
            _graph_edge(pred="uses_123")

    def test_is_negated_default(self):
        e = _graph_edge()
        assert e.is_negated is False

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            _graph_edge(conf=-0.01)
        with pytest.raises(ValidationError):
            _graph_edge(conf=1.01)

    def test_valid_lowercase_predicates(self):
        for p in ["uses", "evaluated_on", "outperforms", "contains", "depends_on"]:
            e = _graph_edge(pred=p)
            assert e.predicate == p


# ===================================================================
# GraphPath validation
# ===================================================================


class TestGraphPath:
    def test_empty_path(self):
        p = GraphPath(edges=[])
        assert p.confidence == 0.0

    def test_confidence_is_min_of_edges(self):
        e1 = _graph_edge(eid="e1", conf=0.9)
        e2 = _graph_edge(eid="e2", conf=0.5)
        p = GraphPath(edges=[e1, e2])
        assert p.confidence == 0.5

    def test_single_edge_path(self):
        e = _graph_edge(eid="e1", conf=0.75)
        p = GraphPath(edges=[e])
        assert p.confidence == 0.75

    def test_confidence_edge_order_independent(self):
        e1 = _graph_edge(eid="e1", conf=0.3)
        e2 = _graph_edge(eid="e2", conf=0.9)
        p1 = GraphPath(edges=[e1, e2])
        p2 = GraphPath(edges=[e2, e1])
        assert p1.confidence == p2.confidence == 0.3


# ===================================================================
# GraphQuery model
# ===================================================================


class TestGraphQuery:
    def test_defaults(self):
        q = GraphQuery()
        assert q.node_type is None
        assert q.min_confidence == 0.0
        assert q.max_results == 100

    def test_max_results_bounds(self):
        with pytest.raises(ValidationError):
            GraphQuery(max_results=0)
        with pytest.raises(ValidationError):
            GraphQuery(max_results=10001)

    def test_min_confidence_bounds(self):
        with pytest.raises(ValidationError):
            GraphQuery(min_confidence=-0.1)
        with pytest.raises(ValidationError):
            GraphQuery(min_confidence=1.1)


# ===================================================================
# KnowledgeGraph basic operations
# ===================================================================


class TestKnowledgeGraphBasic:
    def test_empty_graph(self):
        g = KnowledgeGraph()
        assert g.node_count() == 0
        assert g.edge_count() == 0

    def test_add_node(self):
        g = KnowledgeGraph()
        n = _graph_node()
        g.add_node(n)
        assert g.node_count() == 1
        assert g.has_node("n_001")

    def test_add_duplicate_node_overwrites(self):
        g = KnowledgeGraph()
        g.add_node(_graph_node(nid="n1", text="First"))
        g.add_node(_graph_node(nid="n1", text="Second"))
        assert g.node_count() == 1
        assert g.get_node("n1").text == "Second"

    def test_add_edge(self):
        g = KnowledgeGraph()
        g.add_node(_graph_node(nid="a"))
        g.add_node(_graph_node(nid="b"))
        g.add_edge(_graph_edge(eid="e1", src="a", tgt="b"))
        assert g.edge_count() == 1

    def test_has_node_false(self):
        g = KnowledgeGraph()
        assert not g.has_node("nonexistent")

    def test_get_node_none(self):
        g = KnowledgeGraph()
        assert g.get_node("nonexistent") is None

    def test_get_edge_none(self):
        g = KnowledgeGraph()
        assert g.get_edge("nonexistent") is None

    def test_get_neighbor_edges(self):
        g = KnowledgeGraph()
        g.add_node(_graph_node(nid="a"))
        g.add_node(_graph_node(nid="b"))
        g.add_node(_graph_node(nid="c"))
        g.add_edge(_graph_edge(eid="e1", src="a", tgt="b"))
        g.add_edge(_graph_edge(eid="e2", src="a", tgt="c"))
        edges = g.get_neighbor_edges("a")
        assert len(edges) == 2


# ===================================================================
# KnowledgeGraph.get_neighbors
# ===================================================================


class TestKnowledgeGraphNeighbors:
    def test_depth_1(self):
        g = _small_graph()
        sub = g.get_neighbors("A", depth=1)
        nids = {n.node_id for n in sub.nodes}
        assert "A" in nids
        assert "B" in nids
        assert "D" in nids
        assert "C" not in nids

    def test_depth_2(self):
        g = _small_graph()
        sub = g.get_neighbors("A", depth=2)
        nids = {n.node_id for n in sub.nodes}
        assert nids == {"A", "B", "C", "D"}

    def test_depth_0_is_clamped_to_1(self):
        g = _small_graph()
        sub = g.get_neighbors("A", depth=0)
        nids = {n.node_id for n in sub.nodes}
        assert "A" in nids
        assert "B" in nids

    def test_nonexistent_node(self):
        g = _small_graph()
        sub = g.get_neighbors("Z", depth=2)
        assert len(sub.nodes) == 0
        assert len(sub.edges) == 0

    def test_isolated_node(self):
        g = _small_graph()
        g.add_node(_graph_node(nid="I", text="Isolated"))
        sub = g.get_neighbors("I", depth=2)
        nids = {n.node_id for n in sub.nodes}
        assert nids == {"I"}
        assert len(sub.edges) == 0

    def test_edges_included(self):
        g = _small_graph()
        sub = g.get_neighbors("B", depth=1)
        eids = {e.edge_id for e in sub.edges}
        assert "e1" in eids
        assert "e2" in eids

    def test_depth_larger_than_graph(self):
        g = _small_graph()
        sub = g.get_neighbors("A", depth=10)
        assert len(sub.nodes) == 4


# ===================================================================
# KnowledgeGraph.shortest_path
# ===================================================================


class TestKnowledgeGraphShortestPath:
    def test_direct_edge(self):
        g = _small_graph()
        path = g.shortest_path("A", "B")
        assert path is not None
        assert len(path.edges) == 1
        assert path.edges[0].edge_id == "e1"

    def test_multi_hop(self):
        g = _small_graph()
        path = g.shortest_path("A", "C")
        assert path is not None
        assert len(path.edges) == 2
        assert path.edges[0].edge_id == "e1"
        assert path.edges[1].edge_id == "e2"

    def test_no_path(self):
        g = _small_graph()
        g.add_node(_graph_node(nid="Z", text="Z"))
        path = g.shortest_path("A", "Z")
        assert path is None

    def test_same_node(self):
        g = _small_graph()
        path = g.shortest_path("A", "A")
        assert path is not None
        assert len(path.edges) == 0

    def test_nonexistent_source(self):
        g = _small_graph()
        path = g.shortest_path("Z", "A")
        assert path is None

    def test_nonexistent_target(self):
        g = _small_graph()
        path = g.shortest_path("A", "Z")
        assert path is None

    def test_undirected_traversal(self):
        g = _small_graph()
        path = g.shortest_path("C", "A")
        assert path is not None
        assert len(path.edges) == 2

    def test_path_confidence_is_min(self):
        g = _small_graph()
        e1 = g.get_edge("e1")
        if e1:
            e1.confidence = 0.6
        path = g.shortest_path("A", "C")
        assert path is not None
        assert path.confidence == 0.6


# ===================================================================
# KnowledgeGraph.find_paths
# ===================================================================


class TestKnowledgeGraphFindPaths:
    def test_single_path(self):
        g = _small_graph()
        paths = g.find_paths("A", "C")
        assert len(paths) == 1

    def test_multiple_paths(self):
        g = _small_graph()
        # Add alternative path A -> D -> C
        g.add_node(_graph_node(nid="D2", text="D2"))
        g.add_edge(_graph_edge(eid="e4", src="D", tgt="C", pred="connects"))
        paths = g.find_paths("A", "C")
        assert len(paths) >= 1

    def test_no_paths(self):
        g = _small_graph()
        g.add_node(_graph_node(nid="Z", text="Z"))
        paths = g.find_paths("A", "Z")
        assert len(paths) == 0

    def test_same_node(self):
        g = _small_graph()
        paths = g.find_paths("A", "A")
        assert len(paths) == 1
        assert len(paths[0].edges) == 0

    def test_max_depth_limits(self):
        g = _small_graph()
        paths = g.find_paths("A", "C", max_depth=1)
        assert len(paths) == 0

    def test_max_depth_allows(self):
        g = _small_graph()
        paths = g.find_paths("A", "C", max_depth=2)
        assert len(paths) == 1

    def test_paths_sorted_by_length_then_confidence(self):
        g = KnowledgeGraph()
        for nid in ["A", "B", "C", "D", "E"]:
            g.add_node(_graph_node(nid=nid, text=f"Node{nid}"))
        g.add_edge(_graph_edge(eid="e1", src="A", tgt="B", pred="connects", conf=0.5))
        g.add_edge(_graph_edge(eid="e2", src="B", tgt="C", pred="connects", conf=0.9))
        g.add_edge(_graph_edge(eid="e3", src="A", tgt="D", pred="connects", conf=0.7))
        g.add_edge(_graph_edge(eid="e4", src="D", tgt="C", pred="connects", conf=0.8))
        paths = g.find_paths("A", "C")
        # Should have 2 paths, sorted by length then -confidence
        assert len(paths) == 2

    def test_nonexistent_nodes(self):
        g = _small_graph()
        assert g.find_paths("Z", "X") == []


# ===================================================================
# KnowledgeGraph.get_subgraph
# ===================================================================


class TestKnowledgeGraphSubgraph:
    def test_subgraph_with_nodes(self):
        g = _small_graph()
        sub = g.get_subgraph({"A", "B"})
        assert len(sub.nodes) == 2
        assert len(sub.edges) == 1

    def test_subgraph_excludes_edges_outside(self):
        g = _small_graph()
        sub = g.get_subgraph({"A"})
        assert len(sub.nodes) == 1
        assert len(sub.edges) == 0

    def test_subgraph_empty(self):
        g = _small_graph()
        sub = g.get_subgraph(set())
        assert len(sub.nodes) == 0
        assert len(sub.edges) == 0

    def test_subgraph_nonexistent_ids(self):
        g = _small_graph()
        sub = g.get_subgraph({"Z"})
        assert len(sub.nodes) == 0


# ===================================================================
# KnowledgeGraph.query
# ===================================================================


class TestKnowledgeGraphQuery:
    def test_query_by_node_type(self):
        g = _small_graph()
        q = GraphQuery(node_type="entity")
        sub = g.query(q)
        assert len(sub.nodes) == 4

    def test_query_by_entity_label(self):
        g = _small_graph()
        for nid in ["A", "B"]:
            n = g.get_node(nid)
            if n:
                n.metadata["entity_label"] = "method"
        q = GraphQuery(entity_label="method")
        sub = g.query(q)
        assert len(sub.nodes) == 2

    def test_query_by_text_contains(self):
        g = _small_graph()
        q = GraphQuery(text_contains="NodeB")
        sub = g.query(q)
        assert len(sub.nodes) == 1
        assert sub.nodes[0].node_id == "B"

    def test_query_by_min_confidence(self):
        g = _small_graph()
        n = g.get_node("A")
        if n:
            n.confidence = 0.3
        q = GraphQuery(min_confidence=0.8)
        sub = g.query(q)
        assert "A" not in {n.node_id for n in sub.nodes}

    def test_query_max_results(self):
        g = _small_graph()
        q = GraphQuery(max_results=2)
        sub = g.query(q)
        assert len(sub.nodes) <= 2

    def test_query_all_nodes(self):
        g = _small_graph()
        q = GraphQuery()
        sub = g.query(q)
        assert len(sub.nodes) == 4

    def test_query_with_predicate_filter_returns_edges(self):
        g = _small_graph()
        q = GraphQuery()
        sub = g.query(q)
        assert len(sub.edges) == 3

    def test_query_case_insensitive_text(self):
        g = _small_graph()
        q = GraphQuery(text_contains="nodeb")
        sub = g.query(q)
        assert len(sub.nodes) == 1

    def test_query_by_type_and_text(self):
        g = _small_graph()
        n = g.get_node("A")
        if n:
            n.node_type = "claim"
        q = GraphQuery(node_type="claim", text_contains="NodeA")
        sub = g.query(q)
        assert len(sub.nodes) == 1

    def test_query_empty_graph(self):
        g = KnowledgeGraph()
        q = GraphQuery(node_type="entity")
        sub = g.query(q)
        assert len(sub.nodes) == 0


# ===================================================================
# KnowledgeGraph.get_connected_components
# ===================================================================


class TestKnowledgeGraphComponents:
    def test_single_component(self):
        g = _small_graph()
        comps = g.get_connected_components()
        assert len(comps) == 1
        assert len(comps[0].nodes) == 4

    def test_disconnected_components(self):
        g = _small_graph()
        g.add_node(_graph_node(nid="X", text="X"))
        g.add_node(_graph_node(nid="Y", text="Y"))
        g.add_edge(_graph_edge(eid="e4", src="X", tgt="Y"))
        comps = g.get_connected_components()
        assert len(comps) == 2

    def test_isolated_node(self):
        g = _small_graph()
        g.add_node(_graph_node(nid="I", text="Isolated"))
        comps = g.get_connected_components()
        assert len(comps) == 2

    def test_components_sorted_by_size(self):
        g = _small_graph()
        g.add_node(_graph_node(nid="S", text="S"))
        comps = g.get_connected_components()
        assert len(comps[0].nodes) >= len(comps[1].nodes)

    def test_empty_graph_components(self):
        g = KnowledgeGraph()
        comps = g.get_connected_components()
        assert comps == []

    def test_component_edges_correct(self):
        g = _small_graph()
        comps = g.get_connected_components()
        edges_in_component = set(e.edge_id for e in comps[0].edges)
        assert edges_in_component == {"e1", "e2", "e3"}


# ===================================================================
# KnowledgeGraph.get_statistics
# ===================================================================


class TestKnowledgeGraphStatistics:
    def test_empty_stats(self):
        g = KnowledgeGraph()
        stats = g.get_statistics()
        assert stats.total_nodes == 0
        assert stats.total_edges == 0
        assert stats.avg_degree == 0.0
        assert stats.density == 0.0

    def test_node_type_counts(self):
        g = _small_graph()
        stats = g.get_statistics()
        assert stats.total_nodes == 4
        assert stats.node_type_counts.get("entity", 0) == 4

    def test_predicate_counts(self):
        g = _small_graph()
        stats = g.get_statistics()
        assert stats.predicate_counts.get("connects", 0) == 3

    def test_avg_degree(self):
        g = _small_graph()
        stats = g.get_statistics()
        # A->B,A->D,B->C: A=2, B=2, C=1, D=1 => avg=6/4=1.5
        assert stats.avg_degree == 1.5

    def test_connected_components_in_stats(self):
        g = _small_graph()
        stats = g.get_statistics()
        assert stats.connected_components == 1

    def test_density(self):
        g = KnowledgeGraph()
        for nid in ["A", "B"]:
            g.add_node(_graph_node(nid=nid, text=nid))
        g.add_edge(_graph_edge(eid="e1", src="A", tgt="B"))
        stats = g.get_statistics()
        # 2 nodes, 1 edge => density = 1/(2*1/2) = 1.0
        assert stats.density == 1.0

    def test_entity_label_counts(self):
        g = KnowledgeGraph()
        n1 = _graph_node(nid="e1", text="GAN")
        n1.metadata["entity_label"] = "method"
        n2 = _graph_node(nid="e2", text="ImageNet")
        n2.metadata["entity_label"] = "dataset"
        g.add_node(n1)
        g.add_node(n2)
        stats = g.get_statistics()
        assert stats.entity_label_counts.get("method", 0) == 1
        assert stats.entity_label_counts.get("dataset", 0) == 1


# ===================================================================
# KnowledgeGraphBuilder
# ===================================================================


class TestKnowledgeGraphBuilder:
    def test_empty_build(self):
        builder = KnowledgeGraphBuilder()
        g = builder.build()
        assert g.node_count() == 0
        assert g.edge_count() == 0

    def test_build_with_entities(self):
        ents = [_entity(eid="e1", text="GAN")]
        g = KnowledgeGraphBuilder().build(entities=ents)
        assert g.node_count() == 1
        assert g.has_node("e1")

    def test_build_with_claims(self):
        claims = [_claim(cid="c1")]
        g = KnowledgeGraphBuilder().build(claims=claims)
        assert g.has_node("c1")

    def test_build_with_chunks(self):
        chunks = [_chunk(cid="ch1")]
        g = KnowledgeGraphBuilder().build(chunks=chunks)
        assert g.has_node("ch1")

    def test_build_with_facts(self):
        facts = [_fact(fid="f1")]
        g = KnowledgeGraphBuilder().build(facts=facts)
        assert g.has_node("f1")

    def test_build_with_triples(self):
        ents = [
            _entity(eid="e1", text="GAN"),
            _entity(eid="e2", text="ImageNet"),
        ]
        trips = [_triple(tid="t1", subj_id="e1", obj_id="e2")]
        g = KnowledgeGraphBuilder().build(entities=ents, triples=trips)
        assert g.edge_count() >= 1

    def test_entity_chunk_derived_edges(self):
        ents = [_entity(eid="e1", chunk_id="ch1")]
        chunks = [_chunk(cid="ch1")]
        g = KnowledgeGraphBuilder().build(entities=ents, chunks=chunks)
        edges = g.get_neighbor_edges("e1")
        predicates = {e.predicate for e in edges}
        assert "appears_in" in predicates

    def test_claim_chunk_derived_edges(self):
        claims = [_claim(cid="c1", chunk_id="ch1")]
        chunks = [_chunk(cid="ch1")]
        g = KnowledgeGraphBuilder().build(claims=claims, chunks=chunks)
        edges = g.get_neighbor_edges("c1")
        predicates = {e.predicate for e in edges}
        assert "appears_in" in predicates

    def test_entity_claim_derived_edges(self):
        ents = [_entity(eid="e1", text="GAN", chunk_id="ch1")]
        claims = [_claim(
            cid="c1",
            sentence="GAN achieves state-of-the-art results.",
            chunk_id="ch1",
        )]
        g = KnowledgeGraphBuilder().build(entities=ents, claims=claims)
        edges = g.get_neighbor_edges("e1")
        predicates = {e.predicate for e in edges}
        assert "mentioned_in" in predicates

    def test_fact_entity_derived_edges(self):
        ents = [_entity(eid="e1", text="GAN")]
        facts = [_fact(fid="f1", value="GAN")]
        g = KnowledgeGraphBuilder().build(entities=ents, facts=facts)
        edges = g.get_neighbor_edges("f1")
        predicates = {e.predicate for e in edges}
        assert "references" in predicates

    def test_build_with_all_inputs(self):
        ents = [_entity(eid="e1", text="GAN", chunk_id="ch1")]
        claims = [_claim(cid="c1", chunk_id="ch1")]
        chunks = [_chunk(cid="ch1")]
        facts = [_fact(fid="f1", value="GAN")]
        trips = [_triple(tid="t1", subj_id="e1", obj_id="e1")]
        g = KnowledgeGraphBuilder().build(
            entities=ents, claims=claims, chunks=chunks,
            facts=facts, triples=trips,
        )
        assert g.node_count() >= 4
        assert g.edge_count() >= 1

    def test_node_metadata_from_entity(self):
        ent = _entity(eid="e1", text="GAN", label=EntityLabel.METHOD)
        g = KnowledgeGraphBuilder().build(entities=[ent])
        node = g.get_node("e1")
        assert node is not None
        assert node.metadata["entity_label"] == "method"
        assert node.metadata["chunk_id"] == "chunk_001"

    def test_node_metadata_from_claim(self):
        claim = _claim(cid="c1", ctype=ClaimType.STATISTICAL)
        g = KnowledgeGraphBuilder().build(claims=[claim])
        node = g.get_node("c1")
        assert node is not None
        assert node.metadata["claim_type"] == "statistical"

    def test_node_metadata_from_chunk(self):
        chunk = _chunk(cid="ch1")
        g = KnowledgeGraphBuilder().build(chunks=[chunk])
        node = g.get_node("ch1")
        assert node is not None
        assert node.metadata["word_count"] > 0

    def test_node_metadata_from_fact(self):
        fact = _fact(fid="f1", ftype=FactType.METHOD)
        g = KnowledgeGraphBuilder().build(facts=[fact])
        node = g.get_node("f1")
        assert node is not None
        assert node.metadata["fact_type"] == "method"

    def test_entity_not_in_chunk_no_derived_edge(self):
        ents = [_entity(eid="e1", chunk_id="ch1")]
        chunks = [_chunk(cid="ch2")]
        g = KnowledgeGraphBuilder().build(entities=ents, chunks=chunks)
        edges = g.get_neighbor_edges("e1")
        predicates = {e.predicate for e in edges}
        assert "appears_in" not in predicates

    def test_entity_not_in_claim_no_derived_edge(self):
        ents = [_entity(eid="e1", text="XYZ", chunk_id="ch1")]
        claims = [_claim(cid="c1", sentence="GAN is good.", chunk_id="ch1")]
        g = KnowledgeGraphBuilder().build(entities=ents, claims=claims)
        edges = g.get_neighbor_edges("e1")
        predicates = {e.predicate for e in edges}
        assert "mentioned_in" not in predicates

    def test_triple_edge_metadata(self):
        ents = [
            _entity(eid="e1", text="GAN"),
            _entity(eid="e2", text="ImageNet"),
        ]
        trips = [_triple(tid="t1", subj_id="e1", obj_id="e2")]
        g = KnowledgeGraphBuilder().build(entities=ents, triples=trips)
        edges = g.get_neighbor_edges("e1")
        assert len(edges) >= 1
        e = edges[0]
        assert e.metadata.get("triple_id") == "t1"

    def test_chunk_text_truncated(self):
        long_text = "word " * 250
        chunk = _chunk(cid="ch1", text=long_text)
        g = KnowledgeGraphBuilder().build(chunks=[chunk])
        node = g.get_node("ch1")
        assert node is not None
        assert len(node.text) <= 200

    def test_chunk_text_not_truncated_if_short(self):
        chunk = _chunk(cid="ch1", text="Short text.")
        g = KnowledgeGraphBuilder().build(chunks=[chunk])
        node = g.get_node("ch1")
        assert node is not None
        assert node.text == "Short text."


# ===================================================================
# build_knowledge_graph function
# ===================================================================


class TestBuildKnowledgeGraph:
    def test_convenience_function(self):
        ents = [_entity(eid="e1")]
        g = build_knowledge_graph(entities=ents)
        assert isinstance(g, KnowledgeGraph)
        assert g.has_node("e1")

    def test_convenience_all_params(self):
        g = build_knowledge_graph(
            entities=[_entity(eid="e1")],
            claims=[_claim(cid="c1")],
            chunks=[_chunk(cid="ch1")],
        )
        assert g.node_count() >= 3


# ===================================================================
# Integration tests
# ===================================================================


class TestKnowledgeGraphIntegration:
    def test_traverse_after_build(self):
        ents = [
            _entity(eid="e1", text="GAN", chunk_id="ch1"),
            _entity(eid="e2", text="ImageNet", chunk_id="ch1"),
        ]
        chunks = [_chunk(cid="ch1")]
        trips = [_triple(tid="t1", subj_id="e1", obj_id="e2")]
        g = KnowledgeGraphBuilder().build(
            entities=ents, chunks=chunks, triples=trips,
        )
        sub = g.get_neighbors("e1", depth=2)
        assert "e2" in {n.node_id for n in sub.nodes}

    def test_path_finding_after_build(self):
        ents = [
            _entity(eid="e1", text="A", chunk_id="ch1"),
            _entity(eid="e2", text="B", chunk_id="ch1"),
            _entity(eid="e3", text="C", chunk_id="ch2"),
        ]
        chunks = [_chunk(cid="ch1"), _chunk(cid="ch2")]
        trips = [
            _triple(tid="t1", subj_id="e1", obj_id="e2"),
            _triple(tid="t2", subj_id="e2", obj_id="e3"),
        ]
        g = KnowledgeGraphBuilder().build(
            entities=ents, chunks=chunks, triples=trips,
        )
        path = g.shortest_path("e1", "e3")
        assert path is not None
        assert len(path.edges) == 2

    def test_query_after_build(self):
        ents = [
            _entity(eid="e1", text="GAN", label=EntityLabel.METHOD),
            _entity(eid="e2", text="ImageNet", label=EntityLabel.DATASET),
        ]
        g = KnowledgeGraphBuilder().build(entities=ents)
        q = GraphQuery(entity_label="method")
        sub = g.query(q)
        assert len(sub.nodes) == 1
        assert sub.nodes[0].node_id == "e1"

    def test_statistics_after_build(self):
        ents = [
            _entity(eid="e1", text="GAN"),
            _entity(eid="e2", text="ImageNet"),
        ]
        trips = [_triple(tid="t1", subj_id="e1", obj_id="e2")]
        g = KnowledgeGraphBuilder().build(entities=ents, triples=trips)
        stats = g.get_statistics()
        assert stats.total_nodes >= 2
        assert stats.total_edges >= 1
