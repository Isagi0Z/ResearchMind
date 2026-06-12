"""Comprehensive tests for TraceabilityVerifier (Module 6, Phase 6).

Covers:
  - Construction & basics
  - Empty review
  - Empty sections
  - Empty findings
  - Gap exemptions
  - Missing evidence_ids
  - Missing source docs
  - Unknown document IDs
  - Missing traces (required types)
  - Trace validation (non-empty, string type)
  - Chunk validation
  - Duplicate evidence IDs
  - Statistics
  - Determinism
  - Large reviews
  - Malformed findings / corpus
  - Convenience helper
  - Serialization
  - Validator compatibility
"""

from __future__ import annotations

import pytest

from researchmind.synthesis.models import (
    ReviewFinding,
    ReviewResult,
    ReviewSection,
)
from researchmind.synthesis.traceability import TraceabilityVerifier, verify_review


# ===========================================================================
# Helpers
# ===========================================================================


def _make_finding(
    finding_id: str = "f_001",
    finding_type: str = "supporting",
    statement: str = "Evidence suggests X is effective.",
    confidence: float = 0.8,
    evidence_ids: list[str] | None = None,
    source_document_ids: list[str] | None = None,
    trace: list[str] | None = None,
) -> ReviewFinding:
    if evidence_ids is None:
        evidence_ids = [f"ev_{finding_id}"]
    if source_document_ids is None:
        source_document_ids = ["doc_001"]
    if trace is None:
        trace = (
            ["trace_step"] if finding_type in ("contradiction", "consensus", "relation") else []
        )
    return ReviewFinding(
        finding_id=finding_id,
        finding_type=finding_type,
        statement=statement,
        confidence=confidence,
        evidence_ids=evidence_ids,
        source_document_ids=source_document_ids,
        trace=trace,
    )


def _make_section(
    section_id: str = "sec_001",
    section_type: str = "findings",
    title: str = "Findings",
    findings: list[ReviewFinding] | None = None,
) -> ReviewSection:
    return ReviewSection(
        section_id=section_id,
        section_type=section_type,
        title=title,
        findings=findings or [],
    )


def _make_review(
    sections: list[ReviewSection] | None = None,
) -> ReviewResult:
    secs = sections or []
    total_f = sum(len(s.findings) for s in secs)
    total_w = sum(s.word_count for s in secs)
    return ReviewResult(
        review_id="rev_001",
        review_type="general",
        title="Test Review",
        abstract="Abstract text." if secs else "",
        sections=secs,
        total_findings=total_f,
        total_words=total_w,
    )


class _MockDoc:
    def __init__(self, doc_id: str):
        self.meta = type("Meta", (), {"ruo_id": doc_id})()


class _MockCorpus:
    def __init__(self, docs: list[_MockDoc] | None = None):
        self._docs = docs or []

    def get_documents(self) -> list[_MockDoc]:
        return self._docs


# ===========================================================================
# 1. Construction & basics
# ===========================================================================


class TestConstruction:
    """TraceabilityVerifier construction and basic attributes."""

    def test_default_construction(self) -> None:
        tv = TraceabilityVerifier()
        assert isinstance(tv, TraceabilityVerifier)

    def test_verify_review_method_exists(self) -> None:
        assert hasattr(TraceabilityVerifier, "verify_review")

    def test_verify_review_callable(self) -> None:
        assert callable(TraceabilityVerifier().verify_review)

    def test_verify_review_returns_tuple(self) -> None:
        review = _make_review()
        result = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_returns_bool_and_list(self) -> None:
        review = _make_review()
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert isinstance(valid, bool)
        assert isinstance(warnings, list)


# ===========================================================================
# 2. Empty review
# ===========================================================================


class TestEmptyReview:
    """Empty review is valid."""

    def test_empty_review_valid(self) -> None:
        review = _make_review()
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is True
        assert warnings == []

    def test_no_sections_valid(self) -> None:
        review = _make_review(sections=[])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is True

    def test_no_findings_valid(self) -> None:
        sec = _make_section(findings=[])
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is True

    def test_multiple_empty_sections_valid(self) -> None:
        secs = [_make_section(f"s{i}") for i in range(3)]
        review = _make_review(sections=secs)
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is True


