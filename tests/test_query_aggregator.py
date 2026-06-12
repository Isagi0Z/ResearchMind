"""Tests for the M5 Evidence Aggregator — collection, dedup, ranking, downgrades, anomalies.

Covers architecture sections 7 (Evidence Aggregation), 10.4 (Confidence
Downgrades), and 10.5 (No-Evidence Policy).
"""

from __future__ import annotations

import pytest

from researchmind.query.aggregator import EvidenceAggregator, EvidenceRanker
from researchmind.query.models import AggregatedEvidence, ExecutionPlan, PlanResult, PlanStep


def make_evidence(
    evidence_id="ev_001",
    source_text="BERT uses SQuAD dataset.",
    confidence=0.85,
    source_engine="multi_hop",
    source_document_id="doc_001",
    source_document_title="BERT Paper",
    relation_type="USES_DATASET",
    evidence_type="path_edge",
    trace=None,
    **kw,
) -> AggregatedEvidence:
    defaults = dict(
        evidence_id=evidence_id,
        source_text=source_text,
        confidence=confidence,
        source_engine=source_engine,
        source_document_id=source_document_id,
        source_document_title=source_document_title,
        relation_type=relation_type,
        evidence_type=evidence_type,
        trace=trace if trace is not None else ["chunk_001"],
    )
    defaults.update(kw)
    return AggregatedEvidence(**defaults)


def make_plan_result(step_results=None) -> PlanResult:
    plan = ExecutionPlan(
        plan_id="plan_test",
        query_id="q_test",
        query_type="FACTUAL",
        steps=[],
    )
    return PlanResult(
        plan=plan,
        step_results=step_results or {},
    )


# ===================================================================
# EvidenceRanker (architecture 7.3)
# ===================================================================


class TestEvidenceRankerConstruction:
    def test_create_ranker(self):
        ranker = EvidenceRanker()
        assert isinstance(ranker, EvidenceRanker)

    def test_rank_empty_list(self):
        ranker = EvidenceRanker()
        assert ranker.rank([]) == []

    def test_rank_single_item(self):
        ranker = EvidenceRanker()
        e = make_evidence()
        assert ranker.rank([e]) == [e]

    def test_rank_orders_by_confidence_desc(self):
        ranker = EvidenceRanker()
        e1 = make_evidence(evidence_id="a", confidence=0.5)
        e2 = make_evidence(evidence_id="b", confidence=0.9)
        result = ranker.rank([e1, e2])
        assert result[0].evidence_id == "b"
        assert result[1].evidence_id == "a"

    def test_rank_path_edge_bonus(self):
        ranker = EvidenceRanker()
        edge = make_evidence(evidence_id="e1", confidence=0.5, evidence_type="path_edge")
        other = make_evidence(evidence_id="e2", confidence=0.55, evidence_type="gap_item")
        result = ranker.rank([other, edge])
        assert result[0].evidence_id == "e1"

    def test_rank_source_doc_bonus(self):
        ranker = EvidenceRanker()
        with_doc = make_evidence(evidence_id="a", confidence=0.5, source_document_id="doc_1")
        no_doc = make_evidence(evidence_id="b", confidence=0.54, source_document_id="")
        result = ranker.rank([no_doc, with_doc])
        assert result[0].evidence_id == "a"

    def test_rank_no_source_text_penalty(self):
        ranker = EvidenceRanker()
        has_text = make_evidence(evidence_id="a", confidence=0.5, source_text="has text")
        no_text = make_evidence(evidence_id="b", confidence=0.69, source_text="")
        result = ranker.rank([no_text, has_text])
        assert result[0].evidence_id == "a"

    def test_rank_no_trace_penalty(self):
        ranker = EvidenceRanker()
        has_trace = make_evidence(evidence_id="a", confidence=0.6, trace=["c1"],
                                  source_document_id="doc_1")
        no_trace = make_evidence(evidence_id="b", confidence=0.9, trace=[],
                                  source_document_id="", evidence_type="gap_item")
        result = ranker.rank([no_trace, has_trace])
        assert result[0].evidence_id == "a"

    def test_rank_score_clamped_non_negative(self):
        ranker = EvidenceRanker()
        e = make_evidence(evidence_id="a", confidence=0.0, source_text="", source_document_id="")
        score = EvidenceRanker._score(e)
        assert score >= 0.0

    def test_rank_deterministic(self):
        ranker = EvidenceRanker()
        items = [
            make_evidence(evidence_id="c", confidence=0.7),
            make_evidence(evidence_id="a", confidence=0.9),
            make_evidence(evidence_id="b", confidence=0.8),
        ]
        r1 = ranker.rank(items[:])
        r2 = ranker.rank(items[:])
        assert [e.evidence_id for e in r1] == [e.evidence_id for e in r2]

    def test_rank_equal_confidence_stable(self):
        ranker = EvidenceRanker()
        items = [
            make_evidence(evidence_id="x", confidence=0.5, source_text="x"),
            make_evidence(evidence_id="y", confidence=0.5, source_text="y"),
        ]
        result = ranker.rank(items[:])
        assert len(result) == 2


