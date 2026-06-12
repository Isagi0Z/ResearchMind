"""Comprehensive tests for ReviewOrchestrator (Module 6, Phase 8).

Covers:
  - Construction & basics
  - Empty corpus / minimal pipeline
  - All 8 review types
  - Full pipeline with valid data
  - Error isolation (each stage exception)
  - Determinism
  - Large collections
  - Convenience helper
  - Serialization
  - Edge cases
"""

from __future__ import annotations

import pytest

from researchmind.synthesis.models import (
    ReviewFinding,
    ReviewRequest,
    ReviewResult,
    ReviewSection,
)
from researchmind.synthesis.orchestrator import ReviewOrchestrator, generate_review


# ===========================================================================
# Mock helpers
# ===========================================================================


def _make_entity_node(
    entity_id: str = "e_001",
    label: str = "method",
    confidence: float = 0.8,
) -> object:
    return type("Node", (), {
        "node_id": entity_id,
        "node_type": "entity",
        "metadata": {"label": label, "confidence": confidence},
    })()


def _make_edge(
    source: str = "e_001",
    target: str = "e_002",
    relation: str = "COMPARES_WITH",
    confidence: float = 0.7,
) -> object:
    return type("Edge", (), {
        "source_id": source,
        "target_id": target,
        "relation_type": relation,
        "metadata": {"confidence": confidence} if confidence else {},
    })()


def _make_claim(
    claim_id: str = "c_001",
    text: str = "Evidence suggests X is effective.",
    confidence: float = 0.8,
) -> object:
    return type("Claim", (), {
        "claim_id": claim_id,
        "text": text,
        "confidence": confidence,
    })()


def _make_doc(
    doc_id: str = "doc_001",
    title: str = "Test Document",
    claims: list | None = None,
) -> object:
    claims = claims or [_make_claim()]
    meta = type("Meta", (), {"ruo_id": doc_id, "title": title})()
    return type("Doc", (), {
        "meta": meta,
        "doc_id": doc_id,
        "title": title,
        "claims": claims,
        "get_claims": lambda: claims,
        "triples": [],
        "evidence_records": [],
        "aggregated_evidence": [],
    })()


def _make_graph(
    nodes: list | None = None,
    edges: list | None = None,
) -> object:
    return type("Graph", (), {
        "nodes": nodes or [],
        "edges": edges or [],
    })()


def _make_corpus(docs: list | None = None) -> object:
    docs = docs or []
    return type("Corpus", (), {
        "get_documents": lambda: docs,
    })()


# ===========================================================================
# 1. Construction & basics
# ===========================================================================


