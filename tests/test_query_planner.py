"""Tests for the M5 query planner — ExecutionPlan generation from ParsedQuery.

Covers all 8 query types, parallel group computation, complexity estimation,
validation, metadata, edge cases, and determinism guarantees.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from researchmind.query.models import ExecutionPlan, ParsedQuery, PlanStep, QueryEntity
from researchmind.query.planner import QueryPlanner, create_plan

# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_entity(text="BERT", cluster_id="clu_003", **kw) -> QueryEntity:
    defaults = dict(text=text, cluster_id=cluster_id, confidence=0.9, entity_type="method")
    defaults.update(kw)
    return QueryEntity(**defaults)


def make_parsed(query_type="FACTUAL", **kw) -> ParsedQuery:
    defaults = dict(
        raw_query="test query",
        query_type=query_type,
        primary_entity=make_entity(),
        entities_resolved=True,
    )
    defaults.update(kw)
    return ParsedQuery(**defaults)


def make_planner() -> QueryPlanner:
    return QueryPlanner()


# ===================================================================
# Planner construction
# ===================================================================


class TestPlannerConstruction:
    def test_create_planner(self):
        planner = make_planner()
        assert isinstance(planner, QueryPlanner)

    def test_create_plan_factual(self):
        planner = make_planner()
        plan = planner.create_plan(make_parsed("FACTUAL"))
        assert isinstance(plan, ExecutionPlan)

    def test_create_plan_explanation(self):
        plan = create_plan(make_parsed("EXPLANATION"))
        assert isinstance(plan, ExecutionPlan)

    def test_create_plan_comparison(self):
        plan = create_plan(make_parsed("COMPARISON"))
        assert isinstance(plan, ExecutionPlan)

    def test_create_plan_consensus(self):
        plan = create_plan(make_parsed("CONSENSUS"))
        assert isinstance(plan, ExecutionPlan)

    def test_create_plan_contradiction(self):
        plan = create_plan(make_parsed("CONTRADICTION"))
        assert isinstance(plan, ExecutionPlan)

    def test_create_plan_research_gap(self):
        plan = create_plan(make_parsed("RESEARCH_GAP"))
        assert isinstance(plan, ExecutionPlan)

    def test_create_plan_multi_hop(self):
        plan = create_plan(make_parsed("MULTI_HOP"))
        assert isinstance(plan, ExecutionPlan)

    def test_create_plan_exploration(self):
        plan = create_plan(make_parsed("EXPLORATION"))
        assert isinstance(plan, ExecutionPlan)

    def test_unsupported_query_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported query type"):
            pq = ParsedQuery.model_construct(
                raw_query="test query", query_type="UNKNOWN"
            )
            create_plan(pq)

    def test_plan_id_is_string(self):
        plan = create_plan(make_parsed())
        assert isinstance(plan.plan_id, str)
        assert plan.plan_id.startswith("plan_")


# ===================================================================
# FACTUAL plan
# ===================================================================


class TestPlanFactual:
    def test_step_count(self):
        plan = create_plan(make_parsed("FACTUAL"))
        assert len(plan.steps) == 3

    def test_step_ids_sequential(self):
        plan = create_plan(make_parsed("FACTUAL"))
        ids = [s.step_id for s in plan.steps]
        assert ids == ["step_001", "step_002", "step_003"]

    def test_sequences_sequential(self):
        plan = create_plan(make_parsed("FACTUAL"))
        seqs = [s.sequence for s in plan.steps]
        assert seqs == [1, 2, 3]

    def test_step1_entity_lookup(self):
        plan = create_plan(make_parsed("FACTUAL"))
        s = plan.steps[0]
        assert s.engine == "multi_hop"
        assert s.query_type == "ENTITY_LOOKUP"
        assert s.target_id == "clu_003"
        assert s.dependencies == []

    def test_step2_evidence_collect(self):
        plan = create_plan(make_parsed("FACTUAL"))
        s = plan.steps[1]
        assert s.engine == "aggregate"
        assert s.query_type == "EVIDENCE_COLLECT"
        assert s.dependencies == ["step_001"]

    def test_step3_answer_build(self):
        plan = create_plan(make_parsed("FACTUAL"))
        s = plan.steps[2]
        assert s.engine == "synthesize"
        assert s.query_type == "ANSWER_BUILD"
        assert s.dependencies == ["step_002"]

    def test_entity_lookup_params(self):
        plan = create_plan(make_parsed("FACTUAL"))
        params = plan.steps[0].parameters
        assert params.get("max_depth") == 2

    def test_evidence_collect_params(self):
        plan = create_plan(make_parsed("FACTUAL"))
        params = plan.steps[1].parameters
        assert params.get("dedup_by") == "evidence_id"

    def test_answer_build_template(self):
        plan = create_plan(make_parsed("FACTUAL"))
        params = plan.steps[2].parameters
        assert params.get("template") == "factual"

    def test_parallel_groups_empty(self):
        plan = create_plan(make_parsed("FACTUAL"))
        assert plan.parallel_groups == [["step_001"], ["step_002"], ["step_003"]]

    def test_complexity_low(self):
        plan = create_plan(make_parsed("FACTUAL"))
        assert plan.estimated_complexity == "medium"

    def test_no_entity_target(self):
        plan = create_plan(make_parsed("FACTUAL", primary_entity=None, entities_resolved=False))
        assert plan.steps[0].target_id is None
        assert plan.steps[1].target_id is None


# ===================================================================
# EXPLANATION plan
# ===================================================================


class TestPlanExplanation:
    def test_step_count(self):
        plan = create_plan(make_parsed("EXPLANATION"))
        assert len(plan.steps) == 4

    def test_step_ids(self):
        plan = create_plan(make_parsed("EXPLANATION"))
        assert [s.step_id for s in plan.steps] == ["step_001", "step_002", "step_003", "step_004"]

    def test_step1_entity_lookup(self):
        plan = create_plan(make_parsed("EXPLANATION"))
        s = plan.steps[0]
        assert s.engine == "multi_hop"
        assert s.query_type == "ENTITY_LOOKUP"

    def test_step2_graph_exploration(self):
        plan = create_plan(make_parsed("EXPLANATION"))
        s = plan.steps[1]
        assert s.engine == "multi_hop"
        assert s.query_type == "GRAPH_EXPLORATION"
        assert s.dependencies == ["step_001"]

    def test_step3_evidence_collect(self):
        plan = create_plan(make_parsed("EXPLANATION"))
        s = plan.steps[2]
        assert s.engine == "aggregate"
        assert s.query_type == "EVIDENCE_COLLECT"
        assert s.dependencies == ["step_002"]

    def test_step4_answer_build(self):
        plan = create_plan(make_parsed("EXPLANATION"))
        s = plan.steps[3]
        assert s.engine == "synthesize"
        assert s.dependencies == ["step_003"]

    def test_answer_template(self):
        plan = create_plan(make_parsed("EXPLANATION"))
        assert plan.steps[3].parameters.get("template") == "explanation"

    def test_parallel_groups(self):
        plan = create_plan(make_parsed("EXPLANATION"))
        expected = [["step_001"], ["step_002"], ["step_003"], ["step_004"]]
        assert plan.parallel_groups == expected

    def test_complexity_medium(self):
        plan = create_plan(make_parsed("EXPLANATION"))
        assert plan.estimated_complexity == "medium"

    def test_graph_explore_max_depth(self):
        plan = create_plan(make_parsed("EXPLANATION", max_hops=5))
        assert plan.steps[1].parameters.get("max_depth") == 3


# ===================================================================
# COMPARISON plan
# ===================================================================


class TestPlanComparison:
    def test_step_count(self):
        plan = create_plan(make_parsed("COMPARISON"))
        assert len(plan.steps) == 5

    def test_step_ids(self):
        plan = create_plan(make_parsed("COMPARISON"))
        expected = ["step_001", "step_002", "step_003", "step_004", "step_005"]
        assert [s.step_id for s in plan.steps] == expected

    def test_steps_1_and_2_entity_lookups(self):
        plan = create_plan(make_parsed("COMPARISON"))
        assert plan.steps[0].engine == "multi_hop"
        assert plan.steps[0].query_type == "ENTITY_LOOKUP"
        assert plan.steps[1].engine == "multi_hop"
        assert plan.steps[1].query_type == "ENTITY_LOOKUP"

    def test_step1_target_primary(self):
        plan = create_plan(make_parsed("COMPARISON", primary_entity=make_entity("A", "clu_a")))
        assert plan.steps[0].target_id == "clu_a"

    def test_step2_target_secondary(self):
        sec = [make_entity("B", "clu_b")]
        plan = create_plan(make_parsed("COMPARISON", secondary_entities=sec))
        assert plan.steps[1].target_id == "clu_b"

    def test_step3_compare(self):
        plan = create_plan(make_parsed("COMPARISON"))
        s = plan.steps[2]
        assert s.engine == "consensus"
        assert s.query_type == "COMPARISON_ANALYSIS"
        assert s.dependencies == ["step_001", "step_002"]

    def test_step4_evidence_collect(self):
        plan = create_plan(make_parsed("COMPARISON"))
        assert plan.steps[3].dependencies == ["step_003"]

    def test_step5_answer_build(self):
        plan = create_plan(make_parsed("COMPARISON"))
        assert plan.steps[4].dependencies == ["step_004"]
        assert plan.steps[4].parameters.get("template") == "comparison"

    def test_parallel_groups(self):
        plan = create_plan(make_parsed("COMPARISON"))
        expected = [["step_001", "step_002"], ["step_003"], ["step_004"], ["step_005"]]
        assert plan.parallel_groups == expected

    def test_compare_target_and_secondary(self):
        sec = [make_entity("B", "clu_b")]
        plan = create_plan(make_parsed("COMPARISON", secondary_entities=sec))
        s = plan.steps[2]
        assert s.target_id == "clu_003"
        assert s.secondary_ids == ["clu_b"]

    def test_no_secondary_entity(self):
        plan = create_plan(make_parsed("COMPARISON", secondary_entities=[]))
        assert plan.steps[1].target_id is None
        assert plan.steps[2].secondary_ids == []

    def test_complexity_medium(self):
        plan = create_plan(make_parsed("COMPARISON"))
        assert plan.estimated_complexity == "medium"


# ===================================================================
# CONSENSUS plan
# ===================================================================


class TestPlanConsensus:
    def test_step_count(self):
        plan = create_plan(make_parsed("CONSENSUS"))
        assert len(plan.steps) == 4

    def test_step_ids(self):
        plan = create_plan(make_parsed("CONSENSUS"))
        assert [s.step_id for s in plan.steps] == ["step_001", "step_002", "step_003", "step_004"]

    def test_step1_entity_lookup(self):
        plan = create_plan(make_parsed("CONSENSUS"))
        assert plan.steps[0].query_type == "ENTITY_LOOKUP"

    def test_step2_consensus_analysis(self):
        plan = create_plan(make_parsed("CONSENSUS"))
        s = plan.steps[1]
        assert s.engine == "consensus"
        assert s.query_type == "CONSENSUS_ANALYSIS"
        assert s.dependencies == ["step_001"]

    def test_step2_min_confidence_param(self):
        plan = create_plan(make_parsed("CONSENSUS", min_confidence=0.5))
        assert plan.steps[1].parameters.get("min_confidence") == 0.5

    def test_step3_evidence_collect(self):
        plan = create_plan(make_parsed("CONSENSUS"))
        assert plan.steps[2].dependencies == ["step_002"]
        assert plan.steps[2].parameters.get("dedup_by") == "doc_id"

    def test_step4_answer_build(self):
        plan = create_plan(make_parsed("CONSENSUS"))
        assert plan.steps[3].parameters.get("template") == "consensus"

    def test_parallel_groups(self):
        plan = create_plan(make_parsed("CONSENSUS"))
        expected = [["step_001"], ["step_002"], ["step_003"], ["step_004"]]
        assert plan.parallel_groups == expected


# ===================================================================
# CONTRADICTION plan
# ===================================================================


class TestPlanContradiction:
    def test_step_count(self):
        plan = create_plan(make_parsed("CONTRADICTION"))
        assert len(plan.steps) == 4

    def test_step_ids(self):
        plan = create_plan(make_parsed("CONTRADICTION"))
        assert [s.step_id for s in plan.steps] == ["step_001", "step_002", "step_003", "step_004"]

    def test_step1_entity_lookup(self):
        plan = create_plan(make_parsed("CONTRADICTION"))
        assert plan.steps[0].query_type == "ENTITY_LOOKUP"

    def test_step2_contradiction_analysis(self):
        plan = create_plan(make_parsed("CONTRADICTION"))
        s = plan.steps[1]
        assert s.engine == "contradiction"
        assert s.query_type == "CONTRADICTION_ANALYSIS"
        assert s.dependencies == ["step_001"]

    def test_step3_evidence_collect(self):
        plan = create_plan(make_parsed("CONTRADICTION"))
        assert plan.steps[2].dependencies == ["step_002"]

    def test_step4_answer_build(self):
        plan = create_plan(make_parsed("CONTRADICTION"))
        assert plan.steps[3].parameters.get("template") == "contradiction"

    def test_parallel_groups(self):
        plan = create_plan(make_parsed("CONTRADICTION"))
        expected = [["step_001"], ["step_002"], ["step_003"], ["step_004"]]
        assert plan.parallel_groups == expected


# ===================================================================
# RESEARCH_GAP plan
# ===================================================================


class TestPlanResearchGap:
    def test_step_count(self):
        plan = create_plan(make_parsed("RESEARCH_GAP"))
        assert len(plan.steps) == 4

    def test_step_ids(self):
        plan = create_plan(make_parsed("RESEARCH_GAP"))
        assert [s.step_id for s in plan.steps] == ["step_001", "step_002", "step_003", "step_004"]

    def test_step1_entity_lookup(self):
        plan = create_plan(make_parsed("RESEARCH_GAP"))
        assert plan.steps[0].query_type == "ENTITY_LOOKUP"

    def test_step2_gap_analysis(self):
        plan = create_plan(make_parsed("RESEARCH_GAP"))
        s = plan.steps[1]
        assert s.engine == "gap"
        assert s.query_type == "GAP_ANALYSIS"
        assert s.dependencies == ["step_001"]

    def test_step2_gap_types(self):
        plan = create_plan(make_parsed("RESEARCH_GAP"))
        gap_types = plan.steps[1].parameters.get("gap_types", [])
        assert "ISOLATED_ENTITY" in gap_types
        assert "MISSING_COMPARISON" in gap_types
        assert "LOW_CONFIDENCE_CLAIM" in gap_types

    def test_step3_evidence_collect(self):
        plan = create_plan(make_parsed("RESEARCH_GAP"))
        assert plan.steps[2].dependencies == ["step_002"]

    def test_step4_answer_build(self):
        plan = create_plan(make_parsed("RESEARCH_GAP"))
        assert plan.steps[3].parameters.get("template") == "gap_analysis"

    def test_parallel_groups(self):
        plan = create_plan(make_parsed("RESEARCH_GAP"))
        expected = [["step_001"], ["step_002"], ["step_003"], ["step_004"]]
        assert plan.parallel_groups == expected


# ===================================================================
# MULTI_HOP plan
# ===================================================================


class TestPlanMultiHop:
    def test_step_count(self):
        plan = create_plan(make_parsed("MULTI_HOP"))
        assert len(plan.steps) == 5

    def test_step_ids(self):
        plan = create_plan(make_parsed("MULTI_HOP"))
        expected = ["step_001", "step_002", "step_003", "step_004", "step_005"]
        assert [s.step_id for s in plan.steps] == expected

    def test_steps_1_and_2_entity_lookups(self):
        plan = create_plan(make_parsed("MULTI_HOP"))
        assert plan.steps[0].query_type == "ENTITY_LOOKUP"
        assert plan.steps[1].query_type == "ENTITY_LOOKUP"
        assert plan.steps[0].dependencies == []
        assert plan.steps[1].dependencies == []

    def test_step1_source_target(self):
        plan = create_plan(make_parsed("MULTI_HOP", primary_entity=make_entity("A", "clu_a")))
        assert plan.steps[0].target_id == "clu_a"

    def test_step2_target_from_secondary(self):
        sec = [make_entity("B", "clu_b")]
        plan = create_plan(make_parsed("MULTI_HOP", secondary_entities=sec))
        assert plan.steps[1].target_id == "clu_b"

    def test_step3_path_reasoning(self):
        plan = create_plan(make_parsed("MULTI_HOP"))
        s = plan.steps[2]
        assert s.engine == "multi_hop"
        assert s.query_type == "PATH_REASONING"
        assert s.dependencies == ["step_001", "step_002"]

    def test_step4_evidence_collect(self):
        plan = create_plan(make_parsed("MULTI_HOP"))
        assert plan.steps[3].dependencies == ["step_003"]

    def test_step5_answer_build(self):
        plan = create_plan(make_parsed("MULTI_HOP"))
        assert plan.steps[4].parameters.get("template") == "multi_hop"
        assert plan.steps[4].dependencies == ["step_004"]

    def test_parallel_groups(self):
        plan = create_plan(make_parsed("MULTI_HOP"))
        expected = [["step_001", "step_002"], ["step_003"], ["step_004"], ["step_005"]]
        assert plan.parallel_groups == expected

    def test_path_max_depth_from_parsed(self):
        plan = create_plan(make_parsed("MULTI_HOP", max_hops=8))
        assert plan.steps[2].parameters.get("max_depth") == 4

    def test_path_max_depth_clamped(self):
        plan = create_plan(make_parsed("MULTI_HOP", max_hops=2))
        assert plan.steps[2].parameters.get("max_depth") == 2

    def test_no_secondary(self):
        plan = create_plan(make_parsed("MULTI_HOP", secondary_entities=[]))
        assert plan.steps[1].target_id is None


# ===================================================================
# EXPLORATION plan
# ===================================================================


class TestPlanExploration:
    def test_step_count(self):
        plan = create_plan(make_parsed("EXPLORATION"))
        assert len(plan.steps) == 4

    def test_step_ids(self):
        plan = create_plan(make_parsed("EXPLORATION"))
        assert [s.step_id for s in plan.steps] == ["step_001", "step_002", "step_003", "step_004"]

    def test_step1_entity_lookup(self):
        plan = create_plan(make_parsed("EXPLORATION"))
        assert plan.steps[0].query_type == "ENTITY_LOOKUP"

    def test_step2_neighborhood_search(self):
        plan = create_plan(make_parsed("EXPLORATION"))
        s = plan.steps[1]
        assert s.engine == "multi_hop"
        assert s.query_type == "GRAPH_EXPLORATION"
        assert s.dependencies == ["step_001"]

    def test_step2_max_depth_default(self):
        plan = create_plan(make_parsed("EXPLORATION"))
        assert plan.steps[1].parameters.get("max_depth") == 2

    def test_step3_evidence_collect(self):
        plan = create_plan(make_parsed("EXPLORATION"))
        assert plan.steps[2].dependencies == ["step_002"]

    def test_step4_answer_build(self):
        plan = create_plan(make_parsed("EXPLORATION"))
        assert plan.steps[3].parameters.get("template") == "exploration"

    def test_parallel_groups(self):
        plan = create_plan(make_parsed("EXPLORATION"))
        expected = [["step_001"], ["step_002"], ["step_003"], ["step_004"]]
        assert plan.parallel_groups == expected

    def test_complexity_medium(self):
        plan = create_plan(make_parsed("EXPLORATION"))
        assert plan.estimated_complexity == "medium"


# ===================================================================
# Determinism — same input always yields same output
# ===================================================================


class TestPlanDeterminism:
    def test_same_input_same_plan_id(self):
        pq = make_parsed("FACTUAL")
        p1 = create_plan(pq)
        p2 = create_plan(pq)
        assert p1.plan_id == p2.plan_id

    def test_same_input_same_steps(self):
        pq = make_parsed("FACTUAL")
        p1 = create_plan(pq)
        p2 = create_plan(pq)
        for s1, s2 in zip(p1.steps, p2.steps):
            assert s1.step_id == s2.step_id
            assert s1.engine == s2.engine
            assert s1.query_type == s2.query_type
            assert s1.dependencies == s2.dependencies

    def test_same_input_same_parallel_groups(self):
        pq = make_parsed("COMPARISON")
        p1 = create_plan(pq)
        p2 = create_plan(pq)
        assert p1.parallel_groups == p2.parallel_groups

    def test_same_input_same_complexity(self):
        pq = make_parsed("MULTI_HOP")
        p1 = create_plan(pq)
        p2 = create_plan(pq)
        assert p1.estimated_complexity == p2.estimated_complexity

    def test_consecutive_plans_have_unique_ids(self):
        p1 = create_plan(make_parsed("FACTUAL"))
        p2 = create_plan(make_parsed("COMPARISON"))
        assert p1.plan_id != p2.plan_id

    def test_empty_query_plan_is_deterministic(self):
        pq = make_parsed("FACTUAL", raw_query="", primary_entity=None, entities_resolved=False)
        p1 = create_plan(pq)
        p2 = create_plan(pq)
        assert p1.plan_id == p2.plan_id


# ===================================================================
# Parallel groups — topological layering
# ===================================================================


class TestParallelGroups:
    def test_all_sequential(self):
        steps = [
            PlanStep(step_id="s1", sequence=1, engine="multi_hop", query_type="A"),
            PlanStep(step_id="s2", sequence=2, engine="multi_hop", query_type="B", dependencies=["s1"]),
        ]
        groups = QueryPlanner._compute_parallel_groups(steps)
        assert groups == [["s1"], ["s2"]]

    def test_branching(self):
        steps = [
            PlanStep(step_id="s1", sequence=1, engine="multi_hop", query_type="A"),
            PlanStep(step_id="s2", sequence=2, engine="multi_hop", query_type="B", dependencies=["s1"]),
            PlanStep(step_id="s3", sequence=3, engine="multi_hop", query_type="C", dependencies=["s1"]),
        ]
        groups = QueryPlanner._compute_parallel_groups(steps)
        assert groups == [["s1"], ["s2", "s3"]]

    def test_merge(self):
        steps = [
            PlanStep(step_id="s1", sequence=1, engine="multi_hop", query_type="A"),
            PlanStep(step_id="s2", sequence=2, engine="multi_hop", query_type="B"),
            PlanStep(step_id="s3", sequence=3, engine="multi_hop", query_type="C", dependencies=["s1", "s2"]),
        ]
        groups = QueryPlanner._compute_parallel_groups(steps)
        assert groups == [["s1", "s2"], ["s3"]]

    def test_all_independent(self):
        steps = [
            PlanStep(step_id="s1", sequence=1, engine="multi_hop", query_type="A"),
            PlanStep(step_id="s2", sequence=2, engine="multi_hop", query_type="B"),
            PlanStep(step_id="s3", sequence=3, engine="multi_hop", query_type="C"),
        ]
        groups = QueryPlanner._compute_parallel_groups(steps)
        assert groups == [["s1", "s2", "s3"]]

    def test_single_step(self):
        steps = [PlanStep(step_id="s1", sequence=1, engine="multi_hop", query_type="A")]
        groups = QueryPlanner._compute_parallel_groups(steps)
        assert groups == [["s1"]]

    def test_empty_steps(self):
        groups = QueryPlanner._compute_parallel_groups([])
        assert groups == []

    def test_deep_chain(self):
        steps = [
            PlanStep.model_construct(step_id="s1", sequence=1, engine="a", query_type="A"),
            PlanStep.model_construct(step_id="s2", sequence=2, engine="a", query_type="B", dependencies=["s1"]),
            PlanStep.model_construct(step_id="s3", sequence=3, engine="a", query_type="C", dependencies=["s2"]),
            PlanStep.model_construct(step_id="s4", sequence=4, engine="a", query_type="D", dependencies=["s3"]),
            PlanStep.model_construct(step_id="s5", sequence=5, engine="a", query_type="E", dependencies=["s4"]),
        ]
        groups = QueryPlanner._compute_parallel_groups(steps)
        assert groups == [["s1"], ["s2"], ["s3"], ["s4"], ["s5"]]

    def test_diamond(self):
        steps = [
            PlanStep.model_construct(step_id="s1", sequence=1, engine="a", query_type="A"),
            PlanStep.model_construct(step_id="s2", sequence=2, engine="a", query_type="B", dependencies=["s1"]),
            PlanStep.model_construct(step_id="s3", sequence=3, engine="a", query_type="C", dependencies=["s1"]),
            PlanStep.model_construct(step_id="s4", sequence=4, engine="a", query_type="D", dependencies=["s2", "s3"]),
        ]
        groups = QueryPlanner._compute_parallel_groups(steps)
        assert groups == [["s1"], ["s2", "s3"], ["s4"]]

    def test_deterministic_order(self):
        steps = [
            PlanStep.model_construct(step_id="z1", sequence=1, engine="a", query_type="A"),
            PlanStep.model_construct(step_id="a2", sequence=2, engine="a", query_type="B"),
            PlanStep.model_construct(step_id="m3", sequence=3, engine="a", query_type="C"),
        ]
        g1 = QueryPlanner._compute_parallel_groups(steps)
        g2 = QueryPlanner._compute_parallel_groups(steps)
        assert g1 == g2


# ===================================================================
# Complexity estimation
# ===================================================================


class TestComplexity:
    def test_low_for_2_steps(self):
        steps = [
            PlanStep.model_construct(step_id="s1", sequence=1, engine="a", query_type="A"),
            PlanStep.model_construct(step_id="s2", sequence=2, engine="a", query_type="B"),
        ]
        assert QueryPlanner._estimate_complexity(steps) == "low"

    def test_medium_for_3_steps(self):
        steps = [
            PlanStep.model_construct(step_id="s1", sequence=1, engine="a", query_type="A"),
            PlanStep.model_construct(step_id="s2", sequence=2, engine="a", query_type="B"),
            PlanStep.model_construct(step_id="s3", sequence=3, engine="a", query_type="C"),
        ]
        assert QueryPlanner._estimate_complexity(steps) == "medium"

    def test_medium_for_4_steps(self):
        steps = [PlanStep.model_construct(step_id=f"s{i}", sequence=i, engine="a", query_type="A") for i in range(1, 5)]
        assert QueryPlanner._estimate_complexity(steps) == "medium"

    def test_medium_for_5_steps(self):
        steps = [PlanStep.model_construct(step_id=f"s{i}", sequence=i, engine="a", query_type="A") for i in range(1, 6)]
        assert QueryPlanner._estimate_complexity(steps) == "medium"

    def test_high_for_6_steps(self):
        steps = [PlanStep.model_construct(step_id=f"s{i}", sequence=i, engine="a", query_type="A") for i in range(1, 7)]
        assert QueryPlanner._estimate_complexity(steps) == "high"

    def test_low_for_1_step(self):
        steps = [PlanStep.model_construct(step_id="s1", sequence=1, engine="a", query_type="A")]
        assert QueryPlanner._estimate_complexity(steps) == "low"

    def test_low_for_0_steps(self):
        assert QueryPlanner._estimate_complexity([]) == "low"

    def test_deterministic(self):
        steps = [PlanStep.model_construct(step_id=f"s{i}", sequence=i, engine="a", query_type="A") for i in range(1, 4)]
        r1 = QueryPlanner._estimate_complexity(steps)
        r2 = QueryPlanner._estimate_complexity(steps)
        assert r1 == r2


# ===================================================================
# Plan validation
# ===================================================================


class TestValidation:
    def test_valid_plan_passes(self):
        steps = [
            PlanStep(step_id="s1", sequence=1, engine="multi_hop", query_type="A"),
            PlanStep(step_id="s2", sequence=2, engine="aggregate", query_type="B", dependencies=["s1"]),
        ]
        QueryPlanner._validate_plan(steps)

    def test_duplicate_step_id_raises(self):
        steps = [
            PlanStep(step_id="s1", sequence=1, engine="multi_hop", query_type="A"),
            PlanStep(step_id="s1", sequence=2, engine="aggregate", query_type="B"),
        ]
        with pytest.raises(ValueError, match="Duplicate step_id"):
            QueryPlanner._validate_plan(steps)

    def test_missing_dependency_raises(self):
        steps = [
            PlanStep(step_id="s1", sequence=1, engine="multi_hop", query_type="A", dependencies=["s2"]),
        ]
        with pytest.raises(ValueError, match="does not exist"):
            QueryPlanner._validate_plan(steps)

    def test_empty_step_id_raises(self):
        steps = [
            PlanStep(step_id="", sequence=1, engine="multi_hop", query_type="A"),
        ]
        with pytest.raises(ValueError, match="non-empty"):
            QueryPlanner._validate_plan(steps)

    def test_circular_dependency_direct(self):
        steps = [
            PlanStep.model_construct(step_id="s1", sequence=1, engine="a", query_type="A", dependencies=["s2"]),
            PlanStep.model_construct(step_id="s2", sequence=2, engine="a", query_type="B", dependencies=["s1"]),
        ]
        with pytest.raises(ValueError, match="Circular"):
            QueryPlanner._validate_plan(steps)

    def test_circular_dependency_indirect(self):
        steps = [
            PlanStep.model_construct(step_id="s1", sequence=1, engine="a", query_type="A", dependencies=["s2"]),
            PlanStep.model_construct(step_id="s2", sequence=2, engine="a", query_type="B", dependencies=["s3"]),
            PlanStep.model_construct(step_id="s3", sequence=3, engine="a", query_type="C", dependencies=["s1"]),
        ]
        with pytest.raises(ValueError, match="Circular"):
            QueryPlanner._validate_plan(steps)

    def test_self_dependency_raises(self):
        steps = [
            PlanStep.model_construct(step_id="s1", sequence=1, engine="a", query_type="A", dependencies=["s1"]),
        ]
        with pytest.raises(ValueError, match="Circular"):
            QueryPlanner._validate_plan(steps)

    def test_generated_plan_is_valid(self):
        for qt in ["FACTUAL", "EXPLANATION", "COMPARISON", "CONSENSUS",
                    "CONTRADICTION", "RESEARCH_GAP", "MULTI_HOP", "EXPLORATION"]:
            plan = create_plan(make_parsed(qt))
            QueryPlanner._validate_plan(plan.steps)


# ===================================================================
# Metadata — warnings, ambiguity, entity resolution
# ===================================================================


class TestMetadata:
    def test_entity_not_resolved_warning(self):
        plan = create_plan(make_parsed("FACTUAL", entities_resolved=False, primary_entity=None))
        assert any("not resolved" in w for w in plan.warnings)

    def test_ambiguity_warning(self):
        entity = make_entity(is_ambiguous=True, alternatives=["clu_004", "clu_005"])
        plan = create_plan(make_parsed("FACTUAL", primary_entity=entity))
        assert any("Ambiguous" in w for w in plan.warnings)

    def test_parsing_warnings_propagated(self):
        plan = create_plan(make_parsed("FACTUAL", parsing_warnings=["test warning"]))
        assert "test warning" in plan.warnings

    def test_no_warnings_clean(self):
        plan = create_plan(make_parsed("FACTUAL"))
        assert len([w for w in plan.warnings if "Ambiguous" in w or "not resolved" in w]) == 0

    def test_query_type_in_plan(self):
        plan = create_plan(make_parsed("CONTRADICTION"))
        assert plan.query_type == "CONTRADICTION"

    def test_parallel_groups_in_plan(self):
        plan = create_plan(make_parsed("COMPARISON"))
        assert isinstance(plan.parallel_groups, list)

    def test_step_status_pending(self):
        plan = create_plan(make_parsed("FACTUAL"))
        for s in plan.steps:
            assert s.status == "pending"

    def test_step_warnings_initially_empty(self):
        plan = create_plan(make_parsed("FACTUAL"))
        for s in plan.steps:
            assert s.warnings == []

    def test_step_confidence_zero(self):
        plan = create_plan(make_parsed("FACTUAL"))
        for s in plan.steps:
            assert s.confidence == 0.0

    def test_step_result_none(self):
        plan = create_plan(make_parsed("FACTUAL"))
        for s in plan.steps:
            assert s.result is None

    def test_plan_total_steps_matches(self):
        plan = create_plan(make_parsed("MULTI_HOP"))
        assert plan.total_steps == len(plan.steps)


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    def test_no_entities(self):
        plan = create_plan(make_parsed("RESEARCH_GAP", primary_entity=None, entities_resolved=False))
        assert len(plan.steps) == 4
        assert plan.steps[0].target_id is None

    def test_no_entities_factual(self):
        plan = create_plan(make_parsed("FACTUAL", primary_entity=None, entities_resolved=False))
        assert len(plan.steps) == 3
        assert plan.steps[0].target_id is None

    def test_many_secondary_entities(self):
        sec = [make_entity(f"E{i}", f"clu_{i}") for i in range(5)]
        plan = create_plan(make_parsed("COMPARISON", secondary_entities=sec))
        assert plan.steps[1].target_id == "clu_0"

    def test_multiple_constraints(self):
        from researchmind.query.models import QueryConstraint
        constraints = [
            QueryConstraint(field="year", operator="gte", value=2020),
            QueryConstraint(field="confidence", operator="gte", value=0.5),
        ]
        plan = create_plan(make_parsed("FACTUAL", constraints=constraints))
        assert len(plan.steps) == 3

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported query type"):
            pq = ParsedQuery.model_construct(
                raw_query="test query", query_type="UNKNOWN"
            )
            create_plan(pq)

    def test_empty_query_raw(self):
        pq = ParsedQuery(
            raw_query="",
            query_type="FACTUAL",
            entities_resolved=False,
        )
        plan = create_plan(pq)
        assert len(plan.steps) == 3
        assert plan.steps[0].target_id is None

    def test_create_plan_convenience_function(self):
        plan = create_plan(make_parsed("FACTUAL"))
        assert isinstance(plan, ExecutionPlan)

    def test_plan_has_query_id_field(self):
        plan = create_plan(make_parsed("FACTUAL"))
        assert plan.query_id == ""

    def test_plan_with_all_max_hops(self):
        plan = create_plan(make_parsed("MULTI_HOP", max_hops=10))
        assert plan.steps[2].parameters.get("max_depth") == 4

    def test_plan_with_min_max_hops(self):
        plan = create_plan(make_parsed("MULTI_HOP", max_hops=1))
        assert plan.steps[2].parameters.get("max_depth") == 1

    def test_factual_with_ambiguous_entity_and_no_resolution(self):
        entity = make_entity(is_ambiguous=True, alternatives=["clu_a", "clu_b"])
        plan = create_plan(make_parsed("FACTUAL", primary_entity=entity, entities_resolved=False))
        assert any("Ambiguous" in w for w in plan.warnings)
        assert any("not resolved" in w for w in plan.warnings)

    def test_exploration_with_no_entity(self):
        plan = create_plan(make_parsed("EXPLORATION", primary_entity=None, entities_resolved=False))
        assert len(plan.steps) == 4

    def test_explanation_with_no_entity(self):
        plan = create_plan(make_parsed("EXPLANATION", primary_entity=None, entities_resolved=False))
        assert len(plan.steps) == 4


# ===================================================================
# Helper methods
# ===================================================================


class TestHelperMethods:
    def test_next_step_id_starts_at_one(self):
        planner = make_planner()
        assert planner._next_step_id() == "step_001"

    def test_next_step_id_increments(self):
        planner = make_planner()
        planner._next_step_id()
        assert planner._next_step_id() == "step_002"

    def test_next_step_id_pads_to_three_digits(self):
        planner = make_planner()
        for _ in range(100):
            planner._next_step_id()
        assert planner._next_step_id() == "step_101"

    def test_generate_plan_id_deterministic(self):
        pq = make_parsed("FACTUAL")
        planner = make_planner()
        id1 = planner._generate_plan_id(pq)
        id2 = planner._generate_plan_id(pq)
        assert id1 == id2

    def test_generate_plan_id_unique_per_type(self):
        f = make_parsed("FACTUAL")
        c = make_parsed("COMPARISON")
        planner = make_planner()
        assert planner._generate_plan_id(f) != planner._generate_plan_id(c)

    def test_generate_plan_id_format(self):
        pq = make_parsed("FACTUAL")
        planner = make_planner()
        pid = planner._generate_plan_id(pq)
        assert pid.startswith("plan_")
        assert len(pid) == 5 + 12  # "plan_" + 12 hex chars

    def test_primary_target_with_entity(self):
        pq = make_parsed()
        assert QueryPlanner._primary_target(pq) == "clu_003"

    def test_primary_target_without_entity(self):
        pq = make_parsed(primary_entity=None, entities_resolved=False)
        assert QueryPlanner._primary_target(pq) is None

    def test_primary_target_different_cluster(self):
        pq = make_parsed(primary_entity=make_entity("X", "clu_x"))
        assert QueryPlanner._primary_target(pq) == "clu_x"

    def test_make_step_creates_unique_ids(self):
        planner = make_planner()
        s1 = planner._make_step("multi_hop", "ENTITY_LOOKUP")
        s2 = planner._make_step("consensus", "CONSENSUS_ANALYSIS")
        assert s1.step_id != s2.step_id

    def test_make_step_engine_and_type(self):
        planner = make_planner()
        s = planner._make_step("gap", "GAP_ANALYSIS")
        assert s.engine == "gap"
        assert s.query_type == "GAP_ANALYSIS"

    def test_make_step_target(self):
        planner = make_planner()
        s = planner._make_step("multi_hop", "ENTITY_LOOKUP", target_id="clu_001")
        assert s.target_id == "clu_001"

    def test_make_step_secondary_ids(self):
        planner = make_planner()
        s = planner._make_step("multi_hop", "ENTITY_LOOKUP", secondary_ids=["clu_b", "clu_c"])
        assert s.secondary_ids == ["clu_b", "clu_c"]

    def test_make_step_params(self):
        planner = make_planner()
        s = planner._make_step("multi_hop", "ENTITY_LOOKUP", parameters={"max_depth": 3})
        assert s.parameters == {"max_depth": 3}

    def test_make_step_deps(self):
        planner = make_planner()
        s = planner._make_step("multi_hop", "ENTITY_LOOKUP", dependencies=["step_001"])
        assert s.dependencies == ["step_001"]


# ===================================================================
# Integration — planner + models
# ===================================================================


class TestIntegration:
    def test_plan_is_execution_plan(self):
        plan = create_plan(make_parsed("FACTUAL"))
        assert isinstance(plan, ExecutionPlan)
        assert isinstance(plan.steps, list)
        assert all(isinstance(s, PlanStep) for s in plan.steps)

    def test_plan_roundtrip(self):
        plan = create_plan(make_parsed("FACTUAL"))
        dump = plan.model_dump()
        reloaded = ExecutionPlan(**dump)
        assert reloaded.plan_id == plan.plan_id
        assert len(reloaded.steps) == len(plan.steps)

    def test_plan_validates_via_model(self):
        plan = create_plan(make_parsed("MULTI_HOP"))
        try:
            ExecutionPlan.model_validate(plan.model_dump())
        except ValidationError:
            pytest.fail("Plan failed model validation")

    def test_comparison_parallel_groups_in_plan(self):
        plan = create_plan(make_parsed("COMPARISON"))
        for group in plan.parallel_groups:
            for sid in group:
                assert any(s.step_id == sid for s in plan.steps)

    def test_all_plan_steps_have_pending_status(self):
        plan = create_plan(make_parsed("EXPLANATION"))
        for s in plan.steps:
            assert s.status == "pending"

    def test_all_plan_steps_have_positive_sequence(self):
        plan = create_plan(make_parsed("CONTRADICTION"))
        for s in plan.steps:
            assert s.sequence >= 1


# ===================================================================
# Plan structure invariants (cross-type)
# ===================================================================


class TestPlanInvariants:
    def test_no_empty_step_ids(self):
        for qt in ["FACTUAL", "EXPLANATION", "COMPARISON", "CONSENSUS",
                    "CONTRADICTION", "RESEARCH_GAP", "MULTI_HOP", "EXPLORATION"]:
            plan = create_plan(make_parsed(qt))
            for s in plan.steps:
                assert s.step_id, f"Empty step_id in {qt}"

    def test_all_step_ids_unique_within_plan(self):
        for qt in ["FACTUAL", "EXPLANATION", "COMPARISON", "CONSENSUS",
                    "CONTRADICTION", "RESEARCH_GAP", "MULTI_HOP", "EXPLORATION"]:
            plan = create_plan(make_parsed(qt))
            ids = [s.step_id for s in plan.steps]
            assert len(ids) == len(set(ids)), f"Duplicate step IDs in {qt}"

    def test_all_dependencies_exist(self):
        for qt in ["FACTUAL", "EXPLANATION", "COMPARISON", "CONSENSUS",
                    "CONTRADICTION", "RESEARCH_GAP", "MULTI_HOP", "EXPLORATION"]:
            plan = create_plan(make_parsed(qt))
            all_ids = {s.step_id for s in plan.steps}
            for s in plan.steps:
                for dep in s.dependencies:
                    assert dep in all_ids, f"{qt}: {s.step_id} depends on {dep} not in plan"

    def test_no_circular_dependencies(self):
        for qt in ["FACTUAL", "EXPLANATION", "COMPARISON", "CONSENSUS",
                    "CONTRADICTION", "RESEARCH_GAP", "MULTI_HOP", "EXPLORATION"]:
            plan = create_plan(make_parsed(qt))
            QueryPlanner._validate_plan(plan.steps)

    def test_sequences_are_contiguous_from_one(self):
        for qt in ["FACTUAL", "EXPLANATION", "COMPARISON", "CONSENSUS",
                    "CONTRADICTION", "RESEARCH_GAP", "MULTI_HOP", "EXPLORATION"]:
            plan = create_plan(make_parsed(qt))
            seqs = sorted(s.sequence for s in plan.steps)
            assert seqs == list(range(1, len(plan.steps) + 1)), f"Non-contiguous sequences in {qt}"

    def test_parallel_groups_cover_all_steps(self):
        for qt in ["FACTUAL", "EXPLANATION", "COMPARISON", "CONSENSUS",
                    "CONTRADICTION", "RESEARCH_GAP", "MULTI_HOP", "EXPLORATION"]:
            plan = create_plan(make_parsed(qt))
            grouped = set()
            for g in plan.parallel_groups:
                grouped.update(g)
            all_ids = {s.step_id for s in plan.steps}
            assert grouped == all_ids, f"Parallel groups don't cover all steps in {qt}"

    def test_parallel_groups_no_duplicates(self):
        for qt in ["FACTUAL", "EXPLANATION", "COMPARISON", "CONSENSUS",
                    "CONTRADICTION", "RESEARCH_GAP", "MULTI_HOP", "EXPLORATION"]:
            plan = create_plan(make_parsed(qt))
            seen = set()
            for g in plan.parallel_groups:
                for sid in g:
                    assert sid not in seen, f"Duplicate step {sid} in parallel groups for {qt}"
                    seen.add(sid)

    def test_engine_is_valid(self):
        valid_engines = {"multi_hop", "consensus", "contradiction", "gap", "aggregate", "synthesize"}
        for qt in ["FACTUAL", "EXPLANATION", "COMPARISON", "CONSENSUS",
                    "CONTRADICTION", "RESEARCH_GAP", "MULTI_HOP", "EXPLORATION"]:
            plan = create_plan(make_parsed(qt))
            for s in plan.steps:
                assert s.engine in valid_engines, f"Invalid engine {s.engine} in {qt}"


# ===================================================================
# PlanResult model (architecture 5.5)
# ===================================================================


class TestPlanResult:
    def test_planresult_roundtrip(self):
        from researchmind.query.models import PlanResult
        plan = create_plan(make_parsed("FACTUAL"))
        result = PlanResult(plan=plan)
        assert result.plan.plan_id == plan.plan_id
        assert not result.all_steps_completed
        assert result.final_confidence == 0.0

    def test_planresult_step_results(self):
        from researchmind.query.models import PlanResult
        plan = create_plan(make_parsed("FACTUAL"))
        result = PlanResult(plan=plan, step_results={"step_001": {"data": "test"}})
        assert result.step_results["step_001"]["data"] == "test"

    def test_planresult_all_steps_completed(self):
        from researchmind.query.models import PlanResult
        plan = create_plan(make_parsed("FACTUAL"))
        result = PlanResult(plan=plan, all_steps_completed=True)
        assert result.all_steps_completed
