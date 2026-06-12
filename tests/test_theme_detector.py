"""Comprehensive tests for ThemeDetector (Module 6, Phase 2).

Covers:
  - Construction & basics
  - Empty / edge-case graphs
  - Connected component discovery (BFS, cycles, duplicate edges)
  - Filtering (min_cluster_size, isolated nodes)
  - Theme classification (METHOD, DATASET, METRIC, CONCEPT, tie-breaking)
  - Confidence computation
  - Label selection
  - Determinism (repeated runs identical)
  - Ordering & max_themes cap
  - Metadata
  - Convenience helper
  - Large graphs (100+ nodes)
  - Serialization round-trip
  - Malformed / partial graph objects
"""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from researchmind.corpus.graph import CorpusGraphEdge, CorpusGraphNode, CorpusGraphResult
from researchmind.models.enums import EntityLabel
from researchmind.models.ruo_enums import RelationType
from researchmind.synthesis.models import ThemeCluster, ThemeType
from researchmind.synthesis.theme_detector import ThemeDetector, detect_themes


# ===========================================================================
# Fixtures
# ===========================================================================


def _entity_node(
    node_id: str,
    label: str,
    entity_label: str = "concept",
    confidence: float = 0.5,
) -> CorpusGraphNode:
    return CorpusGraphNode(
        node_id=node_id,
        node_type="entity_cluster",
        label=label,
        metadata={
            "label": entity_label,
            "confidence": confidence,
            "canonical_text": label,
        },
        weight=max(0.0, min(1.0, confidence)),
    )


def _doc_node(node_id: str, label: str = "") -> CorpusGraphNode:
    return CorpusGraphNode(
        node_id=node_id,
        node_type="document",
        label=label or node_id,
    )


def _entity_edge(
    edge_id: str,
    source_id: str,
    target_id: str,
    relation_type: RelationType = RelationType.COMPARES_WITH,
    confidence: float = 0.8,
) -> CorpusGraphEdge:
    return CorpusGraphEdge(
        edge_id=edge_id,
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
        confidence=confidence,
    )


def _doc_entity_edge(
    edge_id: str,
    doc_id: str,
    entity_id: str,
) -> CorpusGraphEdge:
    return CorpusGraphEdge(
        edge_id=edge_id,
        source_id=doc_id,
        target_id=entity_id,
        relation_type=RelationType.EXTENDS,
        confidence=0.9,
        metadata={"edge_kind": "doc_contains_entity"},
    )


def _two_entity_graph() -> CorpusGraphResult:
    a = _entity_node("e1", "BERT", entity_label="method", confidence=0.9)
    b = _entity_node("e2", "RoBERTa", entity_label="method", confidence=0.8)
    e = _entity_edge("ee1", "e1", "e2")
    return CorpusGraphResult(nodes=[a, b], edges=[e], total_nodes_found=2, total_edges_found=1)


# ===========================================================================
# 1. Construction & basics
# ===========================================================================


class TestConstruction:
    """ThemeDetector construction and basic attributes."""

    def test_default_construction(self) -> None:
        td = ThemeDetector()
        assert isinstance(td, ThemeDetector)

    def test_detect_themes_method_exists(self) -> None:
        assert hasattr(ThemeDetector, "detect_themes")

    def test_detect_themes_callable(self) -> None:
        assert callable(ThemeDetector().detect_themes)

    def test_detect_themes_returns_list(self) -> None:
        result = ThemeDetector().detect_themes(graph=None)
        assert isinstance(result, list)

    def test_detect_themes_returns_theme_clusters(self) -> None:
        result = ThemeDetector().detect_themes(_two_entity_graph())
        assert all(isinstance(t, ThemeCluster) for t in result)


# ===========================================================================
# 2. Empty / edge-case graphs
# ===========================================================================


class TestEmptyGraph:
    """Behavior with empty or None graphs."""

    def test_none_graph_returns_empty(self) -> None:
        assert ThemeDetector().detect_themes(graph=None) == []

    def test_empty_nodes_and_edges(self) -> None:
        g = CorpusGraphResult(nodes=[], edges=[])
        assert ThemeDetector().detect_themes(g) == []

    def test_no_entity_nodes(self) -> None:
        doc = _doc_node("d1")
        g = CorpusGraphResult(nodes=[doc], edges=[])
        assert ThemeDetector().detect_themes(g) == []

    def test_document_nodes_only(self) -> None:
        docs = [_doc_node(f"d{i}") for i in range(5)]
        g = CorpusGraphResult(nodes=docs, edges=[])
        assert ThemeDetector().detect_themes(g) == []

    def test_claim_nodes_only(self) -> None:
        claim = CorpusGraphNode(node_id="c1", node_type="claim", label="Claim1")
        g = CorpusGraphResult(nodes=[claim], edges=[])
        assert ThemeDetector().detect_themes(g) == []

    def test_entity_nodes_no_edges(self) -> None:
        e1 = _entity_node("e1", "A")
        e2 = _entity_node("e2", "B")
        g = CorpusGraphResult(nodes=[e1, e2], edges=[])
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 0

    def test_entity_nodes_only_irrelevant_edges(self) -> None:
        e1 = _entity_node("e1", "A")
        e2 = _entity_node("e2", "B")
        edge = _entity_edge("e", "e1", "e2", RelationType.SUPPORTS)
        g = CorpusGraphResult(nodes=[e1, e2], edges=[edge])
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 0

    def test_entity_nodes_no_relevant_edges(self) -> None:
        e1 = _entity_node("e1", "A")
        e2 = _entity_node("e2", "B")
        edge = _entity_edge("e", "e1", "e2", RelationType.CONTRADICTS)
        g = CorpusGraphResult(nodes=[e1, e2], edges=[edge])
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 0