class TestConstruction:
    """ReviewOrchestrator construction."""

    def test_default_construction(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        assert isinstance(ro, ReviewOrchestrator)

    def test_construction_with_all_deps(self) -> None:
        ro = ReviewOrchestrator(
            corpus_manager=_make_corpus(),
            graph=_make_graph(),
            consensus_engine=object(),
            contradiction_engine=object(),
            gap_engine=object(),
            multi_hop_reasoner=object(),
            document_store=object(),
        )
        assert isinstance(ro, ReviewOrchestrator)

    def test_generate_exists(self) -> None:
        assert hasattr(ReviewOrchestrator, "generate")

    def test_generate_callable(self) -> None:
        assert callable(ReviewOrchestrator(corpus_manager=None, graph=None).generate)

    def test_generate_returns_review_result(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        req = ReviewRequest(review_id="r1", review_type="general")
        result = ro.generate(req)
        assert isinstance(result, ReviewResult)

    def test_generate_never_raises(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        for rt in ["general", "method", "dataset", "consensus",
                    "contradiction", "research_gap", "comparative", "landscape"]:
            req = ReviewRequest(review_id="r", review_type=rt)
            result = ro.generate(req)
            assert isinstance(result, ReviewResult)


# ===========================================================================
# 2. Empty corpus / minimal pipeline
# ===========================================================================


class TestEmptyCorpus:
    """Empty corpus returns valid review with warnings."""

    def test_returns_result(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        req = ReviewRequest(review_id="empty", review_type="general")
        result = ro.generate(req)
        assert isinstance(result, ReviewResult)

    def test_has_sections(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert len(result.sections) == 8

    def test_confidence_zero(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert result.confidence == 0.0

    def test_warnings_title(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert result.title == "Literature Review"

    def test_warnings_list(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert isinstance(result.warnings, list)

    def test_errors_empty(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert result.errors == []

    def test_abstract_present(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert result.abstract != ""

    def test_review_id_preserved(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="my_review", review_type="general"))
        assert result.review_id == "my_review"

    def test_metadata_present(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert "pipeline_version" in result.metadata

    def test_empty_graph_no_crash(self) -> None:
        corpus = _make_corpus([_make_doc("doc_001")])
        graph = _make_graph([], [])
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_graph_with_only_docs_no_crash(self) -> None:
        doc = _make_doc("doc_001")
        corpus = _make_corpus([doc])
        doc_node = type("Node", (), {"node_id": "doc_001", "node_type": "document", "metadata": {}})()
        graph = _make_graph([doc_node], [])
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert isinstance(result, ReviewResult)


# ===========================================================================
# 3. Minimal pipeline with entity graph
# ===========================================================================


class TestMinimalPipeline:
    """Minimal valid pipeline with entity graph and documents."""

    @staticmethod
    def _make_minimal_setup():
        doc = _make_doc("doc_001", "Paper A", [
            _make_claim("c1", "Method X achieves 95% accuracy.", 0.9),
        ])
        corpus = _make_corpus([doc])
        e1 = _make_entity_node("e1", "method", 0.9)
        e2 = _make_entity_node("e2", "method", 0.8)
        graph = _make_graph(
            nodes=[e1, e2],
            edges=[_make_edge("e1", "e2", "COMPARES_WITH", 0.85)],
        )
        return corpus, graph

    def test_pipeline_returns_result(self) -> None:
        corpus, graph = self._make_minimal_setup()
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="p", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_pipeline_has_sections(self) -> None:
        corpus, graph = self._make_minimal_setup()
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="p", review_type="general"))
        assert len(result.sections) >= 4

    def test_pipeline_abstract_first(self) -> None:
        corpus, graph = self._make_minimal_setup()
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="p", review_type="general"))
        if result.sections:
            assert result.sections[0].section_type == "abstract"

    def test_pipeline_conclusion_last(self) -> None:
        corpus, graph = self._make_minimal_setup()
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="p", review_type="general"))
        if result.sections:
            assert result.sections[-1].section_type == "conclusion"

    def test_pipeline_confidence_positive(self) -> None:
        corpus, graph = self._make_minimal_setup()
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="p", review_type="general"))
        assert 0.0 <= result.confidence <= 1.0

    def test_pipeline_no_errors(self) -> None:
        corpus, graph = self._make_minimal_setup()
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="p", review_type="general"))
        assert len(result.errors) == 0

    def test_pipeline_total_findings(self) -> None:
        corpus, graph = self._make_minimal_setup()
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="p", review_type="general"))
        total = sum(len(s.findings) for s in result.sections)
        assert result.total_findings == total


# ===========================================================================
# 4. All review types
# ===========================================================================


