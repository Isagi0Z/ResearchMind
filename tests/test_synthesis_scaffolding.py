"""Scaffolding tests for Module 6 — verify imports, models, enums, exports, constructors.

No business logic tests — only structural verification.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# 1. Imports work
# ---------------------------------------------------------------------------

class TestPackageImports:
    """Verify all synthesis submodules import without error."""

    def test_import_synthesis_package(self) -> None:
        import researchmind.synthesis  # noqa

    def test_import_models(self) -> None:
        import researchmind.synthesis.models  # noqa

    def test_import_theme_detector(self) -> None:
        import researchmind.synthesis.theme_detector  # noqa

    def test_import_evidence_collector(self) -> None:
        import researchmind.synthesis.evidence_collector  # noqa

    def test_import_finding_generator(self) -> None:
        import researchmind.synthesis.finding_generator  # noqa

    def test_import_section_builder(self) -> None:
        import researchmind.synthesis.section_builder  # noqa

    def test_import_traceability(self) -> None:
        import researchmind.synthesis.traceability  # noqa

    def test_import_confidence(self) -> None:
        import researchmind.synthesis.confidence  # noqa

    def test_import_orchestrator(self) -> None:
        import researchmind.synthesis.orchestrator  # noqa


# ---------------------------------------------------------------------------
# 2. Exports are correct
# ---------------------------------------------------------------------------

class TestPackageExports:
    """Verify __all__ exports match expected symbols."""

    def test_all_exported(self) -> None:
        from researchmind.synthesis import __all__  # noqa

        expected = {
            "ReviewType",
            "ThemeType",
            "ReviewRequest",
            "ReviewFinding",
            "ReviewSection",
            "ReviewResult",
            "EvidenceBundle",
            "ThemeCluster",
            "ReviewOrchestrator",
            "ThemeDetector",
            "EvidenceCollector",
            "FindingGenerator",
            "SectionBuilder",
            "TraceabilityVerifier",
            "ConfidenceComputer",
            "_generate_id",
            "_SECTION_ORDER",
            "_SECTION_REQUIREMENTS",
            "_SECTION_TITLES",
        }
        assert expected.issubset(set(__all__)), f"Missing: {expected - set(__all__)}"

    def test_review_type_exported(self) -> None:
        from researchmind.synthesis import ReviewType  # noqa

    def test_theme_type_exported(self) -> None:
        from researchmind.synthesis import ThemeType  # noqa

    def test_review_request_exported(self) -> None:
        from researchmind.synthesis import ReviewRequest  # noqa

    def test_review_finding_exported(self) -> None:
        from researchmind.synthesis import ReviewFinding  # noqa

    def test_review_section_exported(self) -> None:
        from researchmind.synthesis import ReviewSection  # noqa

    def test_review_result_exported(self) -> None:
        from researchmind.synthesis import ReviewResult  # noqa

    def test_evidence_bundle_exported(self) -> None:
        from researchmind.synthesis import EvidenceBundle  # noqa

    def test_theme_cluster_exported(self) -> None:
        from researchmind.synthesis import ThemeCluster  # noqa

    def test_orchestrator_exported(self) -> None:
        from researchmind.synthesis import ReviewOrchestrator  # noqa

    def test_theme_detector_exported(self) -> None:
        from researchmind.synthesis import ThemeDetector  # noqa

    def test_evidence_collector_exported(self) -> None:
        from researchmind.synthesis import EvidenceCollector  # noqa

    def test_finding_generator_exported(self) -> None:
        from researchmind.synthesis import FindingGenerator  # noqa

    def test_section_builder_exported(self) -> None:
        from researchmind.synthesis import SectionBuilder  # noqa

    def test_traceability_verifier_exported(self) -> None:
        from researchmind.synthesis import TraceabilityVerifier  # noqa

    def test_confidence_computer_exported(self) -> None:
        from researchmind.synthesis import ConfidenceComputer  # noqa

    def test_generate_id_exported(self) -> None:
        from researchmind.synthesis import _generate_id  # noqa

    def test_section_order_exported(self) -> None:
        from researchmind.synthesis import _SECTION_ORDER  # noqa

    def test_section_requirements_exported(self) -> None:
        from researchmind.synthesis import _SECTION_REQUIREMENTS  # noqa

    def test_section_titles_exported(self) -> None:
        from researchmind.synthesis import _SECTION_TITLES  # noqa


# ---------------------------------------------------------------------------
# 3. Enum values
# ---------------------------------------------------------------------------

class TestReviewTypeEnum:
    """Verify ReviewType enum has all required values."""

    def test_has_general(self) -> None:
        from researchmind.synthesis.models import ReviewType
        assert ReviewType.GENERAL == "general"

    def test_has_method(self) -> None:
        from researchmind.synthesis.models import ReviewType
        assert ReviewType.METHOD == "method"

    def test_has_dataset(self) -> None:
        from researchmind.synthesis.models import ReviewType
        assert ReviewType.DATASET == "dataset"

    def test_has_consensus(self) -> None:
        from researchmind.synthesis.models import ReviewType
        assert ReviewType.CONSENSUS == "consensus"

    def test_has_contradiction(self) -> None:
        from researchmind.synthesis.models import ReviewType
        assert ReviewType.CONTRADICTION == "contradiction"

    def test_has_research_gap(self) -> None:
        from researchmind.synthesis.models import ReviewType
        assert ReviewType.RESEARCH_GAP == "research_gap"

    def test_has_comparative(self) -> None:
        from researchmind.synthesis.models import ReviewType
        assert ReviewType.COMPARATIVE == "comparative"

    def test_has_landscape(self) -> None:
        from researchmind.synthesis.models import ReviewType
        assert ReviewType.LANDSCAPE == "landscape"

    def test_all_values_unique(self) -> None:
        from researchmind.synthesis.models import ReviewType
        values = [e.value for e in ReviewType]
        assert len(values) == len(set(values))

    def test_all_members_count(self) -> None:
        from researchmind.synthesis.models import ReviewType
        assert len(list(ReviewType)) == 8


class TestThemeTypeEnum:
    """Verify ThemeType enum has all required values."""

    def test_has_method(self) -> None:
        from researchmind.synthesis.models import ThemeType
        assert ThemeType.METHOD == "method"

    def test_has_dataset(self) -> None:
        from researchmind.synthesis.models import ThemeType
        assert ThemeType.DATASET == "dataset"

    def test_has_metric(self) -> None:
        from researchmind.synthesis.models import ThemeType
        assert ThemeType.METRIC == "metric"

    def test_has_concept(self) -> None:
        from researchmind.synthesis.models import ThemeType
        assert ThemeType.CONCEPT == "concept"

    def test_has_mixed(self) -> None:
        from researchmind.synthesis.models import ThemeType
        assert ThemeType.MIXED == "mixed"

    def test_all_values_unique(self) -> None:
        from researchmind.synthesis.models import ThemeType
        values = [e.value for e in ThemeType]
        assert len(values) == len(set(values))

    def test_all_members_count(self) -> None:
        from researchmind.synthesis.models import ThemeType
        assert len(list(ThemeType)) == 5


# ---------------------------------------------------------------------------
# 4. Model instantiation — ReviewRequest
# ---------------------------------------------------------------------------

class TestReviewRequestModel:
    """Verify ReviewRequest model creation and validation."""

    def test_minimal_instantiation(self) -> None:
        from researchmind.synthesis.models import ReviewRequest
        req = ReviewRequest(review_id="test_001", review_type="general")
        assert req.review_id == "test_001"
        assert req.review_type == "general"

    def test_default_title_is_empty(self) -> None:
        from researchmind.synthesis.models import ReviewRequest
        req = ReviewRequest(review_id="t1", review_type="method")
        assert req.title == ""

    def test_default_target_documents_empty(self) -> None:
        from researchmind.synthesis.models import ReviewRequest
        req = ReviewRequest(review_id="t2", review_type="dataset")
        assert req.target_documents == []

    def test_default_max_documents(self) -> None:
        from researchmind.synthesis.models import ReviewRequest
        req = ReviewRequest(review_id="t3", review_type="landscape")
        assert req.max_documents == 10

    def test_default_min_confidence(self) -> None:
        from researchmind.synthesis.models import ReviewRequest
        req = ReviewRequest(review_id="t4", review_type="consensus")
        assert req.min_confidence == 0.3

    def test_all_fields_explicit(self) -> None:
        from researchmind.synthesis.models import ReviewRequest
        req = ReviewRequest(
            review_id="full",
            review_type="comparative",
            title="Test Review",
            query="Test query?",
            target_documents=["doc1", "doc2"],
            max_documents=20,
            min_confidence=0.5,
            include_contradictions=False,
            include_gaps=True,
            include_consensus=False,
            metadata={"source": "test"},
        )
        assert req.review_id == "full"
        assert req.title == "Test Review"
        assert req.target_documents == ["doc1", "doc2"]
        assert req.max_documents == 20
        assert req.min_confidence == 0.5
        assert req.include_contradictions is False
        assert req.include_gaps is True
        assert req.include_consensus is False

    def test_invalid_review_type_raises(self) -> None:
        from researchmind.synthesis.models import ReviewRequest
        with pytest.raises(ValidationError):
            ReviewRequest(review_id="bad", review_type="invalid_type")

    def test_empty_review_type_raises(self) -> None:
        from researchmind.synthesis.models import ReviewRequest
        with pytest.raises(ValidationError):
            ReviewRequest(review_id="empty", review_type="")

    def test_case_insensitive_review_type(self) -> None:
        from researchmind.synthesis.models import ReviewRequest
        req = ReviewRequest(review_id="case", review_type="GENERAL")
        assert req.review_type == "general"

    def test_max_documents_zero_raises(self) -> None:
        from researchmind.synthesis.models import ReviewRequest
        with pytest.raises(ValidationError):
            ReviewRequest(review_id="low", review_type="general", max_documents=0)

    def test_max_documents_positive_allowed(self) -> None:
        from researchmind.synthesis.models import ReviewRequest
        req = ReviewRequest(review_id="ok", review_type="general", max_documents=1)
        assert req.max_documents == 1

    def test_confidence_below_min_raises(self) -> None:
        from researchmind.synthesis.models import ReviewRequest
        with pytest.raises(ValidationError):
            ReviewRequest(review_id="neg", review_type="general", min_confidence=-0.1)

    def test_confidence_above_max_raises(self) -> None:
        from researchmind.synthesis.models import ReviewRequest
        with pytest.raises(ValidationError):
            ReviewRequest(review_id="over", review_type="general", min_confidence=1.5)


# ---------------------------------------------------------------------------
# 5. Model instantiation — ReviewFinding
# ---------------------------------------------------------------------------

class TestReviewFindingModel:
    """Verify ReviewFinding model creation and validation."""

    def test_minimal_instantiation(self) -> None:
        from researchmind.synthesis.models import ReviewFinding
        f = ReviewFinding(
            finding_id="find_001",
            finding_type="consensus",
            statement="There is strong consensus that Dropout is effective.",
            confidence=0.85,
        )
        assert f.finding_id == "find_001"
        assert f.finding_type == "consensus"
        assert f.statement != ""
        assert f.confidence == 0.85

    def test_default_empty_lists(self) -> None:
        from researchmind.synthesis.models import ReviewFinding
        f = ReviewFinding(
            finding_id="find_002",
            finding_type="gap",
            statement="Test.",
            confidence=0.5,
        )
        assert f.evidence_ids == []
        assert f.source_document_ids == []
        assert f.source_document_titles == []

    def test_default_counts_zero(self) -> None:
        from researchmind.synthesis.models import ReviewFinding
        f = ReviewFinding(
            finding_id="find_003",
            finding_type="method",
            statement="Test.",
            confidence=0.6,
        )
        assert f.supporting_count == 0
        assert f.contradicting_count == 0
        assert f.neutral_count == 0

    def test_empty_finding_id_raises(self) -> None:
        from researchmind.synthesis.models import ReviewFinding
        with pytest.raises(ValidationError):
            ReviewFinding(
                finding_id="",
                finding_type="consensus",
                statement="Test.",
                confidence=0.5,
            )

    def test_whitespace_finding_id_raises(self) -> None:
        from researchmind.synthesis.models import ReviewFinding
        with pytest.raises(ValidationError):
            ReviewFinding(
                finding_id="   ",
                finding_type="consensus",
                statement="Test.",
                confidence=0.5,
            )

    def test_confidence_below_zero_raises(self) -> None:
        from researchmind.synthesis.models import ReviewFinding
        with pytest.raises(ValidationError):
            ReviewFinding(
                finding_id="f",
                finding_type="consensus",
                statement="Test.",
                confidence=-0.1,
            )

    def test_confidence_above_one_raises(self) -> None:
        from researchmind.synthesis.models import ReviewFinding
        with pytest.raises(ValidationError):
            ReviewFinding(
                finding_id="f",
                finding_type="consensus",
                statement="Test.",
                confidence=1.5,
            )

    def test_metadata_default(self) -> None:
        from researchmind.synthesis.models import ReviewFinding
        f = ReviewFinding(
            finding_id="f_meta",
            finding_type="relation",
            statement="Edge test.",
            confidence=0.9,
        )
        assert f.metadata == {}


# ---------------------------------------------------------------------------
# 6. Model instantiation — ReviewSection
# ---------------------------------------------------------------------------

class TestReviewSectionModel:
    """Verify ReviewSection model creation and validation."""

    def test_minimal_instantiation(self) -> None:
        from researchmind.synthesis.models import ReviewSection
        s = ReviewSection(
            section_id="sec_intro",
            section_type="introduction",
            title="Introduction",
        )
        assert s.section_id == "sec_intro"
        assert s.section_type == "introduction"
        assert s.title == "Introduction"

    def test_default_summary_empty(self) -> None:
        from researchmind.synthesis.models import ReviewSection
        s = ReviewSection(section_id="s1", section_type="abstract", title="Abstract")
        assert s.summary == ""

    def test_default_findings_empty(self) -> None:
        from researchmind.synthesis.models import ReviewSection
        s = ReviewSection(section_id="s2", section_type="conclusion", title="Conclusion")
        assert s.findings == []

    def test_default_paragraphs_empty(self) -> None:
        from researchmind.synthesis.models import ReviewSection
        s = ReviewSection(section_id="s3", section_type="methods_landscape", title="Methods")
        assert s.paragraphs == []

    def test_default_confidence_zero(self) -> None:
        from researchmind.synthesis.models import ReviewSection
        s = ReviewSection(section_id="s4", section_type="datasets", title="Datasets")
        assert s.confidence == 0.0

    def test_default_word_count_zero(self) -> None:
        from researchmind.synthesis.models import ReviewSection
        s = ReviewSection(section_id="s5", section_type="consensus", title="Consensus")
        assert s.word_count == 0

    def test_default_is_mandatory_false(self) -> None:
        from researchmind.synthesis.models import ReviewSection
        s = ReviewSection(section_id="s6", section_type="research_gaps", title="Gaps")
        assert s.is_mandatory is False

    def test_empty_section_id_raises(self) -> None:
        from researchmind.synthesis.models import ReviewSection
        with pytest.raises(ValidationError):
            ReviewSection(section_id="", section_type="intro", title="Intro")

    def test_whitespace_section_id_raises(self) -> None:
        from researchmind.synthesis.models import ReviewSection
        with pytest.raises(ValidationError):
            ReviewSection(section_id="   ", section_type="intro", title="Intro")


# ---------------------------------------------------------------------------
# 7. Model instantiation — ReviewResult
# ---------------------------------------------------------------------------

class TestReviewResultModel:
    """Verify ReviewResult model creation and validation."""

    def test_minimal_instantiation(self) -> None:
        from researchmind.synthesis.models import ReviewResult
        r = ReviewResult(
            review_id="res_001",
            review_type="general",
            title="Deep Learning: A Review",
        )
        assert r.review_id == "res_001"
        assert r.review_type == "general"
        assert r.title == "Deep Learning: A Review"

    def test_abstract_default_empty(self) -> None:
        from researchmind.synthesis.models import ReviewResult
        r = ReviewResult(review_id="r1", review_type="method", title="Methods")
        assert r.abstract == ""

    def test_sections_default_empty(self) -> None:
        from researchmind.synthesis.models import ReviewResult
        r = ReviewResult(review_id="r2", review_type="dataset", title="Datasets")
        assert r.sections == []

    def test_statistics_default_zero(self) -> None:
        from researchmind.synthesis.models import ReviewResult
        r = ReviewResult(review_id="r3", review_type="consensus", title="Consensus")
        assert r.total_findings == 0
        assert r.total_evidence_items == 0
        assert r.total_documents_cited == 0
        assert r.total_words == 0

    def test_confidence_default_zero(self) -> None:
        from researchmind.synthesis.models import ReviewResult
        r = ReviewResult(review_id="r4", review_type="contradiction", title="Contra")
        assert r.confidence == 0.0

    def test_traceability_defaults(self) -> None:
        from researchmind.synthesis.models import ReviewResult
        r = ReviewResult(review_id="r5", review_type="research_gap", title="Gaps")
        assert r.traceability_verified is False
        assert r.traceability_failures == []

    def test_empty_title_raises(self) -> None:
        from researchmind.synthesis.models import ReviewResult
        with pytest.raises(ValidationError):
            ReviewResult(review_id="bad", review_type="general", title="")

    def test_whitespace_title_raises(self) -> None:
        from researchmind.synthesis.models import ReviewResult
        with pytest.raises(ValidationError):
            ReviewResult(review_id="bad", review_type="general", title="   ")

    def test_invalid_review_type_raises(self) -> None:
        from researchmind.synthesis.models import ReviewResult
        with pytest.raises(ValidationError):
            ReviewResult(review_id="bad", review_type="unknown", title="T")

    def test_can_attach_sections(self) -> None:
        from researchmind.synthesis.models import ReviewResult, ReviewSection
        sec = ReviewSection(section_id="s1", section_type="introduction", title="Intro")
        r = ReviewResult(
            review_id="r_attach",
            review_type="general",
            title="Full",
            abstract="Abstract.",
            sections=[sec],
        )
        assert len(r.sections) == 1
        assert r.sections[0].section_type == "introduction"


# ---------------------------------------------------------------------------
# 8. Model instantiation — EvidenceBundle
# ---------------------------------------------------------------------------

class TestEvidenceBundleModel:
    """Verify EvidenceBundle model creation and validation."""

    def test_minimal_instantiation(self) -> None:
        from researchmind.synthesis.models import EvidenceBundle
        b = EvidenceBundle(bundle_id="bnd_001", theme="Deep Learning")
        assert b.bundle_id == "bnd_001"
        assert b.theme == "Deep Learning"

    def test_default_evidence_items_empty(self) -> None:
        from researchmind.synthesis.models import EvidenceBundle
        b = EvidenceBundle(bundle_id="b1", theme="Methods")
        assert b.evidence_items == []

    def test_default_aggregate_confidence_zero(self) -> None:
        from researchmind.synthesis.models import EvidenceBundle
        b = EvidenceBundle(bundle_id="b2", theme="Datasets")
        assert b.aggregate_confidence == 0.0

    def test_default_finding_type_empty(self) -> None:
        from researchmind.synthesis.models import EvidenceBundle
        b = EvidenceBundle(bundle_id="b3", theme="Gaps")
        assert b.finding_type == ""


# ---------------------------------------------------------------------------
# 9. Model instantiation — ThemeCluster
# ---------------------------------------------------------------------------

class TestThemeClusterModel:
    """Verify ThemeCluster model creation and validation."""

    def test_minimal_instantiation(self) -> None:
        from researchmind.synthesis.models import ThemeCluster
        t = ThemeCluster(cluster_id="thm_001", label="Optimization")
        assert t.cluster_id == "thm_001"
        assert t.label == "Optimization"

    def test_default_entity_ids_empty(self) -> None:
        from researchmind.synthesis.models import ThemeCluster
        t = ThemeCluster(cluster_id="t1", label="L1")
        assert t.entity_cluster_ids == []

    def test_default_document_ids_empty(self) -> None:
        from researchmind.synthesis.models import ThemeCluster
        t = ThemeCluster(cluster_id="t2", label="L2")
        assert t.document_ids == []

    def test_default_evidence_count_zero(self) -> None:
        from researchmind.synthesis.models import ThemeCluster
        t = ThemeCluster(cluster_id="t3", label="L3")
        assert t.evidence_count == 0

    def test_default_confidence_zero(self) -> None:
        from researchmind.synthesis.models import ThemeCluster
        t = ThemeCluster(cluster_id="t4", label="L4")
        assert t.confidence == 0.0


# ---------------------------------------------------------------------------
# 10. Deterministic ID generation
# ---------------------------------------------------------------------------

class TestGenerateId:
    """Verify _generate_id is deterministic."""

    def test_returns_string(self) -> None:
        from researchmind.synthesis.models import _generate_id
        result = _generate_id("pre", "a", "b")
        assert isinstance(result, str)

    def test_prefix_format(self) -> None:
        from researchmind.synthesis.models import _generate_id
        result = _generate_id("pre", "a", "b")
        assert result.startswith("pre_")

    def test_hex_suffix_length(self) -> None:
        from researchmind.synthesis.models import _generate_id
        result = _generate_id("pre", "a", "b")
        suffix = result.split("_")[1]
        assert len(suffix) == 12
        int(suffix, 16)  # must be valid hex

    def test_deterministic_same_inputs(self) -> None:
        from researchmind.synthesis.models import _generate_id
        a = _generate_id("pfx", "x", "y")
        b = _generate_id("pfx", "x", "y")
        assert a == b

    def test_deterministic_different_inputs(self) -> None:
        from researchmind.synthesis.models import _generate_id
        a = _generate_id("pfx", "x", "y")
        b = _generate_id("pfx", "x", "z")
        assert a != b

    def test_empty_parts(self) -> None:
        from researchmind.synthesis.models import _generate_id
        result = _generate_id("pre")
        assert result.startswith("pre_")

    def test_single_part(self) -> None:
        from researchmind.synthesis.models import _generate_id
        result = _generate_id("pre", "hello")
        assert result.startswith("pre_")


# ---------------------------------------------------------------------------
# 11. Section constants
# ---------------------------------------------------------------------------

class TestSectionConstants:
    """Verify _SECTION_ORDER, _SECTION_TITLES, _SECTION_REQUIREMENTS."""

    def test_section_order_is_list(self) -> None:
        from researchmind.synthesis.models import _SECTION_ORDER
        assert isinstance(_SECTION_ORDER, list)
        assert len(_SECTION_ORDER) >= 8

    def test_section_order_has_abstract_first(self) -> None:
        from researchmind.synthesis.models import _SECTION_ORDER
        assert _SECTION_ORDER[0] == "abstract"

    def test_section_order_has_conclusion_last(self) -> None:
        from researchmind.synthesis.models import _SECTION_ORDER
        assert _SECTION_ORDER[-1] == "conclusion"

    def test_section_titles_all_section_order_keys(self) -> None:
        from researchmind.synthesis.models import _SECTION_ORDER, _SECTION_TITLES
        for sec in _SECTION_ORDER:
            assert sec in _SECTION_TITLES, f"Missing title for {sec}"

    def test_section_requirements_all_review_types(self) -> None:
        from researchmind.synthesis.models import (
            ReviewType,
            _SECTION_REQUIREMENTS,
        )
        for rt in ReviewType:
            assert rt.value in _SECTION_REQUIREMENTS, f"Missing req for {rt}"

    def test_section_requirements_tuple_length(self) -> None:
        from researchmind.synthesis.models import _SECTION_REQUIREMENTS
        for key, (mandatory, optional) in _SECTION_REQUIREMENTS.items():
            assert len(mandatory) >= 1, f"{key} has no mandatory sections"
            assert isinstance(mandatory, list)
            assert isinstance(optional, list)

    def test_abstract_in_every_review_type(self) -> None:
        from researchmind.synthesis.models import _SECTION_REQUIREMENTS
        for key, (mandatory, _) in _SECTION_REQUIREMENTS.items():
            assert "abstract" in mandatory, f"{key} missing abstract"

    def test_no_duplicate_section_order(self) -> None:
        from researchmind.synthesis.models import _SECTION_ORDER
        assert len(_SECTION_ORDER) == len(set(_SECTION_ORDER))


# ---------------------------------------------------------------------------
# 12. Constructor signatures exist
# ---------------------------------------------------------------------------

class TestClassConstructors:
    """Verify all classes can be instantiated with expected constructor signatures."""

    def test_theme_detector_constructs(self) -> None:
        from researchmind.synthesis.theme_detector import ThemeDetector
        td = ThemeDetector()
        assert isinstance(td, ThemeDetector)

    def test_evidence_collector_constructs(self) -> None:
        from researchmind.synthesis.evidence_collector import EvidenceCollector
        ec = EvidenceCollector()
        assert isinstance(ec, EvidenceCollector)

    def test_evidence_collector_default_construction(self) -> None:
        from researchmind.synthesis.evidence_collector import EvidenceCollector
        ec = EvidenceCollector()
        assert isinstance(ec, EvidenceCollector)

    def test_finding_generator_constructs(self) -> None:
        from researchmind.synthesis.finding_generator import FindingGenerator
        fg = FindingGenerator()
        assert isinstance(fg, FindingGenerator)

    def test_section_builder_constructs(self) -> None:
        from researchmind.synthesis.section_builder import SectionBuilder
        sb = SectionBuilder()
        assert isinstance(sb, SectionBuilder)

    def test_traceability_verifier_constructs(self) -> None:
        from researchmind.synthesis.traceability import TraceabilityVerifier
        tv = TraceabilityVerifier()
        assert isinstance(tv, TraceabilityVerifier)

    def test_confidence_computer_constructs(self) -> None:
        from researchmind.synthesis.confidence import ConfidenceComputer
        cc = ConfidenceComputer()
        assert isinstance(cc, ConfidenceComputer)

    def test_orchestrator_constructs_minimal(self) -> None:
        from researchmind.synthesis.orchestrator import ReviewOrchestrator
        ro = ReviewOrchestrator(corpus_manager="cm", graph="g")
        assert isinstance(ro, ReviewOrchestrator)

    def test_orchestrator_constructs_full(self) -> None:
        from researchmind.synthesis.orchestrator import ReviewOrchestrator
        ro = ReviewOrchestrator(
            corpus_manager="cm",
            graph="g",
            consensus_engine="ce",
            contradiction_engine="cte",
            gap_engine="ge",
            multi_hop_reasoner="mh",
            document_store="ds",
        )
        assert isinstance(ro, ReviewOrchestrator)


# ---------------------------------------------------------------------------
# 13. Required methods exist and raise NotImplementedError
# ---------------------------------------------------------------------------

class TestRequiredMethods:
    """Verify all required methods exist and raise NotImplementedError."""

    def test_theme_detector_detect_themes_exists(self) -> None:
        from researchmind.synthesis.theme_detector import ThemeDetector
        assert hasattr(ThemeDetector, "detect_themes")

    def test_theme_detector_detect_themes_empty_graph(self) -> None:
        from researchmind.synthesis.theme_detector import ThemeDetector
        td = ThemeDetector()
        result = td.detect_themes(graph=None)
        assert result == []

    def test_evidence_collector_collect_exists(self) -> None:
        from researchmind.synthesis.evidence_collector import EvidenceCollector
        assert hasattr(EvidenceCollector, "collect")

    def test_evidence_collector_collect_empty(self) -> None:
        from researchmind.synthesis.evidence_collector import EvidenceCollector
        ec = EvidenceCollector()
        result = ec.collect(corpus=None, graph=None, themes=[])
        assert result == []

    def test_finding_generator_generate_findings_exists(self) -> None:
        from researchmind.synthesis.finding_generator import FindingGenerator
        assert hasattr(FindingGenerator, "generate_findings")

    def test_finding_generator_generate_findings_raises(self) -> None:
        from researchmind.synthesis.finding_generator import FindingGenerator
        from researchmind.synthesis.models import ThemeCluster
        fg = FindingGenerator()
        theme = ThemeCluster(cluster_id="t", label="L")
        result = fg.generate_findings(theme=theme, evidence_bundles=[])
        assert result == []

    def test_section_builder_build_sections_exists(self) -> None:
        from researchmind.synthesis.section_builder import SectionBuilder
        assert hasattr(SectionBuilder, "build_sections")

    def test_section_builder_build_sections_empty(self) -> None:
        from researchmind.synthesis.section_builder import SectionBuilder
        sb = SectionBuilder()
        result = sb.build_sections(review_type="general", findings_by_type={}, corpus_metadata={})
        assert isinstance(result, list)

    def test_traceability_verifier_verify_review_exists(self) -> None:
        from researchmind.synthesis.traceability import TraceabilityVerifier
        assert hasattr(TraceabilityVerifier, "verify_review")

    def test_traceability_verifier_verify_review_empty(self) -> None:
        from researchmind.synthesis.traceability import TraceabilityVerifier
        from researchmind.synthesis.models import ReviewResult
        tv = TraceabilityVerifier()
        review = ReviewResult(review_id="r", review_type="general", title="T")
        valid, warnings = tv.verify_review(review=review, corpus=None)
        assert valid is True
        assert warnings == []

    def test_confidence_computer_compute_finding_confidence_exists(self) -> None:
        from researchmind.synthesis.confidence import ConfidenceComputer
        assert hasattr(ConfidenceComputer, "compute_finding_confidence")

    def test_confidence_computer_compute_finding_confidence_returns_float(self) -> None:
        from researchmind.synthesis.confidence import ConfidenceComputer
        cc = ConfidenceComputer()
        result = cc.compute_finding_confidence(finding_type="consensus", data={})
        assert isinstance(result, float)

    def test_confidence_computer_compute_section_confidence_exists(self) -> None:
        from researchmind.synthesis.confidence import ConfidenceComputer
        assert hasattr(ConfidenceComputer, "compute_section_confidence")

    def test_confidence_computer_compute_section_confidence_empty_returns_zero(self) -> None:
        from researchmind.synthesis.confidence import ConfidenceComputer
        cc = ConfidenceComputer()
        result = cc.compute_section_confidence(findings=[])
        assert result == 0.0

    def test_confidence_computer_compute_review_confidence_exists(self) -> None:
        from researchmind.synthesis.confidence import ConfidenceComputer
        assert hasattr(ConfidenceComputer, "compute_review_confidence")

    def test_confidence_computer_compute_review_confidence_empty_returns_zero(self) -> None:
        from researchmind.synthesis.confidence import ConfidenceComputer
        cc = ConfidenceComputer()
        result = cc.compute_review_confidence(sections=[], mandatory_types=[])
        assert result == 0.0

    def test_orchestrator_generate_exists(self) -> None:
        from researchmind.synthesis.orchestrator import ReviewOrchestrator
        assert hasattr(ReviewOrchestrator, "generate")

    def test_orchestrator_generate_returns_result(self) -> None:
        from researchmind.synthesis.orchestrator import ReviewOrchestrator
        from researchmind.synthesis.models import ReviewRequest, ReviewResult
        ro = ReviewOrchestrator(corpus_manager=None, graph=None)
        req = ReviewRequest(review_id="r", review_type="general")
        result = ro.generate(req)
        assert isinstance(result, ReviewResult)


# ---------------------------------------------------------------------------
# 14. StrEnum compatibility
# ---------------------------------------------------------------------------

class TestStrEnumCompatibility:
    """Verify StrEnum backport works correctly."""

    def test_review_type_is_str(self) -> None:
        from researchmind.synthesis.models import ReviewType
        assert isinstance(ReviewType.GENERAL.value, str)
        assert ReviewType.GENERAL.value == "general"
        assert isinstance(ReviewType.GENERAL, str)

    def test_theme_type_is_str(self) -> None:
        from researchmind.synthesis.models import ThemeType
        assert isinstance(ThemeType.METHOD.value, str)
        assert ThemeType.METHOD.value == "method"
        assert isinstance(ThemeType.METHOD, str)

    def test_review_type_in_string_set(self) -> None:
        from researchmind.synthesis.models import ReviewType
        s = {"general", "method", "dataset"}
        assert ReviewType.GENERAL in s
        assert ReviewType.METHOD in s

    def test_theme_type_comparison(self) -> None:
        from researchmind.synthesis.models import ThemeType
        assert ThemeType.MIXED == "mixed"


# ---------------------------------------------------------------------------
# 15. AggregatedEvidence import
# ---------------------------------------------------------------------------

class TestAggregatedEvidenceReuse:
    """Verify AggregatedEvidence is reused from M5."""

    def test_import_from_query_models(self) -> None:
        from researchmind.query.models import AggregatedEvidence  # noqa

    def test_evidence_bundle_uses_aggregated_evidence(self) -> None:
        from researchmind.query.models import AggregatedEvidence
        from researchmind.synthesis.models import EvidenceBundle
        ev = AggregatedEvidence(
            evidence_id="ev_001",
            source_text="Test evidence.",
            confidence=0.8,
            source_engine="consensus",
            source_document_id="doc_1",
            evidence_type="gap_item",
        )
        bundle = EvidenceBundle(
            bundle_id="bnd_test",
            theme="Test",
            evidence_items=[ev],
            evidence_count=1,
        )
        assert len(bundle.evidence_items) == 1
        assert bundle.evidence_items[0].evidence_id == "ev_001"


# ---------------------------------------------------------------------------
# 16. Determinism enforcement — no UUIDs, no timestamps
# ---------------------------------------------------------------------------

class TestDeterminismEnforcement:
    """Verify no UUID or timestamp usage in model definitions."""

    def test_no_uuid_in_models(self) -> None:
        import inspect
        import researchmind.synthesis.models as models
        source = inspect.getsource(models)
        assert "uuid" not in source, "UUID found in models.py"

    def test_no_datetime_in_models(self) -> None:
        import inspect
        import researchmind.synthesis.models as models
        source = inspect.getsource(models)
        assert "datetime" not in source, "datetime found in models.py"

    def test_no_random_in_models(self) -> None:
        import inspect
        import researchmind.synthesis.models as models
        source = inspect.getsource(models)
        assert "random" not in source, "random found in models.py"

    def test_no_generated_at_in_result(self) -> None:
        from researchmind.synthesis.models import ReviewResult
        assert not hasattr(ReviewResult.model_fields, "generated_at")
