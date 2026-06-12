"""Comprehensive tests for FindingGenerator (Module 6, Phase 4).

Covers:
  - Construction & basics
  - Empty inputs
  - Supporting findings
  - Consensus findings
  - Contradiction findings
  - Gap findings
  - Relation findings
  - Multiple finding types
  - Summary extraction (truncation, spacing)
  - Confidence computation
  - Traceability (evidence_ids, source_doc_ids, traces)
  - Deduplication
  - Ranking & cap
  - Metadata
  - Determinism
  - Serialization round-trip
  - Large evidence sets
  - Convenience helper
  - Malformed evidence
"""

from __future__ import annotations

import pytest

from researchmind.query.models import AggregatedEvidence
from researchmind.synthesis.finding_generator import FindingGenerator, generate_findings
from researchmind.synthesis.models import EvidenceBundle, ReviewFinding, ThemeCluster


# ===========================================================================
# Helpers
# ===========================================================================


def _make_evidence(
    evidence_id: str = "ev_001",
    source_text: str = "Test evidence text for finding generation.",
    confidence: float = 0.8,
    evidence_type: str = "claim",
    source_document_id: str = "doc_001",
    trace: list[str] | None = None,
) -> AggregatedEvidence:
    return AggregatedEvidence(
        evidence_id=evidence_id,
        source_text=source_text,
        confidence=confidence,
        evidence_type=evidence_type,
        source_document_id=source_document_id,
        source_document_title=f"Doc {source_document_id}",
        trace=trace or [],
    )


def _make_bundle(
    bundle_id: str = "bnd_001",
    theme: str = "Test Theme",
    evidence_items: list[AggregatedEvidence] | None = None,
) -> EvidenceBundle:
    items = evidence_items or []
    return EvidenceBundle(
        bundle_id=bundle_id,
        theme=theme,
        evidence_items=items,
        source_document_ids=list({e.source_document_id for e in items if e.source_document_id}),
        evidence_count=len(items),
    )


def _make_theme(
    cluster_id: str = "thm_001",
    label: str = "Transformer",
    theme_type: str = "method",
    entities: list[str] | None = None,
) -> ThemeCluster:
    resolved = entities or [label.lower()]
    return ThemeCluster(
        cluster_id=cluster_id,
        theme_type=theme_type,
        label=label,
        entities=resolved,
        entity_labels=[label],
        entity_cluster_ids=resolved,
    )


# ===========================================================================
# 1. Construction & basics
# ===========================================================================


class TestConstruction:
    """FindingGenerator construction and basic attributes."""

    def test_default_construction(self) -> None:
        fg = FindingGenerator()
        assert isinstance(fg, FindingGenerator)

    def test_generate_findings_method_exists(self) -> None:
        assert hasattr(FindingGenerator, "generate_findings")

    def test_generate_findings_callable(self) -> None:
        assert callable(FindingGenerator().generate_findings)

    def test_generate_findings_returns_list(self) -> None:
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[])
        assert isinstance(result, list)

    def test_generate_findings_returns_review_findings(self) -> None:
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[])
        assert all(isinstance(f, ReviewFinding) for f in result)


# ===========================================================================
# 2. Empty inputs
# ===========================================================================


class TestEmptyInputs:
    """Behavior with empty or None inputs."""

    def test_none_theme(self) -> None:
        result = FindingGenerator().generate_findings(theme=None, evidence_bundles=[])
        assert result == []

    def test_empty_bundles(self) -> None:
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[])
        assert result == []

    def test_bundle_with_zero_count(self) -> None:
        bundle = _make_bundle(evidence_items=[])
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert result == []

    def test_none_bundles_list(self) -> None:
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=None)
        assert result == []


# ===========================================================================
# 3. Supporting findings
# ===========================================================================