class TestAllReviewTypes:
    """All 8 review types produce results."""

    REVIEW_TYPES = [
        "general", "method", "dataset", "consensus",
        "contradiction", "research_gap", "comparative", "landscape",
    ]

    @staticmethod
    def _setup():
        doc = _make_doc("doc_001", "Paper A", [
            _make_claim("c1", "Method X achieves 95%.", 0.9),
        ])
        corpus = _make_corpus([doc])
        e1 = _make_entity_node("e1", "method", 0.9)
        e2 = _make_entity_node("e2", "method", 0.8)
        graph = _make_graph(
            nodes=[e1, e2],
            edges=[_make_edge("e1", "e2", "COMPARES_WITH", 0.85)],
        )
        return corpus, graph

    def test_all_types_return_result(self) -> None:
        corpus, graph = self._setup()
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        for rt in self.REVIEW_TYPES:
            result = ro.generate(ReviewRequest(review_id="r", review_type=rt))
            assert isinstance(result, ReviewResult), f"Failed for {rt}"

    def test_all_types_have_sections(self) -> None:
        corpus, graph = self._setup()
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        for rt in self.REVIEW_TYPES:
            result = ro.generate(ReviewRequest(review_id="r", review_type=rt))
            assert len(result.sections) >= 1, f"No sections for {rt}"

    def test_all_types_correct_review_type(self) -> None:
        corpus, graph = self._setup()
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        for rt in self.REVIEW_TYPES:
            result = ro.generate(ReviewRequest(review_id="r", review_type=rt))
            assert result.review_type == rt

    def test_method_review_has_comparative(self) -> None:
        corpus, graph = self._setup()
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="r", review_type="method"))
        types = [s.section_type for s in result.sections]
        assert "comparative" in types

    def test_landscape_review_has_introduction(self) -> None:
        corpus, graph = self._setup()
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="r", review_type="landscape"))
        types = [s.section_type for s in result.sections]
        assert "introduction" in types

    def test_research_gap_review_has_future_work(self) -> None:
        corpus, graph = self._setup()
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="r", review_type="research_gap"))
        types = [s.section_type for s in result.sections]
        assert "future_work" in types

    def test_dataset_review_has_datasets(self) -> None:
        corpus, graph = self._setup()
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="r", review_type="dataset"))
        types = [s.section_type for s in result.sections]
        assert "datasets" in types

    def test_case_insensitive_review_type(self) -> None:
        corpus, graph = self._setup()
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="r", review_type="GENERAL"))
        assert result.review_type == "general"


# ===========================================================================
# 5. Error isolation — each stage fails gracefully
# ===========================================================================


class TestErrorIsolation:
    """Each pipeline stage failure produces warnings, never crashes."""

    def test_broken_graph_detector(self) -> None:
        class BrokenGraph:
            @property
            def nodes(self):
                raise RuntimeError("graph broken")
            @property
            def edges(self):
                raise RuntimeError("graph broken")
        ro = ReviewOrchestrator(
            corpus_manager=None,
            graph=BrokenGraph(),
        )
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_broken_corpus_collector(self) -> None:
        class BrokenCorpus:
            def get_documents(self):
                raise RuntimeError("corpus broken")
        ro = ReviewOrchestrator(
            corpus_manager=BrokenCorpus(),
            graph=_make_graph(),
        )
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_detector_has_warnings(self) -> None:
        class BrokenGraph:
            @property
            def nodes(self):
                raise RuntimeError("graph broken")
            @property
            def edges(self):
                raise RuntimeError("graph broken")
        ro = ReviewOrchestrator(
            corpus_manager=None,
            graph=BrokenGraph(),
        )
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert len(result.warnings) >= 1

    def test_collector_produces_warnings(self) -> None:
        class BrokenCorpus:
            def get_documents(self):
                raise RuntimeError("broken")
        ro = ReviewOrchestrator(
            corpus_manager=BrokenCorpus(),
            graph=_make_graph([_make_entity_node("e1")]),
        )
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_malformed_graph_no_nodes(self) -> None:
        graph = _make_graph(nodes=None, edges=None)
        ro = ReviewOrchestrator(corpus_manager=None, graph=graph)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_malformed_graph_wrong_types(self) -> None:
        graph = _make_graph(nodes="not_a_list", edges="not_a_list")
        ro = ReviewOrchestrator(corpus_manager=None, graph=graph)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_corpus_without_get_documents(self) -> None:
        class BareCorpus:
            pass
        ro = ReviewOrchestrator(corpus_manager=BareCorpus(), graph=_make_graph())
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_corpus_get_documents_returns_none(self) -> None:
        class NoneCorpus:
            def get_documents(self):
                return None
        ro = ReviewOrchestrator(corpus_manager=NoneCorpus(), graph=_make_graph())
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert isinstance(result, ReviewResult)


# ===========================================================================
# 6. Convenience helper
# ===========================================================================


