"""Comprehensive tests for EvidenceCollector (Module 6, Phase 3).

Covers:
  - Construction & basics
  - Empty inputs
  - Single / multiple themes
  - Claim extraction
  - Triple extraction
  - Evidence record extraction
  - AggregatedEvidence passthrough
  - Theme filtering (entity, text, metadata overlap)
  - Confidence filtering
  - Deduplication (id, text, trace)
  - Ranking & cap
  - Metadata
  - Determinism
  - Malformed inputs
  - Serialization round-trip
  - Large corpus
  - Convenience helper
"""

from __future__ import annotations

from typing import Any

import pytest

from researchmind.query.models import AggregatedEvidence
from researchmind.synthesis.evidence_collector import EvidenceCollector, collect_evidence
from researchmind.synthesis.models import EvidenceBundle, ThemeCluster, _generate_id


# ===========================================================================
# Helpers — mock document and evidence objects
# ===========================================================================


class _MockClaim:
    def __init__(self, claim_id: str, sentence: str, confidence: float = 0.8):
        self.claim_id = claim_id
        self.sentence = sentence
        self.confidence = confidence


class _MockTriple:
    def __init__(self, triple_id: str, subject_text: str, predicate: str,
                 object_text: str, confidence: float = 0.7):
        self.triple_id = triple_id
        self.subject_text = subject_text
        self.predicate = predicate
        self.object_text = object_text
        self.confidence = confidence


class _MockEvidenceRecord:
    def __init__(self, evidence_id: str, source_text: str,
                 confidence: float = 0.9, evidence_type: str = "direct_quote"):
        self.evidence_id = evidence_id
        self.source_text = source_text
        self.confidence = confidence
        self.evidence_type = evidence_type


class _MockMeta:
    def __init__(self, ruo_id: str):
        self.ruo_id = ruo_id


class _MockHeader:
    def __init__(self, title: str = ""):
        self.title = title


class _MockDoc:
    """Minimal duck-typed document for testing."""

    def __init__(
        self,
        doc_id: str,
        title: str = "",
        claims: list[_MockClaim] | None = None,
        triples: list[_MockTriple] | None = None,
        evidence_records: list[_MockEvidenceRecord] | None = None,
        aggregated_evidence: list[Any] | None = None,
    ):
        self.meta = _MockMeta(doc_id)
        self.header = _MockHeader(title)
        self.claims = claims or []
        self.triples = triples or []
        self.evidence_records = evidence_records or []
        self.aggregated_evidence = aggregated_evidence or []


class _MockCorpus:
    """Minimal corpus with get_documents()."""

    def __init__(self, docs: list[_MockDoc]):
        self._docs = docs

    def get_documents(self) -> list[_MockDoc]:
        return self._docs


def _make_theme(
    cluster_id: str = "thm_001",
    label: str = "Transformer",
    theme_type: str = "method",
    entities: list[str] | None = None,
    entity_labels: list[str] | None = None,
    entity_cluster_ids: list[str] | None = None,
    document_ids: list[str] | None = None,
    documents: list[str] | None = None,
) -> ThemeCluster:
    resolved_entities = entities or [label.lower()]
    return ThemeCluster(
        cluster_id=cluster_id,
        theme_type=theme_type,
        label=label,
        entities=resolved_entities,
        entity_labels=entity_labels or [label],
        entity_cluster_ids=entity_cluster_ids or resolved_entities,
        document_ids=document_ids or [],
        documents=documents or [],
        confidence=0.8,
    )


# ===========================================================================
# 1. Construction & basics
# ===========================================================================


class TestConstruction:
    """EvidenceCollector construction and basic attributes."""

    def test_default_construction(self) -> None:
        ec = EvidenceCollector()
        assert isinstance(ec, EvidenceCollector)

    def test_collect_method_exists(self) -> None:
        assert hasattr(EvidenceCollector, "collect")

    def test_collect_callable(self) -> None:
        assert callable(EvidenceCollector().collect)

    def test_collect_returns_list(self) -> None:
        result = EvidenceCollector().collect(corpus=None, graph=None, themes=[])
        assert isinstance(result, list)

    def test_collect_returns_evidence_bundles(self) -> None:
        result = EvidenceCollector().collect(corpus=None, graph=None, themes=[])
        assert all(isinstance(b, EvidenceBundle) for b in result)