# ===================================================================
# EvidenceAggregator — construction
# ===================================================================


class TestEvidenceAggregatorConstruction:
    def test_create_aggregator(self):
        agg = EvidenceAggregator()
        assert isinstance(agg, EvidenceAggregator)

    def test_aggregator_has_ranker(self):
        agg = EvidenceAggregator()
        assert isinstance(agg.ranker, EvidenceRanker)


# ===================================================================
# _collect (Step 1)
# ===================================================================


class TestCollect:
    def test_empty_step_results(self):
        agg = EvidenceAggregator()
        pr = make_plan_result({})
        assert agg._collect(pr) == []

    def test_single_aggregated_evidence(self):
        agg = EvidenceAggregator()
        e = make_evidence()
        pr = make_plan_result({"step_001": e})
        assert agg._collect(pr) == [e]

    def test_list_of_aggregated_evidence(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="a")
        e2 = make_evidence(evidence_id="b")
        pr = make_plan_result({"step_001": [e1, e2]})
        assert agg._collect(pr) == [e1, e2]

    def test_single_dict_result(self):
        agg = EvidenceAggregator()
        d = dict(evidence_id="ev_d", source_text="test", confidence=0.5, evidence_type="path_edge", trace=["c1"])
        pr = make_plan_result({"step_001": d})
        result = agg._collect(pr)
        assert len(result) == 1
        assert result[0].evidence_id == "ev_d"

    def test_list_of_dicts(self):
        agg = EvidenceAggregator()
        d1 = dict(evidence_id="a", source_text="x", confidence=0.5, evidence_type="path_edge", trace=["c1"])
        d2 = dict(evidence_id="b", source_text="y", confidence=0.6, evidence_type="path_edge", trace=["c2"])
        pr = make_plan_result({"step_001": [d1, d2]})
        result = agg._collect(pr)
        assert len(result) == 2

    def test_none_result_skipped(self):
        agg = EvidenceAggregator()
        pr = make_plan_result({"step_001": None})
        assert agg._collect(pr) == []

    def test_invalid_dict_skipped(self):
        agg = EvidenceAggregator()
        pr = make_plan_result({"step_001": {"bad": "data"}})
        assert agg._collect(pr) == []

    def test_mixed_step_results(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="a")
        e2 = make_evidence(evidence_id="b")
        pr = make_plan_result({
            "step_001": e1,
            "step_002": [e2],
            "step_003": None,
        })
        result = agg._collect(pr)
        assert len(result) == 2

    def test_multiple_steps_accumulated(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="s1")
        e2 = make_evidence(evidence_id="s2")
        pr = make_plan_result({"step_001": e1, "step_002": e2})
        result = agg._collect(pr)
        assert len(result) == 2

    def test_empty_dict_result_skipped(self):
        agg = EvidenceAggregator()
        pr = make_plan_result({"step_001": {}})
        assert agg._collect(pr) == []

    def test_nested_list_handled(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="a")
        pr = make_plan_result({"step_001": [[e1]]})
        result = agg._collect(pr)
        assert len(result) == 1


# ===================================================================
# _apply_downgrades (architecture 10.4)
# ===================================================================