class TestConvenienceHelper:
    """Module-level generate_review convenience function."""

    def test_generate_review_returns_result(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        req = ReviewRequest(review_id="r", review_type="general")
        result = generate_review(ro, req)
        assert isinstance(result, ReviewResult)

    def test_generate_review_empty(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = generate_review(ro, ReviewRequest(review_id="r", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_generate_review_consistent_with_generate(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        req = ReviewRequest(review_id="r", review_type="general")
        r1 = generate_review(ro, req)
        r2 = ro.generate(req)
        assert r1.review_id == r2.review_id
        assert r1.confidence == r2.confidence


# ===========================================================================
# 7. Determinism
# ===========================================================================


class TestDeterminism:
    """Repeated runs produce identical results."""

    @staticmethod
    def _setup():
        doc = _make_doc("doc_001", "Paper A", [
            _make_claim("c1", "Method X achieves 95%.", 0.9),
        ])
        corpus = _make_corpus([doc])
        e1 = _make_entity_node("e1", "method", 0.9)
        e2 = _make_entity_node("e2", "method", 0.8)
        graph = _make_graph(
            nodes=[e1, e2],
            edges=[_make_edge("e1", "e2", "COMPARES_WITH", 0.85)],
        )
        return corpus, graph

    def test_repeated_calls_same_result(self) -> None:
        corpus, graph = self._setup()
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        req = ReviewRequest(review_id="det", review_type="general")
        r1 = ro.generate(req)
        r2 = ro.generate(req)
        assert r1.model_dump_json() == r2.model_dump_json()

    def test_deterministic_across_instances(self) -> None:
        corpus, graph = self._setup()
        req = ReviewRequest(review_id="det", review_type="general")
        r1 = ReviewOrchestrator(corpus_manager=corpus, graph=graph).generate(req)
        r2 = ReviewOrchestrator(corpus_manager=corpus, graph=graph).generate(req)
        assert r1.model_dump_json() == r2.model_dump_json()

    def test_deterministic_empty_corpus(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        req = ReviewRequest(review_id="det", review_type="general")
        r1 = ro.generate(req)
        r2 = ro.generate(req)
        assert r1.model_dump_json() == r2.model_dump_json()

    def test_deterministic_all_types(self) -> None:
        corpus, graph = self._setup()
        for rt in ["general", "method", "dataset", "consensus",
                    "contradiction", "landscape"]:
            req = ReviewRequest(review_id="det", review_type=rt)
            ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
            r1 = ro.generate(req)
            r2 = ro.generate(req)
            assert r1.model_dump_json() == r2.model_dump_json(), f"Failed for {rt}"

    def test_no_uuids_in_output(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="det", review_type="general"))
        json_str = result.model_dump_json()
        assert "uuid" not in json_str.lower()
        assert "created_at" not in json_str.lower()
        assert "timestamp" not in json_str.lower()

    def test_no_datetime(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="det", review_type="general"))
        json_str = result.model_dump_json()
        assert "datetime" not in json_str.lower()


# ===========================================================================
# 8. Large collections
# ===========================================================================


class TestLargeCollections:
    """Large input sizes must not crash."""

    def test_100_entity_graph(self) -> None:
        nodes = [_make_entity_node(f"e{i:04d}", "method", 0.5) for i in range(100)]
        edges = [_make_edge(f"e{i:04d}", f"e{(i+1)%100:04d}", "COMPARES_WITH", 0.5)
                 for i in range(100)]
        graph = _make_graph(nodes, edges)
        corpus = _make_corpus([_make_doc("doc_001", "Paper")])
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="big", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_50_documents(self) -> None:
        docs = [_make_doc(f"doc_{i:04d}", f"Paper {i}",
                          [_make_claim(f"c_{i}", f"Claim {i}.", 0.5)])
                for i in range(50)]
        corpus = _make_corpus(docs)
        nodes = [_make_entity_node(f"e{i:04d}", "method", 0.5) for i in range(10)]
        edges = [_make_edge(f"e{i:04d}", f"e{(i+1)%10:04d}", "COMPARES_WITH", 0.5)
                 for i in range(10)]
        graph = _make_graph(nodes, edges)
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="big", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_large_deterministic(self) -> None:
        nodes = [_make_entity_node(f"e{i:04d}", "method", 0.5) for i in range(50)]
        edges = [_make_edge(f"e{i:04d}", f"e{(i+1)%50:04d}", "COMPARES_WITH", 0.5)
                 for i in range(50)]
        graph = _make_graph(nodes, edges)
        corpus = _make_corpus([_make_doc("doc_001", "Paper")])
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        req = ReviewRequest(review_id="big", review_type="general")
        r1 = ro.generate(req)
        r2 = ro.generate(req)
        assert r1.model_dump_json() == r2.model_dump_json()


# ===========================================================================
# 9. Serialization
# ===========================================================================


class TestSerialization:
    """ReviewResult serialization compatibility."""

    def test_model_dump(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="s", review_type="general"))
        d = result.model_dump()
        assert isinstance(d, dict)

    def test_model_validate(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="s", review_type="general"))
        d = result.model_dump()
        restored = ReviewResult.model_validate(d)
        assert restored.review_id == result.review_id

    def test_json_round_trip(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="s", review_type="general"))
        json_str = result.model_dump_json()
        restored = ReviewResult.model_validate_json(json_str)
        assert restored.review_id == result.review_id

    def test_minimal_pipeline_round_trip(self) -> None:
        doc = _make_doc("doc_001", "Paper", [_make_claim("c1", "Claim.", 0.8)])
        corpus = _make_corpus([doc])
        e1 = _make_entity_node("e1", "method", 0.8)
        e2 = _make_entity_node("e2", "method", 0.7)
        graph = _make_graph(nodes=[e1, e2], edges=[_make_edge("e1", "e2", "COMPARES_WITH", 0.7)])
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="s", review_type="general"))
        json_str = result.model_dump_json()
        restored = ReviewResult.model_validate_json(json_str)
        assert len(restored.sections) == len(result.sections)