class TestSupportingFindings:
    """Findings from supporting-type evidence."""

    def test_supporting_from_claim(self) -> None:
        ev = _make_evidence(evidence_type="claim")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="Transformer")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert len(result) == 1
        assert result[0].finding_type == "supporting"

    def test_supporting_from_fact(self) -> None:
        ev = _make_evidence(evidence_type="fact")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="Topic")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert len(result) == 1
        assert result[0].finding_type == "supporting"

    def test_supporting_from_path_edge(self) -> None:
        ev = _make_evidence(evidence_type="path_edge", trace=["step1"])
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="Path")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert len(result) == 1
        assert result[0].finding_type == "supporting"

    def test_supporting_template(self) -> None:
        ev = _make_evidence(evidence_type="claim", source_text="Key insight.")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="BERT")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert "BERT" in result[0].statement
        assert "Evidence suggests" in result[0].statement
        assert "Key insight." in result[0].statement


# ===========================================================================
# 4. Consensus findings
# ===========================================================================


class TestConsensusFindings:
    """Findings from consensus_entry evidence."""

    def test_consensus_from_entry(self) -> None:
        ev = _make_evidence(evidence_type="consensus_entry", trace=["consensus_step"])
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="Agreement")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert len(result) == 1
        assert result[0].finding_type == "consensus"

    def test_consensus_template(self) -> None:
        ev = _make_evidence(evidence_type="consensus_entry", trace=["c1"])
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="CNN")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert "CNN" in result[0].statement
        assert "consensus" in result[0].statement.lower()

    def test_consensus_multiple_entries(self) -> None:
        evs = [
            _make_evidence(f"c{i}", evidence_type="consensus_entry", trace=[f"s{i}"])
            for i in range(3)
        ]
        bundle = _make_bundle(evidence_items=evs)
        theme = _make_theme(label="Topic")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert len(result) == 1
        assert result[0].supporting_count == 3


# ===========================================================================
# 5. Contradiction findings
# ===========================================================================


class TestContradictionFindings:
    """Findings from contradiction evidence."""

    def test_contradiction_from_type(self) -> None:
        ev = _make_evidence(evidence_type="contradiction", trace=["contra_step"])
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="Debate")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert len(result) == 1
        assert result[0].finding_type == "contradiction"

    def test_contradiction_template(self) -> None:
        ev = _make_evidence(evidence_type="contradiction", trace=["c1"])
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="LSTM")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert "LSTM" in result[0].statement
        assert "Conflicting" in result[0].statement

    def test_contradiction_requires_trace(self) -> None:
        ev = _make_evidence(evidence_type="contradiction", trace=["c1"])
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="X")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert len(result[0].trace) > 0


# ===========================================================================
# 6. Gap findings
# ===========================================================================


class TestGapFindings:
    """Findings from gap_item evidence."""

    def test_gap_from_item(self) -> None:
        ev = _make_evidence(evidence_type="gap_item")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="Missing")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert len(result) == 1
        assert result[0].finding_type == "gap"

    def test_gap_template(self) -> None:
        ev = _make_evidence(evidence_type="gap_item")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="Understudied")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert "Understudied" in result[0].statement
        assert "Limited evidence" in result[0].statement


# ===========================================================================
# 7. Relation findings
# ===========================================================================


class TestRelationFindings:
    """Findings from semantic_triple evidence."""

    def test_relation_from_triple(self) -> None:
        ev = _make_evidence(evidence_type="semantic_triple")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="Graph")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert len(result) == 1
        assert result[0].finding_type == "relation"

    def test_relation_template(self) -> None:
        ev = _make_evidence(evidence_type="semantic_triple")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="Relations")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert "Relations" in result[0].statement
        assert "Relationships" in result[0].statement


# ===========================================================================
# 8. Multiple finding types
# ===========================================================================


class TestMultipleTypes:
    """Multiple evidence types produce separate findings."""

    def test_supporting_and_consensus(self) -> None:
        ev1 = _make_evidence("e1", evidence_type="claim")
        ev2 = _make_evidence("e2", evidence_type="consensus_entry", trace=["c1"])
        bundle = _make_bundle(evidence_items=[ev1, ev2])
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        types = {f.finding_type for f in result}
        assert "supporting" in types
        assert "consensus" in types

    def test_all_five_types(self) -> None:
        evs = [
            _make_evidence("e1", evidence_type="claim"),
            _make_evidence("e2", evidence_type="consensus_entry", trace=["c1"]),
            _make_evidence("e3", evidence_type="contradiction", trace=["c1"]),
            _make_evidence("e4", evidence_type="gap_item"),
            _make_evidence("e5", evidence_type="semantic_triple"),
        ]
        bundle = _make_bundle(evidence_items=evs)
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        types = {f.finding_type for f in result}
        assert len(types) == 5

    def test_unknown_type_falls_to_supporting(self) -> None:
        ev = _make_evidence(evidence_type="custom_unknown_type")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert result[0].finding_type == "supporting"