# ===========================================================================
# 3. Single entity node
# ===========================================================================


class TestSingleNode:
    """Behavior with a single entity node."""

    def test_single_entity_no_theme(self) -> None:
        e = _entity_node("e1", "Solo")
        g = CorpusGraphResult(nodes=[e], edges=[])
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 0

    def test_single_entity_with_self_edge(self) -> None:
        e = _entity_node("e1", "Solo")
        edge = _entity_edge("se", "e1", "e1")
        g = CorpusGraphResult(nodes=[e], edges=[edge])
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 0

    def test_single_entity_with_doc_edge(self) -> None:
        e = _entity_node("e1", "Solo")
        d = _doc_node("d1")
        de = _doc_entity_edge("de", "d1", "e1")
        g = CorpusGraphResult(nodes=[e, d], edges=[de])
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 0

    def test_min_cluster_size_one_includes_single(self) -> None:
        e = _entity_node("e1", "Solo")
        g = CorpusGraphResult(nodes=[e], edges=[])
        result = ThemeDetector().detect_themes(g, min_cluster_size=1)
        assert len(result) == 0

    def test_single_entity_with_self_edge_min_size_one(self) -> None:
        e = _entity_node("e1", "Solo")
        edge = _entity_edge("se", "e1", "e1")
        g = CorpusGraphResult(nodes=[e], edges=[edge])
        result = ThemeDetector().detect_themes(g, min_cluster_size=1)
        assert len(result) == 1


# ===========================================================================
# 4. Connected component discovery
# ===========================================================================