class TestConfidenceDowngrades:
    def test_no_downgrade_when_all_present(self):
        agg = EvidenceAggregator()
        e = make_evidence(confidence=0.8)
        result = agg._apply_downgrades([e])
        assert result[0].confidence == 0.8

    def test_no_source_document_halves(self):
        agg = EvidenceAggregator()
        e = make_evidence(confidence=0.8, source_document_id="")
        result = agg._apply_downgrades([e])
        assert result[0].confidence == 0.4

    def test_no_trace_penalty(self):
        agg = EvidenceAggregator()
        e = make_evidence(confidence=0.8, trace=[], evidence_type="aggregate")
        result = agg._apply_downgrades([e])
        assert result[0].confidence == pytest.approx(0.64)

    def test_derived_source_penalty(self):
        agg = EvidenceAggregator()
        e = make_evidence(confidence=0.8, metadata={"source_type": "derived"})
        result = agg._apply_downgrades([e])
        assert result[0].confidence == 0.72

    def test_gap_item_penalty(self):
        agg = EvidenceAggregator()
        e = make_evidence(confidence=0.8, evidence_type="gap_item")
        result = agg._apply_downgrades([e])
        assert result[0].confidence == 0.56

    def test_extra_hops_penalty(self):
        agg = EvidenceAggregator()
        e = make_evidence(confidence=0.8, trace=["c1", "c2", "c3", "c4"])
        result = agg._apply_downgrades([e])
        assert result[0].confidence == pytest.approx(0.8 * 0.9 ** 2)

    def test_combined_downgrades(self):
        agg = EvidenceAggregator()
        e = make_evidence(
            confidence=0.8,
            source_document_id="",
            trace=[],
            evidence_type="gap_item",
        )
        result = agg._apply_downgrades([e])
        assert result[0].confidence == pytest.approx(0.8 * 0.5 * 0.8 * 0.7)

    def test_confidence_clamped_at_zero(self):
        agg = EvidenceAggregator()
        e = make_evidence(confidence=0.001, source_document_id="", trace=[],
                          evidence_type="gap_item")
        result = agg._apply_downgrades([e])
        assert result[0].confidence >= 0.0

    def test_confidence_clamped_at_one(self):
        agg = EvidenceAggregator()
        e = make_evidence(confidence=1.0)
        result = agg._apply_downgrades([e])
        assert result[0].confidence <= 1.0

    def test_rounding(self):
        agg = EvidenceAggregator()
        e = make_evidence(confidence=0.333333, source_document_id="")
        result = agg._apply_downgrades([e])
        assert result[0].confidence == 0.1667

    def test_missing_doc_and_derived(self):
        agg = EvidenceAggregator()
        e = make_evidence(confidence=0.8, source_document_id="", metadata={"source_type": "derived"})
        result = agg._apply_downgrades([e])
        assert result[0].confidence == pytest.approx(0.8 * 0.5 * 0.9)

    def test_no_trace_and_extra_hops(self):
        agg = EvidenceAggregator()
        e = make_evidence(confidence=0.9, trace=[], evidence_type="aggregate")
        result = agg._apply_downgrades([e])
        assert result[0].confidence == pytest.approx(0.72)


# ===================================================================
# _deduplicate (architecture 7.4)
# ===================================================================