# ===========================================================================
# 2. Empty inputs
# ===========================================================================


class TestEmptyInputs:
    """Behavior with empty or None inputs."""

    def test_no_themes_returns_empty(self) -> None:
        result = EvidenceCollector().collect(corpus="anything", graph=None, themes=[])
        assert result == []

    def test_none_corpus_no_themes(self) -> None:
        result = EvidenceCollector().collect(corpus=None, graph=None, themes=[])
        assert result == []

    def test_none_corpus_with_theme(self) -> None:
        theme = _make_theme()
        result = EvidenceCollector().collect(corpus=None, graph=None, themes=[theme])
        assert len(result) == 1
        assert result[0].evidence_items == []

    def test_empty_corpus_with_theme(self) -> None:
        corpus = _MockCorpus([])
        theme = _make_theme(document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert len(result) == 1
        assert result[0].evidence_count == 0

    def test_none_graph(self) -> None:
        corpus = _MockCorpus([])
        theme = _make_theme()
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert len(result) == 1


# ===========================================================================
# 3. Single theme
# ===========================================================================


class TestSingleTheme:
    """Single theme evidence collection."""

    def test_single_theme_one_document(self) -> None:
        claim = _MockClaim("c1", "Transformer models are effective", 0.9)
        doc = _MockDoc("d1", title="Transformer Paper", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(
            label="Transformer",
            entity_labels=["Transformer"],
            document_ids=["d1"],
        )
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert len(result) == 1
        assert result[0].evidence_count >= 1

    def test_single_theme_bundle_id(self) -> None:
        doc = _MockDoc("d1")
        corpus = _MockCorpus([doc])
        theme = _make_theme(cluster_id="thm_custom", label="L")
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert len(result) == 1
        assert result[0].bundle_id.startswith("bnd_")

    def test_single_theme_label_in_bundle(self) -> None:
        doc = _MockDoc("d1")
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="MyTheme")
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].theme == "MyTheme"

    def test_single_theme_empty_evidence(self) -> None:
        doc = _MockDoc("d1")
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Unrelated", document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 0


# ===========================================================================
# 4. Multiple themes
# ===========================================================================