# ===========================================================================
# 3. Gap exemptions
# ===========================================================================


class TestGapExemptions:
    """Gap findings are exempt from traceability checks."""

    def test_gap_without_evidence_is_valid(self) -> None:
        finding = _make_finding("g1", "gap", "Gap finding.",
                                evidence_ids=[], source_document_ids=[])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is True

    def test_gap_without_trace_is_valid(self) -> None:
        finding = _make_finding("g2", "gap", "Gap.", trace=[])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is True

    def test_gap_without_source_docs_is_valid(self) -> None:
        finding = _make_finding("g3", "gap", "Gap.", source_document_ids=[])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is True

    def test_mixed_gap_and_non_gap(self) -> None:
        gap = _make_finding("g1", "gap", "Gap.", evidence_ids=[], source_document_ids=[])
        good = _make_finding("f1", "supporting", "Finding.")
        sec = _make_section(findings=[gap, good])
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is True


# ===========================================================================
# 4. Missing evidence_ids
# ===========================================================================


class TestMissingEvidenceIds:
    """Non-gap findings must have evidence_ids."""

    def test_missing_evidence_ids_fails(self) -> None:
        finding = _make_finding("f1", "supporting", "Text.", evidence_ids=[])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is False

    def test_missing_evidence_id_warning(self) -> None:
        finding = _make_finding("f1", "supporting", "Text.", evidence_ids=[])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        _, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert any("missing evidence_ids" in w for w in warnings)

    def test_duplicate_evidence_ids_warning(self) -> None:
        finding = _make_finding("f1", "supporting", "Text.",
                                evidence_ids=["ev1", "ev1"])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        _, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert any("duplicate evidence_ids" in w for w in warnings)

    def test_duplicate_ids_does_not_fail_review(self) -> None:
        finding = _make_finding("f1", "supporting", "Text.",
                                evidence_ids=["ev1", "ev1"])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, _ = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is True


# ===========================================================================
# 5. Missing source documents
# ===========================================================================


class TestMissingSourceDocs:
    """Non-gap findings must have source_document_ids."""

    def test_missing_source_docs_fails(self) -> None:
        finding = _make_finding("f1", "supporting", "Text.", source_document_ids=[])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is False

    def test_missing_source_docs_warning(self) -> None:
        finding = _make_finding("f1", "supporting", "Text.", source_document_ids=[])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        _, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert any("missing source documents" in w for w in warnings)


# ===========================================================================
# 6. Unknown document IDs
# ===========================================================================


class TestUnknownDocumentIds:
    """References to unknown documents generate warnings."""

    def test_unknown_document_warning(self) -> None:
        finding = _make_finding("f1", "supporting", "Text.",
                                source_document_ids=["unknown_doc"])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        corpus = _MockCorpus([])
        _, warnings = TraceabilityVerifier().verify_review(review=review, corpus=corpus)
        assert any("unknown document" in w for w in warnings)

    def test_unknown_document_fails_review(self) -> None:
        finding = _make_finding("f1", "supporting", "Text.",
                                source_document_ids=["unknown_doc"])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        corpus = _MockCorpus([])
        valid, _ = TraceabilityVerifier().verify_review(review=review, corpus=corpus)
        assert valid is False

    def test_known_document_passes(self) -> None:
        finding = _make_finding("f1", "supporting", "Text.",
                                source_document_ids=["doc_001"])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        corpus = _MockCorpus([_MockDoc("doc_001")])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=corpus)
        assert valid is True

    def test_mixed_known_and_unknown_docs(self) -> None:
        finding = _make_finding("f1", "supporting", "Text.",
                                source_document_ids=["doc_001", "unknown_doc"])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        corpus = _MockCorpus([_MockDoc("doc_001")])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=corpus)
        assert valid is False
        assert any("unknown document" in w for w in warnings)