class TestDeduplicate:
    def test_empty_list(self):
        agg = EvidenceAggregator()
        assert agg._deduplicate([]) == []

    def test_no_duplicates(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="a", source_text="x", relation_type="A", source_document_id="d1")
        e2 = make_evidence(evidence_id="b", source_text="y", relation_type="B", source_document_id="d2")
        result = agg._deduplicate([e1, e2])
        assert len(result) == 2

    def test_duplicate_id_keeps_higher_confidence(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="dup", confidence=0.9, source_text="x")
        e2 = make_evidence(evidence_id="dup", confidence=0.5, source_text="y")
        result = agg._deduplicate([e1, e2])
        assert len(result) == 1
        assert result[0].confidence == 0.9

    def test_duplicate_doc_rel_keeps_highest(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="a", source_document_id="d1", relation_type="R", confidence=0.9, source_text="x")
        e2 = make_evidence(evidence_id="b", source_document_id="d1", relation_type="R", confidence=0.5, source_text="y")
        result = agg._deduplicate([e1, e2])
        assert len(result) == 1
        assert result[0].evidence_id == "a"

    def test_gap_dedup_by_node_and_type(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="a", evidence_type="gap_item", confidence=0.8,
                           source_text="x", metadata={"node_id": "n1", "gap_type": "missing"})
        e2 = make_evidence(evidence_id="b", evidence_type="gap_item", confidence=0.6,
                           source_text="y", metadata={"node_id": "n1", "gap_type": "missing"})
        result = agg._deduplicate([e1, e2])
        assert len(result) == 1
        assert result[0].evidence_id == "a"

    def test_contradiction_dedup_by_doc_pair(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="a", evidence_type="contradiction", confidence=0.9,
                           source_text="x", metadata={"claim_a_document": "d1", "claim_b_document": "d2"})
        e2 = make_evidence(evidence_id="b", evidence_type="contradiction", confidence=0.5,
                           source_text="y", metadata={"claim_a_document": "d1", "claim_b_document": "d2"})
        result = agg._deduplicate([e1, e2])
        assert len(result) == 1
        assert result[0].evidence_id == "a"

    def test_text_dedup_normalized(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="a", source_text="BERT Uses SQuAD.", confidence=0.9)
        e2 = make_evidence(evidence_id="b", source_text="bert uses squad.", confidence=0.5)
        result = agg._deduplicate([e1, e2])
        assert len(result) == 1
        assert result[0].evidence_id == "a"

    def test_text_dedup_whitespace_normalized(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="a", source_text="hello  world", confidence=0.9)
        e2 = make_evidence(evidence_id="b", source_text="hello world", confidence=0.5)
        result = agg._deduplicate([e1, e2])
        assert len(result) == 1

    def test_different_ids_same_doc_rel_keeps_one(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="a", source_document_id="d1", relation_type="R",
                           source_text="text a", confidence=0.7)
        e2 = make_evidence(evidence_id="b", source_document_id="d1", relation_type="R",
                           source_text="text b", confidence=0.9)
        result = agg._deduplicate([e1, e2])
        assert len(result) == 1
        assert result[0].evidence_id == "b"

    def test_doc_rel_dedup_skipped_when_empty(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="a", source_document_id="", relation_type="",
                           source_text="x", confidence=0.9)
        e2 = make_evidence(evidence_id="b", source_document_id="", relation_type="",
                           source_text="y", confidence=0.5)
        result = agg._deduplicate([e1, e2])
        assert len(result) == 2

    def test_deterministic_dedup(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="dup", confidence=0.5, source_text="x")
        e2 = make_evidence(evidence_id="dup", confidence=0.9, source_text="y")
        result = agg._deduplicate([e1, e2])
        assert result[0].confidence == 0.9


# ===================================================================
# _detect_anomalies (architecture 7.5)
# ===================================================================


class TestAnomalyDetection:
    def test_no_anomalies_passthrough(self):
        agg = EvidenceAggregator()
        e = make_evidence()
        result = agg._detect_anomalies([e])
        assert len(result) == 1
        assert result[0].evidence_id == e.evidence_id

    def test_circular_trace_broken(self):
        agg = EvidenceAggregator()
        e = make_evidence(trace=["a", "b", "a", "c"])
        result = agg._detect_anomalies([e])
        assert result[0].trace == ["a", "b", "c"]

    def test_empty_evidence_ids_reduces_confidence(self):
        agg = EvidenceAggregator()
        e = make_evidence(evidence_type="path_edge", confidence=0.8, metadata={})
        result = agg._detect_anomalies([e])
        assert result[0].confidence == 0.7

    def test_gap_item_not_affected_by_evidence_ids_rule(self):
        agg = EvidenceAggregator()
        e = make_evidence(evidence_type="gap_item", confidence=0.8, metadata={})
        result = agg._detect_anomalies([e])
        assert result[0].confidence == 0.8

    def test_confidence_not_reduced_when_evidence_ids_present(self):
        agg = EvidenceAggregator()
        e = make_evidence(evidence_type="path_edge", confidence=0.8,
                          metadata={"evidence_ids": ["eid1"]})
        result = agg._detect_anomalies([e])
        assert result[0].confidence == 0.8

    def test_cycle_with_repeated_adjacent(self):
        agg = EvidenceAggregator()
        e = make_evidence(trace=["a", "a", "b", "c"])
        result = agg._detect_anomalies([e])
        assert result[0].trace == ["a", "b", "c"]

    def test_no_cycle_no_change(self):
        agg = EvidenceAggregator()
        e = make_evidence(trace=["a", "b", "c", "d"])
        result = agg._detect_anomalies([e])
        assert result[0].trace == ["a", "b", "c", "d"]

    def test_confidence_clamped_non_negative_after_penalty(self):
        agg = EvidenceAggregator()
        e = make_evidence(evidence_type="path_edge", confidence=0.05, metadata={})
        result = agg._detect_anomalies([e])
        assert result[0].confidence >= 0.0


