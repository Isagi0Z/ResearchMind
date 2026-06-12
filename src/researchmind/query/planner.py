"""Deterministic query planner for the Research Assistant Layer (Module 5).

Converts a ParsedQuery into an ExecutionPlan with ordered PlanSteps,
parallel groups, and complexity estimation — no execution, routing,
or corpus access.
"""

from __future__ import annotations

from typing import Any

from researchmind.query.models import ExecutionPlan, ParsedQuery, PlanStep


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class QueryPlanner:
    """Creates deterministic execution plans from parsed queries.

    Usage::

        planner = QueryPlanner()
        plan = planner.create_plan(parsed_query)
    """

    def __init__(self) -> None:
        self._step_counter: int = 0

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def create_plan(self, parsed: ParsedQuery) -> ExecutionPlan:
        """Build an ExecutionPlan for a parsed query.

        Raises ``ValueError`` for unsupported query types.
        """
        builders = {
            "FACTUAL": self._plan_factual,
            "COMPARISON": self._plan_comparison,
            "EXPLANATION": self._plan_explanation,
            "CONSENSUS": self._plan_consensus,
            "CONTRADICTION": self._plan_contradiction,
            "RESEARCH_GAP": self._plan_research_gap,
            "MULTI_HOP": self._plan_multi_hop,
            "EXPLORATION": self._plan_exploration,
        }

        builder = builders.get(parsed.query_type)
        if builder is None:
            raise ValueError(f"Unsupported query type: {parsed.query_type}")

        self._step_counter = 0
        plan_id = self._generate_plan_id(parsed)
        steps = builder(parsed)

        self._validate_plan(steps)

        parallel = self._compute_parallel_groups(steps)
        complexity = self._estimate_complexity(steps)

        warnings: list[str] = list(parsed.parsing_warnings)
        if parsed.primary_entity and parsed.primary_entity.is_ambiguous:
            warnings.append(
                f"Ambiguous primary entity '{parsed.primary_entity.text}'"
            )
        if not parsed.entities_resolved:
            warnings.append(
                f"Entities not resolved for {parsed.query_type} query"
            )

        return ExecutionPlan(
            plan_id=plan_id,
            query_id="",
            query_type=parsed.query_type,
            steps=steps,
            total_steps=len(steps),
            parallel_groups=parallel,
            estimated_complexity=complexity,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Step and ID helpers
    # ------------------------------------------------------------------

    def _next_step_id(self) -> str:
        self._step_counter += 1
        return f"step_{self._step_counter:03d}"

    def _generate_plan_id(self, parsed: ParsedQuery) -> str:
        import zlib

        raw = parsed.raw_query or ""
        key = f"{raw}::{parsed.query_type}"
        h = zlib.crc32(key.encode()) & 0xFFFFFFFF
        return f"plan_{h:012x}"

    def _make_step(
        self,
        engine: str,
        query_type: str,
        target_id: str | None = None,
        secondary_ids: list[str] | None = None,
        parameters: dict[str, Any] | None = None,
        dependencies: list[str] | None = None,
    ) -> PlanStep:
        step_id = self._next_step_id()
        return PlanStep(
            step_id=step_id,
            sequence=self._step_counter,
            engine=engine,
            query_type=query_type,
            target_id=target_id,
            secondary_ids=secondary_ids or [],
            parameters=parameters or {},
            dependencies=dependencies or [],
        )

    # ------------------------------------------------------------------
    # Plan builders — one per query type
    # ------------------------------------------------------------------

    def _plan_factual(self, parsed: ParsedQuery) -> list[PlanStep]:
        target = self._primary_target(parsed)
        s1 = self._make_step(
            "multi_hop", "ENTITY_LOOKUP", target,
            parameters={"max_depth": min(2, parsed.max_hops)},
        )
        s2 = self._make_step(
            "aggregate", "EVIDENCE_COLLECT", target,
            parameters={"dedup_by": "evidence_id"},
            dependencies=[s1.step_id],
        )
        s3 = self._make_step(
            "synthesize", "ANSWER_BUILD",
            parameters={"template": "factual"},
            dependencies=[s2.step_id],
        )
        return [s1, s2, s3]

    def _plan_explanation(self, parsed: ParsedQuery) -> list[PlanStep]:
        target = self._primary_target(parsed)
        s1 = self._make_step(
            "multi_hop", "ENTITY_LOOKUP", target,
            parameters={"max_depth": min(2, parsed.max_hops)},
        )
        s2 = self._make_step(
            "multi_hop", "GRAPH_EXPLORATION", target,
            parameters={"max_depth": min(3, parsed.max_hops)},
            dependencies=[s1.step_id],
        )
        s3 = self._make_step(
            "aggregate", "EVIDENCE_COLLECT", target,
            parameters={"dedup_by": "path_id"},
            dependencies=[s2.step_id],
        )
        s4 = self._make_step(
            "synthesize", "ANSWER_BUILD",
            parameters={"template": "explanation"},
            dependencies=[s3.step_id],
        )
        return [s1, s2, s3, s4]

    def _plan_comparison(self, parsed: ParsedQuery) -> list[PlanStep]:
        primary = parsed.primary_entity
        secondary = parsed.secondary_entities[0] if parsed.secondary_entities else None
        target_a = primary.cluster_id if primary else None
        target_b = secondary.cluster_id if secondary else None

        s1 = self._make_step(
            "multi_hop", "ENTITY_LOOKUP", target_a,
            parameters={"max_depth": min(2, parsed.max_hops)},
        )
        s2 = self._make_step(
            "multi_hop", "ENTITY_LOOKUP", target_b,
            parameters={"max_depth": min(2, parsed.max_hops)},
        )
        s3 = self._make_step(
            "consensus", "COMPARISON_ANALYSIS",
            target_id=target_a,
            secondary_ids=[target_b] if target_b else [],
            parameters={"min_confidence": parsed.min_confidence},
            dependencies=[s1.step_id, s2.step_id],
        )
        s4 = self._make_step(
            "aggregate", "EVIDENCE_COLLECT",
            parameters={"dedup_by": "evidence_id"},
            dependencies=[s3.step_id],
        )
        s5 = self._make_step(
            "synthesize", "ANSWER_BUILD",
            parameters={"template": "comparison"},
            dependencies=[s4.step_id],
        )
        return [s1, s2, s3, s4, s5]

    def _plan_consensus(self, parsed: ParsedQuery) -> list[PlanStep]:
        target = self._primary_target(parsed)
        s1 = self._make_step(
            "multi_hop", "ENTITY_LOOKUP", target,
            parameters={"max_depth": min(2, parsed.max_hops)},
        )
        s2 = self._make_step(
            "consensus", "CONSENSUS_ANALYSIS", target,
            parameters={"min_confidence": parsed.min_confidence},
            dependencies=[s1.step_id],
        )
        s3 = self._make_step(
            "aggregate", "EVIDENCE_COLLECT", target,
            parameters={"dedup_by": "doc_id"},
            dependencies=[s2.step_id],
        )
        s4 = self._make_step(
            "synthesize", "ANSWER_BUILD",
            parameters={"template": "consensus"},
            dependencies=[s3.step_id],
        )
        return [s1, s2, s3, s4]

    def _plan_contradiction(self, parsed: ParsedQuery) -> list[PlanStep]:
        target = self._primary_target(parsed)
        s1 = self._make_step(
            "multi_hop", "ENTITY_LOOKUP", target,
            parameters={"max_depth": min(2, parsed.max_hops)},
        )
        s2 = self._make_step(
            "contradiction", "CONTRADICTION_ANALYSIS", target,
            parameters={"min_confidence": parsed.min_confidence},
            dependencies=[s1.step_id],
        )
        s3 = self._make_step(
            "aggregate", "EVIDENCE_COLLECT", target,
            parameters={"dedup_by": "pair_id"},
            dependencies=[s2.step_id],
        )
        s4 = self._make_step(
            "synthesize", "ANSWER_BUILD",
            parameters={"template": "contradiction"},
            dependencies=[s3.step_id],
        )
        return [s1, s2, s3, s4]

    def _plan_research_gap(self, parsed: ParsedQuery) -> list[PlanStep]:
        target = self._primary_target(parsed)
        s1 = self._make_step(
            "multi_hop", "ENTITY_LOOKUP", target,
            parameters={"max_depth": min(2, parsed.max_hops)},
        )
        s2 = self._make_step(
            "gap", "GAP_ANALYSIS", target,
            parameters={
                "gap_types": [
                    "ISOLATED_ENTITY",
                    "MISSING_COMPARISON",
                    "LOW_CONFIDENCE_CLAIM",
                ],
            },
            dependencies=[s1.step_id],
        )
        s3 = self._make_step(
            "aggregate", "EVIDENCE_COLLECT", target,
            parameters={"dedup_by": "gap_key"},
            dependencies=[s2.step_id],
        )
        s4 = self._make_step(
            "synthesize", "ANSWER_BUILD",
            parameters={"template": "gap_analysis"},
            dependencies=[s3.step_id],
        )
        return [s1, s2, s3, s4]

    def _plan_multi_hop(self, parsed: ParsedQuery) -> list[PlanStep]:
        primary = parsed.primary_entity
        secondary = parsed.secondary_entities[0] if parsed.secondary_entities else None
        source = primary.cluster_id if primary else None
        target = secondary.cluster_id if secondary else None
        all_secondary = [e.cluster_id for e in parsed.secondary_entities if e.cluster_id]

        s1 = self._make_step(
            "multi_hop", "ENTITY_LOOKUP", source,
            parameters={"max_depth": min(2, parsed.max_hops)},
        )
        s2 = self._make_step(
            "multi_hop", "ENTITY_LOOKUP", target,
            parameters={"max_depth": min(2, parsed.max_hops)},
        )
        s3 = self._make_step(
            "multi_hop", "PATH_REASONING",
            target_id=source,
            secondary_ids=all_secondary[1:] if len(all_secondary) > 1 else [],
            parameters={"max_depth": min(4, parsed.max_hops)},
            dependencies=[s1.step_id, s2.step_id],
        )
        s4 = self._make_step(
            "aggregate", "EVIDENCE_COLLECT",
            parameters={"dedup_by": "path_seq"},
            dependencies=[s3.step_id],
        )
        s5 = self._make_step(
            "synthesize", "ANSWER_BUILD",
            parameters={"template": "multi_hop"},
            dependencies=[s4.step_id],
        )
        return [s1, s2, s3, s4, s5]

    def _plan_exploration(self, parsed: ParsedQuery) -> list[PlanStep]:
        target = self._primary_target(parsed)
        s1 = self._make_step(
            "multi_hop", "ENTITY_LOOKUP", target,
            parameters={"max_depth": min(2, parsed.max_hops)},
        )
        s2 = self._make_step(
            "multi_hop", "GRAPH_EXPLORATION", target,
            parameters={"max_depth": min(2, parsed.max_hops)},
            dependencies=[s1.step_id],
        )
        s3 = self._make_step(
            "aggregate", "EVIDENCE_COLLECT", target,
            parameters={"dedup_by": "edge_id"},
            dependencies=[s2.step_id],
        )
        s4 = self._make_step(
            "synthesize", "ANSWER_BUILD",
            parameters={"template": "exploration"},
            dependencies=[s3.step_id],
        )
        return [s1, s2, s3, s4]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _primary_target(parsed: ParsedQuery) -> str | None:
        return parsed.primary_entity.cluster_id if parsed.primary_entity else None

    # ------------------------------------------------------------------
    # Parallel groups (Kahn's algorithm / topological layering)
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_parallel_groups(steps: list[PlanStep]) -> list[list[str]]:
        """Compute layers of steps that can execute in parallel.

        Uses topological layering: step A and step B can run in the same
        layer if neither depends on the other, directly or transitively.
        """
        deps = {s.step_id: set(s.dependencies) for s in steps}
        groups: list[list[str]] = []
        remaining = set(deps.keys())

        while remaining:
            ready = {sid for sid in remaining if not deps[sid] & remaining}
            if not ready:
                break
            groups.append(sorted(ready))
            remaining -= ready

        return groups

    # ------------------------------------------------------------------
    # Complexity estimation (architecture formula)
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_complexity(steps: list[PlanStep]) -> str:
        """Estimate complexity from step count."""
        n = len(steps)
        if n <= 2:
            return "low"
        if n <= 5:
            return "medium"
        return "high"

    # ------------------------------------------------------------------
    # Plan validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_plan(steps: list[PlanStep]) -> None:
        """Validate plan integrity.

        Raises ``ValueError`` for:
        - duplicate step IDs
        - missing dependency targets
        - circular dependencies
        """
        step_ids = set()
        for step in steps:
            if not step.step_id:
                raise ValueError("Every PlanStep must have a non-empty step_id")
            if step.step_id in step_ids:
                raise ValueError(f"Duplicate step_id '{step.step_id}'")
            step_ids.add(step.step_id)

        for step in steps:
            for dep_id in step.dependencies:
                if dep_id not in step_ids:
                    raise ValueError(
                        f"Step '{step.step_id}' depends on '{dep_id}' "
                        f"which does not exist in the plan"
                    )

        deps_map = {s.step_id: set(s.dependencies) for s in steps}
        visited: set[str] = set()
        path: list[str] = []

        def _dfs(node: str) -> None:
            if node in path:
                idx = path.index(node)
                cycle = path[idx:] + [node]
                raise ValueError(
                    f"Circular dependency detected: {' → '.join(cycle)}"
                )
            if node in visited:
                return
            path.append(node)
            for dep in deps_map.get(node, set()):
                _dfs(dep)
            path.pop()
            visited.add(node)

        for sid in deps_map:
            _dfs(sid)


def create_plan(parsed: ParsedQuery) -> ExecutionPlan:
    """Convenience function to create an execution plan."""
    return QueryPlanner().create_plan(parsed)
