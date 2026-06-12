"""Deterministic step router for the Research Assistant Layer (Module 5).

Translates PlanSteps into M4-compatible routing directives — validates every
(engine, query_type) route exists, checks parameter constraints, and identifies
which steps dispatch to M4 vs. are handled internally by M5 (aggregate/synthesize).
No execution, no corpus access — pure translation + validation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from researchmind.query.models import ExecutionPlan, PlanStep

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_M4_ENGINES = frozenset({
    "multi_hop", "consensus", "contradiction", "gap",
})

_AGGREGATE_ENGINES = frozenset({"aggregate", "synthesize"})

_ALL_ENGINES = _VALID_M4_ENGINES | _AGGREGATE_ENGINES

_VALID_M4_QUERY_TYPES = frozenset({
    "ENTITY_LOOKUP", "DOCUMENT_LOOKUP", "PATH_REASONING",
    "CONSENSUS_ANALYSIS", "CONTRADICTION_ANALYSIS", "GAP_ANALYSIS",
    "GRAPH_EXPLORATION",
})

_VALID_M5_INTERNAL_TYPES = frozenset({
    "EVIDENCE_COLLECT", "ANSWER_BUILD", "COMPARISON_ANALYSIS",
    "MERGE_CONTRADICTIONS", "FILTER_GAPS",
})

_ALL_QUERY_TYPES = _VALID_M4_QUERY_TYPES | _VALID_M5_INTERNAL_TYPES

_REQUIRES_TARGET: dict[str, set[str]] = {
    "multi_hop": {"PATH_REASONING"},
    "consensus": {"CONSENSUS_ANALYSIS"},
    "contradiction": {"CONTRADICTION_ANALYSIS"},
}

_EXECUTABLE_ENGINES = _VALID_M4_ENGINES  # aggregate/synthesize are M5-internal

# ---------------------------------------------------------------------------
# Routing table — defines valid (engine, query_type) combos and their M4 method
# ---------------------------------------------------------------------------

_ROUTING_TABLE: dict[str, dict[str, dict[str, Any]]] = {
    "multi_hop": {
        "ENTITY_LOOKUP": {"m4_method": "reason"},
        "GRAPH_EXPLORATION": {"m4_method": "reason"},
        "PATH_REASONING": {"m4_method": "reason"},
    },
    "consensus": {
        "CONSENSUS_ANALYSIS": {"m4_method": "analyze"},
        "COMPARISON_ANALYSIS": {"m4_method": "analyze"},
    },
    "contradiction": {
        "CONTRADICTION_ANALYSIS": {"m4_method": "analyze"},
    },
    "gap": {
        "GAP_ANALYSIS": {"m4_method": "analyze"},
    },
    "aggregate": {
        "EVIDENCE_COLLECT": {"m4_method": None},
        "COMPARISON_ANALYSIS": {"m4_method": None},
        "MERGE_CONTRADICTIONS": {"m4_method": None},
        "FILTER_GAPS": {"m4_method": None},
    },
    "synthesize": {
        "ANSWER_BUILD": {"m4_method": None},
    },
}

_ROUTE_INDEX: dict[tuple[str, str], dict[str, Any]] = {}
for _eng, _types in _ROUTING_TABLE.items():
    for _qt, _info in _types.items():
        _ROUTE_INDEX[(_eng, _qt)] = _info


# ---------------------------------------------------------------------------
# StepRoute model
# ---------------------------------------------------------------------------


class StepRoute(BaseModel):
    """A validated routing directive for a single PlanStep.

    Translates a PlanStep's engine + query_type into the exact M4
    sub-engine and query parameters expected by the ReasoningEngine.
    """

    step_id: str
    engine: str
    m4_query_type: str
    m4_method: str | None = None
    target_id: str | None = None
    secondary_ids: list[str] = Field(default_factory=list)
    m4_params: dict[str, Any] = Field(default_factory=dict)
    is_executable: bool = True

    @field_validator("engine")
    @classmethod
    def _validate_engine(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in _ALL_ENGINES:
            raise ValueError(
                f"Unknown engine '{v}'. Must be one of {sorted(_ALL_ENGINES)}"
            )
        return normalized

    @field_validator("m4_query_type")
    @classmethod
    def _validate_m4_query_type(cls, v: str) -> str:
        normalized = v.strip().upper()
        if normalized not in _ALL_QUERY_TYPES:
            raise ValueError(
                f"Unknown m4_query_type '{v}'. Must be one of {sorted(_ALL_QUERY_TYPES)}"
            )
        return normalized


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class StepDispatcher:
    """Translates PlanSteps into M4 routing directives.

    Validates every step has a known (engine, query_type) route and
    produces the parameters needed for M4 dispatch.

    Usage::

        dispatcher = StepDispatcher()
        route = dispatcher.route(plan_step)
        # route.engine == "multi_hop", route.m4_query_type == "ENTITY_LOOKUP"
    """

    # ------------------------------------------------------------------
    # Main entry points
    # ------------------------------------------------------------------

    def route(self, step: PlanStep) -> StepRoute:
        """Translate a single PlanStep into a StepRoute.

        Raises ``ValueError`` if the (engine, query_type) pair is not
        found in the routing table.
        """
        info = self._lookup(step.engine, step.query_type)
        is_exec = step.engine in _EXECUTABLE_ENGINES

        return StepRoute(
            step_id=step.step_id,
            engine=step.engine,
            m4_query_type=step.query_type,
            m4_method=info.get("m4_method"),
            target_id=step.target_id,
            secondary_ids=list(step.secondary_ids),
            m4_params=self._build_m4_params(step),
            is_executable=is_exec,
        )

    def route_plan(self, plan: ExecutionPlan) -> list[StepRoute]:
        """Translate every step in a plan into a StepRoute."""
        return [self.route(s) for s in plan.steps]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, step: PlanStep) -> list[str]:
        """Validate a PlanStep has a known, well-formed route.

        Returns a list of error messages (empty = valid).
        """
        errors: list[str] = []

        try:
            self._lookup(step.engine, step.query_type)
        except ValueError as exc:
            return [str(exc)]

        self._validate_target_requirement(step, errors)
        self._validate_parameters(step, errors)

        return errors

    def validate_plan(self, plan: ExecutionPlan) -> list[str]:
        """Validate all steps in a plan have known routes."""
        all_errors: list[str] = []
        for step in plan.steps:
            all_errors.extend(self.validate(step))
        return all_errors

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_target_requirement(step: PlanStep, errors: list[str]) -> None:
        """Check if the step's engine+query_type requires a target_id."""
        engine_reqs = _REQUIRES_TARGET.get(step.engine, {})
        if step.query_type in engine_reqs and not step.target_id:
            errors.append(
                f"Step '{step.step_id}' ({step.engine}/{step.query_type}) "
                f"requires a target_id but none was provided"
            )

    @staticmethod
    def _validate_parameters(step: PlanStep, errors: list[str]) -> None:
        """Engine-specific parameter validation."""
        params = step.parameters or {}

        if step.engine == "multi_hop":
            depth = params.get("max_depth", 3)
            if not isinstance(depth, int) or depth < 1 or depth > 10:
                errors.append(
                    f"Step '{step.step_id}': multi_hop max_depth must be "
                    f"an int in [1, 10], got {depth!r}"
                )

        elif step.engine in ("consensus", "contradiction"):
            conf = params.get("min_confidence", 0.3)
            if not isinstance(conf, (int, float)) or conf < 0.0 or conf > 1.0:
                errors.append(
                    f"Step '{step.step_id}': {step.engine} min_confidence must "
                    f"be in [0.0, 1.0], got {conf!r}"
                )

        elif step.engine == "gap":
            gap_types = params.get("gap_types")
            if gap_types is not None and (
                not isinstance(gap_types, list) or len(gap_types) == 0
            ):
                errors.append(
                    f"Step '{step.step_id}': gap gap_types must be a "
                    f"non-empty list or omitted entirely"
                )
            if gap_types is not None:
                for gt in gap_types:
                    if not isinstance(gt, str) or not gt.strip():
                        errors.append(
                            f"Step '{step.step_id}': each gap_type must be "
                            f"a non-empty string, got {gt!r}"
                        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_m4_params(step: PlanStep) -> dict[str, Any]:
        """Build the parameter dict for M4 ReasoningQuery."""
        params = dict(step.parameters)

        if "min_confidence" not in params:
            params["min_confidence"] = 0.3

        if step.engine == "multi_hop" and "max_depth" not in params:
            params["max_depth"] = 3

        return params

    @staticmethod
    def _lookup(engine: str, query_type: str) -> dict[str, Any]:
        """Look up a route entry in the routing table.

        Raises ``ValueError`` if the (engine, query_type) pair is unknown.
        """
        eng = engine.strip().lower()
        qt = query_type.strip().upper()
        info = _ROUTE_INDEX.get((eng, qt))

        if info is None:
            known = sorted(f"{e}/{q}" for (e, q) in _ROUTE_INDEX)
            raise ValueError(
                f"Unknown route '{engine}/{query_type}'. "
                f"Known routes: {len(known)} registered"
            )
        return info

    @staticmethod
    def available_routes() -> list[tuple[str, str]]:
        """Return all registered (engine, query_type) routes."""
        return sorted(_ROUTE_INDEX.keys())

    @staticmethod
    def count_routes() -> int:
        """Return the number of registered routes."""
        return len(_ROUTE_INDEX)

    @staticmethod
    def get_route_info(engine: str, query_type: str) -> dict[str, Any] | None:
        """Return route info dict or None if not found."""
        eng = engine.strip().lower()
        qt = query_type.strip().upper()
        return _ROUTE_INDEX.get((eng, qt))


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def route_step(step: PlanStep) -> StepRoute:
    """Convenience function to route a single PlanStep."""
    return StepDispatcher().route(step)


def route_plan(plan: ExecutionPlan) -> list[StepRoute]:
    """Convenience function to route all steps in a plan."""
    return StepDispatcher().route_plan(plan)