# ===================================================================
# aggregate — integration (full pipeline)
# ===================================================================


class TestAggregateIntegration:
    def test_aggregate_empty_plan_result(self):
        agg = EvidenceAggregator()
        pr = make_plan_result({})
        assert agg.aggregate(pr) == []

    def test_aggregate_single_step_single_evidence(self):
        agg = EvidenceAggregator()
        e = make_evidence()
        pr = make_plan_result({"step_001": e})
        result = agg.aggregate(pr)
        assert len(result) == 1

    def test_aggregate_dedup_removes_duplicate_ids(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="same", confidence=0.9, source_text="version a")
        e2 = make_evidence(evidence_id="same", confidence=0.5, source_text="version b")
        pr = make_plan_result({"step_001": e1, "step_002": e2})
        result = agg.aggregate(pr)
        assert len(result) == 1

    def test_aggregate_applies_downgrades(self):
        agg = EvidenceAggregator()
        e = make_evidence(confidence=0.8, source_document_id="",
                          metadata={"evidence_ids": ["eid_1"]})
        pr = make_plan_result({"step_001": e})
        result = agg.aggregate(pr)
        assert result[0].confidence == pytest.approx(0.4)

    def test_aggregate_ranks_by_score(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="low", confidence=0.3, source_text="low")
        e2 = make_evidence(evidence_id="high", confidence=0.9, source_text="high")
        pr = make_plan_result({"step_001": [e1, e2]})
        result = agg.aggregate(pr)
        assert result[0].evidence_id == "high"

    def test_aggregate_deterministic(self):
        agg = EvidenceAggregator()
        items = [
            make_evidence(evidence_id="c", confidence=0.7, source_text="c"),
            make_evidence(evidence_id="a", confidence=0.9, source_text="a"),
            make_evidence(evidence_id="b", confidence=0.8, source_text="b"),
        ]
        pr = make_plan_result({"step_001": items})
        r1 = agg.aggregate(pr)
        r2 = agg.aggregate(pr)
        ids1 = [e.evidence_id for e in r1]
        ids2 = [e.evidence_id for e in r2]
        assert ids1 == ids2

    def test_aggregate_factual_scenario(self):
        agg = EvidenceAggregator()
        evidence = [
            make_evidence(evidence_id="ev_001", source_text="BERT uses SQuAD.",
                          confidence=0.85, source_document_id="doc_001",
                          relation_type="USES_DATASET"),
            make_evidence(evidence_id="ev_002", source_text="BERT uses BookCorpus.",
                          confidence=0.9, source_document_id="doc_001",
                          relation_type="USES_DATASET"),
            make_evidence(evidence_id="ev_003", source_text="BERT fine-tuned on GLUE.",
                          confidence=0.8, source_document_id="doc_002",
                          relation_type="USES_DATASET"),
        ]
        pr = make_plan_result({"step_001": evidence})
        result = agg.aggregate(pr)
        assert len(result) == 2  # ev_002 wins over ev_001 (same doc+rel)
        assert result[0].evidence_id == "ev_002"

    def test_aggregate_consensus_scenario(self):
        agg = EvidenceAggregator()
        evidence = [
            make_evidence(evidence_id="cs_001", evidence_type="consensus_entry",
                          confidence=0.7, source_document_id="doc_a",
                          source_text="Paper A supports dropout."),
            make_evidence(evidence_id="cs_002", evidence_type="consensus_entry",
                          confidence=0.8, source_document_id="doc_b",
                          source_text="Paper B supports dropout."),
        ]
        pr = make_plan_result({"step_001": evidence})
        result = agg.aggregate(pr)
        assert len(result) == 2

    def test_aggregate_contradiction_scenario(self):
        agg = EvidenceAggregator()
        evidence = [
            make_evidence(evidence_id="ct_001", evidence_type="contradiction",
                          confidence=0.75, source_document_id="doc_a",
                          source_text="Paper A says X.",
                          metadata={"claim_a_document": "doc_a", "claim_b_document": "doc_b"}),
            make_evidence(evidence_id="ct_002", evidence_type="contradiction",
                          confidence=0.6, source_document_id="doc_a",
                          source_text="Different version.",
                          metadata={"claim_a_document": "doc_a", "claim_b_document": "doc_b"}),
        ]
        pr = make_plan_result({"step_001": evidence})
        result = agg.aggregate(pr)
        assert len(result) == 1

    def test_aggregate_gap_scenario(self):
        agg = EvidenceAggregator()
        evidence = [
            make_evidence(evidence_id="gp_001", evidence_type="gap_item",
                          confidence=0.5, source_document_id="",
                          source_text="Missing comparison: GAN vs VAE.",
                          metadata={"node_id": "n1", "gap_type": "missing_comparison"}),
            make_evidence(evidence_id="gp_002", evidence_type="gap_item",
                          confidence=0.4, source_document_id="",
                          source_text="Also missing comparison.",
                          metadata={"node_id": "n1", "gap_type": "missing_comparison"}),
        ]
        pr = make_plan_result({"step_001": evidence})
        result = agg.aggregate(pr)
        assert len(result) == 1

    def test_aggregate_mixed_step_formats(self):
        agg = EvidenceAggregator()
        e_obj = make_evidence(evidence_id="from_obj", source_text="obj")
        e_dict = dict(evidence_id="from_dict", source_text="dict",
                      confidence=0.7, evidence_type="path_edge", trace=["c1"])
        pr = make_plan_result({"step_001": e_obj, "step_002": e_dict})
        result = agg.aggregate(pr)
        assert len(result) == 2

    def test_aggregate_breaks_circular_trace(self):
        agg = EvidenceAggregator()
        e = make_evidence(trace=["a", "b", "a", "c"])
        pr = make_plan_result({"step_001": e})
        result = agg.aggregate(pr)
        assert result[0].trace == ["a", "b", "c"]

    def test_aggregate_preserves_source_engine(self):
        agg = EvidenceAggregator()
        e = make_evidence(source_engine="consensus")
        pr = make_plan_result({"step_001": e})
        result = agg.aggregate(pr)
        assert result[0].source_engine == "consensus"

    def test_aggregate_no_evidence_below_threshold(self):
        agg = EvidenceAggregator()
        evidence = [
            make_evidence(evidence_id="low", confidence=0.01, source_text="x"),
        ]
        pr = make_plan_result({"step_001": evidence})
        result = agg.aggregate(pr)
        assert len(result) == 1

    def test_aggregate_all_evidence_removed_by_dedup(self):
        agg = EvidenceAggregator()
        e = make_evidence(evidence_id="only_one", confidence=0.8, source_text="x")
        pr = make_plan_result({"step_001": e, "step_002": e.model_copy(deep=True)})
        result = agg.aggregate(pr)
        assert len(result) == 1