# ===========================================================================
# 7. Missing traces (required types)
# ===========================================================================


class TestMissingTraces:
    """Required finding types must have non-empty trace."""

    def test_contradiction_requires_trace(self) -> None:
        finding = ReviewFinding.model_construct(
            finding_id="f1", finding_type="contradiction",
            statement="Text.", confidence=0.5,
            evidence_ids=["ev1"], source_document_ids=["doc_001"],
            trace=[],
        )
        sec = ReviewSection.model_construct(
            section_id="sec_001", section_type="findings",
            title="Findings", findings=[finding],
        )
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is False
        assert any("requires non-empty trace" in w for w in warnings)

    def test_consensus_requires_trace(self) -> None:
        finding = _make_finding("f1", "consensus", "Text.", trace=[])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is False
        assert any("requires non-empty trace" in w for w in warnings)

    def test_relation_requires_trace(self) -> None:
        finding = _make_finding("f1", "relation", "Text.", trace=[])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is False
        assert any("requires non-empty trace" in w for w in warnings)

    def test_supporting_does_not_require_trace(self) -> None:
        finding = _make_finding("f1", "supporting", "Text.", trace=[])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is True


# ===========================================================================
# 8. Trace validation
# ===========================================================================


class TestTraceValidation:
    """Trace entries must be non-empty strings."""

    def test_empty_string_trace_fails(self) -> None:
        finding = _make_finding("f1", "contradiction", "Text.", trace=[""])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is False

    def test_whitespace_trace_fails(self) -> None:
        finding = _make_finding("f1", "contradiction", "Text.", trace=["   "])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is False

    def test_valid_trace_passes(self) -> None:
        finding = _make_finding("f1", "contradiction", "Text.", trace=["chunk_001"])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is True


# ===========================================================================
# 9. Chunk validation
# ===========================================================================


class TestChunkValidation:
    """Optional chunk_index validation."""

    def test_chunk_present_passes(self) -> None:
        finding = _make_finding("f1", "contradiction", "Text.", trace=["chunk_1"])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        chunk_index = {"chunk_1": "doc_001"}
        valid, warnings = TraceabilityVerifier().verify_review(
            review=review, corpus=None, chunk_index=chunk_index,
        )
        assert valid is True

    def test_chunk_missing_warning(self) -> None:
        finding = _make_finding("f1", "contradiction", "Text.", trace=["missing_chunk"])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        chunk_index = {"other_chunk": "doc_001"}
        _, warnings = TraceabilityVerifier().verify_review(
            review=review, corpus=None, chunk_index=chunk_index,
        )
        assert any("Missing chunk" in w for w in warnings)

    def test_chunk_missing_does_not_fail(self) -> None:
        finding = _make_finding("f1", "contradiction", "Text.", trace=["missing_chunk"])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        chunk_index = {}
        valid, warnings = TraceabilityVerifier().verify_review(
            review=review, corpus=None, chunk_index=chunk_index,
        )
        assert valid is True

    def test_chunk_none_no_validation(self) -> None:
        finding = _make_finding("f1", "contradiction", "Text.", trace=["chunk_x"])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(
            review=review, corpus=None, chunk_index=None,
        )
        assert valid is True


# ===========================================================================
# 10. Statistics
# ===========================================================================


class TestStatistics:
    """Traceability statistics stored in review metadata."""

    def test_statistics_populated(self) -> None:
        finding = _make_finding("f1", "supporting", "Text.")
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        TraceabilityVerifier().verify_review(review=review, corpus=None)
        trace_stats = review.metadata.get("traceability")
        assert trace_stats is not None

    def test_findings_checked_count(self) -> None:
        findings = [
            _make_finding("f1", "supporting", "A."),
            _make_finding("f2", "supporting", "B."),
        ]
        sec = _make_section(findings=findings)
        review = _make_review(sections=[sec])
        TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert review.metadata["traceability"]["findings_checked"] == 2

    def test_findings_failed_count(self) -> None:
        finding = _make_finding("f1", "supporting", "Text.", evidence_ids=[])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert review.metadata["traceability"]["findings_failed"] == 1

    def test_warnings_count(self) -> None:
        finding = _make_finding("f1", "supporting", "Text.", evidence_ids=[])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert review.metadata["traceability"]["warnings"] >= 1

    def test_gap_not_counted_in_checked(self) -> None:
        gap = _make_finding("g1", "gap", "Gap.")
        good = _make_finding("f1", "supporting", "A.")
        sec = _make_section(findings=[gap, good])
        review = _make_review(sections=[sec])
        TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert review.metadata["traceability"]["findings_checked"] == 1


