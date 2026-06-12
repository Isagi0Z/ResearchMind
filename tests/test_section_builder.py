"""Comprehensive tests for SectionBuilder (Module 6, Phase 5).

Covers:
  - Construction & basics
  - All 8 review types (general, method, dataset, consensus,
    contradiction, research_gap, comparative, landscape)
  - Section requirements (mandatory vs optional)
  - Ordering via _SECTION_ORDER
  - Finding assignment per section type
  - Content generation templates
  - Confidence computation
  - Statistics (finding_count, evidence_count, document_count)
  - Deterministic IDs
  - Empty / missing findings
  - Unknown review type
  - Max findings cap
  - Serialization round-trip
  - Convenience helper
  - Validator compatibility (ReviewSection validators pass)
"""

from __future__ import annotations

import pytest

from researchmind.synthesis.models import (
    ReviewFinding,
    ReviewSection,
    ReviewType,
    _SECTION_ORDER,
    _SECTION_REQUIREMENTS,
    _generate_id,
)
from researchmind.synthesis.section_builder import SectionBuilder, build_sections


# ===========================================================================
# Helpers
# ===========================================================================


def _make_finding(
    finding_id: str = "f_001",
    finding_type: str = "supporting",
    statement: str = "Evidence suggests that BERT is effective.",
    confidence: float = 0.8,
    evidence_ids: list[str] | None = None,
    source_document_ids: list[str] | None = None,
    trace: list[str] | None = None,
) -> ReviewFinding:
    return ReviewFinding(
        finding_id=finding_id,
        finding_type=finding_type,
        statement=statement,
        confidence=confidence,
        evidence_ids=evidence_ids or [f"ev_{finding_id}"],
        source_document_ids=source_document_ids or ["doc_001"],
        trace=trace or (["trace_auto"] if finding_type in ("contradiction", "consensus") else []),
    )


def _findings_by_type(
    supporting: int = 0,
    consensus: int = 0,
    contradiction: int = 0,
    gap: int = 0,
    relation: int = 0,
) -> dict[str, list[ReviewFinding]]:
    fbt: dict[str, list[ReviewFinding]] = {}
    if supporting:
        fbt["supporting"] = [
            _make_finding(f"sup_{i}", "supporting", f"Supporting finding {i}.",
                          max(0.01, 0.8 - i * 0.05))
            for i in range(supporting)
        ]
    if consensus:
        fbt["consensus"] = [
            _make_finding(f"con_{i}", "consensus", f"Consensus finding {i}.",
                          max(0.01, 0.9 - i * 0.05), evidence_ids=[f"ev_con_{i}"],
                          trace=["t_con"])
            for i in range(consensus)
        ]
    if contradiction:
        fbt["contradiction"] = [
            _make_finding(f"ctr_{i}", "contradiction", f"Contradiction finding {i}.",
                          max(0.01, 0.7 - i * 0.05), evidence_ids=[f"ev_ctr_{i}"],
                          source_document_ids=[f"doc_{i}"], trace=["t_ctr"])
            for i in range(contradiction)
        ]
    if gap:
        fbt["gap"] = [
            _make_finding(f"gap_{i}", "gap", f"Gap finding {i}.",
                          max(0.01, 0.5 - i * 0.05), evidence_ids=[f"ev_gap_{i}"])
            for i in range(gap)
        ]
    if relation:
        fbt["relation"] = [
            _make_finding(f"rel_{i}", "relation", f"Relation finding {i}.",
                          max(0.01, 0.6 - i * 0.05), evidence_ids=[f"ev_rel_{i}"],
                          source_document_ids=[f"doc_rel_{i}"])
            for i in range(relation)
        ]
    return fbt


# ===========================================================================
# 1. Construction & basics
# ===========================================================================