# ===================================================================
# compute_confidence (architecture 8.4)
# ===================================================================


class TestComputeConfidence:
    def test_empty_list_returns_zero(self):
        agg = EvidenceAggregator()
        assert agg.compute_confidence([]) == 0.0

    def test_single_evidence(self):
        agg = EvidenceAggregator()
        e = make_evidence(confidence=0.75)
        assert agg.compute_confidence([e]) == 0.75

    def test_multiple_evidence_uses_min(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="a", confidence=0.9)
        e2 = make_evidence(evidence_id="b", confidence=0.4)
        assert agg.compute_confidence([e1, e2]) == 0.4

    def test_all_zero_confidence(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="a", confidence=0.0)
        e2 = make_evidence(evidence_id="b", confidence=0.0)
        assert agg.compute_confidence([e1, e2]) == 0.0

    def test_mixed_confidence(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="a", confidence=0.3)
        e2 = make_evidence(evidence_id="b", confidence=0.7)
        e3 = make_evidence(evidence_id="c", confidence=0.5)
        assert agg.compute_confidence([e1, e2, e3]) == 0.3

    def test_downgraded_confidence(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="a", confidence=0.8, source_document_id="")
        evidence = agg._apply_downgrades([e1])
        assert agg.compute_confidence(evidence) == 0.4


# ===================================================================
# No-evidence policy (architecture 10.5)
# ===================================================================