# ===========================================================================
# 11. Determinism
# ===========================================================================


class TestDeterminism:
    """Repeated runs must produce identical output."""

    def test_repeated_calls_same_result(self) -> None:
        finding = _make_finding("f1", "contradiction", "Text.", trace=["t1"])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        r1 = TraceabilityVerifier().verify_review(review=review, corpus=None)
        r2 = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert r1 == r2

    def test_deterministic_across_instances(self) -> None:
        finding = _make_finding("f1", "contradiction", "Text.", trace=["t1"])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        r1 = TraceabilityVerifier().verify_review(review=review, corpus=None)
        r2 = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert r1 == r2

    def test_deterministic_with_warnings(self) -> None:
        finding = _make_finding("f1", "supporting", "Text.", evidence_ids=[])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        r1 = TraceabilityVerifier().verify_review(review=review, corpus=None)
        r2 = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert r1 == r2


# ===========================================================================
# 12. Large reviews
# ===========================================================================


class TestLargeReviews:
    """Large reviews must verify deterministically."""

    def test_100_findings_all_valid(self) -> None:
        findings = [_make_finding(f"f{i:04d}", "supporting", f"Text {i}.")
                    for i in range(100)]
        sec = _make_section(findings=findings)
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is True

    def test_100_findings_some_failing(self) -> None:
        findings = [
            ReviewFinding.model_construct(
                finding_id=f"f{i:04d}", finding_type="contradiction",
                statement=f"Text {i}.", confidence=0.5,
                evidence_ids=["ev1"], source_document_ids=["doc_001"],
                trace=[],
            )
            for i in range(100)
        ]
        sec = ReviewSection.model_construct(
            section_id="sec_001", section_type="findings",
            title="Findings", findings=findings,
        )
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is False
        assert len(warnings) == 100

    def test_large_deterministic(self) -> None:
        findings = [_make_finding(f"f{i:04d}", "supporting", f"Text {i}.")
                    for i in range(100)]
        sec = _make_section(findings=findings)
        review = _make_review(sections=[sec])
        r1 = TraceabilityVerifier().verify_review(review=review, corpus=None)
        r2 = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert r1 == r2


# ===========================================================================
# 13. Malformed findings
# ===========================================================================


class TestMalformedFindings:
    """Graceful handling of corrupted findings."""

    def test_finding_without_type(self) -> None:
        finding = _make_finding(finding_type="", evidence_ids=[])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, _ = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is False

    def test_finding_without_id_warns(self) -> None:
        sec = _make_section(findings=[
            ReviewFinding.model_construct(
                finding_id="",
                finding_type="supporting",
                statement="test",
                confidence=0.5,
                evidence_ids=[],
                source_document_ids=[],
            )
        ])
        review = _make_review(sections=[sec])
        _, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert any("missing" in w for w in warnings)


# ===========================================================================
# 14. Malformed corpus
# ===========================================================================


