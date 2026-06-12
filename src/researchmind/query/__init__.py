"""ResearchMind Research Assistant Layer (Module 5).

Query classification, entity extraction, execution planning, engine routing,
evidence aggregation, answer synthesis, and traceability enforcement —
all operating over M4 reasoning engines without LLMs or external APIs.
"""

from researchmind.query.aggregator import EvidenceAggregator, EvidenceRanker
from researchmind.query.models import (
    AggregatedEvidence,
    ExecutionPlan,
    ParsedQuery,
    PlanResult,
    PlanStep,
    QueryConstraint,
    QueryEntity,
    QueryType,
    ReasoningStep,
    ResearchAnswer,
    ResearchQuery,
)
from researchmind.query.parser import QueryParser, parse_query
from researchmind.query.router import (
    StepDispatcher,
    StepRoute,
    route_plan,
    route_step,
)
from researchmind.query.engine import QueryEngine, answer_query
from researchmind.query.synthesizer import AnswerSynthesizer, synthesize_answer

__all__ = [
    "QueryType",
    "QueryEntity",
    "QueryConstraint",
    "ParsedQuery",
    "ResearchQuery",
    "QueryParser",
    "parse_query",
    "PlanStep",
    "PlanResult",
    "ExecutionPlan",
    "StepDispatcher",
    "StepRoute",
    "route_step",
    "route_plan",
    "AggregatedEvidence",
    "ReasoningStep",
    "ResearchAnswer",
    "EvidenceAggregator",
    "EvidenceRanker",
    "AnswerSynthesizer",
    "synthesize_answer",
    "QueryEngine",
    "answer_query",
]
