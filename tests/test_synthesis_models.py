"""Comprehensive model tests for Module 6 — validators, edge cases, determinism.

Covers every model, every validator, serialization, and cross-model consistency.
No business logic tests.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from researchmind.query.models import AggregatedEvidence
from researchmind.synthesis.models import (
    EvidenceBundle,
    ReviewFinding,
    ReviewRequest,
    ReviewResult,
    ReviewSection,
    ReviewType,
    ThemeCluster,
    ThemeType,
    _SECTION_ORDER,
    _SECTION_REQUIREMENTS,
    _SECTION_TITLES,
    _generate_id,
    _TRACE_REQUIRED_TYPES,
)


# ===========================================================================
# 1. Enum tests
# ===========================================================================

class TestReviewTypeEnum:
    """Verify ReviewType enum values and properties."""

    def test_general(self) -> None:
        assert ReviewType.GENERAL == "general"

    def test_method(self) -> None:
        assert ReviewType.METHOD == "method"

    def test_dataset(self) -> None:
        assert ReviewType.DATASET == "dataset"

    def test_consensus(self) -> None:
        assert ReviewType.CONSENSUS == "consensus"

    def test_contradiction(self) -> None:
        assert ReviewType.CONTRADICTION == "contradiction"

    def test_research_gap(self) -> None:
        assert ReviewType.RESEARCH_GAP == "research_gap"

    def test_comparative(self) -> None:
        assert ReviewType.COMPARATIVE == "comparative"

    def test_landscape(self) -> None:
        assert ReviewType.LANDSCAPE == "landscape"

    def test_all_values_unique(self) -> None:
        values = [e.value for e in ReviewType]
        assert len(values) == len(set(values))

    def test_member_count(self) -> None:
        assert len(list(ReviewType)) == 8


class TestThemeTypeEnum:
    """Verify ThemeType enum values and properties."""

    def test_method(self) -> None:
        assert ThemeType.METHOD == "method"

    def test_dataset(self) -> None:
        assert ThemeType.DATASET == "dataset"

    def test_metric(self) -> None:
        assert ThemeType.METRIC == "metric"

    def test_concept(self) -> None:
        assert ThemeType.CONCEPT == "concept"

    def test_mixed(self) -> None:
        assert ThemeType.MIXED == "mixed"

    def test_all_values_unique(self) -> None:
        values = [e.value for e in ThemeType]
        assert len(values) == len(set(values))

    def test_member_count(self) -> None:
        assert len(list(ThemeType)) == 5


# ===========================================================================
# 2. Helper functions
# ===========================================================================

def make_evidence(evidence_id: str = "ev_001", etype: str = "gap_item") -> AggregatedEvidence:
    return AggregatedEvidence(
        evidence_id=evidence_id,
        source_text="Test evidence text.",
        confidence=0.8,
        source_engine="consensus",
        source_document_id="doc_001",
        evidence_type=etype,
    )


def make_finding(
    finding_id: str = "find_001",
    ftype: str = "consensus",
    statement: str = "Test finding statement.",
    confidence: float = 0.75,
    evidence_ids: list[str] | None = None,
    trace: list[str] | None = None,
) -> ReviewFinding:
    return ReviewFinding(
        finding_id=finding_id,
        finding_type=ftype,
        statement=statement,
        confidence=confidence,
        evidence_ids=evidence_ids or [],
        trace=trace or [],
    )


def make_section(
    section_id: str = "sec_001",
    stype: str = "introduction",
    title: str = "Introduction",
    findings: list[ReviewFinding] | None = None,
    confidence: float = 0.0,
) -> ReviewSection:
    return ReviewSection(
        section_id=section_id,
        section_type=stype,
        title=title,
        findings=findings or [],
        confidence=confidence,
    )


# ===========================================================================
# 3. ReviewRequest
# ===========================================================================

class TestReviewRequestInstantiation:
    """Happy-path construction of ReviewRequest."""

    def test_minimal(self) -> None:
        req = ReviewRequest(review_id="r1", review_type="general")
        assert req.review_id == "r1"
        assert req.review_type == "general"

    def test_minimal_method(self) -> None:
        req = ReviewRequest(review_id="r2", review_type="method")
        assert req.review_id == "r2"

    def test_minimal_dataset(self) -> None:
        req = ReviewRequest(review_id="r3", review_type="dataset")
        assert req.review_type == "dataset"

    def test_minimal_consensus(self) -> None:
        req = ReviewRequest(review_id="r4", review_type="consensus")
        assert req.review_type == "consensus"

    def test_minimal_contradiction(self) -> None:
        req = ReviewRequest(review_id="r5", review_type="contradiction")
        assert req.review_type == "contradiction"

    def test_minimal_research_gap(self) -> None:
        req = ReviewRequest(review_id="r6", review_type="research_gap")
        assert req.review_type == "research_gap"

    def test_minimal_comparative(self) -> None:
        req = ReviewRequest(review_id="r7", review_type="comparative")
        assert req.review_type == "comparative"

    def test_minimal_landscape(self) -> None:
        req = ReviewRequest(review_id="r8", review_type="landscape")
        assert req.review_type == "landscape"

    def test_all_fields(self) -> None:
        req = ReviewRequest(
            review_id="full",
            review_type="general",
            title="Deep Learning Review",
            query="What are the key methods in deep learning?",
            target_entities=["transformer", "cnn"],
            target_documents=["doc_001"],
            min_confidence=0.5,
            max_documents=20,
            include_contradictions=False,
            include_gaps=True,
            include_consensus=False,
            metadata={"source": "user_request"},
        )
        assert req.title == "Deep Learning Review"
        assert req.query == "What are the key methods in deep learning?"
        assert req.target_entities == ["transformer", "cnn"]
        assert req.target_documents == ["doc_001"]
        assert req.min_confidence == 0.5
        assert req.max_documents == 20
        assert req.include_contradictions is False
        assert req.include_gaps is True
        assert req.include_consensus is False
        assert req.metadata == {"source": "user_request"}


class TestReviewRequestDefaults:
    """Default values for optional fields."""

    def test_title_default_empty(self) -> None:
        req = ReviewRequest(review_id="r", review_type="general")
        assert req.title == ""

    def test_query_default_empty(self) -> None:
        req = ReviewRequest(review_id="r", review_type="general")
        assert req.query == ""

    def test_target_entities_default_empty(self) -> None:
        req = ReviewRequest(review_id="r", review_type="general")
        assert req.target_entities == []

    def test_target_documents_default_empty(self) -> None:
        req = ReviewRequest(review_id="r", review_type="general")
        assert req.target_documents == []

    def test_min_confidence_default(self) -> None:
        req = ReviewRequest(review_id="r", review_type="general")
        assert req.min_confidence == 0.3

    def test_max_documents_default(self) -> None:
        req = ReviewRequest(review_id="r", review_type="general")
        assert req.max_documents == 10

    def test_include_contradictions_default(self) -> None:
        req = ReviewRequest(review_id="r", review_type="general")
        assert req.include_contradictions is True

    def test_include_gaps_default(self) -> None:
        req = ReviewRequest(review_id="r", review_type="general")
        assert req.include_gaps is True

    def test_include_consensus_default(self) -> None:
        req = ReviewRequest(review_id="r", review_type="general")
        assert req.include_consensus is True

    def test_metadata_default_empty(self) -> None:
        req = ReviewRequest(review_id="r", review_type="general")
        assert req.metadata == {}


class TestReviewRequestValidators:
    """Validator tests for ReviewRequest."""

    def test_invalid_review_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReviewRequest(review_id="r", review_type="unknown")

    def test_empty_review_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReviewRequest(review_id="r", review_type="")

    def test_case_insensitive_review_type(self) -> None:
        req = ReviewRequest(review_id="r", review_type="GENERAL")
        assert req.review_type == "general"

    def test_mixed_case_review_type(self) -> None:
        req = ReviewRequest(review_id="r", review_type="ReSeArCh_GaP")
        assert req.review_type == "research_gap"

    def test_min_confidence_below_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReviewRequest(review_id="r", review_type="general", min_confidence=-0.1)

    def test_min_confidence_above_one_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReviewRequest(review_id="r", review_type="general", min_confidence=1.5)

    def test_min_confidence_zero_allowed(self) -> None:
        req = ReviewRequest(review_id="r", review_type="general", min_confidence=0.0)
        assert req.min_confidence == 0.0

    def test_min_confidence_one_allowed(self) -> None:
        req = ReviewRequest(review_id="r", review_type="general", min_confidence=1.0)
        assert req.min_confidence == 1.0

    def test_max_documents_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReviewRequest(review_id="r", review_type="general", max_documents=0)

    def test_max_documents_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReviewRequest(review_id="r", review_type="general", max_documents=-5)

    def test_query_whitespace_only_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReviewRequest(review_id="r", review_type="general", query="   ")

    def test_empty_query_allowed(self) -> None:
        req = ReviewRequest(review_id="r", review_type="general", query="")
        assert req.query == ""

    def test_title_whitespace_stripped(self) -> None:
        req = ReviewRequest(review_id="r", review_type="general", title="  title  ")
        assert req.title == "title"

    def test_serialization_roundtrip(self) -> None:
        req = ReviewRequest(
            review_id="rt",
            review_type="comparative",
            title="Compare",
            query="Compare methods?",
        )
        d = req.model_dump()
        restored = ReviewRequest.model_validate(d)
        assert restored.review_id == req.review_id
        assert restored.review_type == req.review_type
        assert restored.title == req.title
        assert restored.query == req.query


# ===========================================================================
# 4. ReviewFinding
# ===========================================================================

class TestReviewFindingInstantiation:
    """Happy-path construction of ReviewFinding."""

    def test_minimal(self) -> None:
        f = ReviewFinding(
            finding_id="f1",
            finding_type="consensus",
            statement="Strong consensus exists.",
            confidence=0.85,
        )
        assert f.finding_id == "f1"
        assert f.finding_type == "consensus"
        assert f.statement == "Strong consensus exists."
        assert f.confidence == 0.85

    def test_all_fields(self) -> None:
        f = ReviewFinding(
            finding_id="f2",
            finding_type="gap",
            statement="Gap identified.",
            confidence=0.6,
            evidence_ids=["ev_001", "ev_002"],
            source_document_ids=["doc_001"],
            source_document_titles=["Paper A"],
            supporting_count=3,
            contradicting_count=1,
            neutral_count=2,
            trace=["chunk_001"],
            metadata={"type": "isolated_entity"},
        )
        assert f.evidence_ids == ["ev_001", "ev_002"]
        assert f.source_document_ids == ["doc_001"]
        assert f.source_document_titles == ["Paper A"]
        assert f.supporting_count == 3
        assert f.contradicting_count == 1
        assert f.neutral_count == 2
        assert f.trace == ["chunk_001"]
        assert f.metadata == {"type": "isolated_entity"}


class TestReviewFindingDefaults:
    """Default values for optional fields."""

    def test_evidence_ids_default(self) -> None:
        f = make_finding()
        assert f.evidence_ids == []

    def test_source_document_ids_default(self) -> None:
        f = make_finding()
        assert f.source_document_ids == []

    def test_source_document_titles_default(self) -> None:
        f = make_finding()
        assert f.source_document_titles == []

    def test_counts_default_zero(self) -> None:
        f = make_finding()
        assert f.supporting_count == 0
        assert f.contradicting_count == 0
        assert f.neutral_count == 0

    def test_trace_default_empty(self) -> None:
        f = make_finding()
        assert f.trace == []

    def test_metadata_default_empty(self) -> None:
        f = make_finding()
        assert f.metadata == {}


class TestReviewFindingValidators:
    """Validator tests for ReviewFinding."""

    def test_empty_finding_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(finding_id="")

    def test_whitespace_finding_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(finding_id="   ")

    def test_empty_statement_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(statement="")

    def test_whitespace_statement_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(statement="   ")

    def test_confidence_below_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(confidence=-0.01)

    def test_confidence_above_one_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(confidence=1.01)

    def test_confidence_zero_allowed(self) -> None:
        f = make_finding(confidence=0.0)
        assert f.confidence == 0.0

    def test_confidence_one_allowed(self) -> None:
        f = make_finding(confidence=1.0)
        assert f.confidence == 1.0

    def test_empty_evidence_id_in_list_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(evidence_ids=["ev_001", ""])

    def test_whitespace_evidence_id_in_list_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(evidence_ids=["ev_001", "  "])

    def test_trace_required_for_path_edge(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(ftype="path_edge", trace=[])

    def test_trace_required_for_contradiction(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(ftype="contradiction", trace=[])

    def test_trace_required_for_consensus_entry(self) -> None:
        with pytest.raises(ValidationError):
            make_finding(ftype="consensus_entry", trace=[])

    def test_trace_not_required_for_gap(self) -> None:
        f = make_finding(ftype="gap", trace=[])
        assert f.finding_type == "gap"

    def test_trace_not_required_for_method(self) -> None:
        f = make_finding(ftype="method", trace=[])
        assert f.finding_type == "method"

    def test_trace_not_required_for_dataset(self) -> None:
        f = make_finding(ftype="dataset", trace=[])
        assert f.finding_type == "dataset"

    def test_trace_not_required_for_relation(self) -> None:
        f = make_finding(ftype="relation", trace=[])
        assert f.finding_type == "relation"

    def test_trace_accepted_when_provided(self) -> None:
        f = make_finding(ftype="contradiction", trace=["chunk_a", "chunk_b"])
        assert len(f.trace) == 2

    def test_trace_required_types_constant(self) -> None:
        assert "path_edge" in _TRACE_REQUIRED_TYPES
        assert "contradiction" in _TRACE_REQUIRED_TYPES
        assert "consensus_entry" in _TRACE_REQUIRED_TYPES

    def test_serialization_roundtrip(self) -> None:
        f = make_finding(
            finding_id="f_rt",
            ftype="gap",
            statement="Test",
            confidence=0.5,
            evidence_ids=["ev_001"],
        )
        d = f.model_dump()
        restored = ReviewFinding.model_validate(d)
        assert restored.finding_id == f.finding_id
        assert restored.statement == f.statement
        assert restored.confidence == f.confidence


# ===========================================================================
# 5. ReviewSection
# ===========================================================================

class TestReviewSectionInstantiation:
    """Happy-path construction of ReviewSection."""

    def test_minimal(self) -> None:
        s = ReviewSection(
            section_id="s1",
            section_type="introduction",
            title="Introduction",
        )
        assert s.section_id == "s1"
        assert s.section_type == "introduction"
        assert s.title == "Introduction"

    def test_all_fields(self) -> None:
        finding = make_finding()
        s = ReviewSection(
            section_id="s2",
            section_type="conclusion",
            title="Conclusion",
            content="Summary content.",
            summary="Brief summary.",
            findings=[finding],
            paragraphs=["Para 1.", "Para 2."],
            confidence=0.75,
            word_count=150,
            is_mandatory=True,
            statistics={"num_findings": 1},
            metadata={"generated_by": "section_builder"},
        )
        assert s.content == "Summary content."
        assert s.summary == "Brief summary."
        assert len(s.findings) == 1
        assert len(s.paragraphs) == 2
        assert s.confidence == 0.75
        assert s.word_count == 150
        assert s.is_mandatory is True
        assert s.statistics == {"num_findings": 1}
        assert s.metadata == {"generated_by": "section_builder"}


class TestReviewSectionDefaults:
    """Default values for optional fields."""

    def test_content_default_empty(self) -> None:
        s = make_section()
        assert s.content == ""

    def test_summary_default_empty(self) -> None:
        s = make_section()
        assert s.summary == ""

    def test_findings_default_empty(self) -> None:
        s = make_section()
        assert s.findings == []

    def test_paragraphs_default_empty(self) -> None:
        s = make_section()
        assert s.paragraphs == []

    def test_confidence_default_zero(self) -> None:
        s = make_section()
        assert s.confidence == 0.0

    def test_word_count_default_zero(self) -> None:
        s = make_section()
        assert s.word_count == 0

    def test_is_mandatory_default_false(self) -> None:
        s = make_section()
        assert s.is_mandatory is False


class TestReviewSectionValidators:
    """Validator tests for ReviewSection."""

    def test_empty_section_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_section(section_id="")

    def test_whitespace_section_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_section(section_id="   ")

    def test_empty_title_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_section(title="")

    def test_whitespace_title_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_section(title="   ")

    def test_confidence_below_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_section(confidence=-0.1)

    def test_confidence_above_one_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_section(confidence=1.5)

    def test_confidence_exceeds_finding_min_raises(self) -> None:
        f1 = make_finding(finding_id="a", confidence=0.5)
        f2 = make_finding(finding_id="b", confidence=0.3)
        with pytest.raises(ValidationError):
            make_section(findings=[f1, f2], confidence=0.4)

    def test_confidence_matches_finding_min_allowed(self) -> None:
        f1 = make_finding(finding_id="a", confidence=0.5)
        f2 = make_finding(finding_id="b", confidence=0.3)
        s = make_section(findings=[f1, f2], confidence=0.3)
        assert s.confidence == 0.3

    def test_confidence_below_finding_min_allowed(self) -> None:
        f1 = make_finding(finding_id="a", confidence=0.5)
        f2 = make_finding(finding_id="b", confidence=0.3)
        s = make_section(findings=[f1, f2], confidence=0.2)
        assert s.confidence == 0.2

    def test_confidence_zero_with_findings_allowed(self) -> None:
        f = make_finding(confidence=0.5)
        s = make_section(findings=[f], confidence=0.0)
        assert s.confidence == 0.0

    def test_no_findings_any_confidence_allowed(self) -> None:
        s = make_section(confidence=0.8)
        assert s.confidence == 0.8

    def test_serialization_roundtrip(self) -> None:
        f = make_finding()
        s = make_section(section_id="rt", findings=[f], confidence=0.5)
        d = s.model_dump()
        restored = ReviewSection.model_validate(d)
        assert restored.section_id == s.section_id
        assert restored.confidence == s.confidence
        assert len(restored.findings) == 1


# ===========================================================================
# 6. EvidenceBundle
# ===========================================================================

class TestEvidenceBundleInstantiation:
    """Happy-path construction of EvidenceBundle."""

    def test_minimal(self) -> None:
        ev = make_evidence()
        b = EvidenceBundle(
            bundle_id="b1",
            theme="Deep Learning",
            evidence_items=[ev],
            evidence_count=1,
        )
        assert b.bundle_id == "b1"
        assert b.theme == "Deep Learning"
        assert len(b.evidence_items) == 1

    def test_all_fields(self) -> None:
        ev = make_evidence()
        b = EvidenceBundle(
            bundle_id="b2",
            theme="Optimization",
            evidence_items=[ev],
            source_document_ids=["doc_001"],
            source_entities=["Adam"],
            aggregate_confidence=0.85,
            finding_type="consensus",
            evidence_count=1,
            metadata={"source": "consensus_engine"},
        )
        assert b.source_document_ids == ["doc_001"]
        assert b.source_entities == ["Adam"]
        assert b.aggregate_confidence == 0.85
        assert b.finding_type == "consensus"
        assert b.metadata == {"source": "consensus_engine"}


class TestEvidenceBundleDefaults:
    """Default values for optional fields."""

    def test_evidence_items_default_empty(self) -> None:
        b = EvidenceBundle(bundle_id="b", theme="T", evidence_count=0)
        assert b.evidence_items == []

    def test_source_document_ids_default_empty(self) -> None:
        b = EvidenceBundle(bundle_id="b", theme="T", evidence_count=0)
        assert b.source_document_ids == []

    def test_source_entities_default_empty(self) -> None:
        b = EvidenceBundle(bundle_id="b", theme="T", evidence_count=0)
        assert b.source_entities == []

    def test_aggregate_confidence_default_zero(self) -> None:
        b = EvidenceBundle(bundle_id="b", theme="T", evidence_count=0)
        assert b.aggregate_confidence == 0.0

    def test_finding_type_default_empty(self) -> None:
        b = EvidenceBundle(bundle_id="b", theme="T", evidence_count=0)
        assert b.finding_type == ""


class TestEvidenceBundleValidators:
    """Validator tests for EvidenceBundle."""

    def test_evidence_count_mismatch_raises(self) -> None:
        ev = make_evidence()
        with pytest.raises(ValidationError):
            EvidenceBundle(
                bundle_id="b",
                theme="T",
                evidence_items=[ev],
                evidence_count=5,
            )

    def test_evidence_count_zero_with_empty_items(self) -> None:
        b = EvidenceBundle(bundle_id="b", theme="T", evidence_count=0)
        assert b.evidence_count == 0

    def test_evidence_count_matches_items(self) -> None:
        ev1 = make_evidence("ev_001")
        ev2 = make_evidence("ev_002")
        b = EvidenceBundle(
            bundle_id="b",
            theme="T",
            evidence_items=[ev1, ev2],
            evidence_count=2,
        )
        assert b.evidence_count == 2

    def test_duplicate_evidence_id_raises(self) -> None:
        ev1 = make_evidence("ev_001")
        ev2 = make_evidence("ev_001")
        with pytest.raises(ValidationError):
            EvidenceBundle(
                bundle_id="b",
                theme="T",
                evidence_items=[ev1, ev2],
                evidence_count=2,
            )

    def test_empty_evidence_id_raises(self) -> None:
        ev = make_evidence("")
        with pytest.raises(ValidationError):
            EvidenceBundle(
                bundle_id="b",
                theme="T",
                evidence_items=[ev],
                evidence_count=1,
            )

    def test_aggregate_confidence_below_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceBundle(
                bundle_id="b",
                theme="T",
                aggregate_confidence=-0.1,
                evidence_count=0,
            )

    def test_aggregate_confidence_above_one_raises(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceBundle(
                bundle_id="b",
                theme="T",
                aggregate_confidence=1.5,
                evidence_count=0,
            )

    def test_serialization_roundtrip(self) -> None:
        ev = make_evidence()
        b = EvidenceBundle(
            bundle_id="rt",
            theme="Test",
            evidence_items=[ev],
            evidence_count=1,
        )
        d = b.model_dump()
        restored = EvidenceBundle.model_validate(d)
        assert restored.bundle_id == b.bundle_id
        assert len(restored.evidence_items) == 1


# ===========================================================================
# 7. ThemeCluster
# ===========================================================================

class TestThemeClusterInstantiation:
    """Happy-path construction of ThemeCluster."""

    def test_minimal(self) -> None:
        t = ThemeCluster(cluster_id="c1", label="Optimization Methods")
        assert t.cluster_id == "c1"
        assert t.label == "Optimization Methods"

    def test_with_theme_type(self) -> None:
        t = ThemeCluster(
            cluster_id="c2",
            theme_type="method",
            label="CNN Architectures",
            entities=["ResNet", "U-Net"],
        )
        assert t.theme_type == "method"
        assert t.entities == ["ResNet", "U-Net"]

    def test_all_fields(self) -> None:
        t = ThemeCluster(
            cluster_id="c3",
            theme_type="dataset",
            label="Image Datasets",
            entities=["ImageNet", "CIFAR-10"],
            documents=["doc_001", "doc_002"],
            entity_cluster_ids=["clu_001", "clu_002"],
            entity_labels=["ImageNet", "CIFAR-10"],
            document_ids=["doc_001", "doc_002"],
            relation_types=["USES_DATASET", "EXTENDS"],
            evidence_count=15,
            confidence=0.85,
            metadata={"source": "theme_detector"},
        )
        assert t.documents == ["doc_001", "doc_002"]
        assert t.entity_cluster_ids == ["clu_001", "clu_002"]
        assert t.entity_labels == ["ImageNet", "CIFAR-10"]
        assert t.relation_types == ["USES_DATASET", "EXTENDS"]
        assert t.evidence_count == 15
        assert t.confidence == 0.85
        assert t.metadata == {"source": "theme_detector"}


class TestThemeClusterDefaults:
    """Default values for optional fields."""

    def test_theme_type_default_empty(self) -> None:
        t = ThemeCluster(cluster_id="c", label="L")
        assert t.theme_type == ""

    def test_entities_default_empty(self) -> None:
        t = ThemeCluster(cluster_id="c", label="L")
        assert t.entities == []

    def test_documents_default_empty(self) -> None:
        t = ThemeCluster(cluster_id="c", label="L")
        assert t.documents == []

    def test_entity_cluster_ids_default_empty(self) -> None:
        t = ThemeCluster(cluster_id="c", label="L")
        assert t.entity_cluster_ids == []

    def test_evidence_count_default_zero(self) -> None:
        t = ThemeCluster(cluster_id="c", label="L")
        assert t.evidence_count == 0

    def test_confidence_default_zero(self) -> None:
        t = ThemeCluster(cluster_id="c", label="L")
        assert t.confidence == 0.0


class TestThemeClusterValidators:
    """Validator tests for ThemeCluster."""

    def test_empty_label_raises(self) -> None:
        with pytest.raises(ValidationError):
            ThemeCluster(cluster_id="c", label="")

    def test_whitespace_label_raises(self) -> None:
        with pytest.raises(ValidationError):
            ThemeCluster(cluster_id="c", label="   ")

    def test_confidence_below_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            ThemeCluster(cluster_id="c", label="L", confidence=-0.1)

    def test_confidence_above_one_raises(self) -> None:
        with pytest.raises(ValidationError):
            ThemeCluster(cluster_id="c", label="L", confidence=1.5)

    def test_theme_type_without_entities_raises(self) -> None:
        with pytest.raises(ValidationError):
            ThemeCluster(cluster_id="c", theme_type="method", label="M", entities=[])

    def test_theme_type_with_entities_allowed(self) -> None:
        t = ThemeCluster(cluster_id="c", theme_type="dataset", label="D", entities=["ImageNet"])
        assert t.theme_type == "dataset"

    def test_no_theme_type_without_entities_allowed(self) -> None:
        t = ThemeCluster(cluster_id="c", label="L")
        assert t.entities == []

    def test_serialization_roundtrip(self) -> None:
        t = ThemeCluster(cluster_id="rt", label="Test", entities=["A"], theme_type="method")
        d = t.model_dump()
        restored = ThemeCluster.model_validate(d)
        assert restored.cluster_id == t.cluster_id
        assert restored.label == t.label
        assert restored.entities == t.entities


# ===========================================================================
# 8. ReviewResult
# ===========================================================================

class TestReviewResultInstantiation:
    """Happy-path construction of ReviewResult."""

    def test_minimal(self) -> None:
        r = ReviewResult(
            review_id="res_001",
            review_type="general",
            title="Deep Learning Review",
        )
        assert r.review_id == "res_001"
        assert r.review_type == "general"
        assert r.title == "Deep Learning Review"

    def test_with_sections_and_abstract(self) -> None:
        f = make_finding()
        s = make_section(section_id="s1", findings=[f], confidence=0.5)
        s2 = make_section(section_id="s2", stype="conclusion", title="Conclusion", confidence=0.3)
        r = ReviewResult(
            review_id="res_002",
            review_type="landscape",
            title="Landscape",
            abstract="This review covers the landscape.",
            sections=[s, s2],
            total_findings=1,
            total_words=s.word_count + s2.word_count,
        )
        assert r.abstract == "This review covers the landscape."
        assert len(r.sections) == 2

    def test_all_fields(self) -> None:
        r = ReviewResult(
            review_id="full",
            review_type="comparative",
            title="Full Review",
            abstract="Abstract.",
            confidence=0.7,
            total_findings=0,
            total_evidence_items=5,
            total_documents_cited=3,
            total_words=0,
            traceability_verified=True,
            traceability_failures=[],
            warnings=["warning 1"],
            errors=[],
            bibliography=["Doc A", "Doc B"],
            source_attribution={"doc_001": ["find_001"]},
            statistics={"processing_time_ms": 150},
            metadata={"generator": "orchestrator_v1"},
        )
        assert r.total_evidence_items == 5
        assert r.total_documents_cited == 3
        assert r.traceability_verified is True
        assert r.warnings == ["warning 1"]
        assert r.bibliography == ["Doc A", "Doc B"]
        assert r.source_attribution == {"doc_001": ["find_001"]}
        assert r.statistics == {"processing_time_ms": 150}


class TestReviewResultDefaults:
    """Default values for optional fields."""

    def test_abstract_default_empty(self) -> None:
        r = ReviewResult(review_id="r", review_type="general", title="T")
        assert r.abstract == ""

    def test_sections_default_empty(self) -> None:
        r = ReviewResult(review_id="r", review_type="general", title="T")
        assert r.sections == []

    def test_findings_default_empty(self) -> None:
        r = ReviewResult(review_id="r", review_type="general", title="T")
        assert r.findings == []

    def test_statistics_default_zero(self) -> None:
        r = ReviewResult(review_id="r", review_type="general", title="T")
        assert r.total_findings == 0
        assert r.total_evidence_items == 0
        assert r.total_documents_cited == 0
        assert r.total_words == 0

    def test_confidence_default_zero(self) -> None:
        r = ReviewResult(review_id="r", review_type="general", title="T")
        assert r.confidence == 0.0

    def test_traceability_defaults(self) -> None:
        r = ReviewResult(review_id="r", review_type="general", title="T")
        assert r.traceability_verified is False
        assert r.traceability_failures == []

    def test_warnings_errors_default_empty(self) -> None:
        r = ReviewResult(review_id="r", review_type="general", title="T")
        assert r.warnings == []
        assert r.errors == []


class TestReviewResultValidators:
    """Validator tests for ReviewResult."""

    def test_empty_title_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReviewResult(review_id="r", review_type="general", title="")

    def test_whitespace_title_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReviewResult(review_id="r", review_type="general", title="   ")

    def test_invalid_review_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReviewResult(review_id="r", review_type="unknown", title="T")

    def test_case_insensitive_review_type(self) -> None:
        r = ReviewResult(review_id="r", review_type="METHOD", title="T")
        assert r.review_type == "method"

    def test_abstract_empty_with_sections_raises(self) -> None:
        f = make_finding()
        s = make_section(section_id="s1", findings=[f], confidence=0.5)
        with pytest.raises(ValidationError):
            ReviewResult(
                review_id="r",
                review_type="general",
                title="T",
                sections=[s],
                total_findings=1,
                total_words=s.word_count,
            )

    def test_abstract_empty_without_sections_allowed(self) -> None:
        r = ReviewResult(review_id="r", review_type="general", title="T")
        assert r.abstract == ""

    def test_abstract_with_sections_allowed(self) -> None:
        s = make_section()
        r = ReviewResult(
            review_id="r",
            review_type="general",
            title="T",
            abstract="Valid abstract.",
            sections=[s],
            total_findings=0,
            total_words=s.word_count,
        )
        assert r.abstract == "Valid abstract."

    def test_total_findings_mismatch_raises(self) -> None:
        f = make_finding()
        s = make_section(section_id="s1", findings=[f], confidence=0.5)
        with pytest.raises(ValidationError):
            ReviewResult(
                review_id="r",
                review_type="general",
                title="T",
                abstract="Abstract.",
                sections=[s],
                total_findings=999,
                total_words=s.word_count,
            )

    def test_total_words_mismatch_raises(self) -> None:
        s = ReviewSection(section_id="s1", section_type="introduction",
                          title="Intro", word_count=100)
        with pytest.raises(ValidationError):
            ReviewResult(
                review_id="r",
                review_type="general",
                title="T",
                abstract="Abstract.",
                sections=[s],
                total_findings=0,
                total_words=999,
            )

    def test_total_findings_correct_multiple_sections(self) -> None:
        f1 = make_finding(finding_id="a")
        f2 = make_finding(finding_id="b")
        s1 = make_section(section_id="s1", findings=[f1], confidence=0.5)
        s2 = make_section(section_id="s2", findings=[f2], stype="conclusion",
                          title="Conclusion", confidence=0.3)
        r = ReviewResult(
            review_id="r",
            review_type="general",
            title="T",
            abstract="Abstract.",
            sections=[s1, s2],
            total_findings=2,
            total_words=s1.word_count + s2.word_count,
        )
        assert r.total_findings == 2

    def test_no_sections_no_validation(self) -> None:
        r = ReviewResult(
            review_id="r",
            review_type="general",
            title="T",
            total_findings=0,
            total_words=0,
        )
        assert r.total_findings == 0

    def test_confidence_below_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReviewResult(
                review_id="r",
                review_type="general",
                title="T",
                confidence=-0.1,
            )

    def test_confidence_above_one_raises(self) -> None:
        with pytest.raises(ValidationError):
            ReviewResult(
                review_id="r",
                review_type="general",
                title="T",
                confidence=1.5,
            )

    def test_serialization_roundtrip(self) -> None:
        r = ReviewResult(
            review_id="rt",
            review_type="general",
            title="Roundtrip",
            abstract="Test.",
            total_findings=0,
            total_words=0,
        )
        d = r.model_dump()
        restored = ReviewResult.model_validate(d)
        assert restored.review_id == r.review_id
        assert restored.title == r.title
        assert restored.abstract == r.abstract


# ===========================================================================
# 9. Deterministic ID generation
# ===========================================================================

class TestGenerateId:
    """Verify _generate_id is deterministic and well-formatted."""

    def test_returns_string(self) -> None:
        result = _generate_id("pre", "a", "b")
        assert isinstance(result, str)

    def test_prefix_format(self) -> None:
        result = _generate_id("pre", "a", "b")
        assert result.startswith("pre_")

    def test_hex_suffix_length(self) -> None:
        result = _generate_id("pre", "a", "b")
        suffix = result.split("_")[1]
        assert len(suffix) == 12
        int(suffix, 16)

    def test_deterministic_same_inputs(self) -> None:
        a = _generate_id("pfx", "x", "y")
        b = _generate_id("pfx", "x", "y")
        assert a == b

    def test_different_inputs_different_outputs(self) -> None:
        a = _generate_id("pfx", "x", "y")
        b = _generate_id("pfx", "x", "z")
        assert a != b

    def test_empty_parts(self) -> None:
        result = _generate_id("pre")
        assert result.startswith("pre_")

    def test_single_part(self) -> None:
        result = _generate_id("pre", "hello")
        assert result.startswith("pre_")

    def test_many_parts(self) -> None:
        result = _generate_id("pre", "a", "b", "c", "d")
        assert result.startswith("pre_")

    def test_unicode_stability(self) -> None:
        a = _generate_id("pfx", "café", "résumé")
        b = _generate_id("pfx", "café", "résumé")
        assert a == b


# ===========================================================================
# 10. Section constants
# ===========================================================================

class TestSectionConstants:
    """Verify _SECTION_ORDER, _SECTION_TITLES, _SECTION_REQUIREMENTS."""

    def test_section_order_is_list(self) -> None:
        assert isinstance(_SECTION_ORDER, list)
        assert len(_SECTION_ORDER) >= 8

    def test_abstract_first(self) -> None:
        assert _SECTION_ORDER[0] == "abstract"

    def test_conclusion_last(self) -> None:
        assert _SECTION_ORDER[-1] == "conclusion"

    def test_all_order_keys_in_titles(self) -> None:
        for sec in _SECTION_ORDER:
            assert sec in _SECTION_TITLES, f"Missing title for {sec}"

    def test_all_review_types_in_requirements(self) -> None:
        for rt in ReviewType:
            assert rt.value in _SECTION_REQUIREMENTS, f"Missing req for {rt}"

    def test_each_has_at_least_one_mandatory(self) -> None:
        for key, (mandatory, _) in _SECTION_REQUIREMENTS.items():
            assert len(mandatory) >= 1, f"{key} has no mandatory sections"

    def test_abstract_in_every_mandatory(self) -> None:
        for key, (mandatory, _) in _SECTION_REQUIREMENTS.items():
            assert "abstract" in mandatory, f"{key} missing abstract"

    def test_no_duplicate_section_order(self) -> None:
        assert len(_SECTION_ORDER) == len(set(_SECTION_ORDER))


# ===========================================================================
# 11. Determinism enforcement
# ===========================================================================

class TestDeterminismEnforcement:
    """Verify no UUID, datetime, or random in models."""

    def test_no_uuid(self) -> None:
        import inspect
        import researchmind.synthesis.models as models
        source = inspect.getsource(models)
        assert "uuid" not in source

    def test_no_datetime(self) -> None:
        import inspect
        import researchmind.synthesis.models as models
        source = inspect.getsource(models)
        assert "datetime" not in source

    def test_no_random(self) -> None:
        import inspect
        import researchmind.synthesis.models as models
        source = inspect.getsource(models)
        assert "random" not in source

    def test_no_generated_at(self) -> None:
        assert not hasattr(ReviewResult.model_fields, "generated_at")


# ===========================================================================
# 12. Cross-model integration
# ===========================================================================

class TestCrossModelIntegration:
    """Verify models compose together correctly."""

    def test_finding_in_section(self) -> None:
        f = make_finding()
        s = make_section(section_id="s1", findings=[f], confidence=f.confidence)
        assert s.findings[0].finding_id == f.finding_id

    def test_section_in_result(self) -> None:
        f = make_finding()
        s = make_section(section_id="s1", findings=[f], confidence=f.confidence)
        r = ReviewResult(
            review_id="r",
            review_type="general",
            title="T",
            abstract="A.",
            sections=[s],
            total_findings=1,
            total_words=s.word_count,
        )
        assert r.sections[0].section_id == s.section_id

    def test_finding_in_result_and_section(self) -> None:
        f = make_finding()
        s = make_section(section_id="s1", findings=[f], confidence=f.confidence)
        r = ReviewResult(
            review_id="r",
            review_type="general",
            title="T",
            abstract="A.",
            sections=[s],
            findings=[f],
            total_findings=1,
            total_words=s.word_count,
        )
        assert len(r.findings) == 1
        assert r.findings[0].finding_id == f.finding_id

    def test_evidence_in_bundle(self) -> None:
        ev = make_evidence()
        b = EvidenceBundle(
            bundle_id="b",
            theme="T",
            evidence_items=[ev],
            evidence_count=1,
        )
        assert b.evidence_items[0].evidence_id == ev.evidence_id

    def test_bundle_in_theme_workflow(self) -> None:
        ev = make_evidence()
        b = EvidenceBundle(
            bundle_id="b",
            theme="Optimization",
            evidence_items=[ev],
            evidence_count=1,
        )
        t = ThemeCluster(
            cluster_id="c",
            theme_type="method",
            label="Optimization",
            entities=["Adam", "SGD"],
            evidence_count=1,
        )
        assert t.label == "Optimization"
        assert b.theme == "Optimization"

    def test_full_review_assembly(self) -> None:
        f1 = make_finding(finding_id="f1", ftype="consensus", statement="Consensus on dropout.")
        f2 = make_finding(finding_id="f2", ftype="gap", statement="Gap in GAN research.")
        s1 = make_section(section_id="sec_consensus", stype="consensus",
                          title="Consensus", findings=[f1], confidence=f1.confidence)
        s2 = make_section(section_id="sec_gaps", stype="research_gaps",
                          title="Gaps", findings=[f2], confidence=f2.confidence)
        r = ReviewResult(
            review_id="full_review",
            review_type="general",
            title="Comprehensive Review",
            abstract="This review covers consensus and gaps.",
            sections=[s1, s2],
            findings=[f1, f2],
            total_findings=2,
            total_words=s1.word_count + s2.word_count,
        )
        assert r.total_findings == 2
        assert len(r.sections) == 2
        assert len(r.findings) == 2
        assert r.traceability_verified is False

    def test_error_case_empty_corpus_result(self) -> None:
        r = ReviewResult(
            review_id="empty",
            review_type="general",
            title="Empty Corpus",
            errors=["No documents in corpus"],
        )
        assert len(r.errors) == 1
        assert r.total_findings == 0


# ===========================================================================
# 13. Edge cases
# ===========================================================================

class TestEdgeCases:
    """Boundary and edge-case tests."""

    def test_review_request_no_targets(self) -> None:
        req = ReviewRequest(review_id="r", review_type="general")
        assert req.target_entities == []
        assert req.target_documents == []

    def test_review_finding_max_confidence(self) -> None:
        f = make_finding(confidence=1.0)
        assert f.confidence == 1.0

    def test_review_finding_min_confidence(self) -> None:
        f = make_finding(confidence=0.0)
        assert f.confidence == 0.0

    def test_section_no_findings_max_confidence(self) -> None:
        s = make_section(confidence=1.0)
        assert s.confidence == 1.0

    def test_empty_bundle(self) -> None:
        b = EvidenceBundle(bundle_id="empty", theme="Empty", evidence_count=0)
        assert len(b.evidence_items) == 0
        assert b.evidence_count == 0

    def test_theme_cluster_no_theme_type(self) -> None:
        t = ThemeCluster(cluster_id="c", label="Uncategorized")
        assert t.theme_type == ""
        assert t.entities == []

    def test_result_with_warnings_only(self) -> None:
        r = ReviewResult(
            review_id="warn",
            review_type="general",
            title="With Warnings",
            warnings=["Low confidence", "Sparse evidence"],
        )
        assert len(r.warnings) == 2

    def test_result_with_errors_only(self) -> None:
        r = ReviewResult(
            review_id="err",
            review_type="general",
            title="With Errors",
            errors=["Engine unavailable"],
        )
        assert len(r.errors) == 1

    def test_review_type_from_string(self) -> None:
        rt = ReviewType("general")
        assert rt == ReviewType.GENERAL

    def test_theme_type_from_string(self) -> None:
        tt = ThemeType("mixed")
        assert tt == ThemeType.MIXED

    def test_multiple_findings_different_types_in_section(self) -> None:
        f1 = make_finding(finding_id="f1", ftype="consensus", statement="C1")
        f2 = make_finding(finding_id="f2", ftype="contradiction",
                          statement="C2", trace=["t1"])
        f3 = make_finding(finding_id="f3", ftype="gap", statement="G1")
        s = make_section(
            section_id="multi",
            findings=[f1, f2, f3],
            confidence=min(f1.confidence, f2.confidence, f3.confidence),
        )
        assert len(s.findings) == 3
        assert s.findings[0].finding_type == "consensus"
        assert s.findings[1].finding_type == "contradiction"
        assert s.findings[2].finding_type == "gap"

    def test_evidence_bundle_aggregate_confidence_at_bounds(self) -> None:
        ev = make_evidence()
        b = EvidenceBundle(
            bundle_id="b",
            theme="T",
            evidence_items=[ev],
            aggregate_confidence=0.0,
            evidence_count=1,
        )
        assert b.aggregate_confidence == 0.0

    def test_evidence_bundle_aggregate_confidence_max(self) -> None:
        ev = make_evidence()
        b = EvidenceBundle(
            bundle_id="b",
            theme="T",
            evidence_items=[ev],
            aggregate_confidence=1.0,
            evidence_count=1,
        )
        assert b.aggregate_confidence == 1.0

    def test_model_dump_json_roundtrip(self) -> None:
        f = make_finding()
        s = make_section(section_id="s1", findings=[f], confidence=f.confidence)
        r = ReviewResult(
            review_id="json_rt",
            review_type="general",
            title="JSON Roundtrip",
            abstract="Abstract.",
            sections=[s],
            total_findings=1,
            total_words=s.word_count,
        )
        json_str = r.model_dump_json()
        restored = ReviewResult.model_validate_json(json_str)
        assert restored.review_id == r.review_id
        assert restored.title == r.title
        assert len(restored.sections) == 1