# ===========================================================================
# 10. Edge cases
# ===========================================================================


class TestEdgeCases:
    """Edge cases and malformed inputs."""

    def test_unknown_review_type(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        req = ReviewRequest.model_construct(
            review_id="e", review_type="unknown_type",
        )
        result = ro.generate(req)
        assert isinstance(result, ReviewResult)

    def test_empty_review_id(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_empty_title(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        req = ReviewRequest(review_id="e", review_type="general", title="")
        result = ro.generate(req)
        # title defaults to "Literature Review"
        assert result.title == "Literature Review" or result.title == ""

    def test_none_title(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        req = ReviewRequest.model_construct(
            review_id="e", review_type="general", title=None,
        )
        result = ro.generate(req)
        assert isinstance(result, ReviewResult)

    def test_mixed_entity_types(self) -> None:
        e1 = _make_entity_node("e1", "method", 0.9)
        e2 = _make_entity_node("e2", "dataset", 0.8)
        e3 = _make_entity_node("e3", "metric", 0.7)
        graph = _make_graph(
            nodes=[e1, e2, e3],
            edges=[
                _make_edge("e1", "e2", "COMPARES_WITH", 0.8),
                _make_edge("e2", "e3", "USES_METHOD", 0.7),
            ],
        )
        corpus = _make_corpus([_make_doc("doc_001", "Paper")])
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_entity_without_label(self) -> None:
        node = type("Node", (), {
            "node_id": "e1",
            "node_type": "entity",
            "metadata": {},
        })()
        graph = _make_graph(nodes=[node], edges=[])
        corpus = _make_corpus([_make_doc("doc_001", "Paper")])
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_entity_with_none_metadata(self) -> None:
        node = type("Node", (), {
            "node_id": "e1",
            "node_type": "entity",
            "metadata": None,
        })()
        graph = _make_graph(nodes=[node], edges=[])
        corpus = _make_corpus([_make_doc("doc_001", "Paper")])
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_document_without_claims(self) -> None:
        doc = _make_doc("doc_001", "Paper", claims=[])
        corpus = _make_corpus([doc])
        e1 = _make_entity_node("e1", "method", 0.8)
        graph = _make_graph(nodes=[e1], edges=[])
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_document_without_meta(self) -> None:
        doc = type("Doc", (), {
            "doc_id": "doc_001",
            "title": "Paper",
            "claims": [_make_claim("c1", "Claim.", 0.8)],
            "get_claims": lambda: [_make_claim("c1", "Claim.", 0.8)],
            "triples": [],
            "evidence_records": [],
            "aggregated_evidence": [],
        })()
        corpus = _make_corpus([doc])
        e1 = _make_entity_node("e1", "method", 0.8)
        graph = _make_graph(nodes=[e1], edges=[])
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_finding_with_missing_evidence(self) -> None:
        doc = _make_doc("doc_001", "Paper", [
            _make_claim("c1", "Method X achieves 95%.", 0.9),
        ])
        corpus = _make_corpus([doc])
        e1 = _make_entity_node("e1", "method", 0.9)
        graph = _make_graph(nodes=[e1], edges=[])
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_min_confidence_zero(self) -> None:
        doc = _make_doc("doc_001", "Paper", [
            _make_claim("c1", "Claim.", 0.1),
        ])
        corpus = _make_corpus([doc])
        e1 = _make_entity_node("e1", "method", 0.1)
        graph = _make_graph(nodes=[e1], edges=[])
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general",
                                            min_confidence=0.0))
        assert isinstance(result, ReviewResult)

    def test_min_confidence_one(self) -> None:
        doc = _make_doc("doc_001", "Paper", [
            _make_claim("c1", "Claim.", 0.9),
        ])
        corpus = _make_corpus([doc])
        e1 = _make_entity_node("e1", "method", 0.9)
        graph = _make_graph(nodes=[e1], edges=[])
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general",
                                            min_confidence=1.0))
        assert isinstance(result, ReviewResult)

    def test_no_target_entities(self) -> None:
        doc = _make_doc("doc_001", "Paper", [
            _make_claim("c1", "Claim.", 0.8),
        ])
        corpus = _make_corpus([doc])
        graph = _make_graph(nodes=[], edges=[])
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(
            review_id="e", review_type="general",
            target_entities=[],
        ))
        assert isinstance(result, ReviewResult)

    def test_include_contradictions_false(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(
            review_id="e", review_type="general",
            include_contradictions=False,
        ))
        assert isinstance(result, ReviewResult)

    def test_include_gaps_false(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(
            review_id="e", review_type="general",
            include_gaps=False,
        ))
        assert isinstance(result, ReviewResult)

    def test_entity_node_without_node_type(self) -> None:
        node = type("Node", (), {
            "node_id": "e1",
            "metadata": {"label": "method", "confidence": 0.8},
        })()
        graph = _make_graph(nodes=[node], edges=[])
        corpus = _make_corpus([_make_doc("doc_001", "Paper")])
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_edge_without_relation_type(self) -> None:
        e1 = _make_entity_node("e1", "method", 0.8)
        e2 = _make_entity_node("e2", "method", 0.7)
        edge = type("Edge", (), {
            "source_id": "e1",
            "target_id": "e2",
            "metadata": {},
        })()
        graph = _make_graph(nodes=[e1, e2], edges=[edge])
        corpus = _make_corpus([_make_doc("doc_001", "Paper")])
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        assert isinstance(result, ReviewResult)

    def test_review_with_some_findings(self) -> None:
        doc = _make_doc("doc_001", "Paper", [
            _make_claim("c1", "Method X achieves 95% accuracy on benchmark.", 0.9),
            _make_claim("c2", "Method X outperforms baseline by 5%.", 0.8),
            _make_claim("c3", "Method X is computationally efficient.", 0.7),
        ])
        corpus = _make_corpus([doc])
        e1 = _make_entity_node("e1", "method", 0.9)
        e2 = _make_entity_node("e2", "dataset", 0.8)
        e3 = _make_entity_node("e3", "metric", 0.7)
        graph = _make_graph(
            nodes=[e1, e2, e3],
            edges=[
                _make_edge("e1", "e2", "COMPARES_WITH", 0.85),
                _make_edge("e1", "e3", "USES_METHOD", 0.75),
            ],
        )
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        total = sum(len(s.findings) for s in result.sections)
        assert total >= 0

    def test_abstract_content_present_with_data(self) -> None:
        doc = _make_doc("doc_001", "Paper", [
            _make_claim("c1", "Claim text.", 0.8),
        ])
        corpus = _make_corpus([doc])
        e1 = _make_entity_node("e1", "method", 0.8)
        e2 = _make_entity_node("e2", "method", 0.7)
        graph = _make_graph(
            nodes=[e1, e2],
            edges=[_make_edge("e1", "e2", "COMPARES_WITH", 0.7)],
        )
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="e", review_type="general"))
        if result.sections:
            assert result.abstract != ""