class TestConstruction:
    """SectionBuilder construction and basic attributes."""

    def test_default_construction(self) -> None:
        sb = SectionBuilder()
        assert isinstance(sb, SectionBuilder)

    def test_build_sections_method_exists(self) -> None:
        assert hasattr(SectionBuilder, "build_sections")

    def test_build_sections_callable(self) -> None:
        assert callable(SectionBuilder().build_sections)

    def test_build_sections_returns_list(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        assert isinstance(result, list)

    def test_build_sections_returns_review_sections(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        assert all(isinstance(s, ReviewSection) for s in result)


# ===========================================================================
# 2. Empty / missing inputs
# ===========================================================================


class TestEmptyInputs:
    """Behavior with empty or missing inputs."""

    def test_empty_review_type(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="", findings_by_type={},
        )
        assert result == []

    def test_unknown_review_type(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="nonexistent", findings_by_type={},
        )
        assert result == []

    def test_none_findings_by_type(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type=None,
        )
        assert len(result) > 0

    def test_empty_findings_by_type(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        assert len(result) > 0

    def test_none_corpus_metadata(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={}, corpus_metadata=None,
        )
        assert len(result) > 0


# ===========================================================================
# 3. General review type
# ===========================================================================


class TestGeneralReview:
    """General review type section generation."""

    def test_has_expected_sections(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        req = _SECTION_REQUIREMENTS["general"]
        expected = req[0] + req[1]
        types = {s.section_type for s in result}
        for e in expected:
            assert e in types

    def test_abstract_first(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        assert result[0].section_type == "abstract"

    def test_conclusion_last(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        assert result[-1].section_type == "conclusion"

    def test_mandatory_sections_present(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        mandatory, _ = _SECTION_REQUIREMENTS["general"]
        for m in mandatory:
            assert any(s.section_type == m for s in result)

    def test_is_mandatory_flag(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        mandatory, _ = _SECTION_REQUIREMENTS["general"]
        for s in result:
            if s.section_type in mandatory:
                assert s.is_mandatory is True


# ===========================================================================
# 4. All 8 review types
# ===========================================================================


class TestAllReviewTypes:
    """All eight review types produce sections."""

    def test_method(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="method", findings_by_type={},
        )
        assert len(result) > 0

    def test_dataset(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="dataset", findings_by_type={},
        )
        assert len(result) > 0

    def test_consensus(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="consensus", findings_by_type={},
        )
        assert len(result) > 0

    def test_contradiction(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="contradiction", findings_by_type={},
        )
        assert len(result) > 0

    def test_research_gap(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="research_gap", findings_by_type={},
        )
        assert len(result) > 0

    def test_comparative(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="comparative", findings_by_type={},
        )
        assert len(result) > 0

    def test_landscape(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="landscape", findings_by_type={},
        )
        assert len(result) > 0

    def test_case_insensitive(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="GENERAL", findings_by_type={},
        )
        assert len(result) > 0

    def test_all_types_return_different_section_counts(self) -> None:
        counts = {}
        for rt in ("general", "method", "dataset", "consensus",
                    "contradiction", "research_gap", "comparative", "landscape"):
            result = SectionBuilder().build_sections(
                review_type=rt, findings_by_type={},
            )
            counts[rt] = len(result)
        assert len(set(counts.values())) >= 2


# ===========================================================================
# 5. Section ordering
# ===========================================================================


class TestSectionOrdering:
    """Sections must follow _SECTION_ORDER exactly."""

    def test_order_matches_section_order(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        ordered = [s.section_type for s in result]
        indices = [_SECTION_ORDER.index(st) for st in ordered]
        assert indices == sorted(indices)

    def test_full_order_span(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="landscape", findings_by_type={},
        )
        ordered = [s.section_type for s in result]
        indices = [_SECTION_ORDER.index(st) for st in ordered]
        assert indices == sorted(indices)


# ===========================================================================
# 6. Finding assignment
# ===========================================================================


class TestFindingAssignment:
    """Findings mapped to correct sections."""

    def test_consensus_findings_in_consensus_section(self) -> None:
        fbt = _findings_by_type(consensus=3)
        result = SectionBuilder().build_sections(
            review_type="consensus", findings_by_type=fbt,
        )
        cons_sec = next(s for s in result if s.section_type == "consensus")
        for f in cons_sec.findings:
            assert f.finding_type == "consensus"

    def test_contradiction_findings_in_contradictions_section(self) -> None:
        fbt = _findings_by_type(contradiction=2)
        result = SectionBuilder().build_sections(
            review_type="contradiction", findings_by_type=fbt,
        )
        ctr_sec = next(s for s in result if s.section_type == "contradictions")
        for f in ctr_sec.findings:
            assert f.finding_type == "contradiction"

    def test_gap_findings_in_research_gaps_section(self) -> None:
        fbt = _findings_by_type(gap=2)
        result = SectionBuilder().build_sections(
            review_type="research_gap", findings_by_type=fbt,
        )
        gap_sec = next(s for s in result if s.section_type == "research_gaps")
        for f in gap_sec.findings:
            assert f.finding_type == "gap"

    def test_supporting_in_methods_landscape(self) -> None:
        fbt = _findings_by_type(supporting=2)
        result = SectionBuilder().build_sections(
            review_type="method", findings_by_type=fbt,
        )
        ml_sec = next(s for s in result if s.section_type == "methods_landscape")
        for f in ml_sec.findings:
            assert f.finding_type == "supporting"

    def test_abstract_has_no_findings(self) -> None:
        fbt = _findings_by_type(supporting=3, consensus=2)
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type=fbt,
        )
        abs_sec = next(s for s in result if s.section_type == "abstract")
        assert len(abs_sec.findings) == 0

    def test_conclusion_has_no_findings(self) -> None:
        fbt = _findings_by_type(supporting=3)
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type=fbt,
        )
        conc_sec = next(s for s in result if s.section_type == "conclusion")
        assert len(conc_sec.findings) == 0

    def test_unknown_finding_type_ignored(self) -> None:
        unknown = _make_finding("u1", "unknown_type", "Unknown")
        result = SectionBuilder().build_sections(
            review_type="general",
            findings_by_type={"unknown_type": [unknown]},
        )
        total = sum(len(s.findings) for s in result)
        assert total == 0


# ===========================================================================
# 7. Content generation
# ===========================================================================


class TestContentGeneration:
    """Section content from templates."""

    def test_abstract_content(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
            corpus_metadata={"document_count": 5},
        )
        abs_sec = next(s for s in result if s.section_type == "abstract")
        assert "review examines" in abs_sec.content.lower()
        assert "general" in abs_sec.content.lower()

    def test_content_includes_finding_count(self) -> None:
        fbt = _findings_by_type(supporting=3)
        result = SectionBuilder().build_sections(
            review_type="method", findings_by_type=fbt,
        )
        ml_sec = next(s for s in result if s.section_type == "methods_landscape")
        assert "3" in ml_sec.content or "findings" in ml_sec.content

    def test_conclusion_content(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        conc_sec = next(s for s in result if s.section_type == "conclusion")
        assert "evidence reviewed" in conc_sec.content.lower()

    def test_paragraphs_from_findings(self) -> None:
        fbt = _findings_by_type(supporting=2)
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type=fbt,
        )
        findings_sec = None
        for s in result:
            if s.section_type == "methods_landscape":
                findings_sec = s
                break
        if findings_sec:
            assert len(findings_sec.paragraphs) == 2


# ===========================================================================
# 8. Confidence
# ===========================================================================


class TestConfidence:
    """Section confidence = min of finding confidences."""

    def test_confidence_min_of_findings(self) -> None:
        fbt = _findings_by_type(supporting=3)
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type=fbt,
        )
        for s in result:
            if s.findings:
                min_conf = min(f.confidence for f in s.findings)
                assert s.confidence == min_conf

    def test_confidence_zero_without_findings(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        for s in result:
            if not s.findings:
                assert s.confidence == 0.0

    def test_confidence_validator_satisfied(self) -> None:
        fbt = _findings_by_type(consensus=2, supporting=3)
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type=fbt,
        )
        for s in result:
            if s.findings:
                min_finding_conf = min(f.confidence for f in s.findings)
                assert s.confidence <= min_finding_conf


# ===========================================================================
# 9. Statistics
# ===========================================================================


class TestStatistics:
    """Section statistics fields."""

    def test_finding_count(self) -> None:
        fbt = _findings_by_type(supporting=4)
        result = SectionBuilder().build_sections(
            review_type="method", findings_by_type=fbt,
        )
        ml_sec = next(s for s in result if s.section_type == "methods_landscape")
        assert ml_sec.statistics.get("finding_count") == 4

    def test_evidence_count(self) -> None:
        fbt = _findings_by_type(supporting=3)
        result = SectionBuilder().build_sections(
            review_type="method", findings_by_type=fbt,
        )
        ml_sec = next(s for s in result if s.section_type == "methods_landscape")
        assert ml_sec.statistics.get("evidence_count") == 3

    def test_document_count(self) -> None:
        fbt = _findings_by_type(supporting=2)
        result = SectionBuilder().build_sections(
            review_type="method", findings_by_type=fbt,
        )
        ml_sec = next(s for s in result if s.section_type == "methods_landscape")
        assert ml_sec.statistics.get("document_count") == 1

    def test_statistics_keys_present(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        for s in result:
            assert "finding_count" in s.statistics
            assert "evidence_count" in s.statistics
            assert "document_count" in s.statistics


# ===========================================================================
# 10. Deterministic IDs
# ===========================================================================


class TestDeterministicIds:
    """Section IDs are deterministic via CRC32."""

    def test_id_format(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        for s in result:
            assert s.section_id.startswith("section_")

    def test_deterministic_across_calls(self) -> None:
        r1 = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        r2 = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        for s1, s2 in zip(r1, r2):
            assert s1.section_id == s2.section_id

    def test_no_uuids(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        for s in result:
            assert "uuid" not in s.section_id.lower()


# ===========================================================================
# 11. Max findings cap
# ===========================================================================


class TestMaxFindingsCap:
    """max_findings cap per section."""

    def test_cap_limits_findings(self) -> None:
        fbt = _findings_by_type(supporting=20)
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type=fbt, max_findings=5,
        )
        for s in result:
            if s.section_type == "methods_landscape":
                assert len(s.findings) <= 5

    def test_cap_higher_than_count(self) -> None:
        fbt = _findings_by_type(supporting=3)
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type=fbt, max_findings=100,
        )
        for s in result:
            if s.section_type == "methods_landscape":
                assert len(s.findings) == 3


# ===========================================================================
# 12. Serialization round-trip
# ===========================================================================


class TestSerialization:
    """ReviewSection serialization round-trip."""

    def test_round_trip_json(self) -> None:
        fbt = _findings_by_type(supporting=1)
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type=fbt,
        )
        section = result[0]
        d = section.model_dump()
        restored = ReviewSection.model_validate(d)
        assert restored.section_id == section.section_id
        assert restored.section_type == section.section_type
        assert restored.title == section.title

    def test_round_trip_all_fields(self) -> None:
        fbt = _findings_by_type(supporting=2)
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type=fbt,
        )
        section = result[0]
        d = section.model_dump()
        restored = ReviewSection.model_validate(d)
        assert len(restored.findings) == len(section.findings)
        assert restored.statistics == section.statistics
        assert restored.content == section.content
        assert restored.confidence == section.confidence


# ===========================================================================
# 13. Convenience helper
# ===========================================================================


class TestConvenienceHelper:
    """Module-level build_sections convenience function."""

    def test_convenience_returns_list(self) -> None:
        result = build_sections(review_type="general", findings_by_type={})
        assert isinstance(result, list)

    def test_convenience_returns_sections(self) -> None:
        result = build_sections(review_type="general", findings_by_type={})
        assert all(isinstance(s, ReviewSection) for s in result)

    def test_convenience_empty_type(self) -> None:
        result = build_sections(review_type="", findings_by_type={})
        assert result == []

    def test_convenience_consistent_with_builder(self) -> None:
        fbt = _findings_by_type(supporting=2)
        r1 = build_sections(review_type="general", findings_by_type=fbt)
        r2 = SectionBuilder().build_sections(
            review_type="general", findings_by_type=fbt,
        )
        assert r1 == r2

    def test_convenience_passes_max_findings(self) -> None:
        fbt = _findings_by_type(supporting=10)
        r1 = build_sections(review_type="general", findings_by_type=fbt, max_findings=3)
        r2 = build_sections(review_type="general", findings_by_type=fbt, max_findings=10)
        for s1, s2 in zip(r1, r2):
            if s1.section_type in ("methods_landscape", "findings"):
                assert len(s1.findings) <= len(s2.findings)


# ===========================================================================
# 14. Title mapping
# ===========================================================================


class TestSectionTitles:
    """Section titles from _SECTION_TITLES."""

    def test_abstract_title(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        abs_sec = next(s for s in result if s.section_type == "abstract")
        assert abs_sec.title == "Abstract"

    def test_conclusion_title(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        conc_sec = next(s for s in result if s.section_type == "conclusion")
        assert conc_sec.title == "Conclusion"

    def test_consensus_title(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="consensus", findings_by_type={},
        )
        cons_sec = next(s for s in result if s.section_type == "consensus")
        assert "Consensus" in cons_sec.title


# ===========================================================================
# 15. Word count
# ===========================================================================


class TestWordCount:
    """Word count computed from content + paragraphs."""

    def test_word_count_positive(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        for s in result:
            assert s.word_count >= 0

    def test_word_count_with_findings(self) -> None:
        fbt = _findings_by_type(supporting=3)
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type=fbt,
        )
        for s in result:
            if s.findings:
                assert s.word_count > 0

    def test_word_count_matches(self) -> None:
        fbt = _findings_by_type(supporting=1)
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type=fbt,
        )
        for s in result:
            if s.findings:
                content_words = len(s.content.split())
                para_words = sum(len(p.split()) for p in s.paragraphs)
                assert s.word_count == content_words + para_words


# ===========================================================================
# 16. Duplicate findings
# ===========================================================================


class TestDuplicateFindings:
    """Duplicate findings in input."""

    def test_duplicate_finding_in_multiple_types(self) -> None:
        f = _make_finding("dup", "supporting", "Dup")
        fbt = {
            "supporting": [f],
            "consensus": [_make_finding("c1", "consensus", "C1", trace=["t"])],
        }
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type=fbt,
        )
        total = sum(len(s.findings) for s in result)
        assert total >= 1


# ===========================================================================
# 17. Metadata on sections
# ===========================================================================


class TestSectionMetadata:
    """Section metadata fields."""

    def test_review_type_in_metadata(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="comparative", findings_by_type={},
        )
        for s in result:
            assert s.metadata.get("review_type") == "comparative"

    def test_section_index_in_metadata(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        for i, s in enumerate(result):
            expected_idx = _SECTION_ORDER.index(s.section_type)
            assert s.metadata.get("section_index") == expected_idx


# ===========================================================================
# 18. Large finding collections
# ===========================================================================


class TestLargeCollections:
    """Large finding sets must complete deterministically."""

    def test_1000_findings(self) -> None:
        fbt = _findings_by_type(supporting=1000)
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type=fbt, max_findings=1000,
        )
        ml_sec = next(s for s in result if s.section_type == "methods_landscape")
        assert len(ml_sec.findings) == 1000

    def test_deterministic_with_large_set(self) -> None:
        fbt = _findings_by_type(supporting=500, consensus=500)
        r1 = SectionBuilder().build_sections(
            review_type="general", findings_by_type=fbt, max_findings=1000,
        )
        r2 = SectionBuilder().build_sections(
            review_type="general", findings_by_type=fbt, max_findings=1000,
        )
        assert r1 == r2


# ===========================================================================
# 19. Validator compatibility
# ===========================================================================


class TestValidatorCompatibility:
    """ReviewSection validators must pass."""

    def test_section_id_non_empty(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        for s in result:
            assert s.section_id.strip()

    def test_title_non_empty(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        for s in result:
            assert s.title.strip()

    def test_confidence_in_bounds(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type=_findings_by_type(supporting=3),
        )
        for s in result:
            assert 0.0 <= s.confidence <= 1.0

    def test_deterministic_id_hex(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
        )
        for s in result:
            assert len(s.section_id) == len("section_") + 12


# ===========================================================================
# 20. corpus_metadata usage
# ===========================================================================


class TestCorpusMetadata:
    """Corpus metadata affects content."""

    def test_document_count_in_abstract(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
            corpus_metadata={"document_count": 10},
        )
        abs_sec = next(s for s in result if s.section_type == "abstract")
        assert "10" in abs_sec.content or "documents" in abs_sec.content

    def test_zero_document_count(self) -> None:
        result = SectionBuilder().build_sections(
            review_type="general", findings_by_type={},
            corpus_metadata={"document_count": 0},
        )
        abs_sec = next(s for s in result if s.section_type == "abstract")
        assert "0" in abs_sec.content or "documents" in abs_sec.content