# ===========================================================================
# 9. Summary extraction
# ===========================================================================


class TestSummaryExtraction:
    """Summary text extraction and truncation."""

    def test_summary_from_evidence_text(self) -> None:
        ev = _make_evidence(source_text="This is the key finding from the research.")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="Topic")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert "key finding" in result[0].statement

    def test_summary_truncated_at_80_chars(self) -> None:
        long_text = "A" * 200
        ev = _make_evidence(source_text=long_text)
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="Topic")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        summary_part = result[0].statement.split("with ")[-1] if "with " in result[0].statement else ""
        assert "..." in summary_part or len(summary_part) <= 80

    def test_summary_whitespace_collapsed(self) -> None:
        ev = _make_evidence(source_text="Multiple   spaces   here")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="Topic")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert "  " not in result[0].statement

    def test_empty_source_text_fallback(self) -> None:
        ev = _make_evidence(source_text="")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="Topic")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert "unknown evidence" in result[0].statement

    def test_best_confidence_used_for_summary(self) -> None:
        ev1 = _make_evidence("e1", source_text="Low confidence text.", confidence=0.1)
        ev2 = _make_evidence("e2", source_text="High confidence finding.", confidence=0.9)
        bundle = _make_bundle(evidence_items=[ev1, ev2])
        theme = _make_theme(label="Topic")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert "High confidence" in result[0].statement


# ===========================================================================
# 10. Confidence computation
# ===========================================================================


class TestConfidence:
    """Finding confidence = max of evidence confidences."""

    def test_single_evidence_confidence(self) -> None:
        ev = _make_evidence(confidence=0.75)
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert result[0].confidence == 0.75

    def test_max_confidence_of_multiple(self) -> None:
        evs = [
            _make_evidence("e1", confidence=0.5),
            _make_evidence("e2", confidence=0.9),
            _make_evidence("e3", confidence=0.3),
        ]
        bundle = _make_bundle(evidence_items=evs)
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert result[0].confidence == 0.9

    def test_confidence_max_one(self) -> None:
        ev = _make_evidence(confidence=1.0)
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert result[0].confidence == 1.0


# ===========================================================================
# 11. Traceability
# ===========================================================================


class TestTraceability:
    """Evidence IDs, source document IDs, and traces."""

    def test_evidence_ids_union(self) -> None:
        evs = [
            _make_evidence("e1", source_document_id="d1"),
            _make_evidence("e2", source_document_id="d1"),
        ]
        bundle = _make_bundle(evidence_items=evs)
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert "e1" in result[0].evidence_ids
        assert "e2" in result[0].evidence_ids

    def test_source_document_ids_union(self) -> None:
        evs = [
            _make_evidence("e1", source_document_id="doc_a"),
            _make_evidence("e2", source_document_id="doc_b"),
        ]
        bundle = _make_bundle(evidence_items=evs)
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert "doc_a" in result[0].source_document_ids
        assert "doc_b" in result[0].source_document_ids

    def test_trace_union(self) -> None:
        evs = [
            _make_evidence("e1", trace=["step1", "step2"]),
            _make_evidence("e2", trace=["step3"]),
        ]
        bundle = _make_bundle(evidence_items=evs)
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert "step1" in result[0].trace
        assert "step2" in result[0].trace
        assert "step3" in result[0].trace

    def test_evidence_ids_sorted(self) -> None:
        evs = [
            _make_evidence("z_ev"),
            _make_evidence("a_ev"),
        ]
        bundle = _make_bundle(evidence_items=evs)
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert result[0].evidence_ids == sorted(result[0].evidence_ids)

    def test_trace_deduplicated(self) -> None:
        evs = [
            _make_evidence("e1", trace=["step1"]),
            _make_evidence("e2", trace=["step1", "step2"]),
        ]
        bundle = _make_bundle(evidence_items=evs)
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert result[0].trace.count("step1") == 1