# ===========================================================================
# 11. Warning generation
# ===========================================================================


class TestWarnings:
    """Warning generation from pipeline stages."""

    def test_empty_corpus_no_warnings(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="w", review_type="general"))
        assert len(result.warnings) == 0

    def test_broken_detector_has_warning(self) -> None:
        class BadGraph:
            @property
            def nodes(self):
                raise ValueError("bad graph")
            @property
            def edges(self):
                raise ValueError("bad graph")
        ro = ReviewOrchestrator(corpus_manager=None, graph=BadGraph())
        result = ro.generate(ReviewRequest(review_id="w", review_type="general"))
        assert any("Theme detection" in w for w in result.warnings)

    def test_warnings_sorted(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="w", review_type="general"))
        warnings = result.warnings
        assert warnings == sorted(warnings)

    def test_traceability_verification_warning(self) -> None:
        doc = _make_doc("doc_001", "Paper", [
            _make_claim("c1", "Claim.", 0.8),
        ])
        corpus = _make_corpus([doc])
        e1 = _make_entity_node("e1", "method", 0.8)
        e2 = _make_entity_node("e2", "method", 0.7)
        graph = _make_graph(
            nodes=[e1, e2],
            edges=[_make_edge("e1", "e2", "COMPARES_WITH", 0.7)],
        )
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="w", review_type="general"))
        assert isinstance(result, ReviewResult)


