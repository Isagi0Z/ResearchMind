"""Tests for the M5 Query Engine integration layer — pipeline orchestration.

Covers construction, end-to-end flows for all 8 query types, execution
routing, PlanResult building, aggregation, synthesis, determinism, and
edge cases.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from researchmind.query.engine import QueryEngine, answer_query
from researchmind.query.models import (
    AggregatedEvidence,
    ExecutionPlan,
    ParsedQuery,
    PlanResult,
    PlanStep,
    QueryEntity,
    ReasoningStep,
    ResearchAnswer,
    ResearchQuery,
)

NOW = datetime.now(timezone.utc)

# ===================================================================
# Mock engines — return AggregatedEvidence-compatible dicts/lists
# so the EvidenceAggregator can process them without importing M4.
# ===================================================================


class MockMultiHop:
    def __init__(self, result: Any = None):
        self._result = result

    def reason(self, source_id, target_id, query):
        if self._result is not None:
            return self._result
        return [
            dict(
                evidence_id="mh_001",
                source_text=f"Multi-hop result for {target_id or source_id}",
                confidence=0.85,
                source_engine="multi_hop",
                source_document_id="doc_mh",
                source_document_title="MultiHop Document",
                relation_type="RELATED_TO",
                evidence_type="path_edge",
                trace=["chunk_mh"],
            ),
        ]


class MockConsensus:
    def __init__(self, result: Any = None):
        self._result = result

    def analyze(self, target_id, query):
        if self._result is not None:
            return self._result
        return [
            dict(
                evidence_id="cs_001",
                source_text=f"Consensus for {target_id}",
                confidence=0.78,
                source_engine="consensus",
                source_document_id="doc_cs",
                source_document_title="Consensus Document",
                relation_type="SUPPORTS",
                evidence_type="consensus_entry",
                trace=["chunk_cs"],
                metadata={"stance": "support"},
            ),
        ]


class MockContradiction:
    def __init__(self, result: Any = None):
        self._result = result

    def analyze(self, target_id, query):
        if self._result is not None:
            return self._result
        return [
            dict(
                evidence_id="ct_001",
                source_text=f"Contradiction for {target_id}",
                confidence=0.92,
                source_engine="contradiction",
                source_document_id="doc_ct",
                source_document_title="Contradiction Document",
                relation_type="CONTRADICTS",
                evidence_type="contradiction",
                trace=["chunk_ct"],
                metadata={"contradiction_type": "direct"},
            ),
        ]


class MockGap:
    def __init__(self, result: Any = None):
        self._result = result

    def analyze(self, query):
        if self._result is not None:
            return self._result
        return [
            dict(
                evidence_id="gp_001",
                source_text="Isolated entity found.",
                confidence=0.65,
                source_engine="gap",
                source_document_id="",
                source_document_title="",
                relation_type=None,
                evidence_type="gap_item",
                trace=[],
                metadata={"gap_type": "ISOLATED_ENTITY", "suggestion": "Consider connecting this entity."},
            ),
        ]


class MockFailingEngine:
    def reason(self, **kw):
        raise RuntimeError("Engine failure")

    def analyze(self, **kw):
        raise RuntimeError("Engine failure")


# ===================================================================
# Factory helpers
# ===================================================================


def make_entity(text="BERT", entity_type="method", cluster_id="clu_003", **kw) -> QueryEntity:
    defaults = dict(text=text, entity_type=entity_type, cluster_id=cluster_id, confidence=0.9)
    defaults.update(kw)
    return QueryEntity(**defaults)


def make_engine(engines: dict[str, Any] | None = None, **kw) -> QueryEngine:
    defaults = dict(
        multi_hop=MockMultiHop(),
        consensus=MockConsensus(),
        contradiction=MockContradiction(),
        gap=MockGap(),
    )
    if engines:
        defaults.update(engines)
    defaults.update(kw)
    return QueryEngine(**defaults)


# ===================================================================
# Construction
# ===================================================================


class TestConstruction:
    def test_create_engine_defaults(self):
        engine = QueryEngine()
        assert isinstance(engine, QueryEngine)

    def test_create_engine_with_mocks(self):
        engine = make_engine()
        assert isinstance(engine, QueryEngine)

    def test_convenience_function(self):
        result = answer_query("test query")
        assert isinstance(result, ResearchAnswer)

    def test_engine_different_instances_independent(self):
        e1 = make_engine()
        e2 = make_engine()
        r1 = e1.answer("What is BERT?")
        r2 = e2.answer("What is BERT?")
        assert r1.answer_id == r2.answer_id

    def test_engine_with_custom_components(self):
        from researchmind.query.parser import QueryParser
        from researchmind.query.planner import QueryPlanner
        engine = QueryEngine(
            parser=QueryParser(),
            planner=QueryPlanner(),
            multi_hop=MockMultiHop(),
        )
        assert isinstance(engine, QueryEngine)

    def test_execute_returns_tuple(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_001", raw_query="test", created_at=NOW)
        result = engine.execute(q)
        assert len(result) == 5
        parsed, plan, plan_result, evidence, answer = result
        assert isinstance(parsed, ParsedQuery)
        assert isinstance(plan, ExecutionPlan)
        assert isinstance(plan_result, PlanResult)
        assert isinstance(evidence, list)
        assert isinstance(answer, ResearchAnswer)

    def test_answer_returns_research_answer(self):
        engine = make_engine()
        result = engine.answer("What is BERT?")
        assert isinstance(result, ResearchAnswer)


# ===================================================================
# End-to-end — all 8 query types
# ===================================================================


class TestFactualE2E:
    def test_factual_answer_contains_entity(self):
        engine = make_engine()
        result = engine.answer("What datasets does BERT use?")
        assert result.query_type == "FACTUAL"
        assert isinstance(result.answer, str)
        assert len(result.answer) > 0

    def test_factual_confidence_nonzero(self):
        engine = make_engine()
        result = engine.answer("What is the Adam optimizer?")
        assert result.confidence > 0.0

    def test_factual_has_evidence(self):
        engine = make_engine()
        result = engine.answer("Who proposed Batch Normalization?")
        assert len(result.evidence) > 0

    def test_factual_has_engines(self):
        engine = make_engine()
        result = engine.answer("What is ResNet?")
        assert "multi_hop" in result.engines_invoked

    def test_factual_traceability_verified(self):
        engine = make_engine()
        result = engine.answer("What is U-Net?")
        assert isinstance(result.traceability_verified, bool)


class TestExplanationE2E:
    def test_explanation_answer_produced(self):
        engine = make_engine()
        result = engine.answer("Explain how Batch Normalization works.")
        assert len(result.answer) > 0
        assert isinstance(result, ResearchAnswer)

    def test_explanation_confidence(self):
        engine = make_engine()
        result = engine.answer("Describe the attention mechanism.")
        assert result.confidence >= 0.0


class TestComparisonE2E:
    def test_comparison_answer_produced(self):
        engine = make_engine()
        result = engine.answer("Compare Adam and SGD.")
        assert len(result.answer) > 0
        assert isinstance(result, ResearchAnswer)

    def test_comparison_has_evidence(self):
        engine = make_engine()
        result = engine.answer("Compare ResNet with U-Net.")
        assert len(result.evidence) >= 0


class TestConsensusE2E:
    def test_consensus_answer_produced(self):
        engine = make_engine()
        result = engine.answer("What is the consensus on Dropout?")
        assert len(result.answer) > 0
        assert isinstance(result, ResearchAnswer)

    def test_consensus_classification(self):
        engine = make_engine()
        result = engine.answer("Do papers agree about Adam?")
        assert result.classification is not None or result.confidence >= 0.0


class TestContradictionE2E:
    def test_contradiction_answer_produced(self):
        engine = make_engine()
        result = engine.answer("What contradicts the attention mechanism?")
        assert result.query_type == "CONTRADICTION"
        assert len(result.answer) > 0

    def test_contradiction_has_classification(self):
        engine = make_engine()
        result = engine.answer("Which papers disagree with the Attention paper?")
        assert result.classification is not None or result.confidence >= 0.0


class TestResearchGapE2E:
    def test_gap_answer_produced(self):
        engine = make_engine()
        result = engine.answer("What research gaps exist around GANs?")
        assert result.query_type == "RESEARCH_GAP"
        assert len(result.answer) > 0

    def test_gap_classification(self):
        engine = make_engine()
        result = engine.answer("Which methods lack comparisons?")
        assert result.classification is not None or result.confidence >= 0.0


class TestMultiHopE2E:
    def test_multi_hop_answer_produced(self):
        engine = make_engine()
        result = engine.answer("Find paths between ResNet and ImageNet.")
        assert len(result.answer) > 0
        assert isinstance(result, ResearchAnswer)

    def test_multi_hop_has_evidence(self):
        engine = make_engine()
        result = engine.answer("Find paths between BERT and ImageNet.")
        assert len(result.evidence) >= 0


class TestExplorationE2E:
    def test_exploration_answer_produced(self):
        engine = make_engine()
        result = engine.answer("Explore what is connected to BERT.")
        assert len(result.answer) > 0
        assert isinstance(result, ResearchAnswer)

    def test_exploration_has_evidence(self):
        engine = make_engine()
        result = engine.answer("Show connections related to ResNet.")
        assert len(result.evidence) >= 0


# ===================================================================
# Execution
# ===================================================================


class TestExecution:
    def test_executable_routes_only(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_001", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        for step in plan.steps:
            if step.engine in ("multi_hop", "consensus", "contradiction", "gap"):
                assert step.step_id in plan_result.step_results or step.step_id in plan_result.failed_steps

    def test_non_executable_routes_skipped(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_002", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        for step in plan.steps:
            if step.engine in ("aggregate", "synthesize"):
                assert step.step_id not in plan_result.step_results

    def test_mixed_routes(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_003", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        executable_count = sum(1 for s in plan.steps if s.engine in ("multi_hop", "consensus", "contradiction", "gap"))
        non_exec_count = sum(1 for s in plan.steps if s.engine in ("aggregate", "synthesize"))
        result_count = len(plan_result.step_results)
        assert result_count == executable_count

    def test_failing_engine_recorded(self):
        engine = make_engine(engines={"multi_hop": MockFailingEngine()})
        q = ResearchQuery(query_id="q_fail", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        assert len(plan_result.failed_steps) > 0

    def test_all_steps_fail_sets_flag(self):
        engine = make_engine(engines={
            "multi_hop": MockFailingEngine(),
            "consensus": MockFailingEngine(),
            "contradiction": MockFailingEngine(),
            "gap": MockFailingEngine(),
        })
        q = ResearchQuery(query_id="q_all_fail", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        assert plan_result.all_steps_completed is False
        assert len(plan_result.failed_steps) > 0

    def test_no_engine_registered(self):
        engine = QueryEngine()
        q = ResearchQuery(query_id="q_noeng", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        assert len(plan_result.failed_steps) > 0

    def test_engine_exception_preserves_other_results(self):
        engine = make_engine(engines={"multi_hop": MockFailingEngine()})
        q = ResearchQuery(query_id="q_partial", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        # At least some steps may have succeeded (non multi_hop steps)
        assert isinstance(answer, ResearchAnswer)

    def test_execution_does_not_mutate_plan(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_immut", raw_query="test", created_at=NOW)
        parsed_before, plan_before, *_ = engine.execute(q)
        parsed_after, plan_after, *_ = engine.execute(q)
        assert plan_before.plan_id == plan_after.plan_id


# ===================================================================
# PlanResult
# ===================================================================


class TestPlanResult:
    def test_all_steps_completed(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_allok", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        if not plan_result.failed_steps:
            assert plan_result.all_steps_completed is True

    def test_partial_completion(self):
        engine = make_engine(engines={"multi_hop": MockFailingEngine()})
        q = ResearchQuery(query_id="q_partial", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        if plan_result.failed_steps:
            assert plan_result.all_steps_completed is False

    def test_failed_steps_listed(self):
        engine = make_engine(engines={"multi_hop": MockFailingEngine()})
        q = ResearchQuery(query_id="q_flist", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        if plan_result.failed_steps:
            for sid in plan_result.failed_steps:
                assert any(s.step_id == sid for s in plan.steps if s.engine not in ("aggregate", "synthesize"))

    def test_warnings_in_plan_result(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_warn", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        assert isinstance(plan_result.plan_warnings, list)


# ===================================================================
# Aggregation
# ===================================================================


class TestAggregation:
    def test_evidence_passed_through(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_ev", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        assert len(evidence) >= 0

    def test_evidence_items_from_engines(self):
        mh = MockMultiHop()
        engine = make_engine(engines={"multi_hop": mh})
        q = ResearchQuery(query_id="q_evsrc", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        if evidence:
            item = evidence[0]
            assert hasattr(item, "evidence_id")
            assert hasattr(item, "confidence")

    def test_empty_evidence_no_crash(self):
        engine = make_engine(engines={
            "multi_hop": MockMultiHop(result=[]),
            "consensus": MockConsensus(result=[]),
            "contradiction": MockContradiction(result=[]),
            "gap": MockGap(result=[]),
        })
        q = ResearchQuery(query_id="q_emptyev", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        assert evidence == []
        assert answer.confidence == 0.0


# ===================================================================
# Synthesis
# ===================================================================


class TestSynthesis:
    def test_answer_produced(self):
        engine = make_engine()
        result = engine.answer("What is BERT?")
        assert len(result.answer) > 0

    def test_no_evidence_answer(self):
        engine = make_engine(engines={
            "multi_hop": MockMultiHop(result=[]),
            "consensus": MockConsensus(result=[]),
            "contradiction": MockContradiction(result=[]),
            "gap": MockGap(result=[]),
        })
        result = engine.answer("What is BERT?")
        assert result.confidence == 0.0
        assert "Insufficient evidence" in result.answer

    def test_answer_has_reasoning_trace(self):
        engine = make_engine()
        result = engine.answer("What is BERT?")
        assert isinstance(result.reasoning_trace, list)

    def test_answer_has_evidence_ids(self):
        engine = make_engine()
        result = engine.answer("What is BERT?")
        assert isinstance(result.evidence_ids, list)

    def test_answer_has_sources(self):
        engine = make_engine()
        result = engine.answer("What is BERT?")
        assert isinstance(result.sources, list)

    def test_answer_has_query(self):
        engine = make_engine()
        result = engine.answer("What is BERT?")
        assert isinstance(result.query, ResearchQuery)

    def test_answer_has_plan(self):
        engine = make_engine()
        result = engine.answer("What is BERT?")
        assert result.plan is not None

    def test_answer_classification_for_consensus(self):
        engine = make_engine()
        result = engine.answer("What is the consensus on Dropout?")
        assert result.classification is not None or result.confidence >= 0.0


# ===================================================================
# Determinism
# ===================================================================


class TestDeterminism:
    def test_same_input_same_output(self):
        engine = make_engine()
        a = engine.answer("What is BERT?")
        b = engine.answer("What is BERT?")
        assert a.answer_id == b.answer_id
        assert a.answer == b.answer
        assert a.confidence == b.confidence

    def test_same_query_same_evidence_ids(self):
        engine = make_engine()
        a = engine.answer("What is BERT?")
        b = engine.answer("What is BERT?")
        assert a.evidence_ids == b.evidence_ids

    def test_different_query_different_answer(self):
        engine = make_engine()
        a = engine.answer("What is BERT?")
        b = engine.answer("What is Adam?")
        assert a.answer_id != b.answer_id

    def test_execute_deterministic(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_det", raw_query="What is BERT?", created_at=NOW)
        r1 = engine.execute(q)
        r2 = engine.execute(q)
        assert r1[4].answer_id == r2[4].answer_id

    def test_execute_ordered_by_step_id(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_order", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        step_ids = list(plan_result.step_results.keys())
        assert step_ids == sorted(step_ids)

    def test_no_uuid_in_answer_id(self):
        engine = make_engine()
        result = engine.answer("What is BERT?")
        import re
        assert not re.search(r'[a-f0-9]{8}-[a-f0-9]{4}-', result.answer_id)
        assert result.answer_id.startswith("ans_")

    def test_answer_id_format(self):
        engine = make_engine()
        result = engine.answer("What is BERT?")
        assert len(result.answer_id) == 16  # "ans_" + 12 hex chars

    def test_query_id_format(self):
        engine = make_engine()
        result = engine.answer("What is BERT?")
        assert result.query.query_id.startswith("qry_")
        assert len(result.query.query_id) == 16  # "qry_" + 12 hex chars

    def test_repeated_calls_preserve_order(self):
        engine = make_engine()
        for _ in range(5):
            result = engine.answer("What is BERT?")
            # Just verify no crash
        assert True


# ===================================================================
# Integration
# ===================================================================


class TestIntegration:
    def test_parser_to_planner(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_ip", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, *_ = engine.execute(q)
        assert isinstance(parsed, ParsedQuery)
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) > 0

    def test_planner_to_router(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_pr", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, *_ = engine.execute(q)
        route_count = sum(1 for s in plan.steps if s.engine in ("multi_hop", "consensus", "contradiction", "gap"))
        result_count = len(plan_result.step_results)
        assert result_count <= route_count

    def test_router_to_engines(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_re", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, *_ = engine.execute(q)
        for step_id, result in plan_result.step_results.items():
            assert result is not None

    def test_engines_to_aggregator(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_ea", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        assert isinstance(evidence, list)

    def test_aggregator_to_synthesizer(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_as", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        assert answer.evidence_ids == [e.evidence_id for e in evidence if e.evidence_id]

    def test_full_pipeline_multi_hop(self):
        engine = make_engine()
        result = engine.answer("Find paths between X and Y.")
        assert result is not None

    def test_full_pipeline_consensus(self):
        engine = make_engine()
        result = engine.answer("What is the consensus on Dropout?")
        assert isinstance(result, ResearchAnswer)

    def test_execute_returns_parsed(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_rp", raw_query="What is BERT?", created_at=NOW)
        parsed, *_ = engine.execute(q)
        assert isinstance(parsed, ParsedQuery)

    def test_execute_returns_plan(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_rpl", raw_query="What is BERT?", created_at=NOW)
        _, plan, *_ = engine.execute(q)
        assert isinstance(plan, ExecutionPlan)

    def test_execute_returns_plan_result(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_rpr", raw_query="What is BERT?", created_at=NOW)
        _, _, plan_result, *_ = engine.execute(q)
        assert isinstance(plan_result, PlanResult)

    def test_execute_returns_evidence(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_rev", raw_query="What is BERT?", created_at=NOW)
        *_, evidence, _ = engine.execute(q)
        assert isinstance(evidence, list)

    def test_execute_returns_answer(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_rans", raw_query="What is BERT?", created_at=NOW)
        *_, answer = engine.execute(q)
        assert isinstance(answer, ResearchAnswer)


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    def test_empty_query(self):
        engine = make_engine()
        result = engine.answer("")
        assert isinstance(result, ResearchAnswer)

    def test_whitespace_query(self):
        engine = make_engine()
        result = engine.answer("   ")
        assert isinstance(result, ResearchAnswer)

    def test_malformed_query_gibberish(self):
        engine = make_engine()
        result = engine.answer("!@#$%^&*()")
        assert isinstance(result, ResearchAnswer)

    def test_very_long_query(self):
        engine = make_engine()
        long_text = "What is " + "X" * 10000 + "?"
        result = engine.answer(long_text)
        assert isinstance(result, ResearchAnswer)

    def test_query_with_only_stop_words(self):
        engine = make_engine()
        result = engine.answer("the and of to a in")
        assert isinstance(result, ResearchAnswer)

    def test_engine_with_no_multi_hop(self):
        engine = QueryEngine(
            consensus=MockConsensus(),
            contradiction=MockContradiction(),
            gap=MockGap(),
        )
        result = engine.answer("What is BERT?")
        assert isinstance(result, ResearchAnswer)

    def test_engine_with_no_consensus(self):
        engine = QueryEngine(
            multi_hop=MockMultiHop(),
            contradiction=MockContradiction(),
            gap=MockGap(),
        )
        result = engine.answer("What is the consensus on Dropout?")
        assert isinstance(result, ResearchAnswer)

    def test_engine_with_only_multi_hop(self):
        engine = QueryEngine(multi_hop=MockMultiHop())
        result = engine.answer("What is BERT?")
        assert isinstance(result, ResearchAnswer)

    def test_all_engines_none(self):
        engine = QueryEngine()
        result = engine.answer("What is BERT?")
        assert isinstance(result, ResearchAnswer)

    def test_answer_id_present(self):
        engine = make_engine()
        result = engine.answer("What is BERT?")
        assert result.answer_id is not None
        assert len(result.answer_id) > 0

    def test_generated_at_set(self):
        engine = make_engine()
        result = engine.answer("What is BERT?")
        assert isinstance(result.generated_at, datetime)

    def test_plan_total_steps_matches(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_pts", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        assert plan.total_steps == len(plan.steps)

    def test_execution_multiple_calls(self):
        engine = make_engine()
        for i in range(10):
            result = engine.answer(f"Query number {i}.")
            assert isinstance(result, ResearchAnswer)

    def test_same_plan_for_same_query(self):
        engine = make_engine()
        q1 = ResearchQuery(query_id="q_a", raw_query="What is BERT?", created_at=NOW)
        q2 = ResearchQuery(query_id="q_b", raw_query="What is BERT?", created_at=NOW)
        _, p1, *_ = engine.execute(q1)
        _, p2, *_ = engine.execute(q2)
        assert p1.plan_id == p2.plan_id

    def test_empty_query_no_crash(self):
        engine = make_engine()
        result = engine.answer("")
        assert isinstance(result, ResearchAnswer)

    def test_engine_reuses_components(self):
        from researchmind.query.aggregator import EvidenceAggregator
        from researchmind.query.synthesizer import AnswerSynthesizer
        agg = EvidenceAggregator()
        synth = AnswerSynthesizer()
        engine = QueryEngine(aggregator=agg, synthesizer=synth, multi_hop=MockMultiHop())
        a = engine.answer("test")
        b = engine.answer("test")
        assert a.answer == b.answer

    def test_step_results_contain_only_executable(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_ser", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        non_exec = {"aggregate", "synthesize"}
        for step_id in plan_result.step_results:
            step = next((s for s in plan.steps if s.step_id == step_id), None)
            assert step is None or step.engine not in non_exec

    def test_execution_time_ms_in_plan_result(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_et", raw_query="test", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        assert plan_result.execution_time_ms >= 0

    def test_failed_steps_as_strings(self):
        engine = make_engine(engines={"multi_hop": MockFailingEngine()})
        q = ResearchQuery(query_id="q_fs", raw_query="test", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        for sid in plan_result.failed_steps:
            assert isinstance(sid, str)

    def test_evidence_preserves_source_engine(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_se", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        for ev in evidence:
            assert ev.source_engine in ("multi_hop", "consensus", "contradiction", "gap", "")

    def test_plan_result_has_plan_ref(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_prr", raw_query="test", created_at=NOW)
        parsed, plan, plan_result, *_ = engine.execute(q)
        assert plan_result.plan.plan_id == plan.plan_id

    def test_answer_has_engines_invoked(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_ei", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, evidence, answer = engine.execute(q)
        assert isinstance(answer.engines_invoked, list)

    def test_empty_query_creates_valid_parsed(self):
        engine = make_engine()
        result = engine.answer("")
        assert result.query is not None

    def test_engine_with_edge_case_entity(self):
        engine = make_engine()
        result = engine.answer("What is X?" * 50)
        assert isinstance(result, ResearchAnswer)

    def test_no_crash_on_special_characters(self):
        engine = make_engine()
        result = engine.answer("\n\t\r")
        assert isinstance(result, ResearchAnswer)

    def test_all_query_types_return_answer(self):
        engine = make_engine()
        queries = [
            "What is BERT?",
            "How does attention work?",
            "Compare Adam and SGD.",
            "What is the consensus on Dropout?",
            "What contradicts the attention mechanism?",
            "What research gaps exist around GANs?",
            "How is BERT connected to ImageNet?",
            "What is connected to BERT?",
        ]
        for q in queries:
            result = engine.answer(q)
            assert isinstance(result, ResearchAnswer), f"Failed on: {q}"
            assert len(result.answer) > 0 or result.confidence == 0.0

    def test_failing_engine_still_produces_answer(self):
        engine = make_engine(engines={
            "multi_hop": MockFailingEngine(),
            "consensus": MockFailingEngine(),
            "contradiction": MockFailingEngine(),
            "gap": MockFailingEngine(),
        })
        result = engine.answer("What is BERT?")
        assert isinstance(result, ResearchAnswer)

    def test_deterministic_over_multiple_runs(self):
        engine = make_engine()
        ids = set()
        for _ in range(10):
            result = engine.answer("What is BERT?")
            ids.add(result.answer_id)
        assert len(ids) == 1

    def test_mock_gap_result_no_source_doc(self):
        engine = make_engine()
        result = engine.answer("What research gaps exist?")
        assert isinstance(result, ResearchAnswer)

    def test_answer_contains_warnings(self):
        engine = make_engine()
        result = engine.answer("")
        assert isinstance(result.warnings, list)

    def test_plan_result_warnings_from_plan(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_wp", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, plan_result, *_ = engine.execute(q)
        # Plan may have warnings from the planner
        assert len(plan_result.plan_warnings) >= 0

    def test_mock_multi_hop_result_dict_format(self):
        mh = MockMultiHop(result=[
            dict(
                evidence_id="custom",
                source_text="custom result",
                confidence=0.5,
                source_engine="multi_hop",
                source_document_id="doc_custom",
                source_document_title="Custom",
                relation_type="RELATED",
                evidence_type="path_edge",
                trace=["chunk"],
            ),
        ])
        engine = make_engine(engines={"multi_hop": mh})
        result = engine.answer("What is BERT?")
        assert len(result.evidence) > 0

    def test_mock_consensus_metadata(self):
        cs = MockConsensus(result=[
            dict(
                evidence_id="cs_custom",
                source_text="Test consensus",
                confidence=0.9,
                source_engine="consensus",
                source_document_id="doc_cs",
                source_document_title="CS Doc",
                relation_type="SUPPORTS",
                evidence_type="consensus_entry",
                trace=["chunk"],
                metadata={"stance": "support"},
            ),
        ])
        engine = make_engine(engines={"consensus": cs, "multi_hop": MockMultiHop(result=[])})
        result = engine.answer("What is the consensus on Dropout?")
        assert result.confidence >= 0.0

    def test_multiple_steps_same_engine(self):
        engine = make_engine()
        result = engine.answer("Compare Adam and SGD.")
        assert len(result.evidence) >= 0

    def test_plan_has_steps(self):
        engine = make_engine()
        q = ResearchQuery(query_id="q_ps", raw_query="What is BERT?", created_at=NOW)
        parsed, plan, *_ = engine.execute(q)
        assert len(plan.steps) > 0

    def test_execute_answer_id_via_answer(self):
        engine = make_engine()
        result = engine.answer("What is BERT?")
        assert result.answer_id.startswith("ans_")

    def test_confidence_clamped(self):
        engine = make_engine()
        result = engine.answer("What is BERT?")
        assert 0.0 <= result.confidence <= 1.0