class TestNoEvidencePolicy:
    def test_no_evidence_response_string(self):
        resp = EvidenceAggregator.no_evidence_response()
        assert isinstance(resp, str)
        assert len(resp) > 10
        assert "Insufficient evidence" in resp

    def test_check_no_evidence_empty(self):
        assert EvidenceAggregator.check_no_evidence([]) is True

    def test_check_no_evidence_with_evidence(self):
        e = make_evidence(confidence=0.5)
        assert EvidenceAggregator.check_no_evidence([e]) is False

    def test_check_no_evidence_below_threshold(self):
        e = make_evidence(confidence=0.05)
        assert EvidenceAggregator.check_no_evidence([e], min_confidence=0.1) is True

    def test_check_no_evidence_above_threshold(self):
        e = make_evidence(confidence=0.15)
        assert EvidenceAggregator.check_no_evidence([e], min_confidence=0.1) is False

    def test_check_no_evidence_default_threshold(self):
        e = make_evidence(confidence=0.0)
        assert EvidenceAggregator.check_no_evidence([e]) is False
        assert EvidenceAggregator.check_no_evidence([e], min_confidence=0.01) is True

    def test_check_no_evidence_with_multiple_below(self):
        e1 = make_evidence(evidence_id="a", confidence=0.02)
        e2 = make_evidence(evidence_id="b", confidence=0.03)
        assert EvidenceAggregator.check_no_evidence([e1, e2], min_confidence=0.1) is True


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    def test_evidence_with_empty_id(self):
        agg = EvidenceAggregator()
        e = make_evidence(evidence_id="", source_text="no id")
        pr = make_plan_result({"step_001": e})
        result = agg.aggregate(pr)
        assert len(result) == 1

    def test_evidence_with_no_trace(self):
        agg = EvidenceAggregator()
        e = make_evidence(confidence=0.8, trace=[], source_document_id="doc_001",
                          evidence_type="aggregate")
        pr = make_plan_result({"step_001": e})
        result = agg.aggregate(pr)
        assert len(result) == 1
        assert result[0].confidence == pytest.approx(0.8 * 0.8)

    def test_evidence_with_no_source_document(self):
        agg = EvidenceAggregator()
        e = make_evidence(confidence=0.8, source_document_id="", trace=["c1"],
                          evidence_type="aggregate")
        pr = make_plan_result({"step_001": e})
        result = agg.aggregate(pr)
        assert result[0].confidence == pytest.approx(0.8 * 0.5)

    def test_evidence_with_no_source_text(self):
        agg = EvidenceAggregator()
        e = make_evidence(source_text="", confidence=0.8)
        pr = make_plan_result({"step_001": e})
        result = agg.aggregate(pr)
        assert len(result) == 1

    def test_evidence_with_all_fields_empty(self):
        agg = EvidenceAggregator()
        e = make_evidence(
            evidence_id="", source_text="", confidence=0.5,
            source_document_id="", trace=[], evidence_type="aggregate",
        )
        pr = make_plan_result({"step_001": e})
        result = agg.aggregate(pr)
        assert len(result) == 1

    def test_evidence_with_high_confidence(self):
        agg = EvidenceAggregator()
        e = make_evidence(confidence=0.9999)
        pr = make_plan_result({"step_001": e})
        result = agg.aggregate(pr)
        assert result[0].confidence <= 1.0

    def test_evidence_with_metadata(self):
        agg = EvidenceAggregator()
        e = make_evidence(metadata={"source_type": "direct", "page": 3})
        pr = make_plan_result({"step_001": e})
        result = agg.aggregate(pr)
        assert result[0].metadata["source_type"] == "direct"
        assert result[0].metadata["page"] == 3

    def test_multiple_steps_with_gap_dedup(self):
        agg = EvidenceAggregator()
        e1 = make_evidence(evidence_id="g1", evidence_type="gap_item", confidence=0.7,
                           source_text="gap a", source_document_id="",
                           metadata={"node_id": "n1", "gap_type": "missing"})
        e2 = make_evidence(evidence_id="g2", evidence_type="gap_item", confidence=0.5,
                           source_text="gap b", source_document_id="",
                           metadata={"node_id": "n1", "gap_type": "missing"})
        e3 = make_evidence(evidence_id="g3", evidence_type="gap_item", confidence=0.9,
                           source_text="gap c", source_document_id="",
                           metadata={"node_id": "n2", "gap_type": "missing"})
        pr = make_plan_result({"step_001": [e1, e2], "step_002": e3})
        result = agg.aggregate(pr)
        assert len(result) == 2

    def test_full_pipeline_preserves_order(self):
        agg = EvidenceAggregator()
        evidence = [
            make_evidence(evidence_id="a", confidence=0.3, source_text="a",
                          source_document_id="doc_a", relation_type="R_A",
                          metadata={"evidence_ids": ["eid_a"]}),
            make_evidence(evidence_id="b", confidence=0.9, source_text="b",
                          source_document_id="doc_b", relation_type="R_B",
                          metadata={"evidence_ids": ["eid_b"]}),
            make_evidence(evidence_id="c", confidence=0.6, source_text="c",
                          source_document_id="doc_c", relation_type="R_C",
                          metadata={"evidence_ids": ["eid_c"]}),
        ]
        pr = make_plan_result({"step_001": evidence})
        result = agg.aggregate(pr)
        ids = [e.evidence_id for e in result]
        assert ids == ["b", "c", "a"]

    def test_plan_result_with_no_plan_steps(self):
        agg = EvidenceAggregator()
        plan = ExecutionPlan(plan_id="p", query_id="q", query_type="FACTUAL", steps=[])
        pr = PlanResult(plan=plan, step_results={})
        assert agg.aggregate(pr) == []