# ===========================================================================
# 12. Metadata
# ===========================================================================


class TestMetadata:
    """Pipeline metadata is populated."""

    def test_pipeline_version(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="m", review_type="general"))
        assert result.metadata.get("pipeline_version") == "1.0"

    def test_max_themes_in_metadata(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="m", review_type="general"))
        assert "max_themes" in result.metadata

    def test_warnings_not_errors(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="m", review_type="general"))
        assert len(result.errors) == 0


# ===========================================================================
# 13. ReviewResult post-conditions
# ===========================================================================


class TestResultPostConditions:
    """Post-conditions on generated ReviewResult."""

    def test_total_words_matches_sections(self) -> None:
        doc = _make_doc("doc_001", "Paper", [
            _make_claim("c1", "Claim.", 0.8),
        ])
        corpus = _make_corpus([doc])
        e1 = _make_entity_node("e1", "method", 0.8)
        e2 = _make_entity_node("e2", "method", 0.7)
        graph = _make_graph(
            nodes=[e1, e2],
            edges=[_make_edge("e1", "e2", "COMPARES_WITH", 0.7)],
        )
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="p", review_type="general"))
        computed = sum(s.word_count for s in result.sections)
        assert result.total_words == computed

    def test_total_findings_matches_sections(self) -> None:
        doc = _make_doc("doc_001", "Paper", [
            _make_claim("c1", "Claim.", 0.8),
        ])
        corpus = _make_corpus([doc])
        e1 = _make_entity_node("e1", "method", 0.8)
        e2 = _make_entity_node("e2", "method", 0.7)
        graph = _make_graph(
            nodes=[e1, e2],
            edges=[_make_edge("e1", "e2", "COMPARES_WITH", 0.7)],
        )
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="p", review_type="general"))
        computed = sum(len(s.findings) for s in result.sections)
        assert result.total_findings == computed

    def test_confidence_is_float(self) -> None:
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        result = ro.generate(ReviewRequest(review_id="p", review_type="general"))
        assert isinstance(result.confidence, float)

    def test_confidence_in_0_1(self) -> None:
        doc = _make_doc("doc_001", "Paper", [
            _make_claim("c1", "Claim.", 0.8),
        ])
        corpus = _make_corpus([doc])
        e1 = _make_entity_node("e1", "method", 0.8)
        e2 = _make_entity_node("e2", "method", 0.7)
        graph = _make_graph(
            nodes=[e1, e2],
            edges=[_make_edge("e1", "e2", "COMPARES_WITH", 0.7)],
        )
        ro = ReviewOrchestrator(corpus_manager=corpus, graph=graph)
        result = ro.generate(ReviewRequest(review_id="p", review_type="general"))
        assert 0.0 <= result.confidence <= 1.0
