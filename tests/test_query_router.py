"""Tests for the M5 query routing engine — PlanStep → StepRoute translation.

Covers all 11 registered routes, target requirement validation, parameter
validation (max_depth, min_confidence, gap_types), plan-level routing,
metadata introspection, determinism, and edge cases.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from researchmind.query.models import ExecutionPlan, PlanStep
from researchmind.query.router import (
    StepDispatcher,
    StepRoute,
    route_plan,
    route_step,
)

# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

_step_counter: int = 0


def _next_sid() -> str:
    global _step_counter
    _step_counter += 1
    return f"step_{_step_counter:03d}"


def make_step(
    engine="multi_hop",
    query_type="ENTITY_LOOKUP",
    target_id="clu_003",
    secondary_ids=None,
    parameters=None,
    step_id=None,
):
    return PlanStep(
        step_id=step_id or _next_sid(),
        sequence=1,
        engine=engine,
        query_type=query_type,
        target_id=target_id,
        secondary_ids=secondary_ids or [],
        parameters=parameters or {},
    )


def make_plan(steps=None):
    steps = steps or [make_step()]
    return ExecutionPlan(
        plan_id="plan_test",
        query_id="",
        query_type="FACTUAL",
        steps=steps,
        total_steps=len(steps),
    )


def make_dispatcher():
    return StepDispatcher()


def make_raw_step(
    step_id="step_001",
    sequence=1,
    engine="multi_hop",
    query_type="ENTITY_LOOKUP",
    target_id=None,
    secondary_ids=None,
    parameters=None,
):
    """Create a PlanStep that bypasses Pydantic validation.

    Used for testing invalid engine/query_type combinations that
    PlanStep.__init__ would normally reject.
    """
    return PlanStep.model_construct(
        step_id=step_id,
        sequence=sequence,
        engine=engine,
        query_type=query_type,
        target_id=target_id,
        secondary_ids=secondary_ids or [],
        parameters=parameters or {},
        dependencies=[],
        status="pending",
        result=None,
        confidence=0.0,
        warnings=[],
    )


# ===================================================================
# StepRoute model
# ===================================================================


class TestStepRouteConstruction:
    def test_minimal(self):
        route = StepRoute(
            step_id="step_001", engine="multi_hop", m4_query_type="ENTITY_LOOKUP",
        )
        assert route.step_id == "step_001"
        assert route.engine == "multi_hop"
        assert route.m4_query_type == "ENTITY_LOOKUP"
        assert route.target_id is None
        assert route.secondary_ids == []
        assert route.m4_params == {}
        assert route.is_executable is True
        assert route.m4_method is None

    def test_full(self):
        route = StepRoute(
            step_id="step_002",
            engine="consensus",
            m4_query_type="CONSENSUS_ANALYSIS",
            m4_method="analyze",
            target_id="clu_005",
            secondary_ids=["clu_006"],
            m4_params={"min_confidence": 0.5},
            is_executable=True,
        )
        assert route.step_id == "step_002"
        assert route.engine == "consensus"
        assert route.m4_query_type == "CONSENSUS_ANALYSIS"
        assert route.m4_method == "analyze"
        assert route.target_id == "clu_005"
        assert route.secondary_ids == ["clu_006"]
        assert route.m4_params == {"min_confidence": 0.5}
        assert route.is_executable is True

    def test_engine_normalized_lower(self):
        route = StepRoute(step_id="s1", engine="Multi_Hop", m4_query_type="ENTITY_LOOKUP")
        assert route.engine == "multi_hop"

    def test_m4_query_type_normalized_upper(self):
        route = StepRoute(step_id="s1", engine="multi_hop", m4_query_type="entity_lookup")
        assert route.m4_query_type == "ENTITY_LOOKUP"

    def test_invalid_engine_raises(self):
        with pytest.raises(ValidationError, match="Unknown engine"):
            StepRoute(step_id="s1", engine="nonexistent", m4_query_type="ENTITY_LOOKUP")

    def test_invalid_m4_query_type_raises(self):
        with pytest.raises(ValidationError, match="Unknown m4_query_type"):
            StepRoute(step_id="s1", engine="multi_hop", m4_query_type="BOGUS_TYPE")

    def test_all_valid_engines_accepted(self):
        for eng in ("multi_hop", "consensus", "contradiction", "gap", "aggregate", "synthesize"):
            route = StepRoute(step_id="s1", engine=eng, m4_query_type="ENTITY_LOOKUP")
            assert route.engine == eng

    def test_all_valid_m4_query_types_accepted(self):
        for qt in (
            "ENTITY_LOOKUP", "DOCUMENT_LOOKUP", "PATH_REASONING",
            "CONSENSUS_ANALYSIS", "CONTRADICTION_ANALYSIS", "GAP_ANALYSIS",
            "GRAPH_EXPLORATION",
        ):
            route = StepRoute(step_id="s1", engine="multi_hop", m4_query_type=qt)
            assert route.m4_query_type == qt

    def test_all_m5_internal_types_accepted(self):
        for qt in (
            "EVIDENCE_COLLECT", "ANSWER_BUILD", "COMPARISON_ANALYSIS",
            "MERGE_CONTRADICTIONS", "FILTER_GAPS",
        ):
            route = StepRoute(step_id="s1", engine="aggregate", m4_query_type=qt)
            assert route.m4_query_type == qt

    def test_default_is_executable_true(self):
        route = StepRoute(step_id="s1", engine="multi_hop", m4_query_type="ENTITY_LOOKUP")
        assert route.is_executable is True

    def test_is_executable_false(self):
        route = StepRoute(
            step_id="s1", engine="multi_hop", m4_query_type="ENTITY_LOOKUP",
            is_executable=False,
        )
        assert route.is_executable is False

    def test_empty_secondary_ids_default(self):
        route = StepRoute(step_id="s1", engine="multi_hop", m4_query_type="ENTITY_LOOKUP")
        assert route.secondary_ids == []

    def test_empty_m4_params_default(self):
        route = StepRoute(step_id="s1", engine="multi_hop", m4_query_type="ENTITY_LOOKUP")
        assert route.m4_params == {}


# ===================================================================
# StepDispatcher construction
# ===================================================================


class TestStepDispatcherConstruction:
    def test_create_dispatcher(self):
        d = make_dispatcher()
        assert isinstance(d, StepDispatcher)

    def test_create_multiple_dispatchers(self):
        d1 = make_dispatcher()
        d2 = make_dispatcher()
        assert d1 is not d2

    def test_singleton_like_reuse(self):
        d = make_dispatcher()
        r1 = d.route(make_step())
        r2 = d.route(make_step(engine="consensus", query_type="CONSENSUS_ANALYSIS"))
        assert r1.step_id != r2.step_id or r1.engine != r2.engine


# ===================================================================
# Route lookup — all valid routes
# ===================================================================


class TestRouteMultiHop:
    @pytest.mark.parametrize("qt", ["ENTITY_LOOKUP", "GRAPH_EXPLORATION", "PATH_REASONING"])
    def test_routes(self, qt):
        route = make_dispatcher().route(make_step(engine="multi_hop", query_type=qt))
        assert route.engine == "multi_hop"
        assert route.m4_query_type == qt
        assert route.m4_method == "reason"
        assert route.is_executable is True

    def test_entity_lookup_params(self):
        route = make_dispatcher().route(make_step(
            "multi_hop", "ENTITY_LOOKUP",
            parameters={"max_depth": 2},
        ))
        assert route.m4_params["max_depth"] == 2
        assert route.m4_params.get("min_confidence") == 0.3

    def test_graph_exploration_params(self):
        route = make_dispatcher().route(make_step(
            "multi_hop", "GRAPH_EXPLORATION",
            parameters={"max_depth": 3},
        ))
        assert route.m4_params["max_depth"] == 3

    def test_path_reasoning_target(self):
        route = make_dispatcher().route(make_step(
            "multi_hop", "PATH_REASONING", target_id="clu_010",
        ))
        assert route.target_id == "clu_010"

    def test_entity_lookup_default_max_depth(self):
        route = make_dispatcher().route(make_step("multi_hop", "ENTITY_LOOKUP"))
        assert route.m4_params.get("max_depth") == 3

    def test_target_id_propagated(self):
        route = make_dispatcher().route(make_step(
            "multi_hop", "ENTITY_LOOKUP", target_id="clu_999",
        ))
        assert route.target_id == "clu_999"

    def test_secondary_ids_propagated(self):
        route = make_dispatcher().route(make_step(
            "multi_hop", "PATH_REASONING",
            secondary_ids=["clu_004", "clu_005"],
        ))
        assert route.secondary_ids == ["clu_004", "clu_005"]


class TestRouteConsensus:
    def test_consensus_analysis(self):
        route = make_dispatcher().route(make_step(
            "consensus", "CONSENSUS_ANALYSIS",
        ))
        assert route.engine == "consensus"
        assert route.m4_query_type == "CONSENSUS_ANALYSIS"
        assert route.m4_method == "analyze"
        assert route.is_executable is True

    def test_consensus_min_confidence(self):
        route = make_dispatcher().route(make_step(
            "consensus", "CONSENSUS_ANALYSIS",
            parameters={"min_confidence": 0.7},
        ))
        assert route.m4_params["min_confidence"] == 0.7

    def test_consensus_default_min_confidence(self):
        route = make_dispatcher().route(make_step("consensus", "CONSENSUS_ANALYSIS"))
        assert route.m4_params["min_confidence"] == 0.3

    def test_consensus_target_id(self):
        route = make_dispatcher().route(make_step(
            "consensus", "CONSENSUS_ANALYSIS", target_id="clu_050",
        ))
        assert route.target_id == "clu_050"


class TestRouteContradiction:
    def test_contradiction_analysis(self):
        route = make_dispatcher().route(make_step(
            "contradiction", "CONTRADICTION_ANALYSIS",
        ))
        assert route.engine == "contradiction"
        assert route.m4_query_type == "CONTRADICTION_ANALYSIS"
        assert route.m4_method == "analyze"
        assert route.is_executable is True

    def test_contradiction_min_confidence(self):
        route = make_dispatcher().route(make_step(
            "contradiction", "CONTRADICTION_ANALYSIS",
            parameters={"min_confidence": 0.5},
        ))
        assert route.m4_params["min_confidence"] == 0.5

    def test_contradiction_default_min_confidence(self):
        route = make_dispatcher().route(make_step("contradiction", "CONTRADICTION_ANALYSIS"))
        assert route.m4_params["min_confidence"] == 0.3

    def test_contradiction_target_id(self):
        route = make_dispatcher().route(make_step(
            "contradiction", "CONTRADICTION_ANALYSIS", target_id="clu_060",
        ))
        assert route.target_id == "clu_060"


class TestRouteGap:
    def test_gap_analysis(self):
        route = make_dispatcher().route(make_step("gap", "GAP_ANALYSIS"))
        assert route.engine == "gap"
        assert route.m4_query_type == "GAP_ANALYSIS"
        assert route.m4_method == "analyze"
        assert route.is_executable is True

    def test_gap_with_gap_types(self):
        route = make_dispatcher().route(make_step(
            "gap", "GAP_ANALYSIS",
            parameters={"gap_types": ["ISOLATED_ENTITY", "MISSING_COMPARISON"]},
        ))
        assert route.m4_params["gap_types"] == ["ISOLATED_ENTITY", "MISSING_COMPARISON"]

    def test_gap_default_min_confidence(self):
        route = make_dispatcher().route(make_step("gap", "GAP_ANALYSIS"))
        assert route.m4_params["min_confidence"] == 0.3

    def test_gap_no_target_required(self):
        route = make_dispatcher().route(make_step(
            "gap", "GAP_ANALYSIS", target_id=None,
        ))
        assert route.target_id is None


class TestRouteAggregate:
    @pytest.mark.parametrize("qt", [
        "EVIDENCE_COLLECT", "COMPARISON_ANALYSIS",
        "MERGE_CONTRADICTIONS", "FILTER_GAPS",
    ])
    def test_routes(self, qt):
        route = make_dispatcher().route(make_step(engine="aggregate", query_type=qt))
        assert route.engine == "aggregate"
        assert route.m4_query_type == qt
        assert route.m4_method is None
        assert route.is_executable is False

    def test_evidence_collect_params(self):
        route = make_dispatcher().route(make_step(
            "aggregate", "EVIDENCE_COLLECT",
            parameters={"dedup_by": "evidence_id"},
        ))
        assert route.m4_params["dedup_by"] == "evidence_id"

    def test_aggregate_not_executable(self):
        for qt in ("EVIDENCE_COLLECT", "COMPARISON_ANALYSIS", "MERGE_CONTRADICTIONS", "FILTER_GAPS"):
            route = make_dispatcher().route(make_step("aggregate", qt))
            assert route.is_executable is False


class TestRouteSynthesize:
    def test_answer_build(self):
        route = make_dispatcher().route(make_step("synthesize", "ANSWER_BUILD"))
        assert route.engine == "synthesize"
        assert route.m4_query_type == "ANSWER_BUILD"
        assert route.m4_method is None
        assert route.is_executable is False

    def test_synthesize_params(self):
        route = make_dispatcher().route(make_step(
            "synthesize", "ANSWER_BUILD",
            parameters={"template": "factual"},
        ))
        assert route.m4_params["template"] == "factual"

    def test_synthesize_not_executable(self):
        route = make_dispatcher().route(make_step("synthesize", "ANSWER_BUILD"))
        assert route.is_executable is False


# ===================================================================
# Invalid routes
# ===================================================================


class TestInvalidRoutes:
    def test_unknown_engine(self):
        with pytest.raises(ValueError, match="Unknown route"):
            make_dispatcher().route(make_raw_step(engine="bogus", query_type="ENTITY_LOOKUP"))

    def test_unknown_query_type(self):
        with pytest.raises(ValueError, match="Unknown route"):
            make_dispatcher().route(make_raw_step(engine="multi_hop", query_type="BOGUS_TYPE"))

    def test_known_engine_unknown_type(self):
        with pytest.raises(ValueError, match="Unknown route"):
            make_dispatcher().route(make_raw_step(engine="multi_hop", query_type="GAP_ANALYSIS"))

    def test_known_type_unknown_engine(self):
        with pytest.raises(ValueError, match="Unknown route"):
            make_dispatcher().route(make_raw_step(engine="gap", query_type="ENTITY_LOOKUP"))

    def test_aggregate_with_m4_type_not_in_table(self):
        with pytest.raises(ValueError, match="Unknown route"):
            make_dispatcher().route(make_raw_step(engine="aggregate", query_type="ENTITY_LOOKUP"))

    def test_synthesize_with_wrong_type(self):
        with pytest.raises(ValueError, match="Unknown route"):
            make_dispatcher().route(make_raw_step(engine="synthesize", query_type="EVIDENCE_COLLECT"))

    def test_empty_engine_raises(self):
        with pytest.raises(ValueError, match="Unknown route"):
            make_dispatcher().route(make_raw_step(engine="", query_type="ENTITY_LOOKUP"))

    def test_empty_query_type_raises(self):
        with pytest.raises(ValueError, match="Unknown route"):
            make_dispatcher().route(make_raw_step(engine="multi_hop", query_type=""))


# ===================================================================
# Target requirement validation
# ===================================================================


class TestTargetRequirementValidation:
    def test_path_reasoning_requires_target(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "PATH_REASONING", target_id=None,
        ))
        assert any("requires a target_id" in e for e in errors)

    def test_path_reasoning_with_target_ok(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "PATH_REASONING", target_id="clu_010",
        ))
        assert len(errors) == 0

    def test_consensus_requires_target(self):
        errors = make_dispatcher().validate(make_step(
            "consensus", "CONSENSUS_ANALYSIS", target_id=None,
        ))
        assert any("requires a target_id" in e for e in errors)

    def test_consensus_with_target_ok(self):
        errors = make_dispatcher().validate(make_step(
            "consensus", "CONSENSUS_ANALYSIS", target_id="clu_005",
        ))
        assert len(errors) == 0

    def test_contradiction_requires_target(self):
        errors = make_dispatcher().validate(make_step(
            "contradiction", "CONTRADICTION_ANALYSIS", target_id=None,
        ))
        assert any("requires a target_id" in e for e in errors)

    def test_contradiction_with_target_ok(self):
        errors = make_dispatcher().validate(make_step(
            "contradiction", "CONTRADICTION_ANALYSIS", target_id="clu_060",
        ))
        assert len(errors) == 0

    def test_entity_lookup_no_target_ok(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "ENTITY_LOOKUP", target_id=None,
        ))
        assert len(errors) == 0

    def test_graph_exploration_no_target_ok(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "GRAPH_EXPLORATION", target_id=None,
        ))
        assert len(errors) == 0

    def test_gap_analysis_no_target_ok(self):
        errors = make_dispatcher().validate(make_step(
            "gap", "GAP_ANALYSIS", target_id=None,
        ))
        assert len(errors) == 0


# ===================================================================
# Parameter validation
# ===================================================================


class TestMultiHopParamValidation:
    def test_max_depth_1_valid(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "ENTITY_LOOKUP",
            parameters={"max_depth": 1},
        ))
        assert len(errors) == 0

    def test_max_depth_10_valid(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "ENTITY_LOOKUP",
            parameters={"max_depth": 10},
        ))
        assert len(errors) == 0

    def test_max_depth_5_valid(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "ENTITY_LOOKUP",
            parameters={"max_depth": 5},
        ))
        assert len(errors) == 0

    def test_max_depth_0_invalid(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "ENTITY_LOOKUP",
            parameters={"max_depth": 0},
        ))
        assert any("max_depth" in e for e in errors)

    def test_max_depth_11_invalid(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "ENTITY_LOOKUP",
            parameters={"max_depth": 11},
        ))
        assert any("max_depth" in e for e in errors)

    def test_max_depth_negative_invalid(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "ENTITY_LOOKUP",
            parameters={"max_depth": -1},
        ))
        assert any("max_depth" in e for e in errors)

    def test_max_depth_string_invalid(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "ENTITY_LOOKUP",
            parameters={"max_depth": "deep"},
        ))
        assert any("max_depth" in e for e in errors)

    def test_max_depth_float_invalid_type(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "ENTITY_LOOKUP",
            parameters={"max_depth": 2.5},
        ))
        assert any("max_depth" in e for e in errors)

    def test_no_max_depth_ok(self):
        errors = make_dispatcher().validate(make_step("multi_hop", "ENTITY_LOOKUP"))
        assert len(errors) == 0


class TestConsensusParamValidation:
    def test_min_confidence_0_0_valid(self):
        errors = make_dispatcher().validate(make_step(
            "consensus", "CONSENSUS_ANALYSIS",
            parameters={"min_confidence": 0.0},
        ))
        assert len(errors) == 0

    def test_min_confidence_1_0_valid(self):
        errors = make_dispatcher().validate(make_step(
            "consensus", "CONSENSUS_ANALYSIS",
            parameters={"min_confidence": 1.0},
        ))
        assert len(errors) == 0

    def test_min_confidence_0_5_valid(self):
        errors = make_dispatcher().validate(make_step(
            "consensus", "CONSENSUS_ANALYSIS",
            parameters={"min_confidence": 0.5},
        ))
        assert len(errors) == 0

    def test_min_confidence_negative_invalid(self):
        errors = make_dispatcher().validate(make_step(
            "consensus", "CONSENSUS_ANALYSIS",
            parameters={"min_confidence": -0.1},
        ))
        assert any("min_confidence" in e for e in errors)

    def test_min_confidence_over_1_invalid(self):
        errors = make_dispatcher().validate(make_step(
            "consensus", "CONSENSUS_ANALYSIS",
            parameters={"min_confidence": 1.5},
        ))
        assert any("min_confidence" in e for e in errors)

    def test_min_confidence_string_invalid(self):
        errors = make_dispatcher().validate(make_step(
            "consensus", "CONSENSUS_ANALYSIS",
            parameters={"min_confidence": "high"},
        ))
        assert any("min_confidence" in e for e in errors)

    def test_no_min_confidence_ok(self):
        errors = make_dispatcher().validate(make_step("consensus", "CONSENSUS_ANALYSIS"))
        assert len(errors) == 0


class TestContradictionParamValidation:
    def test_min_confidence_0_3_valid(self):
        errors = make_dispatcher().validate(make_step(
            "contradiction", "CONTRADICTION_ANALYSIS",
            parameters={"min_confidence": 0.3},
        ))
        assert len(errors) == 0

    def test_min_confidence_0_0_valid(self):
        errors = make_dispatcher().validate(make_step(
            "contradiction", "CONTRADICTION_ANALYSIS",
            parameters={"min_confidence": 0.0},
        ))
        assert len(errors) == 0

    def test_min_confidence_negative_invalid(self):
        errors = make_dispatcher().validate(make_step(
            "contradiction", "CONTRADICTION_ANALYSIS",
            parameters={"min_confidence": -0.5},
        ))
        assert any("min_confidence" in e for e in errors)

    def test_min_confidence_over_1_invalid(self):
        errors = make_dispatcher().validate(make_step(
            "contradiction", "CONTRADICTION_ANALYSIS",
            parameters={"min_confidence": 1.1},
        ))
        assert any("min_confidence" in e for e in errors)

    def test_no_min_confidence_ok(self):
        errors = make_dispatcher().validate(make_step("contradiction", "CONTRADICTION_ANALYSIS"))
        assert len(errors) == 0


class TestGapParamValidation:
    def test_gap_types_list_valid(self):
        errors = make_dispatcher().validate(make_step(
            "gap", "GAP_ANALYSIS",
            parameters={"gap_types": ["ISOLATED_ENTITY"]},
        ))
        assert len(errors) == 0

    def test_gap_types_multiple_valid(self):
        errors = make_dispatcher().validate(make_step(
            "gap", "GAP_ANALYSIS",
            parameters={"gap_types": ["A", "B", "C"]},
        ))
        assert len(errors) == 0

    def test_gap_types_empty_invalid(self):
        errors = make_dispatcher().validate(make_step(
            "gap", "GAP_ANALYSIS",
            parameters={"gap_types": []},
        ))
        assert any("gap_types" in e for e in errors)

    def test_gap_types_omitted_ok(self):
        errors = make_dispatcher().validate(make_step("gap", "GAP_ANALYSIS"))
        assert len(errors) == 0

    def test_gap_types_none_ok(self):
        errors = make_dispatcher().validate(make_step(
            "gap", "GAP_ANALYSIS",
            parameters={"gap_types": None},
        ))
        assert len(errors) == 0

    def test_gap_type_non_string_invalid(self):
        errors = make_dispatcher().validate(make_step(
            "gap", "GAP_ANALYSIS",
            parameters={"gap_types": [123]},
        ))
        assert any("gap_type" in e.lower() for e in errors)

    def test_gap_type_empty_string_invalid(self):
        errors = make_dispatcher().validate(make_step(
            "gap", "GAP_ANALYSIS",
            parameters={"gap_types": [""]},
        ))
        assert any("gap_type" in e.lower() for e in errors)

    def test_gap_types_not_list_invalid(self):
        errors = make_dispatcher().validate(make_step(
            "gap", "GAP_ANALYSIS",
            parameters={"gap_types": "ISOLATED_ENTITY"},
        ))
        assert any("gap_types" in e for e in errors)


# ===================================================================
# validate() error states
# ===================================================================


class TestValidateEdgeCases:
    def test_validate_invalid_route_returns_one_error(self):
        errors = make_dispatcher().validate(make_raw_step(engine="bogus", query_type="X"))
        assert len(errors) == 1

    def test_validate_valid_step_returns_empty(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "ENTITY_LOOKUP", target_id="clu_003",
            parameters={"max_depth": 2},
        ))
        assert errors == []

    def test_validate_consensus_step_valid(self):
        errors = make_dispatcher().validate(make_step(
            "consensus", "CONSENSUS_ANALYSIS", target_id="clu_005",
            parameters={"min_confidence": 0.5},
        ))
        assert errors == []

    def test_validate_aggregate_step_valid(self):
        errors = make_dispatcher().validate(make_step(
            "aggregate", "EVIDENCE_COLLECT",
        ))
        assert errors == []

    def test_validate_synthesize_step_valid(self):
        errors = make_dispatcher().validate(make_step(
            "synthesize", "ANSWER_BUILD",
        ))
        assert errors == []

    def test_validate_gap_step_valid(self):
        errors = make_dispatcher().validate(make_step(
            "gap", "GAP_ANALYSIS",
        ))
        assert errors == []

    def test_validate_multiple_errors(self):
        errors = make_dispatcher().validate(make_step(
            "consensus", "CONSENSUS_ANALYSIS",
            target_id=None,
            parameters={"min_confidence": 1.5},
        ))
        assert len(errors) >= 2


# ===================================================================
# Plan-level routing
# ===================================================================


class TestRoutePlan:
    def test_route_plan_single_step(self):
        plan = make_plan()
        routes = make_dispatcher().route_plan(plan)
        assert len(routes) == 1
        assert isinstance(routes[0], StepRoute)

    def test_route_plan_multiple_steps(self):
        steps = [
            make_step("multi_hop", "ENTITY_LOOKUP"),
            make_step("consensus", "CONSENSUS_ANALYSIS", target_id="clu_005"),
            make_step("aggregate", "EVIDENCE_COLLECT"),
            make_step("synthesize", "ANSWER_BUILD"),
        ]
        plan = make_plan(steps)
        routes = make_dispatcher().route_plan(plan)
        assert len(routes) == 4
        assert routes[0].engine == "multi_hop"
        assert routes[1].engine == "consensus"
        assert routes[2].engine == "aggregate"
        assert routes[3].engine == "synthesize"

    def test_route_plan_preserves_step_ids(self):
        steps = [
            make_step(step_id="s1", engine="multi_hop", query_type="ENTITY_LOOKUP"),
            make_step(step_id="s2", engine="gap", query_type="GAP_ANALYSIS"),
        ]
        plan = make_plan(steps)
        routes = make_dispatcher().route_plan(plan)
        assert [r.step_id for r in routes] == ["s1", "s2"]

    def test_route_plan_m4_methods(self):
        plan = make_plan([
            make_step("multi_hop", "ENTITY_LOOKUP"),
            make_step("consensus", "CONSENSUS_ANALYSIS", target_id="c"),
            make_step("aggregate", "EVIDENCE_COLLECT"),
        ])
        routes = make_dispatcher().route_plan(plan)
        assert routes[0].m4_method == "reason"
        assert routes[1].m4_method == "analyze"
        assert routes[2].m4_method is None

    def test_route_plan_executable_flags(self):
        plan = make_plan([
            make_step("multi_hop", "ENTITY_LOOKUP"),
            make_step("aggregate", "EVIDENCE_COLLECT"),
            make_step("synthesize", "ANSWER_BUILD"),
        ])
        routes = make_dispatcher().route_plan(plan)
        assert routes[0].is_executable is True
        assert routes[1].is_executable is False
        assert routes[2].is_executable is False

    def test_route_plan_with_factual(self):
        from researchmind.query.planner import create_plan
        from researchmind.query.models import ParsedQuery, QueryEntity

        parsed = ParsedQuery(
            raw_query="what is BERT",
            query_type="FACTUAL",
            primary_entity=QueryEntity(text="BERT", cluster_id="clu_003"),
            entities_resolved=True,
        )
        plan = create_plan(parsed)
        routes = make_dispatcher().route_plan(plan)
        assert len(routes) == 3
        assert routes[0].engine == "multi_hop"
        assert routes[0].m4_query_type == "ENTITY_LOOKUP"
        assert routes[1].engine == "aggregate"
        assert routes[1].m4_query_type == "EVIDENCE_COLLECT"
        assert routes[2].engine == "synthesize"
        assert routes[2].m4_query_type == "ANSWER_BUILD"

    def test_route_plan_with_comparison(self):
        from researchmind.query.planner import create_plan
        from researchmind.query.models import ParsedQuery, QueryEntity

        parsed = ParsedQuery(
            raw_query="compare A and B",
            query_type="COMPARISON",
            primary_entity=QueryEntity(text="A", cluster_id="clu_a"),
            secondary_entities=[QueryEntity(text="B", cluster_id="clu_b")],
            entities_resolved=True,
        )
        plan = create_plan(parsed)
        routes = make_dispatcher().route_plan(plan)
        assert len(routes) == 5
        assert routes[0].engine == "multi_hop"
        assert routes[2].engine == "consensus"

    def test_route_plan_all_types(self):
        from researchmind.query.planner import create_plan
        from researchmind.query.models import ParsedQuery, QueryEntity

        def p(qt, ent=True):
            return ParsedQuery(
                raw_query=f"test {qt}",
                query_type=qt,
                primary_entity=QueryEntity(text="X", cluster_id="clu_x") if ent else None,
                secondary_entities=([QueryEntity(text="Y", cluster_id="clu_y")] if qt == "COMPARISON" else []),
                entities_resolved=ent,
            )

        types = ["FACTUAL", "EXPLANATION", "COMPARISON", "CONSENSUS",
                 "CONTRADICTION", "RESEARCH_GAP", "MULTI_HOP", "EXPLORATION"]
        for qt in types:
            parsed = p(qt)
            plan = create_plan(parsed)
            routes = make_dispatcher().route_plan(plan)
            assert len(routes) == plan.total_steps
            assert len(routes) > 0


class TestValidatePlan:
    def test_validate_plan_all_valid(self):
        plan = make_plan([
            make_step("multi_hop", "ENTITY_LOOKUP", target_id="c1"),
            make_step("consensus", "CONSENSUS_ANALYSIS", target_id="c2"),
        ])
        errors = make_dispatcher().validate_plan(plan)
        assert errors == []

    def test_validate_plan_with_errors(self):
        plan = make_plan([
            make_step("multi_hop", "PATH_REASONING", target_id=None),
            make_step("consensus", "CONSENSUS_ANALYSIS", target_id=None),
        ])
        errors = make_dispatcher().validate_plan(plan)
        assert len(errors) == 2

    def test_validate_plan_mixed_valid_invalid(self):
        plan = make_plan([
            make_step("multi_hop", "ENTITY_LOOKUP"),
            make_step("consensus", "CONSENSUS_ANALYSIS", target_id=None),
            make_step("aggregate", "EVIDENCE_COLLECT"),
        ])
        errors = make_dispatcher().validate_plan(plan)
        assert len(errors) == 1

    def test_validate_plan_invalid_route(self):
        plan = make_plan([
            make_raw_step(engine="bogus", query_type="X"),
        ])
        errors = make_dispatcher().validate_plan(plan)
        assert len(errors) == 1

    def test_validate_plan_empty_plan(self):
        plan = make_plan(steps=[])
        errors = make_dispatcher().validate_plan(plan)
        assert errors == []


# ===================================================================
# Metadata and introspection
# ===================================================================


class TestMetadata:
    def test_available_routes_count(self):
        routes = make_dispatcher().available_routes()
        assert len(routes) == 12

    def test_available_routes_contains_multi_hop(self):
        routes = make_dispatcher().available_routes()
        assert ("multi_hop", "ENTITY_LOOKUP") in routes
        assert ("multi_hop", "GRAPH_EXPLORATION") in routes
        assert ("multi_hop", "PATH_REASONING") in routes

    def test_available_routes_contains_consensus(self):
        routes = make_dispatcher().available_routes()
        assert ("consensus", "CONSENSUS_ANALYSIS") in routes
        assert ("consensus", "COMPARISON_ANALYSIS") in routes

    def test_available_routes_contains_contradiction(self):
        routes = make_dispatcher().available_routes()
        assert ("contradiction", "CONTRADICTION_ANALYSIS") in routes

    def test_available_routes_contains_gap(self):
        routes = make_dispatcher().available_routes()
        assert ("gap", "GAP_ANALYSIS") in routes

    def test_available_routes_contains_aggregate(self):
        routes = make_dispatcher().available_routes()
        assert ("aggregate", "EVIDENCE_COLLECT") in routes
        assert ("aggregate", "COMPARISON_ANALYSIS") in routes
        assert ("aggregate", "MERGE_CONTRADICTIONS") in routes
        assert ("aggregate", "FILTER_GAPS") in routes

    def test_available_routes_contains_synthesize(self):
        routes = make_dispatcher().available_routes()
        assert ("synthesize", "ANSWER_BUILD") in routes

    def test_count_routes(self):
        assert make_dispatcher().count_routes() == 12

    def test_get_route_info_exists(self):
        info = make_dispatcher().get_route_info("multi_hop", "ENTITY_LOOKUP")
        assert info is not None
        assert info["m4_method"] == "reason"

    def test_get_route_info_consensus(self):
        info = make_dispatcher().get_route_info("consensus", "CONSENSUS_ANALYSIS")
        assert info is not None
        assert info["m4_method"] == "analyze"

    def test_get_route_info_aggregate(self):
        info = make_dispatcher().get_route_info("aggregate", "EVIDENCE_COLLECT")
        assert info is not None
        assert info["m4_method"] is None

    def test_get_route_info_not_found(self):
        info = make_dispatcher().get_route_info("multi_hop", "BOGUS")
        assert info is None

    def test_get_route_info_wrong_engine(self):
        info = make_dispatcher().get_route_info("gap", "ENTITY_LOOKUP")
        assert info is None


# ===================================================================
# Determinism
# ===================================================================


class TestDeterminism:
    def test_route_deterministic(self):
        d = make_dispatcher()
        step = make_step("multi_hop", "ENTITY_LOOKUP", target_id="clu_003")
        r1 = d.route(step)
        r2 = d.route(step)
        assert r1.step_id == r2.step_id
        assert r1.engine == r2.engine
        assert r1.m4_query_type == r2.m4_query_type
        assert r1.m4_method == r2.m4_method
        assert r1.m4_params == r2.m4_params
        assert r1.is_executable == r2.is_executable

    def test_route_plan_deterministic(self):
        d = make_dispatcher()
        steps = [
            make_step("multi_hop", "ENTITY_LOOKUP"),
            make_step("consensus", "CONSENSUS_ANALYSIS", target_id="c"),
            make_step("aggregate", "EVIDENCE_COLLECT"),
        ]
        plan = make_plan(steps)
        r1 = d.route_plan(plan)
        r2 = d.route_plan(plan)
        for a, b in zip(r1, r2):
            assert a.step_id == b.step_id
            assert a.engine == b.engine

    def test_available_routes_deterministic(self):
        d = make_dispatcher()
        r1 = d.available_routes()
        r2 = d.available_routes()
        assert r1 == r2

    def test_validate_deterministic(self):
        d = make_dispatcher()
        step = make_step("consensus", "CONSENSUS_ANALYSIS", target_id=None)
        e1 = d.validate(step)
        e2 = d.validate(step)
        assert e1 == e2

    def test_no_random_ids(self):
        route = make_dispatcher().route(make_step())
        assert "step_" in route.step_id


# ===================================================================
# Convenience functions
# ===================================================================


class TestConvenienceFunctions:
    def test_route_step(self):
        step = make_step("multi_hop", "ENTITY_LOOKUP", target_id="clu_003")
        route = route_step(step)
        assert isinstance(route, StepRoute)
        assert route.engine == "multi_hop"
        assert route.m4_query_type == "ENTITY_LOOKUP"

    def test_route_step_consensus(self):
        step = make_step("consensus", "CONSENSUS_ANALYSIS", target_id="clu_005")
        route = route_step(step)
        assert route.engine == "consensus"
        assert route.m4_method == "analyze"

    def test_route_step_aggregate(self):
        step = make_step("aggregate", "EVIDENCE_COLLECT")
        route = route_step(step)
        assert route.engine == "aggregate"
        assert route.is_executable is False

    def test_route_plan_convenience(self):
        plan = make_plan([
            make_step("multi_hop", "ENTITY_LOOKUP"),
            make_step("aggregate", "EVIDENCE_COLLECT"),
        ])
        routes = route_plan(plan)
        assert len(routes) == 2

    def test_route_step_module_function_matches_method(self):
        step = make_step("multi_hop", "ENTITY_LOOKUP")
        from_method = make_dispatcher().route(step)
        from_func = route_step(step)
        assert from_method.step_id == from_func.step_id
        assert from_method.engine == from_func.engine
        assert from_method.m4_query_type == from_func.m4_query_type


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    def test_no_target_id_none(self):
        route = make_dispatcher().route(make_step(
            "multi_hop", "ENTITY_LOOKUP", target_id=None,
        ))
        assert route.target_id is None

    def test_empty_secondary_ids(self):
        route = make_dispatcher().route(make_step(
            "multi_hop", "ENTITY_LOOKUP", secondary_ids=[],
        ))
        assert route.secondary_ids == []

    def test_empty_parameters(self):
        route = make_dispatcher().route(make_step(
            "multi_hop", "ENTITY_LOOKUP", parameters={},
        ))
        assert route.m4_params["min_confidence"] == 0.3
        assert route.m4_params["max_depth"] == 3

    def test_parameters_with_extra_fields(self):
        route = make_dispatcher().route(make_step(
            "multi_hop", "ENTITY_LOOKUP",
            parameters={"extra": "value", "max_depth": 5},
        ))
        assert route.m4_params["extra"] == "value"
        assert route.m4_params["max_depth"] == 5

    def test_min_confidence_preserved_when_set(self):
        route = make_dispatcher().route(make_step(
            "multi_hop", "ENTITY_LOOKUP",
            parameters={"min_confidence": 0.9},
        ))
        assert route.m4_params["min_confidence"] == 0.9

    def test_aggregate_with_all_params(self):
        route = make_dispatcher().route(make_step(
            "aggregate", "EVIDENCE_COLLECT",
            target_id="clu_003",
            secondary_ids=["clu_a", "clu_b"],
            parameters={"dedup_by": "doc_id"},
        ))
        assert route.target_id == "clu_003"
        assert route.secondary_ids == ["clu_a", "clu_b"]
        assert route.m4_params["dedup_by"] == "doc_id"
        assert route.is_executable is False

    def test_step_id_preserved(self):
        route = make_dispatcher().route(make_step(step_id="custom_id"))
        assert route.step_id == "custom_id"

    def test_secondary_ids_order_preserved(self):
        route = make_dispatcher().route(make_step(
            "multi_hop", "PATH_REASONING",
            secondary_ids=["z", "a", "m"],
        ))
        assert route.secondary_ids == ["z", "a", "m"]

    def test_validate_unknown_engine_unreachable(self):
        errors = make_dispatcher().validate(make_step(
            engine="multi_hop", query_type="PATH_REASONING",
            target_id=None,
        ))
        assert len(errors) == 1
        assert "requires a target_id" in errors[0]

    def test_validate_all_engines_at_once(self):
        for engine in ("multi_hop", "consensus", "contradiction", "gap"):
            for qt_info in _all_routes_for_engine(engine):
                step = make_step(engine=engine, query_type=qt_info["qt"], **qt_info.get("extra", {}))
                errors = make_dispatcher().validate(step)
                assert isinstance(errors, list)


def _all_routes_for_engine(engine: str) -> list[dict]:
    table = {
        "multi_hop": [
            {"qt": "ENTITY_LOOKUP", "extra": {}},
            {"qt": "GRAPH_EXPLORATION", "extra": {}},
            {"qt": "PATH_REASONING", "extra": {"target_id": "clu_x"}},
        ],
        "consensus": [
            {"qt": "CONSENSUS_ANALYSIS", "extra": {"target_id": "clu_x"}},
            {"qt": "COMPARISON_ANALYSIS", "extra": {"target_id": "clu_x"}},
        ],
        "contradiction": [{"qt": "CONTRADICTION_ANALYSIS", "extra": {"target_id": "clu_x"}}],
        "gap": [{"qt": "GAP_ANALYSIS", "extra": {}}],
    }
    return table.get(engine, [])


# ===================================================================
# Parameter boundary and edge cases
# ===================================================================


class TestParamBoundaries:
    def test_max_depth_exactly_1(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "ENTITY_LOOKUP", parameters={"max_depth": 1},
        ))
        assert errors == []

    def test_max_depth_exactly_10(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "ENTITY_LOOKUP", parameters={"max_depth": 10},
        ))
        assert errors == []

    def test_max_depth_just_under_1(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "ENTITY_LOOKUP", parameters={"max_depth": 0},
        ))
        assert len(errors) > 0

    def test_max_depth_just_over_10(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "ENTITY_LOOKUP", parameters={"max_depth": 11},
        ))
        assert len(errors) > 0

    def test_min_confidence_exactly_0(self):
        for eng in ("consensus", "contradiction"):
            errors = make_dispatcher().validate(make_step(
                eng, f"CONSENSUS_ANALYSIS" if eng == "consensus" else "CONTRADICTION_ANALYSIS",
                target_id="clu_x",
                parameters={"min_confidence": 0.0},
            ))
            assert errors == []

    def test_min_confidence_exactly_1(self):
        for eng in ("consensus", "contradiction"):
            errors = make_dispatcher().validate(make_step(
                eng, f"CONSENSUS_ANALYSIS" if eng == "consensus" else "CONTRADICTION_ANALYSIS",
                target_id="clu_x",
                parameters={"min_confidence": 1.0},
            ))
            assert errors == []

    def test_min_confidence_just_under_0(self):
        errors = make_dispatcher().validate(make_step(
            "consensus", "CONSENSUS_ANALYSIS",
            target_id="clu_x",
            parameters={"min_confidence": -0.001},
        ))
        assert len(errors) > 0

    def test_min_confidence_just_over_1(self):
        errors = make_dispatcher().validate(make_step(
            "consensus", "CONSENSUS_ANALYSIS",
            target_id="clu_x",
            parameters={"min_confidence": 1.001},
        ))
        assert len(errors) > 0


# ===================================================================
# Edge: empty plan
# ===================================================================


class TestEmptyPlan:
    def test_empty_plan_validates(self):
        plan = make_plan(steps=[])
        errors = make_dispatcher().validate_plan(plan)
        assert errors == []

    def test_empty_plan_routes_to_empty(self):
        plan = ExecutionPlan(
            plan_id="plan_empty", query_id="", query_type="FACTUAL",
            steps=[], total_steps=0,
        )
        routes = make_dispatcher().route_plan(plan)
        assert routes == []

    def test_empty_plan_via_convenience(self):
        plan = ExecutionPlan(
            plan_id="plan_empty", query_id="", query_type="FACTUAL",
            steps=[], total_steps=0,
        )
        routes = route_plan(plan)
        assert routes == []


# ===================================================================
# Edge: module-level constants accessibility
# ===================================================================


class TestModuleConstants:
    def test_import_step_route(self):
        from researchmind.query.router import StepRoute
        assert StepRoute is not None

    def test_import_step_dispatcher(self):
        from researchmind.query.router import StepDispatcher
        assert StepDispatcher is not None

    def test_import_route_step(self):
        from researchmind.query.router import route_step
        assert callable(route_step)

    def test_import_route_plan(self):
        from researchmind.query.router import route_plan
        assert callable(route_plan)

    def test_imports_from_package(self):
        from researchmind.query import StepDispatcher, StepRoute, route_plan, route_step
        assert StepDispatcher is not None
        assert StepRoute is not None


# ===================================================================
# Error message quality
# ===================================================================


class TestErrorMessages:
    def test_unknown_route_message_contains_route(self):
        with pytest.raises(ValueError) as exc:
            make_dispatcher().route(make_raw_step(engine="multi_hop", query_type="BOGUS"))
        msg = str(exc.value)
        assert "multi_hop/BOGUS" in msg
        assert "Unknown route" in msg

    def test_unknown_route_message_has_count(self):
        with pytest.raises(ValueError) as exc:
            make_dispatcher().route(make_step(engine="multi_hop", query_type="BOGUS"))
        msg = str(exc.value)
        assert "registered" in msg

    def test_target_requirement_message_contains_step_id(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "PATH_REASONING", target_id=None, step_id="my_step",
        ))
        assert "my_step" in errors[0]

    def test_max_depth_error_message_contains_value(self):
        errors = make_dispatcher().validate(make_step(
            "multi_hop", "ENTITY_LOOKUP",
            parameters={"max_depth": "bad"},
        ))
        assert "'bad'" in errors[0] or "bad" in errors[0]

    def test_min_confidence_error_message_contains_value(self):
        errors = make_dispatcher().validate(make_step(
            "consensus", "CONSENSUS_ANALYSIS",
            target_id="clu_x",
            parameters={"min_confidence": "high"},
        ))
        assert "'high'" in errors[0] or "high" in errors[0]