class TestMultipleThemes:
    """Multiple themes produce separate bundles."""

    def test_two_themes_two_bundles(self) -> None:
        doc = _MockDoc("d1")
        corpus = _MockCorpus([doc])
        t1 = _make_theme(cluster_id="t1", label="ThemeA")
        t2 = _make_theme(cluster_id="t2", label="ThemeB")
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[t1, t2])
        assert len(result) == 2

    def test_themes_with_different_documents(self) -> None:
        c1 = _MockClaim("c1", "CNN models", 0.8)
        c2 = _MockClaim("c2", "RNN models", 0.7)
        d1 = _MockDoc("d1", claims=[c1])
        d2 = _MockDoc("d2", claims=[c2])
        corpus = _MockCorpus([d1, d2])
        t1 = _make_theme(cluster_id="t1", label="CNN", entity_labels=["CNN"],
                         document_ids=["d1"])
        t2 = _make_theme(cluster_id="t2", label="RNN", entity_labels=["RNN"],
                         document_ids=["d2"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[t1, t2])
        assert len(result) == 2


# ===========================================================================
# 5. Claim extraction
# ===========================================================================


class TestClaimExtraction:
    """Evidence extraction from document claims."""

    def test_single_claim(self) -> None:
        claim = _MockClaim("c1", "BERT improves accuracy", 0.85)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="BERT", entity_labels=["BERT"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 1
        assert result[0].evidence_items[0].source_text == "BERT improves accuracy"

    def test_multiple_claims(self) -> None:
        claims = [
            _MockClaim("c1", "Method A works", 0.9),
            _MockClaim("c2", "Method B fails", 0.5),
        ]
        doc = _MockDoc("d1", claims=claims)
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Method", entity_labels=["Method"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 2

    def test_claim_confidence_preserved(self) -> None:
        claim = _MockClaim("c1", "Claim text", 0.75)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Claim", entity_labels=["Claim"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_items[0].confidence == 0.75

    def test_claim_document_id(self) -> None:
        claim = _MockClaim("c1", "Text", 0.8)
        doc = _MockDoc("doc_xyz", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Text", entity_labels=["Text"],
                            document_ids=["doc_xyz"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_items[0].source_document_id == "doc_xyz"

    def test_claim_evidence_type(self) -> None:
        claim = _MockClaim("c1", "Text", 0.8)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Text", entity_labels=["Text"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_items[0].evidence_type == "claim"


# ===========================================================================
# 6. Triple extraction
# ===========================================================================


class TestTripleExtraction:
    """Evidence extraction from document triples."""

    def test_single_triple(self) -> None:
        triple = _MockTriple("t1", "BERT", "uses", "Transformer", 0.8)
        doc = _MockDoc("d1", triples=[triple])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="BERT", entity_labels=["BERT"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 1
        assert "BERT" in result[0].evidence_items[0].source_text

    def test_triple_confidence(self) -> None:
        triple = _MockTriple("t1", "A", "is", "B", 0.65)
        doc = _MockDoc("d1", triples=[triple])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="A", entity_labels=["A"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_items[0].confidence == 0.65

    def test_triple_evidence_type(self) -> None:
        triple = _MockTriple("t1", "A", "is", "B", 0.7)
        doc = _MockDoc("d1", triples=[triple])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="A", entity_labels=["A"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_items[0].evidence_type == "triple"


# ===========================================================================
# 7. Evidence record extraction
# ===========================================================================


class TestEvidenceRecordExtraction:
    """Evidence extraction from document evidence_records."""

    def test_single_record(self) -> None:
        rec = _MockEvidenceRecord("r1", "Record text", 0.95, "direct_quote")
        doc = _MockDoc("d1", evidence_records=[rec])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Record", entity_labels=["Record"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 1
        assert result[0].evidence_items[0].source_text == "Record text"

    def test_record_confidence(self) -> None:
        rec = _MockEvidenceRecord("r1", "Text", 0.88)
        doc = _MockDoc("d1", evidence_records=[rec])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Text", entity_labels=["Text"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_items[0].confidence == 0.88

    def test_record_evidence_type(self) -> None:
        rec = _MockEvidenceRecord("r1", "Text", 0.8, "paraphrase")
        doc = _MockDoc("d1", evidence_records=[rec])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Text", entity_labels=["Text"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_items[0].evidence_type == "paraphrase"


# ===========================================================================
# 8. AggregatedEvidence passthrough
# ===========================================================================


class TestAggregatedEvidencePassthrough:
    """Pre-existing AggregatedEvidence objects passed through."""

    def test_passthrough_single(self) -> None:
        ae = AggregatedEvidence(
            evidence_id="ae1", source_text="Existing evidence",
            confidence=0.9, evidence_type="consensus_entry",
            trace=["step1"],
        )
        doc = _MockDoc("d1", aggregated_evidence=[ae])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Existing", entity_labels=["Existing"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 1
        assert result[0].evidence_items[0].source_text == "Existing evidence"

    def test_passthrough_confidence(self) -> None:
        ae = AggregatedEvidence(
            evidence_id="ae1", source_text="Text", confidence=0.6,
            evidence_type="gap_item",
        )
        doc = _MockDoc("d1", aggregated_evidence=[ae])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Text", entity_labels=["Text"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_items[0].confidence == 0.6

    def test_passthrough_dict(self) -> None:
        ae_dict = {
            "evidence_id": "ae_dict",
            "source_text": "Dict evidence",
            "confidence": 0.7,
            "evidence_type": "claim",
        }
        doc = _MockDoc("d1", aggregated_evidence=[ae_dict])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Dict", entity_labels=["Dict"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 1

    def test_passthrough_document_id_assigned(self) -> None:
        ae = AggregatedEvidence(
            evidence_id="ae1", source_text="Text", confidence=0.8,
            evidence_type="claim",
        )
        doc = _MockDoc("d1", aggregated_evidence=[ae])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Text", entity_labels=["Text"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_items[0].source_document_id == "d1"


# ===========================================================================
# 9. Theme filtering — entity overlap
# ===========================================================================


class TestThemeFilteringEntity:
    """Theme filtering by entity overlap."""

    def test_entity_label_in_text(self) -> None:
        claim = _MockClaim("c1", "CNN achieves high accuracy", 0.9)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Optimization", entity_labels=["CNN"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 1

    def test_entity_id_in_text(self) -> None:
        claim = _MockClaim("c1", "ent_bert is a method", 0.8)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="X", entities=["ent_bert"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 1

    def test_entity_cluster_id_in_text(self) -> None:
        claim = _MockClaim("c1", "cluster_lstm shows results", 0.8)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="X", entity_cluster_ids=["cluster_lstm"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 1

    def test_entity_id_in_evidence_id(self) -> None:
        ae = AggregatedEvidence(
            evidence_id="e2_entity_bert",
            source_text="Some text",
            confidence=0.8,
            evidence_type="claim",
        )
        doc = _MockDoc("d1", aggregated_evidence=[ae])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="X", entities=["entity_bert"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 1


# ===========================================================================
# 10. Theme filtering — text overlap
# ===========================================================================


class TestThemeFilteringText:
    """Theme filtering by text overlap."""

    def test_label_in_source_text(self) -> None:
        claim = _MockClaim("c1", "Transformer architecture is key", 0.9)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Transformer", document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 1

    def test_label_missing_from_text(self) -> None:
        claim = _MockClaim("c1", "Nothing related here", 0.9)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Transformer", document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 0

    def test_case_insensitive_text_match(self) -> None:
        claim = _MockClaim("c1", "transformer models", 0.8)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="TRANSFORMER", document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 1

    def test_label_in_document_title(self) -> None:
        claim = _MockClaim("c1", "Some text", 0.8)
        doc = _MockDoc("d1", title="BERT Paper", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="BERT", document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 1


# ===========================================================================
# 11. Theme filtering — metadata overlap
# ===========================================================================


class TestThemeFilteringMetadata:
    """Theme filtering by metadata overlap."""

    def test_theme_label_in_metadata(self) -> None:
        ae = AggregatedEvidence(
            evidence_id="ae1", source_text="Text",
            confidence=0.8, evidence_type="claim",
            metadata={"category": "RNN methods"},
        )
        doc = _MockDoc("d1", aggregated_evidence=[ae])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="RNN", document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 1

    def test_theme_label_in_metadata_list(self) -> None:
        ae = AggregatedEvidence(
            evidence_id="ae1", source_text="Text",
            confidence=0.8, evidence_type="claim",
            metadata={"tags": ["cnn", "transformer"]},
        )
        doc = _MockDoc("d1", aggregated_evidence=[ae])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="transformer", document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 1


# ===========================================================================
# 12. Confidence filtering
# ===========================================================================


class TestConfidenceFiltering:
    """min_confidence filtering."""

    def test_min_confidence_filters_low(self) -> None:
        claims = [
            _MockClaim("c1", "High conf text", 0.9),
            _MockClaim("c2", "Low conf text", 0.3),
        ]
        doc = _MockDoc("d1", claims=claims)
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="text", entity_labels=["text"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(
            corpus=corpus, graph=None, themes=[theme], min_confidence=0.5,
        )
        assert result[0].evidence_count == 1

    def test_min_confidence_zero_allows_all(self) -> None:
        claims = [
            _MockClaim("c1", "Low text", 0.1),
            _MockClaim("c2", "High text", 0.9),
        ]
        doc = _MockDoc("d1", claims=claims)
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="text", entity_labels=["text"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(
            corpus=corpus, graph=None, themes=[theme], min_confidence=0.0,
        )
        assert result[0].evidence_count == 2

    def test_min_confidence_high_excludes_all(self) -> None:
        claim = _MockClaim("c1", "Some text", 0.4)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="text", entity_labels=["text"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(
            corpus=corpus, graph=None, themes=[theme], min_confidence=0.9,
        )
        assert result[0].evidence_count == 0

    def test_min_confidence_exact_boundary(self) -> None:
        claim = _MockClaim("c1", "Edge text", 0.5)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="text", entity_labels=["text"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(
            corpus=corpus, graph=None, themes=[theme], min_confidence=0.5,
        )
        assert result[0].evidence_count == 1


# ===========================================================================
# 13. Deduplication
# ===========================================================================


class TestDeduplication:
    """Evidence deduplication by id, text, and trace."""

    def test_dedup_by_id(self) -> None:
        ae1 = AggregatedEvidence(
            evidence_id="e1", source_text="Same", confidence=0.8,
            evidence_type="claim",
        )
        ae2 = AggregatedEvidence(
            evidence_id="e1", source_text="Same", confidence=0.9,
            evidence_type="claim",
        )
        doc = _MockDoc("d1", aggregated_evidence=[ae1, ae2])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Same", entity_labels=["Same"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 1

    def test_dedup_keeps_highest_confidence(self) -> None:
        ae1 = AggregatedEvidence(
            evidence_id="e1", source_text="Text", confidence=0.5,
            evidence_type="claim",
        )
        ae2 = AggregatedEvidence(
            evidence_id="e1", source_text="Text", confidence=0.9,
            evidence_type="claim",
        )
        doc = _MockDoc("d1", aggregated_evidence=[ae1, ae2])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Text", entity_labels=["Text"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_items[0].confidence == 0.9

    def test_dedup_different_ids_same_text(self) -> None:
        ae1 = AggregatedEvidence(
            evidence_id="e1", source_text="Duplicate text", confidence=0.8,
            evidence_type="claim",
        )
        ae2 = AggregatedEvidence(
            evidence_id="e2", source_text="Duplicate text", confidence=0.7,
            evidence_type="claim",
        )
        doc = _MockDoc("d1", aggregated_evidence=[ae1, ae2])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Duplicate", entity_labels=["Duplicate"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 2

    def test_dedup_whitespace_normalized(self) -> None:
        ae1 = AggregatedEvidence(
            evidence_id="e1", source_text="Same  text", confidence=0.8,
            evidence_type="claim",
        )
        ae2 = AggregatedEvidence(
            evidence_id="e2", source_text="Same   text", confidence=0.8,
            evidence_type="claim",
        )
        doc = _MockDoc("d1", aggregated_evidence=[ae1, ae2])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Same", entity_labels=["Same"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 2


# ===========================================================================
# 14. Ranking
# ===========================================================================


class TestRanking:
    """Evidence ranking: confidence desc → trace len desc → id asc."""

    def test_highest_confidence_first(self) -> None:
        claims = [
            _MockClaim("c2", "Low conf", 0.3),
            _MockClaim("c1", "High conf", 0.9),
        ]
        doc = _MockDoc("d1", claims=claims)
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="conf", entity_labels=["conf"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_items[0].confidence >= result[0].evidence_items[-1].confidence

    def test_same_confidence_longer_trace_first(self) -> None:
        ae1 = AggregatedEvidence(
            evidence_id="e1", source_text="Short trace", confidence=0.8,
            evidence_type="claim", trace=["a"],
        )
        ae2 = AggregatedEvidence(
            evidence_id="e2", source_text="Long trace", confidence=0.8,
            evidence_type="claim", trace=["a", "b", "c"],
        )
        doc = _MockDoc("d1", aggregated_evidence=[ae1, ae2])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="trace", entity_labels=["trace"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert len(result[0].evidence_items[0].trace) >= len(result[0].evidence_items[-1].trace)

    def test_deterministic_id_tiebreaker(self) -> None:
        ae1 = AggregatedEvidence(
            evidence_id="z_id", source_text="Same conf", confidence=0.8,
            evidence_type="claim",
        )
        ae2 = AggregatedEvidence(
            evidence_id="a_id", source_text="Same conf too", confidence=0.8,
            evidence_type="claim",
        )
        doc = _MockDoc("d1", aggregated_evidence=[ae1, ae2])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Same", entity_labels=["Same"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        ids = [e.evidence_id for e in result[0].evidence_items]
        assert ids == sorted(ids)


# ===========================================================================
# 15. Cap behavior
# ===========================================================================


class TestMaxEvidenceCap:
    """max_evidence_per_theme cap."""

    def test_cap_limits_evidence(self) -> None:
        claims = [_MockClaim(f"c{i}", f"Matching text {i}", 0.5 + i * 0.05)
                  for i in range(20)]
        doc = _MockDoc("d1", claims=claims)
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Matching", entity_labels=["Matching"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(
            corpus=corpus, graph=None, themes=[theme], max_evidence_per_theme=5,
        )
        assert result[0].evidence_count == 5

    def test_cap_higher_than_count(self) -> None:
        claim = _MockClaim("c1", "Matching text", 0.8)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Matching", entity_labels=["Matching"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(
            corpus=corpus, graph=None, themes=[theme], max_evidence_per_theme=100,
        )
        assert result[0].evidence_count == 1

    def test_cap_zero_returns_empty(self) -> None:
        claim = _MockClaim("c1", "Matching text", 0.8)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Matching", entity_labels=["Matching"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(
            corpus=corpus, graph=None, themes=[theme], max_evidence_per_theme=0,
        )
        assert result[0].evidence_count == 0


# ===========================================================================
# 16. Metadata in bundles
# ===========================================================================


class TestBundleMetadata:
    """Bundle metadata fields."""

    def test_metadata_contains_theme_label(self) -> None:
        doc = _MockDoc("d1")
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="LabelX")
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].metadata.get("theme_label") == "LabelX"

    def test_metadata_contains_theme_type(self) -> None:
        doc = _MockDoc("d1")
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="L", theme_type="dataset")
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].metadata.get("theme_type") == "dataset"

    def test_metadata_contains_document_count(self) -> None:
        doc = _MockDoc("d1")
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="L", document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].metadata.get("document_count") == 0

    def test_source_document_ids_populated(self) -> None:
        claim = _MockClaim("c1", "BERT is good", 0.9)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="BERT", entity_labels=["BERT"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert "d1" in result[0].source_document_ids

    def test_aggregate_confidence_computed(self) -> None:
        claims = [
            _MockClaim("c1", "BERT a", 1.0),
            _MockClaim("c2", "BERT b", 0.0),
        ]
        doc = _MockDoc("d1", claims=claims)
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="BERT", entity_labels=["BERT"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].aggregate_confidence == pytest.approx(0.5)


# ===========================================================================
# 17. Determinism
# ===========================================================================


class TestDeterminism:
    """Repeated runs must produce identical output."""

    def test_repeated_calls_same_result(self) -> None:
        claims = [
            _MockClaim("c1", "Text A", 0.9),
            _MockClaim("c2", "Text B", 0.5),
        ]
        doc = _MockDoc("d1", claims=claims)
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Text", entity_labels=["Text"],
                            document_ids=["d1"])
        r1 = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        r2 = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert r1[0].evidence_count == r2[0].evidence_count
        assert [e.evidence_id for e in r1[0].evidence_items] == [e.evidence_id for e in r2[0].evidence_items]

    def test_deterministic_order(self) -> None:
        claims = [_MockClaim(f"c{i}", f"Text {i}", 0.5 + i * 0.05)
                  for i in range(10)]
        doc = _MockDoc("d1", claims=claims)
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Text", entity_labels=["Text"],
                            document_ids=["d1"])
        r1 = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        r2 = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        ids1 = [e.evidence_id for e in r1[0].evidence_items]
        ids2 = [e.evidence_id for e in r2[0].evidence_items]
        assert ids1 == ids2

    def test_deterministic_across_instances(self) -> None:
        claim = _MockClaim("c1", "BERT method", 0.8)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="BERT", entity_labels=["BERT"],
                            document_ids=["d1"])
        r1 = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        r2 = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert r1 == r2

    def test_no_uuids_in_bundle_ids(self) -> None:
        doc = _MockDoc("d1")
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="L")
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert "uuid" not in result[0].bundle_id.lower()


# ===========================================================================
# 18. Malformed / partial inputs
# ===========================================================================


class TestMalformedInputs:
    """Graceful handling of malformed inputs."""

    def test_document_no_meta(self) -> None:
        class BadDoc:
            pass
        corpus = _MockCorpus([BadDoc()])
        theme = _make_theme(label="X", document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert len(result) == 1

    def test_document_no_claims_attr(self) -> None:
        class MinimalDoc:
            def __init__(self):
                self.meta = _MockMeta("d1")
                self.header = _MockHeader("Title")
        corpus = _MockCorpus([MinimalDoc()])
        theme = _make_theme(label="X", document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert len(result) == 1

    def test_claim_missing_fields(self) -> None:
        class BadClaim:
            pass
        doc = _MockDoc("d1")
        doc.claims = [BadClaim()]
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="X", document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert len(result) == 1

    def test_evidence_record_missing_fields(self) -> None:
        class BadRecord:
            pass
        doc = _MockDoc("d1")
        doc.evidence_records = [BadRecord()]
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="X", document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert len(result) == 1

    def test_triple_missing_fields(self) -> None:
        class BadTriple:
            pass
        doc = _MockDoc("d1")
        doc.triples = [BadTriple()]
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="X", document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert len(result) == 1

    def test_corpus_without_get_documents(self) -> None:
        class BareCorpus:
            pass
        theme = _make_theme(label="X")
        result = EvidenceCollector().collect(corpus=BareCorpus(), graph=None, themes=[theme])
        assert len(result) == 1

    def test_none_document_in_list(self) -> None:
        corpus = _MockCorpus([None])
        theme = _make_theme(label="X", document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert len(result) == 1

    def test_get_documents_raises(self) -> None:
        class BrokenCorpus:
            def get_documents(self) -> list:
                raise RuntimeError("broken")
        theme = _make_theme(label="X")
        result = EvidenceCollector().collect(corpus=BrokenCorpus(), graph=None, themes=[theme])
        assert len(result) == 1


# ===========================================================================
# 19. Serialization round-trip
# ===========================================================================


class TestSerialization:
    """EvidenceBundle serialization round-trip."""

    def test_round_trip_json(self) -> None:
        claim = _MockClaim("c1", "BERT is good", 0.9)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="BERT", entity_labels=["BERT"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        bundle = result[0]
        d = bundle.model_dump()
        restored = EvidenceBundle.model_validate(d)
        assert restored.bundle_id == bundle.bundle_id
        assert restored.theme == bundle.theme
        assert restored.evidence_count == bundle.evidence_count

    def test_round_trip_empty_bundle(self) -> None:
        theme = _make_theme(label="Empty")
        result = EvidenceCollector().collect(corpus=None, graph=None, themes=[theme])
        bundle = result[0]
        d = bundle.model_dump()
        restored = EvidenceBundle.model_validate(d)
        assert restored.evidence_count == 0
        assert restored.evidence_items == []

    def test_round_trip_aggregated_evidence(self) -> None:
        claim = _MockClaim("c1", "Claim text", 0.85)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="Claim", entity_labels=["Claim"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        ev = result[0].evidence_items[0]
        d = ev.model_dump()
        restored = AggregatedEvidence.model_validate(d)
        assert restored.evidence_id == ev.evidence_id
        assert restored.source_text == ev.source_text


# ===========================================================================
# 20. Large corpus
# ===========================================================================


class TestLargeCorpus:
    """Large corpus with many documents."""

    def test_50_documents(self) -> None:
        docs = [
            _MockDoc(f"d{i}", claims=[_MockClaim(f"c{i}", f"Text {i} about BERT", 0.8)])
            for i in range(50)
        ]
        corpus = _MockCorpus(docs)
        theme = _make_theme(
            label="BERT", entity_labels=["BERT"],
            document_ids=[f"d{i}" for i in range(50)],
        )
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 50

    def test_large_corpus_multiple_themes(self) -> None:
        docs_a = [_MockDoc(f"a{i}", claims=[_MockClaim(f"ca{i}", f"CNN text {i}", 0.8)])
                  for i in range(20)]
        docs_b = [_MockDoc(f"b{i}", claims=[_MockClaim(f"cb{i}", f"RNN text {i}", 0.7)])
                  for i in range(20)]
        corpus = _MockCorpus(docs_a + docs_b)
        t1 = _make_theme(cluster_id="t1", label="CNN", entity_labels=["CNN"],
                         document_ids=[f"a{i}" for i in range(20)])
        t2 = _make_theme(cluster_id="t2", label="RNN", entity_labels=["RNN"],
                         document_ids=[f"b{i}" for i in range(20)])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[t1, t2])
        assert len(result) == 2
        assert result[0].evidence_count == 20

    def test_large_corpus_deduplication(self) -> None:
        ae = AggregatedEvidence(
            evidence_id="shared", source_text="Shared BERT text",
            confidence=0.9, evidence_type="claim",
        )
        docs = [_MockDoc(f"d{i}", aggregated_evidence=[ae]) for i in range(10)]
        corpus = _MockCorpus(docs)
        theme = _make_theme(label="BERT", entity_labels=["BERT"],
                            document_ids=[f"d{i}" for i in range(10)])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 1


# ===========================================================================
# 21. Convenience helper
# ===========================================================================


class TestConvenienceHelper:
    """Module-level collect_evidence convenience function."""

    def test_convenience_returns_list(self) -> None:
        result = collect_evidence(corpus=None, graph=None, themes=[])
        assert isinstance(result, list)

    def test_convenience_returns_bundles(self) -> None:
        result = collect_evidence(corpus=None, graph=None, themes=[])
        assert all(isinstance(b, EvidenceBundle) for b in result)

    def test_convenience_empty_themes(self) -> None:
        result = collect_evidence(corpus="x", graph=None, themes=[])
        assert result == []

    def test_convenience_theme_collected(self) -> None:
        claim = _MockClaim("c1", "BERT method works", 0.8)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="BERT", entity_labels=["BERT"],
                            document_ids=["d1"])
        result = collect_evidence(corpus=corpus, graph=None, themes=[theme])
        assert len(result) == 1
        assert result[0].evidence_count == 1

    def test_convenience_passes_max_evidence(self) -> None:
        claims = [_MockClaim(f"c{i}", f"BERT text {i}", 0.8) for i in range(10)]
        doc = _MockDoc("d1", claims=claims)
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="BERT", entity_labels=["BERT"],
                            document_ids=["d1"])
        r1 = collect_evidence(corpus=corpus, graph=None, themes=[theme], max_evidence_per_theme=3)
        r2 = collect_evidence(corpus=corpus, graph=None, themes=[theme], max_evidence_per_theme=10)
        assert r1[0].evidence_count == 3
        assert r2[0].evidence_count == 10

    def test_convenience_consistent_with_detector(self) -> None:
        claim = _MockClaim("c1", "BERT is best", 0.9)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="BERT", entity_labels=["BERT"],
                            document_ids=["d1"])
        r1 = collect_evidence(corpus=corpus, graph=None, themes=[theme])
        r2 = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert r1 == r2


# ===========================================================================
# 22. Multiple evidence sources combined
# ===========================================================================


class TestCombinedSources:
    """Multiple evidence sources combined in a single document."""

    def test_claims_and_triples(self) -> None:
        claim = _MockClaim("c1", "CNN is accurate", 0.9)
        triple = _MockTriple("t1", "CNN", "uses", "loss", 0.7)
        doc = _MockDoc("d1", claims=[claim], triples=[triple])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="CNN", entity_labels=["CNN"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count >= 2

    def test_all_sources(self) -> None:
        claim = _MockClaim("c1", "X method", 0.9)
        triple = _MockTriple("t1", "X", "uses", "Y", 0.7)
        rec = _MockEvidenceRecord("r1", "X evidence", 0.95)
        ae = AggregatedEvidence(
            evidence_id="ae1", source_text="X pre-existing", confidence=0.8,
            evidence_type="claim",
        )
        doc = _MockDoc("d1", claims=[claim], triples=[triple],
                       evidence_records=[rec], aggregated_evidence=[ae])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="X", entity_labels=["X"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count >= 3

    def test_evidence_type_distinct(self) -> None:
        claim = _MockClaim("c1", "X claim", 0.9)
        triple = _MockTriple("t1", "X", "uses", "Y", 0.7)
        doc = _MockDoc("d1", claims=[claim], triples=[triple])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="X", entity_labels=["X"],
                            document_ids=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        types = {e.evidence_type for e in result[0].evidence_items}
        assert "claim" in types
        assert "triple" in types


# ===========================================================================
# 23. Document deduplication
# ===========================================================================


class TestDocumentDeduplication:
    """Duplicate document IDs must not produce duplicate evidence."""

    def test_duplicate_document_ids(self) -> None:
        claim = _MockClaim("c1", "BERT text", 0.8)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="BERT", entity_labels=["BERT"],
                            document_ids=["d1", "d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 1

    def test_duplicate_documents_in_doc_ids_and_documents(self) -> None:
        claim = _MockClaim("c1", "BERT text", 0.8)
        doc = _MockDoc("d1", claims=[claim])
        corpus = _MockCorpus([doc])
        theme = _make_theme(label="BERT", entity_labels=["BERT"],
                            document_ids=["d1"], documents=["d1"])
        result = EvidenceCollector().collect(corpus=corpus, graph=None, themes=[theme])
        assert result[0].evidence_count == 1