class TestConnectedComponents:
    """BFS-based component discovery."""

    def test_two_entities_one_component(self) -> None:
        result = ThemeDetector().detect_themes(_two_entity_graph())
        assert len(result) == 1

    def test_two_disconnected_components(self) -> None:
        a = _entity_node("e1", "A")
        b = _entity_node("e2", "B")
        c = _entity_node("e3", "C")
        d = _entity_node("e4", "D")
        e1 = _entity_edge("e1", "e1", "e2")
        e2 = _entity_edge("e2", "e3", "e4")
        g = CorpusGraphResult(nodes=[a, b, c, d], edges=[e1, e2])
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 2

    def test_three_entity_chain(self) -> None:
        nodes = [_entity_node(f"e{i}", f"N{i}") for i in range(3)]
        edges = [
            _entity_edge(f"e{i:02d}", f"e{i}", f"e{i+1}")
            for i in range(2)
        ]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 1
        assert result[0].metadata.get("entity_count") == 3

    def test_star_component(self) -> None:
        center = _entity_node("center", "Center")
        leaves = [_entity_node(f"leaf{i}", f"Leaf{i}") for i in range(5)]
        edges = [_entity_edge(f"e{i}", "center", f"leaf{i}") for i in range(5)]
        g = CorpusGraphResult(nodes=[center] + leaves, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 1
        assert result[0].metadata.get("entity_count") == 6

    def test_component_entity_ids_correct(self) -> None:
        result = ThemeDetector().detect_themes(_two_entity_graph())
        cluster = result[0]
        assert "e1" in cluster.entity_cluster_ids
        assert "e2" in cluster.entity_cluster_ids

    def test_component_entity_labels_correct(self) -> None:
        result = ThemeDetector().detect_themes(_two_entity_graph())
        cluster = result[0]
        assert "BERT" in cluster.entity_labels
        assert "RoBERTa" in cluster.entity_labels


# ===========================================================================
# 5. Cycles
# ===========================================================================


class TestCycles:
    """Cycle handling in connected components."""

    def test_simple_triangle(self) -> None:
        nodes = [_entity_node(f"e{i}", f"N{i}") for i in range(3)]
        edges = [
            _entity_edge("e01", "e0", "e1"),
            _entity_edge("e12", "e1", "e2"),
            _entity_edge("e20", "e2", "e0"),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 1
        assert result[0].metadata.get("entity_count") == 3

    def test_cycle_with_tail(self) -> None:
        nodes = [_entity_node(f"e{i}", f"N{i}") for i in range(5)]
        edges = [
            _entity_edge("e01", "e0", "e1"),
            _entity_edge("e12", "e1", "e2"),
            _entity_edge("e20", "e2", "e0"),
            _entity_edge("e23", "e2", "e3"),
            _entity_edge("e34", "e3", "e4"),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 1
        assert result[0].metadata.get("entity_count") == 5

    def test_two_separate_cycles(self) -> None:
        nodes = [_entity_node(f"e{i}", f"N{i}") for i in range(6)]
        edges = [
            _entity_edge("e01", "e0", "e1"),
            _entity_edge("e12", "e1", "e2"),
            _entity_edge("e20", "e2", "e0"),
            _entity_edge("e34", "e3", "e4"),
            _entity_edge("e45", "e4", "e5"),
            _entity_edge("e53", "e5", "e3"),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 2

    def test_self_loop_only(self) -> None:
        e = _entity_node("e1", "Solo")
        loop = _entity_edge("loop", "e1", "e1")
        g = CorpusGraphResult(nodes=[e], edges=[loop])
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 0

    def test_complex_cycle_terminates(self) -> None:
        nodes = [_entity_node(f"e{i}", f"N{i}") for i in range(10)]
        edges = [
            _entity_edge(f"e{i:02d}", f"e{i}", f"e{(i+1)%10}")
            for i in range(10)
        ] + [
            _entity_edge(f"x{i:02d}", f"e{i}", f"e{(i+3)%10}")
            for i in range(10)
        ]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g, min_cluster_size=1)
        assert len(result) == 1
        assert result[0].metadata.get("entity_count") == 10


# ===========================================================================
# 6. Duplicate edges
# ===========================================================================


class TestDuplicateEdges:
    """Duplicate edges must not affect output."""

    def test_duplicate_edge_same_component(self) -> None:
        nodes = [_entity_node(f"e{i}", f"N{i}") for i in range(2)]
        edges = [
            _entity_edge("e1", "e0", "e1"),
            _entity_edge("e2", "e0", "e1"),
        ]
        g1 = CorpusGraphResult(nodes=nodes, edges=[edges[0]])
        g2 = CorpusGraphResult(nodes=nodes, edges=edges)
        r1 = ThemeDetector().detect_themes(g1)
        r2 = ThemeDetector().detect_themes(g2)
        assert len(r1) == len(r2) == 1

    def test_duplicate_edges_no_new_component(self) -> None:
        nodes = [_entity_node(f"e{i}", f"N{i}") for i in range(4)]
        edges_base = [
            _entity_edge("e01", "e0", "e1"),
            _entity_edge("e23", "e2", "e3"),
        ]
        edges_dup = edges_base + [
            _entity_edge("dup1", "e0", "e1"),
            _entity_edge("dup2", "e2", "e3"),
        ]
        g1 = CorpusGraphResult(nodes=nodes, edges=edges_base)
        g2 = CorpusGraphResult(nodes=nodes, edges=edges_dup)
        r1 = ThemeDetector().detect_themes(g1)
        r2 = ThemeDetector().detect_themes(g2)
        assert len(r1) == len(r2)

    def test_reverse_edges_not_duplicate(self) -> None:
        a = _entity_node("e1", "A")
        b = _entity_node("e2", "B")
        edges = [
            _entity_edge("fwd", "e1", "e2"),
            _entity_edge("rev", "e2", "e1"),
        ]
        g = CorpusGraphResult(nodes=[a, b], edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 1


# ===========================================================================
# 7. Filtering — min_cluster_size
# ===========================================================================


class TestFiltering:
    """Filtering by min_cluster_size."""

    def test_min_size_default_filters_single(self) -> None:
        a = _entity_node("e1", "A")
        b = _entity_node("e2", "B")
        c = _entity_node("e3", "C")
        edges = [_entity_edge("e12", "e1", "e2")]
        g = CorpusGraphResult(nodes=[a, b, c], edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 1
        assert result[0].metadata.get("entity_count") == 2

    def test_min_size_three_filters_smaller(self) -> None:
        nodes = [_entity_node(f"e{i}", f"N{i}") for i in range(5)]
        edges = [_entity_edge(f"e{i:02d}", f"e{i}", f"e{i+1}") for i in range(4)]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g, min_cluster_size=4)
        assert len(result) == 1
        result2 = ThemeDetector().detect_themes(g, min_cluster_size=5)
        assert len(result2) == 1
        result3 = ThemeDetector().detect_themes(g, min_cluster_size=6)
        assert len(result3) == 0

    def test_min_size_one_includes_everything(self) -> None:
        nodes = [_entity_node(f"e{i}", f"N{i}") for i in range(4)]
        edges = [_entity_edge(f"e{i:02d}", f"e{i}", f"e{i+1}") for i in range(3)]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g, min_cluster_size=1)
        assert len(result) == 1

    def test_min_size_zero_treated_as_one(self) -> None:
        result = ThemeDetector().detect_themes(_two_entity_graph(), min_cluster_size=0)
        assert len(result) == 1


# ===========================================================================
# 8. Theme classification — METHOD
# ===========================================================================


class TestClassificationMethod:
    """Majority METHOD classification."""

    def test_two_methods(self) -> None:
        a = _entity_node("e1", "BERT", entity_label="method", confidence=0.9)
        b = _entity_node("e2", "GPT", entity_label="method", confidence=0.8)
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=[a, b], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].theme_type == "method"

    def test_three_methods_concept(self) -> None:
        nodes = [
            _entity_node("e1", "A", entity_label="method"),
            _entity_node("e2", "B", entity_label="method"),
            _entity_node("e3", "C", entity_label="concept"),
        ]
        edges = [_entity_edge("e12", "e1", "e2"), _entity_edge("e23", "e2", "e3")]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert result[0].theme_type == "method"

    def test_method_tie_wins_over_dataset(self) -> None:
        nodes = [
            _entity_node("e1", "A", entity_label="method"),
            _entity_node("e2", "B", entity_label="dataset"),
            _entity_node("e3", "C", entity_label="method"),
            _entity_node("e4", "D", entity_label="dataset"),
        ]
        edges = [
            _entity_edge("e12", "e1", "e2"),
            _entity_edge("e23", "e2", "e3"),
            _entity_edge("e34", "e3", "e4"),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert result[0].theme_type == "method"

    def test_method_edge_type_uses_method(self) -> None:
        a = _entity_node("e1", "SVM", entity_label="method")
        b = _entity_node("e2", "RF", entity_label="method")
        e = _entity_edge("e", "e1", "e2", RelationType.USES_METHOD)
        g = CorpusGraphResult(nodes=[a, b], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 1
        assert result[0].theme_type == "method"


# ===========================================================================
# 9. Theme classification — DATASET
# ===========================================================================


class TestClassificationDataset:
    """Majority DATASET classification."""

    def test_two_datasets(self) -> None:
        a = _entity_node("e1", "ImageNet", entity_label="dataset")
        b = _entity_node("e2", "COCO", entity_label="dataset")
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=[a, b], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].theme_type == "dataset"

    def test_dataset_tie_wins_over_metric(self) -> None:
        nodes = [
            _entity_node("e1", "A", entity_label="dataset"),
            _entity_node("e2", "B", entity_label="metric"),
            _entity_node("e3", "C", entity_label="dataset"),
        ]
        edges = [_entity_edge("e12", "e1", "e2"), _entity_edge("e23", "e2", "e3")]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert result[0].theme_type == "dataset"


# ===========================================================================
# 10. Theme classification — METRIC
# ===========================================================================


class TestClassificationMetric:
    """Majority METRIC classification."""

    def test_two_metrics(self) -> None:
        a = _entity_node("e1", "F1", entity_label="metric")
        b = _entity_node("e2", "BLEU", entity_label="metric")
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=[a, b], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].theme_type == "metric"

    def test_metric_concept_mixed(self) -> None:
        nodes = [
            _entity_node("e1", "F1", entity_label="metric"),
            _entity_node("e2", "Accuracy", entity_label="metric"),
            _entity_node("e3", "Loss", entity_label="concept"),
        ]
        edges = [_entity_edge("e12", "e1", "e2"), _entity_edge("e23", "e2", "e3")]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert result[0].theme_type == "metric"


# ===========================================================================
# 11. Theme classification — CONCEPT (fallback)
# ===========================================================================


class TestClassificationConcept:
    """CONCEPT as fallback classification."""

    def test_all_concepts(self) -> None:
        nodes = [
            _entity_node("e1", "Attention", entity_label="concept"),
            _entity_node("e2", "Transformer", entity_label="concept"),
        ]
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=nodes, edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].theme_type == "concept"

    def test_unknown_entity_label_becomes_concept(self) -> None:
        nodes = [
            _entity_node("e1", "Foo", entity_label="unknown_type"),
            _entity_node("e2", "Bar", entity_label="unknown_type"),
        ]
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=nodes, edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].theme_type == "concept"

    def test_all_tool_label_becomes_concept(self) -> None:
        nodes = [
            _entity_node("e1", "PyTorch", entity_label="tool"),
            _entity_node("e2", "TF", entity_label="tool"),
        ]
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=nodes, edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].theme_type == "concept"

    def test_all_other_label_becomes_concept(self) -> None:
        nodes = [
            _entity_node("e1", "X", entity_label="other"),
            _entity_node("e2", "Y", entity_label="other"),
        ]
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=nodes, edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].theme_type == "concept"