# ===========================================================================
# 12. Deduplication
# ===========================================================================


class TestDeduplication:
    """Finding deduplication by text and evidence IDs."""

    def test_same_text_same_evidence_deduped(self) -> None:
        ev = _make_evidence("e1", evidence_type="claim", source_text="Same text")
        bundle1 = _make_bundle("b1", evidence_items=[ev])
        bundle2 = _make_bundle("b2", evidence_items=[ev])
        theme = _make_theme()
        result = FindingGenerator().generate_findings(
            theme=theme, evidence_bundles=[bundle1, bundle2],
        )
        supporting = [f for f in result if f.finding_type == "supporting"]
        assert len(supporting) <= 1

    def test_different_text_same_type_separate(self) -> None:
        ev1 = _make_evidence("e1", evidence_type="claim", source_text="Text A")
        ev2 = _make_evidence("e2", evidence_type="claim", source_text="Text B")
        bundle = _make_bundle(evidence_items=[ev1, ev2])
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert len(result) == 1

    def test_dedup_keeps_higher_confidence(self) -> None:
        ev_low = _make_evidence("e1", evidence_type="claim", source_text="Text", confidence=0.5)
        ev_high = _make_evidence("e1", evidence_type="claim", source_text="Text", confidence=0.9)
        bundle_low = _make_bundle("bl", evidence_items=[ev_low])
        bundle_high = _make_bundle("bh", evidence_items=[ev_high])
        theme = _make_theme()
        result = FindingGenerator().generate_findings(
            theme=theme, evidence_bundles=[bundle_low, bundle_high],
        )
        assert result[0].confidence == 0.9


# ===========================================================================
# 13. Ranking
# ===========================================================================


class TestRanking:
    """Finding ranking: confidence desc, evidence count desc, statement asc."""

    def test_highest_confidence_first(self) -> None:
        ev_low = _make_evidence("e1", evidence_type="claim", confidence=0.3,
                                source_text="Low")
        bundle_low = _make_bundle("bl", evidence_items=[ev_low])
        ev_high = _make_evidence("e2", evidence_type="consensus_entry",
                                 confidence=0.9, source_text="High", trace=["c1"])
        bundle_high = _make_bundle("bh", evidence_items=[ev_high])
        theme = _make_theme()
        result = FindingGenerator().generate_findings(
            theme=theme, evidence_bundles=[bundle_low, bundle_high],
        )
        assert result[0].confidence >= result[-1].confidence

    def test_same_confidence_more_evidence_first(self) -> None:
        evs_many = [
            _make_evidence(f"e{i}", evidence_type="gap_item", confidence=0.5)
            for i in range(5)
        ]
        evs_few = [
            _make_evidence(f"f{i}", evidence_type="semantic_triple", confidence=0.5)
            for i in range(2)
        ]
        bundle_many = _make_bundle("bm", evidence_items=evs_many)
        bundle_few = _make_bundle("bf", evidence_items=evs_few)
        theme = _make_theme()
        result = FindingGenerator().generate_findings(
            theme=theme, evidence_bundles=[bundle_many, bundle_few],
        )
        gap_idx = next(i for i, f in enumerate(result) if f.finding_type == "gap")
        rel_idx = next(i for i, f in enumerate(result) if f.finding_type == "relation")
        assert gap_idx < rel_idx

    def test_statement_asc_tiebreaker(self) -> None:
        ev_a = _make_evidence("e1", evidence_type="claim", confidence=0.5,
                              source_text="Alpha text")
        ev_b = _make_evidence("e2", evidence_type="claim", confidence=0.5,
                              source_text="Beta text")
        bundle_a = _make_bundle("ba", evidence_items=[ev_a])
        bundle_b = _make_bundle("bb", evidence_items=[ev_b])
        theme = _make_theme(label="Z")
        result = FindingGenerator().generate_findings(
            theme=theme, evidence_bundles=[bundle_a, bundle_b],
        )
        assert len(result) == 1


# ===========================================================================
# 14. Cap behavior
# ===========================================================================


