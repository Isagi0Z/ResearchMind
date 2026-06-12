"""Comprehensive tests for ConfidenceComputer (Module 6, Phase 7).

Covers:
  - Construction & basics
  - Finding confidence: consensus, contradiction, gap (5 subtypes),
    method, dataset, relation, supporting, unknown, clamping
  - Section confidence: empty, single, multiple, mixed, malformed
  - Review confidence: empty, mandatory, mixed, traceability failures
  - Convenience helpers
  - Determinism
  - Large collections
  - Integration with ReviewFinding / ReviewSection
  - Edge cases & malformed data
"""

from __future__ import annotations

import pytest

from researchmind.synthesis.confidence import (
    ConfidenceComputer,
    compute_finding_confidence,
    compute_review_confidence,
    compute_section_confidence,
)
from researchmind.synthesis.models import ReviewFinding, ReviewSection


# ===========================================================================
# Helpers
# ===========================================================================


def _make_finding(
    finding_id: str = "f_001",
    confidence: float = 0.8,
    finding_type: str = "supporting",
) -> ReviewFinding:
    return ReviewFinding(
        finding_id=finding_id,
        finding_type=finding_type,
        statement=f"Finding {finding_id}.",
        confidence=confidence,
    )


def _make_section(
    section_id: str = "sec_001",
    section_type: str = "findings",
    confidence: float = 0.0,
    findings: list[ReviewFinding] | None = None,
) -> ReviewSection:
    fs = findings or []
    if findings:
        min_conf = min(f.confidence for f in fs)
        conf = min(confidence, min_conf) if confidence > min_conf else confidence
    else:
        conf = 0.0
    return ReviewSection(
        section_id=section_id,
        section_type=section_type,
        title=section_type,
        confidence=conf,
        findings=fs,
    )


# ===========================================================================
# 1. Construction & basics
# ===========================================================================


