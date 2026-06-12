"""Query Engine integration layer for the Research Assistant Layer (Module 5).

Wires together QueryParser, QueryPlanner, StepDispatcher, M4 reasoning
engines, EvidenceAggregator, and AnswerSynthesizer into a single public API.

Orchestration only — no new reasoning logic.
"""

from __future__ import annotations

import time
import zlib
from datetime import datetime, timezone
from typing import Any

from researchmind.query.aggregator import EvidenceAggregator
from researchmind.query.models import (
    AggregatedEvidence,
    ExecutionPlan,
    ParsedQuery,
    PlanResult,
    ResearchAnswer,
    ResearchQuery,
)
from researchmind.query.parser import QueryParser
from researchmind.query.planner import QueryPlanner
from researchmind.query.router import StepDispatcher, StepRoute
from researchmind.query.synthesizer import AnswerSynthesizer

# ---------------------------------------------------------------------------
# Engine registry — maps engine names to dispatch callables.
# No switch statements, no reflection.
# ---------------------------------------------------------------------------


def _call_multi_hop(engine: Any, route: StepRoute, query: Any) -> Any:
    """Dispatch to MultiHopReasoner.reason()."""
    return engine.reason(
        source_id=query.source_id,
        target_id=query.target_id,
        query=query,
    )


def _call_consensus(engine: Any, route: StepRoute, query: Any) -> Any:
    """Dispatch to ConsensusEngine.analyze()."""
    target_id = route.target_id
    if target_id is None and query.node_ids:
        target_id = query.node_ids[0]
    return engine.analyze(target_id=target_id, query=query)


def _call_contradiction(engine: Any, route: StepRoute, query: Any) -> Any:
    """Dispatch to ContradictionEngine.analyze()."""
    target_id = route.target_id
    if target_id is None and query.node_ids:
        target_id = query.node_ids[0]
    return engine.analyze(target_id=target_id, query=query)


def _call_gap(engine: Any, route: StepRoute, query: Any) -> Any:
    """Dispatch to ResearchGapEngine.analyze()."""
    return engine.analyze(query=query)


_ENGINE_REGISTRY: dict[str, Any] = {
    "multi_hop": _call_multi_hop,
    "consensus": _call_consensus,
    "contradiction": _call_contradiction,
    "gap": _call_gap,
}


# ---------------------------------------------------------------------------
# QueryEngine
# ---------------------------------------------------------------------------


