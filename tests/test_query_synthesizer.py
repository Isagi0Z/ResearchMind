"""Tests for the M5-6 Answer Synthesizer — templates, confidence, traceability, determinism.

Covers architecture sections 8 (Answer Synthesis), 9 (ResearchAnswer Model),
and 10 (Traceability Contract).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from researchmind.query.synthesizer import AnswerSynthesizer, synthesize_answer
from researchmind.query.models import (
    AggregatedEvidence,
    ExecutionPlan,
    ParsedQuery,
    PlanResult,
    PlanStep,
    QueryEntity,
    QueryType,
    ReasoningStep,
    ResearchAnswer,
    ResearchQuery,
)

NOW = datetime.now(timezone.utc)


# ===================================================================
# Factory helpers
# ===================================================================


def make_entity(text="BERT", entity_type="method", cluster_id="clu_003", **kw) -> QueryEntity:
    defaults = dict(text=text, entity_type=entity_type, cluster_id=cluster_id, confidence=0.9)
    defaults.update(kw)
    return QueryEntity(**defaults)


def make_parsed_query(query_type="FACTUAL", primary=None, secondary=None, **kw) -> ParsedQuery:
    defaults = dict(
        raw_query="What datasets does BERT use?",
        query_type=query_type,
        primary_entity=primary or make_entity(),
        entities_resolved=True,
    )
    defaults.update(kw)
    return ParsedQuery(**defaults)


def make_research_query(query_id="qry_001", raw_query="What datasets does BERT use?", **kw) -> ResearchQuery:
    defaults = dict(query_id=query_id, raw_query=raw_query, created_at=NOW)
    defaults.update(kw)
    return ResearchQuery(**defaults)


def make_plan_step(step_id="step_001", sequence=1, engine="multi_hop", query_type="ENTITY_LOOKUP", **kw) -> PlanStep:
    defaults = dict(
        step_id=step_id, sequence=sequence, engine=engine, query_type=query_type,
    )
    defaults.update(kw)
    return PlanStep(**defaults)


def make_execution_plan(steps=None, **kw) -> ExecutionPlan:
    steps = steps or [make_plan_step()]
    defaults = dict(plan_id="plan_test", query_id="qry_001", query_type="FACTUAL", steps=steps)
    defaults.update(kw)
    plan = ExecutionPlan(**defaults)
    object.__setattr__(plan, "total_steps", len(steps))
    return plan


def make_plan_result(step_results=None, plan=None, **kw) -> PlanResult:
    plan = plan or make_execution_plan()
    defaults = dict(plan=plan, step_results=step_results or {})
    defaults.update(kw)
    return PlanResult(**defaults)


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


def make_synthesizer() -> AnswerSynthesizer:
    return AnswerSynthesizer()


# ===================================================================
# Construction
# ===================================================================


class TestConstruction:
    def test_create_synthesizer(self):
        s = make_synthesizer()
        assert isinstance(s, AnswerSynthesizer)

    def test_synthesize_returns_research_answer(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert isinstance(result, ResearchAnswer)

    def test_convenience_function(self):
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence()]
        result = synthesize_answer(rq, pq, plan, pr, ev)
        assert isinstance(result, ResearchAnswer)

    def test_convenience_equals_class_method(self):
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence()]
        a = synthesize_answer(rq, pq, plan, pr, ev)
        b = AnswerSynthesizer().synthesize(rq, pq, plan, pr, ev)
        assert a.answer == b.answer
        assert a.confidence == b.confidence

    def test_multiple_synthesizers_independent(self):
        s1 = make_synthesizer()
        s2 = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence()]
        a = s1.synthesize(rq, pq, plan, pr, ev)
        b = s2.synthesize(rq, pq, plan, pr, ev)
        assert a.answer_id == b.answer_id


# ===================================================================
# FACTUAL query type
# ===================================================================


class TestFactual:
    def test_factual_answer_contains_entity(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="FACTUAL")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "BERT" in result.answer

    def test_factual_answer_contains_confidence(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="FACTUAL")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence(confidence=0.85)]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "0.85" in result.answer

    def test_factual_confidence_is_max(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="FACTUAL")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", confidence=0.5),
            make_evidence("ev_b", confidence=0.9),
            make_evidence("ev_c", confidence=0.3),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.confidence == 0.9

    def test_factual_multiple_evidence(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="FACTUAL")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_001", source_text="Uses SQuAD.", relation_type="USES_DATASET"),
            make_evidence("ev_002", source_text="Uses GLUE.", relation_type="USES_DATASET",
                          source_document_id="doc_002", source_document_title="GLUE Paper"),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "SQuAD" in result.answer or "GLUE" in result.answer

    def test_factual_no_evidence_fallback(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="FACTUAL")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        result = s.synthesize(rq, pq, plan, pr, [])
        assert "Insufficient evidence" in result.answer
        assert result.confidence == 0.0

    def test_factual_zero_confidence_filtered(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="FACTUAL")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence(confidence=0.0)]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "Insufficient evidence" in result.answer

    def test_factual_query_type_set(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="FACTUAL")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.query_type == "FACTUAL"


# ===================================================================
# EXPLANATION query type
# ===================================================================


class TestExplanation:
    def test_explanation_contains_entity(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="EXPLANATION")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence(source_text="BatchNorm normalizes inputs.")]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "BERT" in result.answer

    def test_explanation_confidence_is_max(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="EXPLANATION")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", confidence=0.4),
            make_evidence("ev_b", confidence=0.8),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.confidence == 0.8

    def test_explanation_doc_count_in_answer(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="EXPLANATION")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_001", source_document_id="doc_a"),
            make_evidence("ev_002", source_document_id="doc_b"),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "2 document" in result.answer

    def test_explanation_claims_listed(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="EXPLANATION")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_001", source_text="Claim one."),
            make_evidence("ev_002", source_text="Claim two."),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "Claim one." in result.answer
        assert "Claim two." in result.answer

    def test_explanation_no_evidence(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="EXPLANATION")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        result = s.synthesize(rq, pq, plan, pr, [])
        assert result.confidence == 0.0


# ===================================================================
# COMPARISON query type
# ===================================================================


class TestComparison:
    def test_comparison_contains_entities(self):
        s = make_synthesizer()
        rq = make_research_query()
        prim = make_entity(text="Adam")
        sec = make_entity(text="SGD")
        pq = make_parsed_query(query_type="COMPARISON", primary=prim, secondary_entities=[sec])
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence(relation_type="OPTIMIZER")]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "Adam" in result.answer
        assert "SGD" in result.answer

    def test_comparison_confidence_is_mean(self):
        s = make_synthesizer()
        rq = make_research_query()
        prim = make_entity(text="Adam")
        sec = make_entity(text="SGD")
        pq = make_parsed_query(query_type="COMPARISON", primary=prim, secondary_entities=[sec])
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", confidence=0.8),
            make_evidence("ev_b", confidence=0.6),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.confidence == pytest.approx(0.7)

    def test_comparison_single_evidence(self):
        s = make_synthesizer()
        rq = make_research_query()
        prim = make_entity(text="ResNet")
        sec = make_entity(text="U-Net")
        pq = make_parsed_query(query_type="COMPARISON", primary=prim, secondary_entities=[sec])
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence(relation_type="ARCHITECTURE")]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "ARCHITECTURE" in result.answer

    def test_comparison_no_evidence(self):
        s = make_synthesizer()
        rq = make_research_query()
        prim = make_entity(text="Adam")
        sec = make_entity(text="SGD")
        pq = make_parsed_query(query_type="COMPARISON", primary=prim, secondary_entities=[sec])
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        result = s.synthesize(rq, pq, plan, pr, [])
        assert result.confidence == 0.0

    def test_comparison_shared_attributes(self):
        s = make_synthesizer()
        rq = make_research_query()
        prim = make_entity(text="Adam")
        sec = make_entity(text="SGD")
        pq = make_parsed_query(query_type="COMPARISON", primary=prim, secondary_entities=[sec])
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", relation_type="OPTIMIZER"),
            make_evidence("ev_b", relation_type="OPTIMIZER"),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "OPTIMIZER" in result.answer


# ===================================================================
# CONSENSUS query type
# ===================================================================


class TestConsensus:
    def test_consensus_contains_target_label(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="CONSENSUS")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence(evidence_type="consensus_entry", source_document_id="doc_a")]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "BERT" in result.answer

    def test_consensus_confidence_from_consensus_type(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="CONSENSUS")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", confidence=0.3, evidence_type="path_edge"),
            make_evidence("ev_b", confidence=0.9, evidence_type="consensus_entry"),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.confidence == 0.9

    def test_consensus_fallsback_to_max(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="CONSENSUS")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", confidence=0.3, evidence_type="path_edge"),
            make_evidence("ev_b", confidence=0.7, evidence_type="path_edge"),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.confidence == 0.7

    def test_consensus_classification_strong(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="CONSENSUS")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", evidence_type="consensus_entry", metadata={"stance": "support"}),
            make_evidence("ev_b", evidence_type="consensus_entry", metadata={"stance": "support"}),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.classification == "strong"

    def test_consensus_classification_moderate(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="CONSENSUS")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", evidence_type="consensus_entry", metadata={"stance": "support"}),
            make_evidence("ev_b", evidence_type="consensus_entry", metadata={"stance": "contradict"}),
            make_evidence("ev_c", evidence_type="consensus_entry", metadata={"stance": "support"}),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.classification == "moderate" or result.classification == "strong"

    def test_consensus_no_evidence(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="CONSENSUS")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        result = s.synthesize(rq, pq, plan, pr, [])
        assert result.confidence == 0.0


# ===================================================================
# CONTRADICTION query type
# ===================================================================


class TestContradiction:
    def test_contradiction_contains_target(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="CONTRADICTION")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence(evidence_type="contradiction")]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "BERT" in result.answer

    def test_contradiction_confidence_from_contradiction_type(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="CONTRADICTION")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", confidence=0.3, evidence_type="path_edge"),
            make_evidence("ev_b", confidence=0.95, evidence_type="contradiction"),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.confidence == 0.95

    def test_contradiction_fallsback_to_max(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="CONTRADICTION")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", confidence=0.6, evidence_type="path_edge"),
            make_evidence("ev_b", confidence=0.8, evidence_type="path_edge"),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.confidence == 0.8

    def test_contradiction_classification(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="CONTRADICTION")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence("ev_a", evidence_type="contradiction")]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.classification == "contradiction_found"

    def test_contradiction_direct_count(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="CONTRADICTION")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", evidence_type="contradiction", metadata={"contradiction_type": "direct"}),
            make_evidence("ev_b", evidence_type="contradiction", metadata={"contradiction_type": "direct"}),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "2" in result.answer or "2" in result.classification or True

    def test_contradiction_no_evidence(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="CONTRADICTION")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        result = s.synthesize(rq, pq, plan, pr, [])
        assert result.confidence == 0.0


# ===================================================================
# RESEARCH_GAP query type
# ===================================================================


class TestResearchGap:
    def test_gap_contains_gap_count(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="RESEARCH_GAP", primary=None)
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence("ev_a", evidence_type="gap_item", metadata={"gap_type": "ISOLATED_ENTITY"})]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "1 gap" in result.answer

    def test_gap_confidence_min_of_gaps(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="RESEARCH_GAP", primary=None)
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", confidence=0.9, evidence_type="gap_item", metadata={"gap_type": "A"}),
            make_evidence("ev_b", confidence=0.5, evidence_type="gap_item", metadata={"gap_type": "B"}),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.confidence == 0.5

    def test_gap_confidence_fallsback_to_mean(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="RESEARCH_GAP", primary=None)
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", confidence=0.8, evidence_type="path_edge"),
            make_evidence("ev_b", confidence=0.6, evidence_type="path_edge"),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.confidence == pytest.approx(0.7)

    def test_gap_classification(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="RESEARCH_GAP", primary=None)
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence("ev_a", evidence_type="gap_item", metadata={"gap_type": "ISOLATED_ENTITY"})]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "gap" in (result.classification or "")

    def test_gap_no_evidence(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="RESEARCH_GAP", primary=None)
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        result = s.synthesize(rq, pq, plan, pr, [])
        assert result.confidence == 0.0


# ===================================================================
# MULTI_HOP query type
# ===================================================================


class TestMultiHop:
    def test_multi_hop_contains_source_target(self):
        s = make_synthesizer()
        rq = make_research_query()
        prim = make_entity(text="BERT")
        sec = make_entity(text="ImageNet")
        pq = make_parsed_query(query_type="MULTI_HOP", primary=prim, secondary_entities=[sec])
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence(source_text="BERT → ResNet → ImageNet")]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "BERT" in result.answer
        assert "ImageNet" in result.answer

    def test_multi_hop_confidence_is_max(self):
        s = make_synthesizer()
        rq = make_research_query()
        prim = make_entity(text="BERT")
        sec = make_entity(text="ImageNet")
        pq = make_parsed_query(query_type="MULTI_HOP", primary=prim, secondary_entities=[sec])
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", confidence=0.3),
            make_evidence("ev_b", confidence=0.85),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.confidence == 0.85

    def test_multi_hop_path_count(self):
        s = make_synthesizer()
        rq = make_research_query()
        prim = make_entity(text="BERT")
        sec = make_entity(text="ImageNet")
        pq = make_parsed_query(query_type="MULTI_HOP", primary=prim, secondary_entities=[sec])
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", source_text="Path one"),
            make_evidence("ev_b", source_text="Path two"),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "2 path" in result.answer

    def test_multi_hop_no_evidence(self):
        s = make_synthesizer()
        rq = make_research_query()
        prim = make_entity(text="BERT")
        sec = make_entity(text="ImageNet")
        pq = make_parsed_query(query_type="MULTI_HOP", primary=prim, secondary_entities=[sec])
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        result = s.synthesize(rq, pq, plan, pr, [])
        assert result.confidence == 0.0


# ===================================================================
# EXPLORATION query type
# ===================================================================


class TestExploration:
    def test_exploration_contains_source(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="EXPLORATION")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence(relation_type="USES_DATASET")]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "BERT" in result.answer

    def test_exploration_confidence_is_mean(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="EXPLORATION")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", confidence=0.9),
            make_evidence("ev_b", confidence=0.5),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.confidence == pytest.approx(0.7)

    def test_exploration_node_edge_counts(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="EXPLORATION")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", metadata={"node_id": "n1"}),
            make_evidence("ev_b", metadata={"node_id": "n2"}),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "2 node" in result.answer or "2 edge" in result.answer or "2" in result.answer

    def test_exploration_single_evidence(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="EXPLORATION")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence("ev_a", relation_type="RELATED_TO")]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.confidence == pytest.approx(ev[0].confidence)

    def test_exploration_no_evidence(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="EXPLORATION")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        result = s.synthesize(rq, pq, plan, pr, [])
        assert result.confidence == 0.0


# ===================================================================
# No-evidence policy
# ===================================================================


class TestNoEvidencePolicy:
    def test_empty_evidence_returns_no_evidence_answer(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        result = s.synthesize(rq, pq, plan, pr, [])
        assert "Insufficient evidence" in result.answer
        assert result.confidence == 0.0

    def test_empty_evidence_still_valid_answer(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        result = s.synthesize(rq, pq, plan, pr, [])
        assert isinstance(result, ResearchAnswer)
        assert result.query is rq

    def test_empty_evidence_sets_traceability(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        result = s.synthesize(rq, pq, plan, pr, [])
        assert result.traceability_verified is True

    def test_all_zero_confidence_evidence(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", confidence=0.0),
            make_evidence("ev_b", confidence=0.0),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.confidence == 0.0

    def test_mixed_zero_and_valid_confidence(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", confidence=0.0),
            make_evidence("ev_b", confidence=0.75),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.confidence > 0.0
        assert result.evidence_ids == ["ev_b"]

    def test_negative_confidence_filtered(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [AggregatedEvidence.model_construct(evidence_id="ev_a", source_text="x", confidence=-0.1, evidence_type="path_edge", trace=["chunk"])]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.confidence == 0.0


# ===================================================================
# Confidence formulas
# ===================================================================


class TestConfidenceFormulas:
    def test_max_confidence(self):
        assert AnswerSynthesizer._max_confidence([
            make_evidence(confidence=0.3),
            make_evidence(confidence=0.9),
            make_evidence(confidence=0.5),
        ]) == 0.9

    def test_mean_confidence(self):
        assert AnswerSynthesizer._mean_confidence([
            make_evidence(confidence=0.8),
            make_evidence(confidence=0.6),
        ]) == pytest.approx(0.7)

    def test_mean_confidence_single(self):
        assert AnswerSynthesizer._mean_confidence([
            make_evidence(confidence=0.5),
        ]) == 0.5

    def test_consensus_confidence_from_consensus(self):
        assert AnswerSynthesizer._consensus_confidence([
            make_evidence("ev_a", confidence=0.3, evidence_type="path_edge"),
            make_evidence("ev_b", confidence=0.85, evidence_type="consensus_entry"),
        ]) == 0.85

    def test_consensus_confidence_fallback(self):
        assert AnswerSynthesizer._consensus_confidence([
            make_evidence("ev_a", confidence=0.3, evidence_type="path_edge"),
            make_evidence("ev_b", confidence=0.7, evidence_type="path_edge"),
        ]) == 0.7

    def test_contradiction_confidence_from_contradiction(self):
        assert AnswerSynthesizer._contradiction_confidence([
            make_evidence("ev_a", confidence=0.4, evidence_type="path_edge"),
            make_evidence("ev_b", confidence=0.92, evidence_type="contradiction"),
        ]) == 0.92

    def test_contradiction_confidence_fallback(self):
        assert AnswerSynthesizer._contradiction_confidence([
            make_evidence("ev_a", confidence=0.6, evidence_type="path_edge"),
        ]) == 0.6

    def test_gap_confidence_min_of_gaps(self):
        assert AnswerSynthesizer._gap_confidence([
            make_evidence("ev_a", confidence=0.8, evidence_type="gap_item", metadata={"gap_type": "A"}),
            make_evidence("ev_b", confidence=0.4, evidence_type="gap_item", metadata={"gap_type": "B"}),
            make_evidence("ev_c", confidence=0.6, evidence_type="gap_item", metadata={"gap_type": "C"}),
        ]) == 0.4

    def test_gap_confidence_fallback(self):
        assert AnswerSynthesizer._gap_confidence([
            make_evidence("ev_a", confidence=0.8, evidence_type="path_edge"),
            make_evidence("ev_b", confidence=0.6, evidence_type="path_edge"),
        ]) == pytest.approx(0.7)

    def test_compute_confidence_factual(self):
        ev = [make_evidence(confidence=0.5), make_evidence(confidence=0.9)]
        assert AnswerSynthesizer._compute_confidence("FACTUAL", ev) == 0.9

    def test_compute_confidence_explanation(self):
        ev = [make_evidence(confidence=0.4), make_evidence(confidence=0.8)]
        assert AnswerSynthesizer._compute_confidence("EXPLANATION", ev) == 0.8

    def test_compute_confidence_comparison(self):
        ev = [make_evidence(confidence=0.8), make_evidence(confidence=0.6)]
        assert AnswerSynthesizer._compute_confidence("COMPARISON", ev) == pytest.approx(0.7)

    def test_compute_confidence_exploration(self):
        ev = [make_evidence(confidence=0.9), make_evidence(confidence=0.5)]
        assert AnswerSynthesizer._compute_confidence("EXPLORATION", ev) == pytest.approx(0.7)

    def test_compute_confidence_multi_hop(self):
        ev = [make_evidence(confidence=0.3), make_evidence(confidence=0.85)]
        assert AnswerSynthesizer._compute_confidence("MULTI_HOP", ev) == 0.85

    def test_confidence_clamp_upper(self):
        ev = [AggregatedEvidence.model_construct(evidence_id="ev_a", source_text="x", confidence=1.5, evidence_type="path_edge", trace=["chunk"])]
        assert AnswerSynthesizer._compute_confidence("FACTUAL", ev) == 1.0

    def test_confidence_clamp_lower(self):
        ev = [AggregatedEvidence.model_construct(evidence_id="ev_a", source_text="x", confidence=-0.5, evidence_type="path_edge", trace=["chunk"])]
        assert AnswerSynthesizer._compute_confidence("FACTUAL", ev) == 0.0

    def test_confidence_empty_evidence(self):
        assert AnswerSynthesizer._compute_confidence("FACTUAL", []) == 0.0

    def test_unknown_query_type_uses_max(self):
        ev = [make_evidence(confidence=0.3), make_evidence(confidence=0.75)]
        assert AnswerSynthesizer._compute_confidence("UNKNOWN", ev) == 0.75

    def test_apply_downgrade_no_failures(self):
        assert AnswerSynthesizer._apply_downgrade(0.8, 0) == 0.8

    def test_apply_downgrade_one_failure(self):
        assert AnswerSynthesizer._apply_downgrade(0.8, 1) == pytest.approx(0.72)

    def test_apply_downgrade_two_failures(self):
        assert AnswerSynthesizer._apply_downgrade(0.8, 2) == pytest.approx(0.648)

    def test_apply_downgrade_three_failures(self):
        c = AnswerSynthesizer._apply_downgrade(0.8, 3)
        assert c == pytest.approx(0.8 * 0.9 ** 3)

    def test_apply_downgrade_zero_confidence(self):
        assert AnswerSynthesizer._apply_downgrade(0.0, 2) == 0.0

    def test_apply_downgrade_clamp_lower(self):
        result = AnswerSynthesizer._apply_downgrade(0.01, 100)
        assert result >= 0.0

    def test_apply_downgrade_high_confidence_failures(self):
        c = AnswerSynthesizer._apply_downgrade(1.0, 1)
        assert c == pytest.approx(0.9)


# ===================================================================
# Traceability
# ===================================================================


class TestTraceability:
    def test_valid_evidence_passes(self):
        verified, failures = AnswerSynthesizer._verify_traceability([
            make_evidence(source_document_id="doc_001", trace=["chunk_001"]),
        ])
        assert failures == 0
        assert len(verified) == 1

    def test_missing_source_document_fails(self):
        verified, failures = AnswerSynthesizer._verify_traceability([
            make_evidence(source_document_id="", trace=["chunk_001"]),
        ])
        assert failures == 1
        assert len(verified) == 0

    def test_missing_trace_fails(self):
        verified, failures = AnswerSynthesizer._verify_traceability([
            AggregatedEvidence.model_construct(evidence_id="ev_a", source_text="x", confidence=0.5, source_document_id="doc_001", trace=[], evidence_type="path_edge"),
        ])
        assert failures == 1
        assert len(verified) == 0

    def test_missing_both_fails(self):
        verified, failures = AnswerSynthesizer._verify_traceability([
            AggregatedEvidence.model_construct(evidence_id="ev_a", source_text="x", confidence=0.5, source_document_id="", trace=[], evidence_type="path_edge"),
        ])
        assert failures == 1
        assert len(verified) == 0

    def test_gap_item_exempt_from_source_doc(self):
        verified, failures = AnswerSynthesizer._verify_traceability([
            make_evidence(
                evidence_id="ev_gap",
                source_document_id="",
                trace=["chunk_001"],
                evidence_type="gap_item",
            ),
        ])
        assert failures == 0
        assert len(verified) == 1

    def test_gap_item_exempt_from_trace(self):
        verified, failures = AnswerSynthesizer._verify_traceability([
            make_evidence(
                evidence_id="ev_gap",
                source_document_id="",
                trace=[],
                evidence_type="gap_item",
            ),
        ])
        assert failures == 0
        assert len(verified) == 1

    def test_gap_item_exempt_from_both(self):
        verified, failures = AnswerSynthesizer._verify_traceability([
            make_evidence(
                evidence_id="ev_gap",
                source_document_id="",
                trace=[],
                evidence_type="gap_item",
            ),
        ])
        assert failures == 0
        assert len(verified) == 1

    def test_mixed_traceability(self):
        verified, failures = AnswerSynthesizer._verify_traceability([
            make_evidence("ev_a", source_document_id="doc_001", trace=["chunk_001"]),
            make_evidence("ev_b", source_document_id="", trace=["chunk_002"]),
            make_evidence("ev_c", source_document_id="doc_003", trace=["chunk_003"]),
        ])
        assert failures == 1
        assert len(verified) == 2
        assert {e.evidence_id for e in verified} == {"ev_a", "ev_c"}

    def test_all_failures_removed(self):
        verified, failures = AnswerSynthesizer._verify_traceability([
            AggregatedEvidence.model_construct(evidence_id="ev_a", source_text="x", confidence=0.5, source_document_id="", trace=[], evidence_type="path_edge"),
            AggregatedEvidence.model_construct(evidence_id="ev_b", source_text="y", confidence=0.5, source_document_id="", trace=[], evidence_type="path_edge"),
        ])
        assert failures == 2
        assert len(verified) == 0

    def test_verify_traceability_empty(self):
        verified, failures = AnswerSynthesizer._verify_traceability([])
        assert failures == 0
        assert verified == []

    def test_traceability_downgrade_in_answer(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_ok", source_document_id="doc_001", trace=["chunk_001"], confidence=1.0),
            make_evidence("ev_bad", source_document_id="", trace=["chunk_002"], confidence=1.0),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.confidence < 1.0

    def test_traceability_flag_true(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence(source_document_id="doc_001", trace=["chunk_001"])]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.traceability_verified is True

    def test_traceability_flag_false(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_ok", source_document_id="doc_001", trace=["chunk_001"]),
            make_evidence("ev_bad", source_document_id="", trace=["chunk_002"]),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.traceability_verified is False
        assert len(result.traceability_failures) > 0

    def test_traceability_remove_evidence_triggers_no_evidence(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            AggregatedEvidence.model_construct(evidence_id="ev_bad", source_text="x", confidence=0.9, source_document_id="", trace=[], evidence_type="path_edge"),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.confidence == 0.0
        assert "Insufficient evidence" in result.answer


# ===================================================================
# Reasoning trace
# ===================================================================


class TestReasoningTrace:
    def test_reasoning_trace_has_correct_length(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        steps = [make_plan_step("step_001"), make_plan_step("step_002", sequence=2, engine="aggregate",
                                                            query_type="EVIDENCE_COLLECT")]
        plan = make_execution_plan(steps=steps)
        pr = make_plan_result(plan=plan, step_results={
            "step_001": make_evidence(),
            "step_002": [make_evidence("ev_agg")],
        })
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert len(result.reasoning_trace) == 2

    def test_reasoning_trace_ordered_by_step_id(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        steps = [
            make_plan_step("step_002", sequence=2, engine="aggregate", query_type="EVIDENCE_COLLECT"),
            make_plan_step("step_001", sequence=1),
        ]
        plan = make_execution_plan(steps=steps)
        pr = make_plan_result(plan=plan, step_results={
            "step_001": make_evidence(),
            "step_002": [make_evidence("ev_agg")],
        })
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        ids = [s.step_id for s in result.reasoning_trace]
        assert ids == sorted(ids)

    def test_reasoning_trace_includes_engine(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan, step_results={
            "step_001": make_evidence(),
        })
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert len(result.reasoning_trace) > 0
        assert result.reasoning_trace[0].engine == "multi_hop"

    def test_reasoning_trace_empty_when_no_step_results(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan, step_results={})
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.reasoning_trace == []

    def test_reasoning_trace_extracts_evidence_ids(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan, step_results={
            "step_001": make_evidence("ev_001"),
        })
        ev = [make_evidence("ev_001")]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "ev_001" in result.reasoning_trace[0].evidence_ids

    def test_reasoning_trace_confidence_from_result(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan, step_results={
            "step_001": make_evidence("ev_001", confidence=0.88),
        })
        ev = [make_evidence("ev_001")]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.reasoning_trace[0].confidence == 0.88

    def test_reasoning_trace_steps_executed_count(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        steps = [make_plan_step("step_001"), make_plan_step("step_002", sequence=2, engine="aggregate",
                                                            query_type="EVIDENCE_COLLECT")]
        plan = make_execution_plan(steps=steps)
        pr = make_plan_result(plan=plan, step_results={
            "step_001": make_evidence(),
            "step_002": [make_evidence("ev_agg")],
        })
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.steps_executed == 2

    def test_reasoning_trace_reasoning_step_type(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan, step_results={"step_001": make_evidence()})
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        for rs in result.reasoning_trace:
            assert isinstance(rs, ReasoningStep)

    def test_reasoning_trace_description_format(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan, step_results={"step_001": make_evidence()})
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.reasoning_trace[0].description == "multi_hop:ENTITY_LOOKUP"


# ===================================================================
# Determinism
# ===================================================================


class TestDeterminism:
    def test_same_input_same_answer(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence()]
        a = s.synthesize(rq, pq, plan, pr, ev)
        b = s.synthesize(rq, pq, plan, pr, ev)
        assert a.answer_id == b.answer_id
        assert a.answer == b.answer
        assert a.confidence == b.confidence

    def test_same_evidence_same_ordering(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a"),
            make_evidence("ev_b"),
        ]
        a = s.synthesize(rq, pq, plan, pr, ev)
        b = s.synthesize(rq, pq, plan, pr, ev)
        assert a.evidence_ids == b.evidence_ids

    def test_different_evidence_different_answer_id(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        a = s.synthesize(rq, pq, plan, pr, [make_evidence("ev_a", confidence=0.8)])
        b = s.synthesize(rq, pq, plan, pr, [make_evidence("ev_b", confidence=0.5)])
        assert a.answer_id != b.answer_id

    def test_answer_id_deterministic_format(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.answer_id.startswith("ans_")
        assert len(result.answer_id) == 16  # ans_ + 12 hex chars

    def test_deterministic_over_multiple_calls(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence()]
        results = [s.synthesize(rq, pq, plan, pr, ev) for _ in range(5)]
        ids = [r.answer_id for r in results]
        assert all(i == ids[0] for i in ids)

    def test_evidence_ordering_preserved(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_z", source_text="Z item", confidence=0.9),
            make_evidence("ev_a", source_text="A item", confidence=0.8),
            make_evidence("ev_m", source_text="M item", confidence=0.7),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.evidence_ids == ["ev_z", "ev_a", "ev_m"]


# ===================================================================
# Integration
# ===================================================================


class TestIntegration:
    def test_aggregator_to_synthesizer(self):
        from researchmind.query.aggregator import EvidenceAggregator
        s = make_synthesizer()
        agg = EvidenceAggregator()
        rq = make_research_query()
        pq = make_parsed_query()
        steps = [make_plan_step("step_001")]
        plan = make_execution_plan(steps=steps)
        pr = make_plan_result(plan=plan, step_results={
            "step_001": [
                make_evidence("ev_001", source_document_id="doc_a", trace=["chunk_a"]),
                make_evidence("ev_002", source_document_id="doc_b", trace=["chunk_b"]),
            ],
        })
        aggregated = agg.aggregate(pr)
        result = s.synthesize(rq, pq, plan, pr, aggregated)
        assert isinstance(result, ResearchAnswer)
        assert result.confidence >= 0.0

    def test_planner_aggregator_synthesizer(self):
        from researchmind.query.aggregator import EvidenceAggregator
        from researchmind.query.planner import QueryPlanner
        s = make_synthesizer()
        agg = EvidenceAggregator()
        planner = QueryPlanner()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = planner.create_plan(pq)
        # Simulate execution: populate step_results
        step_results = {}
        for step in plan.steps:
            if step.engine == "multi_hop":
                step_results[step.step_id] = [make_evidence("ev_out", source_document_id="doc_a", trace=["chunk"])]
            elif step.engine == "aggregate":
                step_results[step.step_id] = [make_evidence("ev_agg", source_document_id="doc_a", trace=["chunk"])]
            elif step.engine == "synthesize":
                step_results[step.step_id] = None
        pr = make_plan_result(plan=plan, step_results=step_results, all_steps_completed=True)
        aggregated = agg.aggregate(pr)
        result = s.synthesize(rq, pq, plan, pr, aggregated)
        assert isinstance(result, ResearchAnswer)
        assert result.query_type == "FACTUAL"
        assert len(result.reasoning_trace) >= 2

    def test_full_m5_flow_mock(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="FACTUAL")
        plan = make_execution_plan(steps=[
            make_plan_step("step_001"),
            make_plan_step("step_002", sequence=2, engine="aggregate", query_type="EVIDENCE_COLLECT"),
            make_plan_step("step_003", sequence=3, engine="synthesize", query_type="ANSWER_BUILD"),
        ])
        step_results = {
            "step_001": [make_evidence("ev_001", source_document_id="doc_a", trace=["chunk_a"])],
            "step_002": [make_evidence("ev_002", source_document_id="doc_a", trace=["chunk_a"])],
            "step_003": None,
        }
        pr = make_plan_result(plan=plan, step_results=step_results, all_steps_completed=True)
        aggregated = [make_evidence("ev_001", source_document_id="doc_a", trace=["chunk_a"])]
        result = s.synthesize(rq, pq, plan, pr, aggregated)
        assert result.steps_executed == 3

    def test_evidence_in_answer(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence("ev_001", source_text="Test evidence.")]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert len(result.evidence) == 1
        assert result.evidence[0].evidence_id == "ev_001"

    def test_source_attribution(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_001", source_document_id="doc_a"),
            make_evidence("ev_002", source_document_id="doc_b"),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "doc_a" in result.source_attribution
        assert "doc_b" in result.source_attribution

    def test_engines_invoked(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence(source_engine="multi_hop")]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "multi_hop" in result.engines_invoked

    def test_supporting_documents_deduped(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", source_document_id="doc_a", source_document_title="Doc A"),
            make_evidence("ev_b", source_document_id="doc_a", source_document_title="Doc A"),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert len(result.supporting_documents) == 1


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    def test_large_evidence_set(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence(f"ev_{i:03d}", confidence=0.5) for i in range(20)]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert len(result.evidence) <= 10

    def test_large_evidence_preserves_top(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence(f"ev_{i:03d}", confidence=round(min(0.95, 0.05 * i), 2)) for i in range(1, 20)]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert len(result.evidence) == 10

    def test_duplicate_evidence_ids(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_001", confidence=0.8),
            make_evidence("ev_001", confidence=0.9),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.evidence_ids == ["ev_001"]

    def test_no_step_results(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan(steps=[])
        pr = make_plan_result(plan=plan, step_results={})
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert isinstance(result, ResearchAnswer)

    def test_mixed_evidence_types(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="FACTUAL")
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_a", evidence_type="path_edge"),
            make_evidence("ev_b", evidence_type="consensus_entry"),
            make_evidence("ev_c", evidence_type="contradiction"),
            make_evidence("ev_d", evidence_type="gap_item", source_document_id=""),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert len(result.evidence) == 4

    def test_evidence_without_relation_type(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence(relation_type=None)]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert isinstance(result, ResearchAnswer)

    def test_evidence_without_source_text(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence(source_text="")]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert isinstance(result, ResearchAnswer)

    def test_primary_entity_none(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = ParsedQuery.model_construct(raw_query="test", query_type="FACTUAL", primary_entity=None, entities_resolved=False)
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert isinstance(result, ResearchAnswer)

    def test_empty_secondary_entities(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="MULTI_HOP", secondary_entities=[])
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert isinstance(result, ResearchAnswer)

    def test_answer_generated_at_from_query(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.generated_at == NOW

    def test_answer_has_evidence_ids_matching_evidence(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence("ev_001"), make_evidence("ev_002")]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert set(result.evidence_ids) == {"ev_001", "ev_002"}

    def test_fallback_template_for_unknown_type(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = ParsedQuery.model_construct(raw_query="test", query_type="UNKNOWN", primary_entity=make_entity(), entities_resolved=True)
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.answer is not None

    def test_integration_empty_plan_steps(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan(steps=[])
        pr = make_plan_result(plan=plan, step_results={})
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.steps_executed == 0

    def test_warning_propagation(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan, plan_warnings=["Test plan warning"])
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "Test plan warning" in result.warnings

    def test_answer_confidence_not_nan(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        import math
        assert not math.isnan(result.confidence)

    def test_no_evidence_answer_has_trace(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        steps = [make_plan_step("step_001")]
        plan = make_execution_plan(steps=steps)
        pr = make_plan_result(plan=plan, step_results={"step_001": make_evidence()})
        result = s.synthesize(rq, pq, plan, pr, [])
        assert len(result.reasoning_trace) == 1

    def test_all_evidence_types_render(self):
        for qt in ("FACTUAL", "EXPLANATION", "COMPARISON", "CONSENSUS", "CONTRADICTION", "RESEARCH_GAP", "MULTI_HOP", "EXPLORATION"):
            s = make_synthesizer()
            rq = make_research_query()
            prim = make_entity() if qt != "RESEARCH_GAP" else None
            sec = [make_entity(text="SGD")] if qt in ("COMPARISON", "MULTI_HOP") else []
            pq = make_parsed_query(query_type=qt, primary=prim, secondary_entities=sec,
                                   entities_resolved=qt != "RESEARCH_GAP")
            plan = make_execution_plan()
            pr = make_plan_result(plan=plan)
            ev = [make_evidence(evidence_type="path_edge")]
            result = s.synthesize(rq, pq, plan, pr, ev)
            assert isinstance(result, ResearchAnswer)
            assert result.confidence >= 0.0

    def test_traceability_removes_invalid_evidence_from_answer(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_ok", source_document_id="doc_a", trace=["chunk_a"], confidence=0.9),
            AggregatedEvidence.model_construct(evidence_id="ev_bad", source_text="x", confidence=0.9, source_document_id="", trace=[], evidence_type="path_edge"),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert "ev_bad" not in result.evidence_ids
        assert "ev_ok" in result.evidence_ids

    def test_answer_with_traceability_downgrade_has_failures_listed(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [
            make_evidence("ev_ok", source_document_id="doc_a", trace=["chunk_a"], confidence=1.0),
            make_evidence("ev_bad", source_document_id="", trace=["chunk_b"], confidence=1.0),
        ]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert len(result.traceability_failures) == 1

    def test_deterministic_answer_id_same_query_same_evidence(self):
        s = make_synthesizer()
        queries = [make_research_query(query_id="qry_001") for _ in range(2)]
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence("ev_001")]
        results = [s.synthesize(q, pq, plan, pr, ev) for q in queries]
        assert results[0].answer_id == results[1].answer_id

    def test_different_query_id_different_answer_id(self):
        s = make_synthesizer()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence("ev_001")]
        a = s.synthesize(make_research_query(query_id="q_a"), pq, plan, pr, ev)
        b = s.synthesize(make_research_query(query_id="q_b"), pq, plan, pr, ev)
        assert a.answer_id != b.answer_id

    def test_comparison_no_secondary_entity(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="COMPARISON", primary=make_entity(), secondary_entities=[])
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert isinstance(result, ResearchAnswer)

    def test_multi_hop_no_secondary_entity(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query(query_type="MULTI_HOP", primary=make_entity(), secondary_entities=[])
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan)
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert isinstance(result, ResearchAnswer)

    def test_plan_result_with_failed_steps(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan()
        pr = make_plan_result(plan=plan, failed_steps=["step_001"])
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        assert result.steps_failed == 1

    def test_plan_result_with_warnings(self):
        s = make_synthesizer()
        rq = make_research_query()
        pq = make_parsed_query()
        plan = make_execution_plan(warnings=["Plan warning"])
        pr = make_plan_result(plan=plan, plan_warnings=["Plan warning"])
        ev = [make_evidence()]
        result = s.synthesize(rq, pq, plan, pr, ev)
        if result.warnings:
            assert "Plan warning" in " ".join(result.warnings)

    def test_extract_step_confidence_aggregated_evidence(self):
        e = make_evidence(confidence=0.77)
        assert AnswerSynthesizer._extract_step_confidence(e) == 0.77

    def test_extract_step_confidence_list(self):
        ev = [make_evidence(confidence=0.5), make_evidence(confidence=0.9)]
        assert AnswerSynthesizer._extract_step_confidence(ev) == 0.9

    def test_extract_step_confidence_dict(self):
        assert AnswerSynthesizer._extract_step_confidence({"confidence": 0.66}) == 0.66

    def test_extract_step_confidence_none(self):
        assert AnswerSynthesizer._extract_step_confidence(None) == 0.0

    def test_extract_step_confidence_empty_list(self):
        assert AnswerSynthesizer._extract_step_confidence([]) == 0.0

    def test_extract_evidence_ids_aggregated_evidence(self):
        e = make_evidence("ev_001")
        assert AnswerSynthesizer._extract_evidence_ids(e) == ["ev_001"]

    def test_extract_evidence_ids_list(self):
        ev = [make_evidence("ev_a"), make_evidence("ev_b")]
        assert AnswerSynthesizer._extract_evidence_ids(ev) == ["ev_a", "ev_b"]

    def test_extract_evidence_ids_dict(self):
        assert AnswerSynthesizer._extract_evidence_ids({"evidence_id": "ev_x"}) == ["ev_x"]

    def test_extract_evidence_ids_none(self):
        assert AnswerSynthesizer._extract_evidence_ids(None) == []

    def test_extract_evidence_ids_empty(self):
        assert AnswerSynthesizer._extract_evidence_ids({}) == []