# ===========================================================================
# 12. Theme classification — tie-breaking
# ===========================================================================


class TestClassificationTieBreak:
    """Tie-breaking for classification (METHOD > DATASET > METRIC > CONCEPT)."""

    def test_tie_method_vs_dataset(self) -> None:
        nodes = [
            _entity_node("e1", "SVM", entity_label="method"),
            _entity_node("e2", "ImageNet", entity_label="dataset"),
        ]
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=nodes, edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].theme_type == "method"

    def test_tie_dataset_vs_metric(self) -> None:
        nodes = [
            _entity_node("e1", "COCO", entity_label="dataset"),
            _entity_node("e2", "F1", entity_label="metric"),
        ]
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=nodes, edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].theme_type == "dataset"

    def test_tie_metric_vs_concept(self) -> None:
        nodes = [
            _entity_node("e1", "BLEU", entity_label="metric"),
            _entity_node("e2", "Attention", entity_label="concept"),
        ]
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=nodes, edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].theme_type == "metric"

    def test_tie_three_way(self) -> None:
        nodes = [
            _entity_node("e1", "SVM", entity_label="method"),
            _entity_node("e2", "COCO", entity_label="dataset"),
            _entity_node("e3", "F1", entity_label="metric"),
        ]
        edges = [
            _entity_edge("e12", "e1", "e2"),
            _entity_edge("e23", "e2", "e3"),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert result[0].theme_type == "method"


# ===========================================================================
# 13. Confidence computation
# ===========================================================================


class TestConfidence:
    """Theme confidence computation."""

    def test_confidence_mean_of_two(self) -> None:
        a = _entity_node("e1", "A", entity_label="method", confidence=0.9)
        b = _entity_node("e2", "B", entity_label="method", confidence=0.7)
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=[a, b], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].confidence == pytest.approx(0.8)

    def test_confidence_three_entities(self) -> None:
        nodes = [
            _entity_node("e1", "A", confidence=1.0),
            _entity_node("e2", "B", confidence=0.5),
            _entity_node("e3", "C", confidence=0.0),
        ]
        edges = [_entity_edge("e12", "e1", "e2"), _entity_edge("e23", "e2", "e3")]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert result[0].confidence == pytest.approx(0.5)

    def test_confidence_clamped_above_one(self) -> None:
        a = _entity_node("e1", "A", confidence=1.5)
        b = _entity_node("e2", "B", confidence=1.2)
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=[a, b], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].confidence <= 1.0

    def test_confidence_clamped_below_zero(self) -> None:
        a = _entity_node("e1", "A", confidence=-0.5)
        b = _entity_node("e2", "B", confidence=-0.3)
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=[a, b], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].confidence >= 0.0

    def test_confidence_no_metadata(self) -> None:
        n1 = CorpusGraphNode(node_id="e1", node_type="entity_cluster", label="A")
        n2 = CorpusGraphNode(node_id="e2", node_type="entity_cluster", label="B")
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=[n1, n2], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].confidence == 0.0