class TestMalformedCorpus:
    """Graceful handling of corrupted corpus inputs."""

    def test_none_corpus_without_refs_passes(self) -> None:
        finding = _make_finding("f1", "supporting", "Text.")
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is True

    def test_corpus_without_get_documents_treated_as_empty(self) -> None:
        class BareCorpus:
            pass
        finding = _make_finding("f1", "supporting", "Text.",
                                source_document_ids=["doc_001"])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(
            review=review, corpus=BareCorpus(),
        )
        assert valid is False
        assert any("unknown document" in w for w in warnings)

    def test_corpus_get_documents_raises_handled_gracefully(self) -> None:
        class BrokenCorpus:
            def get_documents(self) -> list:
                raise RuntimeError("broken")
        finding = _make_finding("f1", "supporting", "Text.", source_document_ids=[])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(
            review=review, corpus=BrokenCorpus(),
        )
        assert valid is False
        assert any("missing source documents" in w for w in warnings)

    def test_corpus_with_none_documents_handled(self) -> None:
        class CorpusWithNone:
            def get_documents(self) -> list:
                return [None]
        finding = _make_finding("f1", "supporting", "Text.",
                                source_document_ids=["d1"])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, warnings = TraceabilityVerifier().verify_review(
            review=review, corpus=CorpusWithNone(),
        )
        assert valid is False
        assert any("unknown document" in w for w in warnings)


# ===========================================================================
# 15. Convenience helper
# ===========================================================================


class TestConvenienceHelper:
    """Module-level verify_review convenience function."""

    def test_convenience_returns_tuple(self) -> None:
        review = _make_review()
        result = verify_review(review=review, corpus=None)
        assert isinstance(result, tuple)

    def test_convenience_empty_review(self) -> None:
        valid, warnings = verify_review(review=_make_review(), corpus=None)
        assert valid is True

    def test_convenience_detects_failure(self) -> None:
        finding = _make_finding("f1", "supporting", "Text.", evidence_ids=[])
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        valid, _ = verify_review(review=review, corpus=None)
        assert valid is False

    def test_convenience_consistent_with_verifier(self) -> None:
        finding = _make_finding("f1", "supporting", "Text.")
        sec = _make_section(findings=[finding])
        review = _make_review(sections=[sec])
        r1 = verify_review(review=review, corpus=None)
        r2 = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert r1 == r2


# ===========================================================================
# 16. Serialization compatibility
# ===========================================================================


class TestSerialization:
    """ReviewResult / ReviewFinding serialization compatibility."""

    def test_review_round_trip(self) -> None:
        f = _make_finding("f1", "supporting", "Text.")
        sec = _make_section(findings=[f])
        review = _make_review(sections=[sec])
        d = review.model_dump()
        restored = ReviewResult.model_validate(d)
        valid, _ = TraceabilityVerifier().verify_review(review=restored, corpus=None)
        assert valid is True

    def test_finding_round_trip(self) -> None:
        f = _make_finding("f1", "contradiction", "Text.", trace=["t1"])
        d = f.model_dump()
        restored = ReviewFinding.model_validate(d)
        assert restored.finding_id == "f1"


# ===========================================================================
# 17. Multiple sections
# ===========================================================================


class TestMultipleSections:
    """Findings across multiple sections."""

    def test_all_sections_valid(self) -> None:
        s1 = _make_section("s1", "intro", "Intro", findings=[
            _make_finding("f1", "supporting", "A."),
        ])
        s2 = _make_section("s2", "conclusion", "Conclusion", findings=[
            _make_finding("f2", "supporting", "B."),
        ])
        review = _make_review(sections=[s1, s2])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is True

    def test_one_section_fails(self) -> None:
        s1 = _make_section("s1", "intro", "Intro", findings=[
            _make_finding("f1", "supporting", "A."),
        ])
        s2 = _make_section("s2", "bad", "Bad", findings=[
            _make_finding("f2", "supporting", "B.", evidence_ids=[]),
        ])
        review = _make_review(sections=[s1, s2])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is False

    def test_mixed_gap_and_required_traces(self) -> None:
        s1 = _make_section("s1", "gaps", "Gaps", findings=[
            _make_finding("g1", "gap", "Gap.", evidence_ids=[]),
        ])
        s2 = _make_section("s2", "consensus", "Consensus", findings=[
            _make_finding("c1", "consensus", "C.", trace=["t1"]),
        ])
        review = _make_review(sections=[s1, s2])
        valid, warnings = TraceabilityVerifier().verify_review(review=review, corpus=None)
        assert valid is True