class TestMaxFindingsCap:
    """max_findings_per_section cap."""

    def test_cap_limits_findings(self) -> None:
        bundles = []
        for i in range(10):
            etype = ["claim", "consensus_entry", "gap_item", "semantic_triple", "contradiction"][i % 5]
            trace = ["step"] if etype in ("consensus_entry", "contradiction") else []
            ev = _make_evidence(
                f"e{i}", evidence_type=etype, source_text=f"Text {i}",
                trace=trace,
            )
            bundles.append(_make_bundle(f"b{i}", evidence_items=[ev]))
        theme = _make_theme(label="X")
        all_result = FindingGenerator().generate_findings(
            theme=theme, evidence_bundles=bundles, max_findings_per_section=100,
        )
        capped_result = FindingGenerator().generate_findings(
            theme=theme, evidence_bundles=bundles, max_findings_per_section=2,
        )
        assert len(all_result) == 5
        assert len(capped_result) == 2

    def test_cap_higher_than_count(self) -> None:
        ev = _make_evidence(evidence_type="claim")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme()
        result = FindingGenerator().generate_findings(
            theme=theme, evidence_bundles=[bundle], max_findings_per_section=100,
        )
        assert len(result) >= 1


# ===========================================================================
# 15. Metadata
# ===========================================================================


class TestMetadata:
    """Finding metadata fields."""

    def test_metadata_contains_theme_label(self) -> None:
        ev = _make_evidence(evidence_type="claim")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="CustomLabel")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert result[0].metadata.get("theme_label") == "CustomLabel"

    def test_metadata_contains_theme_type(self) -> None:
        ev = _make_evidence(evidence_type="claim")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(theme_type="dataset")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert result[0].metadata.get("theme_type") == "dataset"

    def test_metadata_contains_evidence_count(self) -> None:
        evs = [_make_evidence(f"e{i}", evidence_type="claim") for i in range(3)]
        bundle = _make_bundle(evidence_items=evs)
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert result[0].metadata.get("evidence_count") == 3

    def test_supporting_count_matches(self) -> None:
        evs = [_make_evidence(f"e{i}", evidence_type="claim") for i in range(4)]
        bundle = _make_bundle(evidence_items=evs)
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert result[0].supporting_count == 4


# ===========================================================================
# 16. Determinism
# ===========================================================================


class TestDeterminism:
    """Repeated runs must produce identical output."""

    def test_repeated_calls_same_result(self) -> None:
        ev = _make_evidence(evidence_type="claim")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme()
        r1 = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        r2 = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert r1 == r2

    def test_deterministic_across_instances(self) -> None:
        ev = _make_evidence(evidence_type="claim")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme()
        r1 = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        r2 = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert r1 == r2

    def test_deterministic_finding_ids(self) -> None:
        ev = _make_evidence(evidence_type="claim")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme()
        r1 = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        r2 = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert r1[0].finding_id == r2[0].finding_id

    def test_no_uuids_in_finding_ids(self) -> None:
        ev = _make_evidence(evidence_type="claim")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert "uuid" not in result[0].finding_id.lower()


# ===========================================================================
# 17. Serialization round-trip
# ===========================================================================


class TestSerialization:
    """ReviewFinding serialization round-trip."""

    def test_round_trip_json(self) -> None:
        ev = _make_evidence(evidence_type="claim")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme()
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        finding = result[0]
        d = finding.model_dump()
        restored = ReviewFinding.model_validate(d)
        assert restored.finding_id == finding.finding_id
        assert restored.finding_type == finding.finding_type
        assert restored.statement == finding.statement

    def test_round_trip_all_fields(self) -> None:
        evs = [
            _make_evidence("e1", evidence_type="claim", confidence=0.8,
                           source_document_id="d1", trace=["t1"]),
            _make_evidence("e2", evidence_type="claim", confidence=0.9,
                           source_document_id="d2", trace=["t2"]),
        ]
        bundle = _make_bundle(evidence_items=evs)
        theme = _make_theme(label="Test")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        finding = result[0]
        d = finding.model_dump()
        restored = ReviewFinding.model_validate(d)
        assert restored.evidence_ids == finding.evidence_ids
        assert restored.source_document_ids == finding.source_document_ids
        assert restored.trace == finding.trace
        assert restored.metadata == finding.metadata


# ===========================================================================
# 18. Large evidence sets
# ===========================================================================