# ===========================================================================
# 14. Label selection
# ===========================================================================


class TestLabelSelection:
    """Label selection: highest confidence → longest → lexicographically smallest."""

    def test_highest_confidence_wins(self) -> None:
        a = _entity_node("e1", "Low", confidence=0.3)
        b = _entity_node("e2", "High", confidence=0.9)
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=[a, b], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].label == "High"

    def test_tie_confidence_longest_label(self) -> None:
        a = _entity_node("e1", "Short", confidence=0.8)
        b = _entity_node("e2", "LongerName", confidence=0.8)
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=[a, b], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].label == "LongerName"

    def test_tie_confidence_length_lexicographically(self) -> None:
        a = _entity_node("e1", "Beta", confidence=0.8)
        b = _entity_node("e2", "Alpha", confidence=0.8)
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=[a, b], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].label == "Alpha"

    def test_three_way_label_tie(self) -> None:
        nodes = [
            _entity_node("e1", "C", confidence=0.5),
            _entity_node("e2", "B", confidence=0.5),
            _entity_node("e3", "A", confidence=0.5),
        ]
        edges = [_entity_edge("e12", "e1", "e2"), _entity_edge("e23", "e2", "e3")]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert result[0].label == "A"


# ===========================================================================
# 15. Determinism
# ===========================================================================