# ===================================================================
# Error handling
# ===================================================================


class TestErrorHandling:
    def test_aggregate_with_none_step_results(self):
        agg = EvidenceAggregator()
        plan = ExecutionPlan(plan_id="p", query_id="q", query_type="FACTUAL", steps=[])
        pr = PlanResult(plan=plan, step_results={"step_001": None})
        result = agg.aggregate(pr)
        assert result == []

    def test_aggregate_missing_key_in_dict_skipped(self):
        agg = EvidenceAggregator()
        plan = ExecutionPlan(plan_id="p", query_id="q", query_type="FACTUAL", steps=[])
        pr = PlanResult(plan=plan, step_results={"step_001": {"bad_key": "value"}})
        result = agg.aggregate(pr)
        assert result == []

    def test_aggregate_with_string_result(self):
        agg = EvidenceAggregator()
        plan = ExecutionPlan(plan_id="p", query_id="q", query_type="FACTUAL", steps=[])
        pr = PlanResult(plan=plan, step_results={"step_001": "not evidence"})
        result = agg.aggregate(pr)
        assert result == []

    def test_aggregate_with_int_result(self):
        agg = EvidenceAggregator()
        plan = ExecutionPlan(plan_id="p", query_id="q", query_type="FACTUAL", steps=[])
        pr = PlanResult(plan=plan, step_results={"step_001": 42})
        result = agg.aggregate(pr)
        assert result == []

    def test_aggregate_non_evidence_object_skipped(self):
        agg = EvidenceAggregator()
        plan = ExecutionPlan(plan_id="p", query_id="q", query_type="FACTUAL", steps=[])

        class FakeResult:
            pass

        pr = PlanResult(plan=plan, step_results={"step_001": FakeResult()})
        result = agg.aggregate(pr)
        assert result == []


# ===================================================================
# Introspection
# ===================================================================


class TestIntrospection:
    def test_no_evidence_response_is_constant(self):
        r1 = EvidenceAggregator.no_evidence_response()
        r2 = EvidenceAggregator.no_evidence_response()
        assert r1 == r2

    def test_aggregator_reusable(self):
        agg = EvidenceAggregator()
        e = make_evidence()
        pr1 = make_plan_result({"step_001": e})
        pr2 = make_plan_result({"step_001": e})
        r1 = agg.aggregate(pr1)
        r2 = agg.aggregate(pr2)
        assert len(r1) == len(r2)

    def test_multiple_aggregators_independent(self):
        a1 = EvidenceAggregator()
        a2 = EvidenceAggregator()
        e = make_evidence()
        pr = make_plan_result({"step_001": e})
        assert a1.aggregate(pr) == a2.aggregate(pr)


# ===================================================================
# _normalize_text
# ===================================================================


class TestNormalizeText:
    def test_lowercases(self):
        assert EvidenceAggregator._normalize_text("Hello World") == "hello world"

    def test_collapses_whitespace(self):
        assert EvidenceAggregator._normalize_text("hello   world") == "hello world"

    def test_strips_whitespace(self):
        assert EvidenceAggregator._normalize_text("  hello world  ") == "hello world"

    def test_empty_string(self):
        assert EvidenceAggregator._normalize_text("") == ""

    def test_whitespace_only(self):
        assert EvidenceAggregator._normalize_text("   ") == ""