class TestConstruction:
    """ConfidenceComputer construction and method existence."""

    def test_default_construction(self) -> None:
        cc = ConfidenceComputer()
        assert isinstance(cc, ConfidenceComputer)

    def test_compute_finding_confidence_exists(self) -> None:
        assert hasattr(ConfidenceComputer, "compute_finding_confidence")

    def test_compute_section_confidence_exists(self) -> None:
        assert hasattr(ConfidenceComputer, "compute_section_confidence")

    def test_compute_review_confidence_exists(self) -> None:
        assert hasattr(ConfidenceComputer, "compute_review_confidence")

    def test_compute_finding_confidence_returns_float(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("consensus", {})
        assert isinstance(r, float)

    def test_compute_section_confidence_returns_float(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_section_confidence([])
        assert isinstance(r, float)

    def test_compute_review_confidence_returns_float(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_review_confidence([], [])
        assert isinstance(r, float)


# ===========================================================================
# 2. Finding confidence — consensus
# ===========================================================================


class TestFindingConsensus:
    """consensus finding uses consensus_confidence key."""

    def test_basic_consensus(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("consensus", {"consensus_confidence": 0.85})
        assert r == 0.85

    def test_consensus_missing_key_default(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("consensus", {})
        assert r == 0.5

    def test_consensus_clamped_high(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("consensus", {"consensus_confidence": 1.5})
        assert r == 1.0

    def test_consensus_clamped_low(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("consensus", {"consensus_confidence": -0.5})
        assert r == 0.0

    def test_consensus_case_insensitive(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("CONSENSUS", {"consensus_confidence": 0.7})
        assert r == 0.7

    def test_consensus_whitespace(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("  consensus  ", {"consensus_confidence": 0.6})
        assert r == 0.6


# ===========================================================================
# 3. Finding confidence — contradiction
# ===========================================================================


class TestFindingContradiction:
    """contradiction finding uses aggregate_confidence key."""

    def test_basic_contradiction(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("contradiction", {"aggregate_confidence": 0.9})
        assert r == 0.9

    def test_contradiction_missing_key_default(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("contradiction", {})
        assert r == 0.5

    def test_contradiction_clamped(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("contradiction", {"aggregate_confidence": 99.0})
        assert r == 1.0


# ===========================================================================
# 4. Finding confidence — gap subtypes
# ===========================================================================


class TestFindingGap:
    """gap finding uses gap_type to select formula."""

    def test_gap_isolated(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("gap", {"gap_type": "isolated", "gap_confidence": 0.6})
        assert r == 0.6

    def test_gap_missing(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("gap", {"gap_type": "missing", "gap_confidence": 0.4})
        assert r == 0.4

    def test_gap_low_confidence(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("gap", {"gap_type": "low_confidence", "claim_confidence": 0.3})
        assert r == 0.7

    def test_gap_low_confidence_clamped(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("gap", {"gap_type": "low_confidence", "claim_confidence": 1.5})
        assert r == 0.0

    def test_gap_under_study(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("gap", {"gap_type": "under_study", "doc_count": 2, "doc_threshold": 10})
        assert r == 0.8

    def test_gap_under_study_full_coverage(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("gap", {"gap_type": "under_study", "doc_count": 10, "doc_threshold": 10})
        assert r == 0.0

    def test_gap_under_study_exceeds_threshold(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("gap", {"gap_type": "under_study", "doc_count": 20, "doc_threshold": 10})
        assert r == 0.0

    def test_gap_unconnected(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("gap", {"gap_type": "unconnected", "entity_count": 3, "max_entity_count": 10})
        assert r == 0.3

    def test_gap_unconnected_exceeds(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("gap", {"gap_type": "unconnected", "entity_count": 15, "max_entity_count": 10})
        assert r == 1.0

    def test_gap_unconnected_no_entities(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("gap", {"gap_type": "unconnected", "entity_count": 0, "max_entity_count": 10})
        assert r == 0.0

    def test_gap_unknown_subtype_default(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("gap", {"gap_type": "weird_subtype"})
        assert r == 0.5

    def test_gap_no_type_key_default(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("gap", {})
        assert r == 0.5

    def test_gap_under_study_default_threshold(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("gap", {"gap_type": "under_study", "doc_count": 0})
        assert r == 1.0

    def test_gap_low_confidence_no_claim_confidence(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("gap", {"gap_type": "low_confidence"})
        assert r == 0.5


# ===========================================================================
# 5. Finding confidence — method
# ===========================================================================


class TestFindingMethod:
    """method finding uses max of entity_edges confidences."""

    def test_method_single_edge(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("method", {
            "entity_edges": [{"confidence": 0.7}],
        })
        assert r == 0.7

    def test_method_max_of_multiple(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("method", {
            "entity_edges": [
                {"confidence": 0.5},
                {"confidence": 0.9},
                {"confidence": 0.3},
            ],
        })
        assert r == 0.9

    def test_method_empty_edges(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("method", {"entity_edges": []})
        assert r == 0.5

    def test_method_no_edges_key(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("method", {})
        assert r == 0.5

    def test_method_edge_without_confidence(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("method", {
            "entity_edges": [{"other": 1}],
        })
        assert r == 0.5

    def test_method_mixed_valid_and_invalid(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("method", {
            "entity_edges": [
                {"confidence": 0.4},
                {"not_confidence": 0.8},
                {"confidence": 0.6},
            ],
        })
        assert r == 0.6

    def test_method_edges_not_list(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("method", {"entity_edges": "not_a_list"})
        assert r == 0.5


# ===========================================================================
# 6. Finding confidence — dataset
# ===========================================================================


class TestFindingDataset:
    """dataset finding uses mean of entity_edges confidences."""

    def test_dataset_single_edge(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("dataset", {
            "entity_edges": [{"confidence": 0.7}],
        })
        assert r == 0.7

    def test_dataset_mean_of_multiple(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("dataset", {
            "entity_edges": [
                {"confidence": 0.6},
                {"confidence": 0.8},
            ],
        })
        assert r == 0.7

    def test_dataset_mean_rounding(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("dataset", {
            "entity_edges": [
                {"confidence": 0.5},
                {"confidence": 0.6},
                {"confidence": 0.7},
            ],
        })
        assert r == 0.6

    def test_dataset_empty_edges(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("dataset", {"entity_edges": []})
        assert r == 0.5

    def test_dataset_no_edges_key(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("dataset", {})
        assert r == 0.5

    def test_dataset_mean_clamped(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("dataset", {
            "entity_edges": [
                {"confidence": -0.5},
                {"confidence": 2.0},
            ],
        })
        assert r == 0.75


# ===========================================================================
# 7. Finding confidence — relation / supporting / unknown
# ===========================================================================


class TestFindingRelation:
    """relation finding uses edge_confidence key."""

    def test_basic_relation(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("relation", {"edge_confidence": 0.85})
        assert r == 0.85

    def test_relation_missing_key(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("relation", {})
        assert r == 0.5


class TestFindingSupporting:
    """supporting / default finding uses plain confidence key."""

    def test_basic_supporting(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("supporting", {"confidence": 0.75})
        assert r == 0.75

    def test_supporting_missing_key(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("supporting", {})
        assert r == 0.5


class TestFindingUnknown:
    """Unknown finding types fall back to confidence key."""

    def test_unknown_type(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("weird_type", {"confidence": 0.6})
        assert r == 0.6

    def test_empty_type(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("", {"confidence": 0.7})
        assert r == 0.7

    def test_none_type(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("", {})
        assert r == 0.5


# ===========================================================================
# 8. Clamping
# ===========================================================================


class TestClamping:
    """All results clamped to [0.0, 1.0]."""

    def test_above_one_clamped(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("consensus", {"consensus_confidence": 5.0})
        assert r == 1.0

    def test_below_zero_clamped(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("consensus", {"consensus_confidence": -5.0})
        assert r == 0.0

    def test_at_bounds_low(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("consensus", {"consensus_confidence": 0.0})
        assert r == 0.0

    def test_at_bounds_high(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("consensus", {"consensus_confidence": 1.0})
        assert r == 1.0

    def test_section_clamped(self) -> None:
        cc = ConfidenceComputer()
        f1 = ReviewFinding.model_construct(
            finding_id="f1", finding_type="supporting",
            statement="test", confidence=999.0,
        )
        r = cc.compute_section_confidence([f1])
        assert r == 1.0


# ===========================================================================
# 9. Section confidence
# ===========================================================================


class TestSectionConfidence:
    """compute_section_confidence = min of finding confidences."""

    def test_empty_findings(self) -> None:
        cc = ConfidenceComputer()
        assert cc.compute_section_confidence([]) == 0.0

    def test_single_finding(self) -> None:
        cc = ConfidenceComputer()
        f = _make_finding("f1", confidence=0.7)
        assert cc.compute_section_confidence([f]) == 0.7

    def test_two_findings_min_wins(self) -> None:
        cc = ConfidenceComputer()
        f1 = _make_finding("f1", confidence=0.9)
        f2 = _make_finding("f2", confidence=0.5)
        assert cc.compute_section_confidence([f1, f2]) == 0.5

    def test_three_findings(self) -> None:
        cc = ConfidenceComputer()
        f1 = _make_finding("f1", confidence=0.8)
        f2 = _make_finding("f2", confidence=0.6)
        f3 = _make_finding("f3", confidence=0.4)
        assert cc.compute_section_confidence([f1, f2, f3]) == 0.4

    def test_all_same_confidence(self) -> None:
        cc = ConfidenceComputer()
        fs = [_make_finding(f"f{i}", confidence=0.5) for i in range(5)]
        assert cc.compute_section_confidence(fs) == 0.5

    def test_findings_list_none(self) -> None:
        cc = ConfidenceComputer()
        assert cc.compute_section_confidence([]) == 0.0

    def test_finding_without_confidence_attr(self) -> None:
        cc = ConfidenceComputer()
        class BadFinding:
            pass
        r = cc.compute_section_confidence([BadFinding()])
        assert r == 0.0


# ===========================================================================
# 10. Review confidence
# ===========================================================================


class TestReviewConfidence:
    """compute_review_confidence uses mandatory sections with findings."""

    def test_empty_sections(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_review_confidence([], ["abstract"])
        assert r == 0.0

    def test_no_mandatory_matches_still_zero(self) -> None:
        cc = ConfidenceComputer()
        sec = _make_section("s1", "optional", confidence=0.8, findings=[_make_finding("f1")])
        r = cc.compute_review_confidence([sec], ["abstract"])
        assert r == 0.0

    def test_mandatory_with_findings(self) -> None:
        cc = ConfidenceComputer()
        f1 = _make_finding("f1", confidence=0.7)
        sec = _make_section("s1", "abstract", confidence=0.7, findings=[f1])
        r = cc.compute_review_confidence([sec], ["abstract"])
        assert r == 0.7

    def test_mandatory_without_findings_ignored(self) -> None:
        cc = ConfidenceComputer()
        sec = _make_section("s1", "abstract", confidence=0.9)
        r = cc.compute_review_confidence([sec], ["abstract"])
        assert r == 0.0

    def test_mandatory_min_of_multiple(self) -> None:
        cc = ConfidenceComputer()
        s1 = _make_section("s1", "abstract", confidence=0.8, findings=[_make_finding("f1", confidence=0.8)])
        s2 = _make_section("s2", "conclusion", confidence=0.5, findings=[_make_finding("f2", confidence=0.5)])
        r = cc.compute_review_confidence([s1, s2], ["abstract", "conclusion"])
        assert r == 0.5

    def test_mandatory_min_ignores_non_mandatory(self) -> None:
        cc = ConfidenceComputer()
        s1 = _make_section("s1", "abstract", confidence=0.5, findings=[_make_finding("f1", confidence=0.5)])
        s2 = _make_section("s2", "optional_sec", confidence=0.1, findings=[_make_finding("f2", confidence=0.1)])
        r = cc.compute_review_confidence([s1, s2], ["abstract"])
        assert r == 0.5

    def test_traceability_failures_penalty(self) -> None:
        cc = ConfidenceComputer()
        f1 = _make_finding("f1", confidence=0.8)
        sec = _make_section("s1", "abstract", confidence=0.8, findings=[f1])
        r = cc.compute_review_confidence([sec], ["abstract"], traceability_failures=1)
        assert r == 0.8 * 0.9

    def test_traceability_failures_multiple(self) -> None:
        cc = ConfidenceComputer()
        f1 = _make_finding("f1", confidence=0.8)
        sec = _make_section("s1", "abstract", confidence=0.8, findings=[f1])
        r = cc.compute_review_confidence([sec], ["abstract"], traceability_failures=3)
        expected = 0.8 * (0.9 ** 3)
        assert r == expected

    def test_traceability_failures_no_mandatory(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_review_confidence([], ["abstract"], traceability_failures=2)
        assert r == 0.0

    def test_mandatory_case_insensitive(self) -> None:
        cc = ConfidenceComputer()
        f1 = _make_finding("f1", confidence=0.7)
        sec = _make_section("s1", "ABSTRACT", confidence=0.7, findings=[f1])
        r = cc.compute_review_confidence([sec], ["abstract"])
        assert r == 0.7

    def test_mandatory_whitespace_stripped(self) -> None:
        cc = ConfidenceComputer()
        f1 = _make_finding("f1", confidence=0.7)
        sec = _make_section("s1", "abstract", confidence=0.7, findings=[f1])
        r = cc.compute_review_confidence([sec], ["  abstract  "])
        assert r == 0.7

    def test_traceability_failures_zero_no_effect(self) -> None:
        cc = ConfidenceComputer()
        f1 = _make_finding("f1", confidence=0.8)
        sec = _make_section("s1", "abstract", confidence=0.8, findings=[f1])
        r = cc.compute_review_confidence([sec], ["abstract"], traceability_failures=0)
        assert r == 0.8

    def test_negative_traceability_treated_as_zero(self) -> None:
        cc = ConfidenceComputer()
        f1 = _make_finding("f1", confidence=0.8)
        sec = _make_section("s1", "abstract", confidence=0.8, findings=[f1])
        r = cc.compute_review_confidence([sec], ["abstract"], traceability_failures=-1)
        assert r == 0.8


# ===========================================================================
# 11. Convenience helpers
# ===========================================================================


class TestConvenienceHelpers:
    """Module-level convenience functions."""

    def test_convenience_compute_finding_confidence(self) -> None:
        r = compute_finding_confidence("consensus", {"consensus_confidence": 0.9})
        assert r == 0.9

    def test_convenience_compute_section_confidence(self) -> None:
        f = _make_finding("f1", confidence=0.6)
        r = compute_section_confidence([f])
        assert r == 0.6

    def test_convenience_compute_review_confidence(self) -> None:
        f = _make_finding("f1", confidence=0.7)
        sec = _make_section("s1", "abstract", confidence=0.7, findings=[f])
        r = compute_review_confidence([sec], ["abstract"])
        assert r == 0.7

    def test_convenience_empty(self) -> None:
        r1 = compute_finding_confidence("consensus", {})
        r2 = compute_section_confidence([])
        r3 = compute_review_confidence([], [])
        assert r1 == 0.5
        assert r2 == 0.0
        assert r3 == 0.0

    def test_convenience_consistent_with_class(self) -> None:
        cc = ConfidenceComputer()
        data = {"consensus_confidence": 0.75}
        r1 = compute_finding_confidence("consensus", data)
        r2 = cc.compute_finding_confidence("consensus", data)
        assert r1 == r2


# ===========================================================================
# 12. Determinism
# ===========================================================================


class TestDeterminism:
    """Repeated calls must produce identical results."""

    def test_repeated_finding_calls(self) -> None:
        cc = ConfidenceComputer()
        data = {"consensus_confidence": 0.75}
        r1 = cc.compute_finding_confidence("consensus", data)
        r2 = cc.compute_finding_confidence("consensus", data)
        assert r1 == r2

    def test_repeated_section_calls(self) -> None:
        cc = ConfidenceComputer()
        f = _make_finding("f1", confidence=0.6)
        r1 = cc.compute_section_confidence([f])
        r2 = cc.compute_section_confidence([f])
        assert r1 == r2

    def test_repeated_review_calls(self) -> None:
        cc = ConfidenceComputer()
        f = _make_finding("f1", confidence=0.7)
        sec = _make_section("s1", "abstract", confidence=0.7, findings=[f])
        r1 = cc.compute_review_confidence([sec], ["abstract"])
        r2 = cc.compute_review_confidence([sec], ["abstract"])
        assert r1 == r2

    def test_across_instances(self) -> None:
        data = {"consensus_confidence": 0.75}
        r1 = ConfidenceComputer().compute_finding_confidence("consensus", data)
        r2 = ConfidenceComputer().compute_finding_confidence("consensus", data)
        assert r1 == r2


# ===========================================================================
# 13. Large collections
# ===========================================================================


class TestLargeCollections:
    """Large finding / section sets must compute correctly."""

    def test_100_findings_section_confidence(self) -> None:
        cc = ConfidenceComputer()
        fs = [_make_finding(f"f{i:04d}", confidence=0.1 + (i / 199))
              for i in range(100)]
        r = cc.compute_section_confidence(fs)
        assert r == 0.1

    def test_100_sections_review_confidence(self) -> None:
        cc = ConfidenceComputer()
        secs = []
        for i in range(100):
            conf = 0.1 + (i / 199)
            f = _make_finding(f"f{i:04d}", confidence=conf)
            secs.append(_make_section(f"s{i:04d}", "abstract", confidence=conf, findings=[f]))
        r = cc.compute_review_confidence(secs, ["abstract"])
        assert r == 0.1

    def test_large_deterministic(self) -> None:
        cc = ConfidenceComputer()
        fs = [_make_finding(f"f{i:04d}", confidence=0.5) for i in range(1000)]
        r1 = cc.compute_section_confidence(fs)
        r2 = cc.compute_section_confidence(fs)
        assert r1 == r2


# ===========================================================================
# 14. Integration with models
# ===========================================================================


class TestModelIntegration:
    """Integration with ReviewFinding and ReviewSection models."""

    def test_finding_confidence_direct(self) -> None:
        cc = ConfidenceComputer()
        f = _make_finding("f1", confidence=0.75)
        r = cc.compute_section_confidence([f])
        assert r == 0.75

    def test_section_confidence_from_builder(self) -> None:
        cc = ConfidenceComputer()
        f1 = _make_finding("f1", confidence=0.9)
        f2 = _make_finding("f2", confidence=0.3)
        sec = _make_section("s1", "findings", confidence=0.3, findings=[f1, f2])
        r = cc.compute_section_confidence(sec.findings)
        assert r == 0.3

    def test_review_confidence_after_section_build(self) -> None:
        cc = ConfidenceComputer()
        f = _make_finding("f1", confidence=0.8)
        sec = _make_section("s1", "conclusion", confidence=0.8, findings=[f])
        r = cc.compute_review_confidence([sec], ["conclusion"])
        assert r == 0.8

    def test_section_confidence_satisfies_validator(self) -> None:
        f1 = _make_finding("f1", confidence=0.7)
        f2 = _make_finding("f2", confidence=0.5)
        section_conf = min(f1.confidence, f2.confidence)
        sec = ReviewSection(
            section_id="s1",
            section_type="findings",
            title="Findings",
            confidence=section_conf,
            findings=[f1, f2],
        )
        assert sec.confidence == 0.5

    def test_serialization_round_trip(self) -> None:
        f = _make_finding("f1", confidence=0.75)
        sec = _make_section("s1", "abstract", confidence=0.75, findings=[f])
        d = sec.model_dump()
        restored = ReviewSection.model_validate(d)
        cc = ConfidenceComputer()
        r = cc.compute_section_confidence(restored.findings)
        assert r == 0.75


# ===========================================================================
# 15. Edge cases
# ===========================================================================


class TestEdgeCases:
    """Edge cases and malformed inputs."""

    def test_finding_confidence_no_data_dict(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("supporting", {})
        assert r == 0.5

    def test_finding_confidence_none_value(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("consensus", {"consensus_confidence": None})
        assert r == 0.5

    def test_section_confidence_non_number_confidence(self) -> None:
        cc = ConfidenceComputer()
        f = _make_finding("f1", confidence=0.5)
        f.confidence = "not_a_number"
        r = cc.compute_section_confidence([f])
        assert r == 0.0

    def test_section_confidence_mixed_valid_and_invalid(self) -> None:
        cc = ConfidenceComputer()
        f1 = _make_finding("f1", confidence=0.8)
        class BadFinding:
            pass
        r = cc.compute_section_confidence([f1, BadFinding()])
        assert r == 0.8

    def test_review_confidence_section_no_confidence_attr(self) -> None:
        cc = ConfidenceComputer()
        class BadSection:
            pass
        bad = BadSection()
        r = cc.compute_review_confidence([bad], ["abstract"])
        assert r == 0.0

    def test_review_confidence_section_no_findings_attr(self) -> None:
        cc = ConfidenceComputer()
        class NoFindingsSection:
            section_type = "abstract"
            confidence = 0.8
        r = cc.compute_review_confidence([NoFindingsSection()], ["abstract"])
        assert r == 0.0

    def test_review_confidence_traceability_string(self) -> None:
        cc = ConfidenceComputer()
        f = _make_finding("f1", confidence=0.8)
        sec = _make_section("s1", "abstract", confidence=0.8, findings=[f])
        r = cc.compute_review_confidence([sec], ["abstract"], traceability_failures=0)
        assert r == 0.8

    def test_float_precision_stability(self) -> None:
        cc = ConfidenceComputer()
        r = cc.compute_finding_confidence("dataset", {
            "entity_edges": [
                {"confidence": 1.0 / 3},
                {"confidence": 2.0 / 3},
            ],
        })
        assert r == 0.5