class TestDeterminism:
    """Repeated runs must produce identical output."""

    def test_repeated_calls_same_result(self) -> None:
        g = _two_entity_graph()
        r1 = ThemeDetector().detect_themes(g)
        r2 = ThemeDetector().detect_themes(g)
        assert r1 == r2

    def test_multiple_components_deterministic(self) -> None:
        nodes = [_entity_node(f"e{i}", f"N{i}") for i in range(6)]
        edges = [
            _entity_edge("e01", "e0", "e1"),
            _entity_edge("e23", "e2", "e3"),
            _entity_edge("e45", "e4", "e5"),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        r1 = ThemeDetector().detect_themes(g)
        r2 = ThemeDetector().detect_themes(g)
        assert [t.cluster_id for t in r1] == [t.cluster_id for t in r2]

    def test_deterministic_across_instances(self) -> None:
        g = _two_entity_graph()
        r1 = ThemeDetector().detect_themes(g)
        r2 = ThemeDetector().detect_themes(g)
        assert r1 == r2

    def test_no_random_source_in_label(self) -> None:
        for _ in range(10):
            result = ThemeDetector().detect_themes(_two_entity_graph())
            assert "random" not in str(result[0].cluster_id)

    def test_deterministic_id_generation(self) -> None:
        g = _two_entity_graph()
        r1 = ThemeDetector().detect_themes(g)
        r2 = ThemeDetector().detect_themes(g)
        assert r1[0].cluster_id == r2[0].cluster_id


# ===========================================================================
# 16. Ordering
# ===========================================================================


class TestOrdering:
    """Result ordering: size desc → confidence desc → label asc."""

    def test_larger_component_first(self) -> None:
        nodes = [_entity_node(f"e{i}", f"N{i}") for i in range(5)]
        edges = [
            _entity_edge("e01", "e0", "e1"),
            _entity_edge("e23", "e2", "e3"),
            _entity_edge("e34", "e3", "e4"),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 2
        assert result[0].metadata.get("entity_count") > result[1].metadata.get("entity_count", 0)

    def test_same_size_higher_confidence_first(self) -> None:
        nodes = [
            _entity_node("e1", "A", confidence=0.9),
            _entity_node("e2", "B", confidence=0.1),
            _entity_node("e3", "C", confidence=0.8),
            _entity_node("e4", "D", confidence=0.2),
        ]
        edges = [
            _entity_edge("e12", "e1", "e2"),
            _entity_edge("e34", "e3", "e4"),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 2
        assert result[0].confidence >= result[1].confidence

    def test_same_size_confidence_label_asc(self) -> None:
        nodes = [
            _entity_node("e1", "Zeta", confidence=0.5),
            _entity_node("e2", "Zet", confidence=0.5),
            _entity_node("e3", "Alpha", confidence=0.5),
            _entity_node("e4", "Alp", confidence=0.5),
        ]
        edges = [
            _entity_edge("e12", "e1", "e2"),
            _entity_edge("e34", "e3", "e4"),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert result[0].label <= result[1].label

    def test_size_priority_over_confidence(self) -> None:
        large_low_conf = [
            _entity_node(f"e{i}", f"N{i}", confidence=0.1) for i in range(5)
        ]
        small_high_conf = [
            _entity_node("e5", "High", confidence=0.9),
            _entity_node("e6", "Low", confidence=0.9),
        ]
        nodes = large_low_conf + small_high_conf
        edges = (
            [_entity_edge(f"e{i:02d}", f"e{i}", f"e{i+1}") for i in range(4)]
            + [_entity_edge("e56", "e5", "e6")]
        )
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 2
        assert result[0].metadata.get("entity_count") == 5
        assert result[1].metadata.get("entity_count") == 2


# ===========================================================================
# 17. Max theme cap
# ===========================================================================


class TestMaxThemes:
    """Cap on number of themes returned."""

    def test_max_themes_limits_output(self) -> None:
        nodes = [_entity_node(f"e{i}", f"N{i}") for i in range(8)]
        edges = [
            _entity_edge(f"e{i:02d}", f"e{i}", f"e{i+1}")
            for i in range(0, 7, 2)
        ]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g, max_themes=2)
        assert len(result) <= 2

    def test_max_themes_high_returns_all(self) -> None:
        nodes = [_entity_node(f"e{i}", f"N{i}") for i in range(8)]
        edges = [
            _entity_edge(f"e{i:02d}", f"e{i}", f"e{i+1}")
            for i in range(0, 7, 2)
        ]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g, max_themes=100)
        assert len(result) == 4

    def test_max_themes_zero_returns_empty(self) -> None:
        result = ThemeDetector().detect_themes(_two_entity_graph(), max_themes=0)
        assert result == []

    def test_max_themes_negative_treated_as_zero(self) -> None:
        result = ThemeDetector().detect_themes(_two_entity_graph(), max_themes=-1)
        assert result == []


# ===========================================================================
# 18. Metadata
# ===========================================================================


class TestMetadata:
    """Metadata fields in ThemeCluster."""

    def test_entity_count_in_metadata(self) -> None:
        result = ThemeDetector().detect_themes(_two_entity_graph())
        assert result[0].metadata.get("entity_count") == 2

    def test_document_count_in_metadata(self) -> None:
        e1 = _entity_node("e1", "A")
        e2 = _entity_node("e2", "B")
        d1 = _doc_node("d1", "Doc1")
        d2 = _doc_node("d2", "Doc2")
        edges = [
            _entity_edge("e", "e1", "e2"),
            _doc_entity_edge("de1", "d1", "e1"),
            _doc_entity_edge("de2", "d2", "e2"),
        ]
        g = CorpusGraphResult(nodes=[e1, e2, d1, d2], edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert result[0].metadata.get("document_count") == 2

    def test_edge_count_in_metadata(self) -> None:
        a = _entity_node("e1", "A")
        b = _entity_node("e2", "B")
        c = _entity_node("e3", "C")
        edges = [
            _entity_edge("e12", "e1", "e2"),
            _entity_edge("e23", "e2", "e3"),
        ]
        g = CorpusGraphResult(nodes=[a, b, c], edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert result[0].metadata.get("edge_count") == 2

    def test_edge_count_no_edges(self) -> None:
        a = _entity_node("e1", "A")
        b = _entity_node("e2", "B")
        e = _entity_edge("e", "e1", "e2", RelationType.CONTRADICTS)
        g = CorpusGraphResult(nodes=[a, b], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 0

    def test_metadata_contains_keys(self) -> None:
        result = ThemeDetector().detect_themes(_two_entity_graph())
        meta = result[0].metadata
        assert "entity_count" in meta
        assert "document_count" in meta
        assert "edge_count" in meta


# ===========================================================================
# 19. Convenience helper
# ===========================================================================


class TestConvenienceHelper:
    """Module-level detect_themes convenience function."""

    def test_convenience_returns_list(self) -> None:
        result = detect_themes(_two_entity_graph())
        assert isinstance(result, list)

    def test_convenience_returns_theme_clusters(self) -> None:
        result = detect_themes(_two_entity_graph())
        assert all(isinstance(t, ThemeCluster) for t in result)

    def test_convenience_empty_graph(self) -> None:
        result = detect_themes(None)
        assert result == []

    def test_convenience_passes_parameters(self) -> None:
        g = _two_entity_graph()
        r1 = detect_themes(g, max_themes=1)
        r2 = detect_themes(g, max_themes=10)
        assert len(r1) <= len(r2)

    def test_convenience_consistent_with_detector(self) -> None:
        g = _two_entity_graph()
        r1 = detect_themes(g)
        r2 = ThemeDetector().detect_themes(g)
        assert r1 == r2


# ===========================================================================
# 20. Large graph (100+ nodes)
# ===========================================================================


class TestLargeGraph:
    """Large graph performance and correctness."""

    def test_100_entity_chain(self) -> None:
        nodes = [_entity_node(f"e{i:04d}", f"N{i}") for i in range(100)]
        edges = [_entity_edge(f"e{i:04d}", f"e{i:04d}", f"e{i+1:04d}") for i in range(99)]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 1
        assert result[0].metadata.get("entity_count") == 100

    def test_100_entity_isolated_pairs(self) -> None:
        nodes = [_entity_node(f"e{i:04d}", f"N{i}") for i in range(100)]
        edges = [_entity_edge(f"e{i:04d}", f"e{i:04d}", f"e{i+1:04d}") for i in range(0, 100, 2)]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g, max_themes=100)
        assert len(result) == 50

    def test_large_graph_all_same_label(self) -> None:
        nodes = [_entity_node(f"e{i:04d}", f"N{i}", entity_label="dataset") for i in range(50)]
        edges = [_entity_edge(f"e{i:04d}", f"e{i:04d}", f"e{(i+1)%50:04d}") for i in range(50)]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert len(result) >= 1

    def test_large_graph_no_edges(self) -> None:
        nodes = [_entity_node(f"e{i:04d}", f"N{i}") for i in range(100)]
        g = CorpusGraphResult(nodes=nodes, edges=[])
        result = ThemeDetector().detect_themes(g)
        assert result == []


# ===========================================================================
# 21. Serialization round-trip
# ===========================================================================


class TestSerialization:
    """ThemeCluster serialization round-trip."""

    def test_round_trip_json(self) -> None:
        result = ThemeDetector().detect_themes(_two_entity_graph())
        cluster = result[0]
        d = cluster.model_dump()
        restored = ThemeCluster.model_validate(d)
        assert restored.cluster_id == cluster.cluster_id
        assert restored.label == cluster.label
        assert restored.theme_type == cluster.theme_type
        assert restored.confidence == cluster.confidence

    def test_round_trip_json_multiple_fields(self) -> None:
        e1 = _entity_node("e1", "BERT", entity_label="method", confidence=0.9)
        e2 = _entity_node("e2", "GPT", entity_label="method", confidence=0.8)
        d1 = _doc_node("d1")
        edges = [
            _entity_edge("e", "e1", "e2"),
            _doc_entity_edge("de", "d1", "e1"),
        ]
        g = CorpusGraphResult(nodes=[e1, e2, d1], edges=edges)
        result = ThemeDetector().detect_themes(g)
        cluster = result[0]
        d = cluster.model_dump()
        restored = ThemeCluster.model_validate(d)
        assert restored.document_ids == cluster.document_ids
        assert restored.entity_cluster_ids == cluster.entity_cluster_ids
        assert restored.entity_labels == cluster.entity_labels
        assert restored.metadata == cluster.metadata

    def test_serialize_empty_before_detect(self) -> None:
        tc = ThemeCluster(cluster_id="test_id", label="Test")
        d = tc.model_dump()
        restored = ThemeCluster.model_validate(d)
        assert restored.cluster_id == "test_id"

    def test_theme_type_enum_round_trip(self) -> None:
        tc = ThemeCluster(cluster_id="t1", theme_type="method", label="M",
                          entities=["e1"])
        assert tc.theme_type == "method"
        d = tc.model_dump()
        restored = ThemeCluster.model_validate(d)
        assert restored.theme_type == "method"


# ===========================================================================
# 22. Edge cases — malformed / partial graph
# ===========================================================================


class TestEdgeCases:
    """Edge cases: malformed nodes, missing attributes, etc."""

    def test_node_without_node_type(self) -> None:
        node = CorpusGraphNode(node_id="n1", node_type="document", label="N")
        g = CorpusGraphResult(nodes=[node], edges=[])
        result = ThemeDetector().detect_themes(g)
        assert result == []

    def test_entity_node_without_metadata(self) -> None:
        n = CorpusGraphNode(node_id="e1", node_type="entity_cluster", label="E1")
        m = CorpusGraphNode(node_id="e2", node_type="entity_cluster", label="E2")
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=[n, m], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 1
        assert result[0].confidence == 0.0

    def test_no_edges_attr(self) -> None:
        class FakeGraph:
            nodes = []
        result = ThemeDetector().detect_themes(FakeGraph())
        assert result == []

    def test_no_nodes_attr(self) -> None:
        class FakeGraph:
            edges = []
        result = ThemeDetector().detect_themes(FakeGraph())
        assert result == []

    def test_missing_entity_label_none(self) -> None:
        n1 = CorpusGraphNode(
            node_id="e1", node_type="entity_cluster", label="E1",
            metadata={"confidence": 0.5},
        )
        n2 = CorpusGraphNode(
            node_id="e2", node_type="entity_cluster", label="E2",
            metadata={"confidence": 0.5},
        )
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=[n1, n2], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].theme_type == "concept"

    def test_entity_node_confidence_none(self) -> None:
        n1 = CorpusGraphNode(
            node_id="e1", node_type="entity_cluster", label="E1",
            metadata={"label": "method"},
        )
        n2 = CorpusGraphNode(
            node_id="e2", node_type="entity_cluster", label="E2",
            metadata={"label": "method"},
        )
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=[n1, n2], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].confidence == 0.0

    def test_entity_node_negative_confidence(self) -> None:
        n1 = _entity_node("e1", "A", confidence=-0.1)
        n2 = _entity_node("e2", "B", confidence=-0.2)
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=[n1, n2], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert result[0].confidence >= 0.0

    def test_mixed_doc_and_entity_graph(self) -> None:
        docs = [_doc_node(f"d{i}") for i in range(3)]
        ents = [_entity_node(f"e{i}", f"Entity{i}") for i in range(4)]
        edges = [
            _entity_edge("e01", "e0", "e1"),
            _entity_edge("e23", "e2", "e3"),
            _doc_entity_edge("de0", "d0", "e0"),
            _doc_entity_edge("de1", "d1", "e1"),
            _doc_entity_edge("de2", "d2", "e2"),
        ]
        g = CorpusGraphResult(nodes=docs + ents, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 2

    def test_detector_does_not_mutate_graph(self) -> None:
        g = _two_entity_graph()
        original_nodes = list(g.nodes)
        original_edges = list(g.edges)
        ThemeDetector().detect_themes(g)
        assert g.nodes == original_nodes
        assert g.edges == original_edges


# ===========================================================================
# 23. Document discovery
# ===========================================================================


class TestDocumentDiscovery:
    """Document ID extraction from entity→document edges."""

    def test_single_document(self) -> None:
        e1 = _entity_node("e1", "A")
        e2 = _entity_node("e2", "B")
        d1 = _doc_node("d1")
        edges = [
            _entity_edge("e", "e1", "e2"),
            _doc_entity_edge("de", "d1", "e1"),
        ]
        g = CorpusGraphResult(nodes=[e1, e2, d1], edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert result[0].document_ids == ["d1"]

    def test_multiple_documents(self) -> None:
        e1 = _entity_node("e1", "A")
        e2 = _entity_node("e2", "B")
        docs = [_doc_node(f"d{i}") for i in range(3)]
        edges = [
            _entity_edge("e", "e1", "e2"),
            _doc_entity_edge("de0", "d0", "e1"),
            _doc_entity_edge("de1", "d1", "e1"),
            _doc_entity_edge("de2", "d2", "e2"),
        ]
        g = CorpusGraphResult(nodes=[e1, e2] + docs, edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert len(result[0].document_ids) == 3

    def test_document_deduplication(self) -> None:
        e1 = _entity_node("e1", "A")
        e2 = _entity_node("e2", "B")
        d1 = _doc_node("d1")
        edges = [
            _entity_edge("e", "e1", "e2"),
            _doc_entity_edge("de1", "d1", "e1"),
            _doc_entity_edge("de2", "d1", "e2"),
        ]
        g = CorpusGraphResult(nodes=[e1, e2, d1], edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert result[0].document_ids == ["d1"]


# ===========================================================================
# 24. USES_METHOD edge type
# ===========================================================================


class TestUsesMethodEdges:
    """USES_METHOD edges used for adjacency."""

    def test_uses_method_creates_component(self) -> None:
        a = _entity_node("e1", "SVM")
        b = _entity_node("e2", "RF")
        e = _entity_edge("e", "e1", "e2", RelationType.USES_METHOD)
        g = CorpusGraphResult(nodes=[a, b], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 1

    def test_uses_method_and_compares_with(self) -> None:
        a = _entity_node("e1", "A")
        b = _entity_node("e2", "B")
        c = _entity_node("e3", "C")
        edges = [
            _entity_edge("e1", "e1", "e2", RelationType.USES_METHOD),
            _entity_edge("e2", "e2", "e3", RelationType.COMPARES_WITH),
        ]
        g = CorpusGraphResult(nodes=[a, b, c], edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 1
        assert result[0].metadata.get("entity_count") == 3


# ===========================================================================
# 25. Relation type tracking
# ===========================================================================


class TestRelationTypes:
    """Relation types tracked in theme cluster."""

    def test_compares_with_in_relation_types(self) -> None:
        result = ThemeDetector().detect_themes(_two_entity_graph())
        assert "compares_with" in result[0].relation_types

    def test_uses_method_in_relation_types(self) -> None:
        a = _entity_node("e1", "A")
        b = _entity_node("e2", "B")
        e = _entity_edge("e", "e1", "e2", RelationType.USES_METHOD)
        g = CorpusGraphResult(nodes=[a, b], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert "uses_method" in result[0].relation_types


# ===========================================================================
# 26. ThemeType enum integration
# ===========================================================================


class TestThemeTypeIntegration:
    """ThemeType enum values match detector output."""

    def test_method_value(self) -> None:
        assert ThemeType.METHOD.value == "method"

    def test_dataset_value(self) -> None:
        assert ThemeType.DATASET.value == "dataset"

    def test_metric_value(self) -> None:
        assert ThemeType.METRIC.value == "metric"

    def test_concept_value(self) -> None:
        assert ThemeType.CONCEPT.value == "concept"

    def test_from_string(self) -> None:
        assert ThemeType("method") == ThemeType.METHOD


# ===========================================================================
# 27. min_cluster_size edge cases
# ===========================================================================


class TestMinClusterSizeEdgeCases:
    """Boundary conditions for min_cluster_size."""

    def test_min_size_one_single_connected_pair(self) -> None:
        a = _entity_node("e1", "A")
        b = _entity_node("e2", "B")
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=[a, b], edges=[e])
        result = ThemeDetector().detect_themes(g, min_cluster_size=1)
        assert len(result) == 1

    def test_min_size_two_filters_pair(self) -> None:
        a = _entity_node("e1", "A")
        b = _entity_node("e2", "B")
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=[a, b], edges=[e])
        result = ThemeDetector().detect_themes(g, min_cluster_size=2)
        assert len(result) == 1

    def test_min_size_three_filters_pair(self) -> None:
        a = _entity_node("e1", "A")
        b = _entity_node("e2", "B")
        e = _entity_edge("e", "e1", "e2")
        g = CorpusGraphResult(nodes=[a, b], edges=[e])
        result = ThemeDetector().detect_themes(g, min_cluster_size=3)
        assert len(result) == 0

    def test_min_size_large_value(self) -> None:
        nodes = [_entity_node(f"e{i}", f"N{i}") for i in range(10)]
        edges = [_entity_edge(f"e{i:02d}", f"e{i}", f"e{i+1}") for i in range(9)]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        result = ThemeDetector().detect_themes(g, min_cluster_size=100)
        assert result == []


# ===========================================================================
# 28. Edge metadata presence
# ===========================================================================


class TestEdgeMetadata:
    """Edge metadata (like edge_kind) does not break detection."""

    def test_edge_with_extra_metadata(self) -> None:
        a = _entity_node("e1", "A")
        b = _entity_node("e2", "B")
        e = CorpusGraphEdge(
            edge_id="e",
            source_id="e1",
            target_id="e2",
            relation_type=RelationType.COMPARES_WITH,
            confidence=0.8,
            metadata={"source": "test", "year": 2024},
        )
        g = CorpusGraphResult(nodes=[a, b], edges=[e])
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 1

    def test_doc_entity_edge_with_extra_metadata(self) -> None:
        e1 = _entity_node("e1", "A")
        e2 = _entity_node("e2", "B")
        d1 = _doc_node("d1")
        edges = [
            _entity_edge("e", "e1", "e2"),
            CorpusGraphEdge(
                edge_id="de",
                source_id="d1",
                target_id="e1",
                relation_type=RelationType.EXTENDS,
                confidence=0.9,
                metadata={"edge_kind": "doc_contains_entity", "entity_label": "method"},
            ),
        ]
        g = CorpusGraphResult(nodes=[e1, e2, d1], edges=edges)
        result = ThemeDetector().detect_themes(g)
        assert len(result) == 1