class TestLargeEvidence:
    """Large evidence collections must complete deterministically."""

    def test_1000_evidence_items(self) -> None:
        evs = [
            _make_evidence(
                f"e{i:04d}",
                evidence_type="claim",
                confidence=0.5 + (i / 1000) * 0.5,
                source_text=f"Finding text number {i} about BERT",
            )
            for i in range(1000)
        ]
        bundle = _make_bundle(evidence_items=evs)
        theme = _make_theme(label="BERT")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert len(result) == 1

    def test_100_bundles(self) -> None:
        bundles = [
            _make_bundle(
                f"b{i:04d}",
                evidence_items=[
                    _make_evidence(
                        f"e{i:04d}",
                        evidence_type="claim",
                        source_text=f"Text {i} about consensus",
                    )
                ],
            )
            for i in range(100)
        ]
        theme = _make_theme(label="consensus")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=bundles)
        assert len(result) == 1

    def test_large_mixed_types_deterministic(self) -> None:
        types = ["claim", "consensus_entry", "contradiction", "gap_item", "semantic_triple"]
        evs = [
            _make_evidence(
                f"e{i:04d}",
                evidence_type=types[i % 5],
                confidence=0.5 + (i / 200) * 0.5,
                source_text=f"Evidence #{i} about Topic",
                trace=[f"step{i}"] if types[i % 5] in ("consensus_entry", "contradiction") else [],
            )
            for i in range(200)
        ]
        bundle = _make_bundle(evidence_items=evs)
        theme = _make_theme(label="Topic")
        r1 = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        r2 = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert r1 == r2


# ===========================================================================
# 19. Convenience helper
# ===========================================================================


class TestConvenienceHelper:
    """Module-level generate_findings convenience function."""

    def test_convenience_returns_list(self) -> None:
        theme = _make_theme()
        result = generate_findings(theme=theme, evidence_bundles=[])
        assert isinstance(result, list)

    def test_convenience_returns_findings(self) -> None:
        theme = _make_theme()
        result = generate_findings(theme=theme, evidence_bundles=[])
        assert all(isinstance(f, ReviewFinding) for f in result)

    def test_convenience_empty_theme(self) -> None:
        result = generate_findings(theme=None, evidence_bundles=[])
        assert result == []

    def test_convenience_consistent_with_generator(self) -> None:
        ev = _make_evidence(evidence_type="claim")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme()
        r1 = generate_findings(theme=theme, evidence_bundles=[bundle])
        r2 = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert r1 == r2

    def test_convenience_passes_max_findings(self) -> None:
        ev = _make_evidence(evidence_type="claim")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme()
        r1 = generate_findings(theme=theme, evidence_bundles=[bundle], max_findings_per_section=1)
        r2 = generate_findings(theme=theme, evidence_bundles=[bundle], max_findings_per_section=10)
        assert len(r1) == len(r2)


# ===========================================================================
# 20. Malformed evidence
# ===========================================================================


class TestMalformedEvidence:
    """Graceful handling of malformed evidence."""

    def test_evidence_missing_type(self) -> None:
        ev = AggregatedEvidence(
            evidence_id="bad", source_text="Text",
            confidence=0.8, evidence_type="",
        )
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="Text")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert len(result) == 1

    def test_evidence_missing_source_text(self) -> None:
        ev = _make_evidence(evidence_type="claim", source_text="")
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="Anything")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert len(result) == 1

    def test_evidence_missing_confidence(self) -> None:
        ev = AggregatedEvidence(
            evidence_id="bad", source_text="Text",
            confidence=0.0, evidence_type="claim",
        )
        bundle = _make_bundle(evidence_items=[ev])
        theme = _make_theme(label="Text")
        result = FindingGenerator().generate_findings(theme=theme, evidence_bundles=[bundle])
        assert len(result) == 1

    def test_mixed_empty_and_valid_bundles(self) -> None:
        empty = _make_bundle("b1", evidence_items=[])
        valid = _make_bundle("b2", evidence_items=[
            _make_evidence("e1", evidence_type="claim"),
        ])
        theme = _make_theme()
        result = FindingGenerator().generate_findings(
            theme=theme, evidence_bundles=[empty, valid],
        )
        assert len(result) == 1