class QueryEngine:
    """Top-level orchestrator for the M5 research assistant pipeline.

    Usage::

        engine = QueryEngine(
            multi_hop=my_multi_hop_reasoner,
            consensus=my_consensus_engine,
            contradiction=my_contradiction_engine,
            gap=my_gap_engine,
        )
        answer = engine.answer("What datasets does BERT use?")
    """

    def __init__(
        self,
        parser: QueryParser | None = None,
        planner: QueryPlanner | None = None,
        dispatcher: StepDispatcher | None = None,
        aggregator: EvidenceAggregator | None = None,
        synthesizer: AnswerSynthesizer | None = None,
        multi_hop: Any = None,
        consensus: Any = None,
        contradiction: Any = None,
        gap: Any = None,
    ) -> None:
        self._parser = parser or QueryParser()
        self._planner = planner or QueryPlanner()
        self._dispatcher = dispatcher or StepDispatcher()
        self._aggregator = aggregator or EvidenceAggregator()
        self._synthesizer = synthesizer or AnswerSynthesizer()

        # Engine registry — engine name → (callable, instance)
        self._engine_instances: dict[str, Any] = {
            "multi_hop": multi_hop,
            "consensus": consensus,
            "contradiction": contradiction,
            "gap": gap,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def answer(self, query_text: str) -> ResearchAnswer:
        """Main entry point: answer a research question from raw text.

        Builds a ResearchQuery, runs the full pipeline, returns the answer.
        Never raises — empty/invalid queries produce fallback answers.
        """
        query_id = self._generate_query_id(query_text)
        raw = query_text.strip() or " "
        query = ResearchQuery.model_construct(
            query_id=query_id,
            raw_query=raw,
            created_at=datetime.now(timezone.utc),
        )
        try:
            _, _, _, _, answer = self.execute(query)
            return answer
        except Exception as exc:
            from researchmind.query.models import ResearchAnswer
            return ResearchAnswer(
                answer_id=f"ans_{zlib.crc32(raw.encode()) & 0xFFFFFFFF:012x}",
                query=query,
                plan=None,
                answer="Insufficient evidence to answer this query.",
                confidence=0.0,
                query_type="FACTUAL",
                generated_at=query.created_at,
                errors=[f"Pipeline error: {exc}"],
            )

    def execute(
        self,
        query: ResearchQuery,
    ) -> tuple[
        ParsedQuery,
        ExecutionPlan,
        PlanResult,
        list[AggregatedEvidence],
        ResearchAnswer,
    ]:
        """Run the full M5 pipeline for a ResearchQuery.

        Returns (parsed_query, plan, plan_result, evidence, answer).
        Never raises on component failures — failures are recorded in
        PlanResult and ResearchAnswer.
        """
        # Stage 2: Parse
        parsed = self._parse(query)

        # Stage 3: Plan
        plan = self._plan(parsed)

        # Stage 4: Route
        routes = self._dispatcher.route_plan(plan)

        # Stage 5: Execute routes
        step_results, failed_steps, all_completed = self._execute_routes(routes)

        # Stage 6: Build PlanResult
        plan_result = PlanResult(
            plan=plan,
            step_results=step_results,
            all_steps_completed=all_completed,
            failed_steps=failed_steps,
            plan_warnings=list(plan.warnings),
        )

        # Stage 7: Aggregate evidence
        aggregated = self._aggregator.aggregate(plan_result)

        # Stage 8: Synthesize answer
        answer = self._synthesizer.synthesize(
            query, parsed, plan, plan_result, aggregated,
        )

        return parsed, plan, plan_result, aggregated, answer

    # ------------------------------------------------------------------
    # Stage helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_query_id(query_text: str) -> str:
        h = zlib.crc32(query_text.strip().lower().encode()) & 0xFFFFFFFF
        return f"qry_{h:012x}"

    def _parse(self, query: ResearchQuery) -> ParsedQuery:
        try:
            parsed = self._parser.parse(query.raw_query)
            query.parsed = parsed
            return parsed
        except Exception:
            fallback = ParsedQuery(
                raw_query=query.raw_query,
                query_type="FACTUAL",
                primary_entity=None,
                entities_resolved=False,
                parsing_warnings=["Parser failed, using fallback"],
            )
            query.parsed = fallback
            return fallback

    def _plan(self, parsed: ParsedQuery) -> ExecutionPlan:
        try:
            return self._planner.create_plan(parsed)
        except Exception as exc:
            return ExecutionPlan(
                plan_id="plan_fallback",
                query_id="",
                query_type=parsed.query_type,
                steps=[],
                total_steps=0,
                warnings=[f"Planner failed: {exc}"],
            )

    def _execute_routes(
        self, routes: list[StepRoute],
    ) -> tuple[dict[str, Any], list[str], bool]:
        """Execute all executable routes, skip M5-internal ones.

        Returns (step_results, failed_steps, all_steps_completed).
        """
        step_results: dict[str, Any] = {}
        failed_steps: list[str] = []

        for route in routes:
            # Skip M5-internal steps (aggregate, synthesize)
            if not route.is_executable:
                continue

            engine_instance = self._engine_instances.get(route.engine)
            if engine_instance is None:
                failed_steps.append(route.step_id)
                continue

            handler = _ENGINE_REGISTRY.get(route.engine)
            if handler is None:
                failed_steps.append(route.step_id)
                continue

            query = self._build_reasoning_query(route)

            try:
                result = handler(engine_instance, route, query)
                step_results[route.step_id] = result
            except Exception:
                failed_steps.append(route.step_id)

        all_completed = len(failed_steps) == 0
        return step_results, failed_steps, all_completed

    # ------------------------------------------------------------------
    # ReasoningQuery builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_reasoning_query(route: StepRoute) -> Any:
        """Build a ReasoningQuery-compatible object from a StepRoute.

        Returns a dict that can be consumed by the engine callbacks.
        Real ReasoningQuery objects are prefered when available.
        """
        params = route.m4_params or {}
        return _ReasoningQuery(
            query_type=route.m4_query_type,
            source_id=route.target_id,
            target_id=route.target_id,
            node_ids=route.secondary_ids or None,
            max_depth=params.get("max_depth", 3),
            min_confidence=params.get("min_confidence", 0.3),
            gap_types=params.get("gap_types"),
        )


# ---------------------------------------------------------------------------
# Simple ReasoningQuery-like container (avoids direct import of M4 models)
# ---------------------------------------------------------------------------


class _ReasoningQuery:
    """Lightweight container matching ReasoningQuery fields.

    Used to avoid importing M4 models directly. Structurally compatible
    with the expected attribute access in engine dispatch callbacks.
    """

    def __init__(
        self,
        query_type: str = "",
        source_id: str | None = None,
        target_id: str | None = None,
        node_ids: list[str] | None = None,
        max_depth: int = 3,
        min_confidence: float = 0.3,
        gap_types: list[str] | None = None,
    ) -> None:
        self.query_type = query_type
        self.source_id = source_id
        self.target_id = target_id
        self.node_ids = node_ids
        self.max_depth = max_depth
        self.min_confidence = min_confidence
        self.gap_types = gap_types


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def answer_query(query_text: str) -> ResearchAnswer:
    """Convenience function to answer a research question.

    Creates a default QueryEngine with no M4 engines registered —
    for production use, construct a QueryEngine with engines.
    """
    return QueryEngine().answer(query_text)
