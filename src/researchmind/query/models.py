"""Data models for the Research Assistant Layer (Module 5).

Query types, parsed queries, execution plans, evidence aggregation,
reasoning traces, and final answers — all Pydantic, all deterministic.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, Enum):
        pass


# ---------------------------------------------------------------------------
# Query type taxonomy (8 types defined in the architecture)
# ---------------------------------------------------------------------------


class QueryType(StrEnum):
    """The 8 research assistant query types from the M5 taxonomy."""

    FACTUAL = "factual"
    COMPARISON = "comparison"
    EXPLANATION = "explanation"
    CONSENSUS = "consensus"
    CONTRADICTION = "contradiction"
    RESEARCH_GAP = "research_gap"
    MULTI_HOP = "multi_hop"
    EXPLORATION = "exploration"


# ---------------------------------------------------------------------------
# Entity and constraint models
# ---------------------------------------------------------------------------


_RECOGNIZED_CONSTRAINT_FIELDS = frozenset({
    "year", "confidence", "document", "relation_type",
})

_VALID_OPERATORS = frozenset({
    "eq", "neq", "gt", "gte", "lt", "lte", "in",
})

_ENTITY_TYPES = frozenset({
    "method", "dataset", "metric", "document", "concept", "unknown",
})


class QueryEntity(BaseModel):
    """An entity mention extracted from the user's question."""

    text: str
    entity_type: str | None = Field(default=None, description="method | dataset | metric | document | concept | unknown")
    cluster_id: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_ambiguous: bool = False
    alternatives: list[str] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def _validate_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("text must be non-empty")
        return stripped

    @field_validator("entity_type")
    @classmethod
    def _validate_entity_type(cls, v: str | None) -> str | None:
        if v is not None and v not in _ENTITY_TYPES:
            raise ValueError(
                f"Unknown entity_type '{v}'. Must be one of {sorted(_ENTITY_TYPES)}"
            )
        return v


class QueryConstraint(BaseModel):
    """A constraint or filter on a query (year, confidence, document, relation_type)."""

    field: str
    operator: str
    value: Any

    @field_validator("field")
    @classmethod
    def _validate_field(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in _RECOGNIZED_CONSTRAINT_FIELDS:
            raise ValueError(
                f"Unrecognized constraint field '{v}'. "
                f"Must be one of {sorted(_RECOGNIZED_CONSTRAINT_FIELDS)}"
            )
        return normalized

    @field_validator("operator")
    @classmethod
    def _validate_operator(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in _VALID_OPERATORS:
            raise ValueError(
                f"Unrecognized operator '{v}'. "
                f"Must be one of {sorted(_VALID_OPERATORS)}"
            )
        return normalized

    @model_validator(mode="after")
    def _validate_value_type(self) -> QueryConstraint:
        field_name = self.field
        val = self.value
        op = self.operator
        if field_name == "year":
            if op == "in":
                if not isinstance(val, list):
                    raise ValueError(f"year constraint with operator 'in' requires a list, got {type(val).__name__}")
            elif not isinstance(val, int):
                try:
                    int(val)
                except (TypeError, ValueError):
                    raise ValueError(f"year constraint value must be an int, got {type(val).__name__}")
        elif field_name == "confidence":
            if not isinstance(val, (int, float)):
                raise ValueError(f"confidence constraint value must be numeric, got {type(val).__name__}")
            fv = float(val)
            if fv < 0.0 or fv > 1.0:
                raise ValueError("confidence constraint must be in [0.0, 1.0]")
        return self


# ---------------------------------------------------------------------------
# Parsed query
# ---------------------------------------------------------------------------


class ParsedQuery(BaseModel):
    """A fully parsed and classified query, ready for planning."""

    raw_query: str
    query_type: str
    primary_entity: QueryEntity | None = None
    secondary_entities: list[QueryEntity] = Field(default_factory=list)
    constraints: list[QueryConstraint] = Field(default_factory=list)
    max_hops: int = Field(default=3)  # clamped to [1, 10] by validator
    min_confidence: float = Field(default=0.3)  # clamped to [0.0, 1.0] by validator
    include_reasoning: bool = True
    include_evidence: bool = True
    entities_resolved: bool = False
    parsing_warnings: list[str] = Field(default_factory=list)

    @field_validator("query_type")
    @classmethod
    def _validate_query_type(cls, v: str) -> str:
        normalized = v.strip().upper()
        known = {qt.name for qt in QueryType}
        if normalized not in known:
            known_str = ", ".join(sorted(known))
            raise ValueError(f"Unknown query_type '{v}'. Must be one of {known_str}")
        return normalized

    @model_validator(mode="after")
    def _require_entities_for_type(self) -> ParsedQuery:
        qt = self.query_type
        entity_requiring_types = {
            "FACTUAL", "COMPARISON", "EXPLANATION",
            "CONSENSUS", "CONTRADICTION", "MULTI_HOP", "EXPLORATION",
        }
        if qt in entity_requiring_types and self.entities_resolved:
            if self.primary_entity is None and not self.secondary_entities:
                raise ValueError(
                    f"Query type {qt} requires at least one entity"
                )
        return self

    @field_validator("max_hops")
    @classmethod
    def _clamp_max_hops(cls, v: int) -> int:
        return max(1, min(v, 10))

    @field_validator("min_confidence")
    @classmethod
    def _clamp_min_confidence(cls, v: float) -> float:
        return max(0.0, min(v, 1.0))


# ---------------------------------------------------------------------------
# Top-level user query
# ---------------------------------------------------------------------------


class ResearchQuery(BaseModel):
    """The top-level user query, before parsing."""

    query_id: str
    raw_query: str
    created_at: datetime
    constraints: list[QueryConstraint] = Field(default_factory=list)
    max_hops: int = Field(default=3)  # clamped to [1, 10] by validator
    min_confidence: float = Field(default=0.3)  # clamped to [0.0, 1.0] by validator
    include_reasoning: bool = True
    include_evidence: bool = True
    parsed: ParsedQuery | None = None

    @field_validator("raw_query")
    @classmethod
    def _validate_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("raw_query must be non-empty")
        return stripped

    @field_validator("max_hops")
    @classmethod
    def _clamp_max_hops(cls, v: int) -> int:
        return max(1, min(v, 10))

    @field_validator("min_confidence")
    @classmethod
    def _clamp_min_confidence(cls, v: float) -> float:
        return max(0.0, min(v, 1.0))


# ---------------------------------------------------------------------------
# Execution planning
# ---------------------------------------------------------------------------


_VALID_ENGINES = frozenset({
    "multi_hop", "consensus", "contradiction", "gap", "aggregate", "synthesize",
})

_VALID_STEP_STATUSES = frozenset({
    "pending", "running", "completed", "failed", "skipped",
})


class PlanStep(BaseModel):
    """A single step in an execution plan."""

    step_id: str
    sequence: int = Field(..., ge=1)
    engine: str
    query_type: str
    target_id: str | None = None
    secondary_ids: list[str] = Field(default_factory=list)
    parameters: dict = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    status: str = "pending"
    result: Any = None
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)

    @field_validator("engine")
    @classmethod
    def _validate_engine(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in _VALID_ENGINES:
            raise ValueError(
                f"Unknown engine '{v}'. Must be one of {sorted(_VALID_ENGINES)}"
            )
        return normalized

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in _VALID_STEP_STATUSES:
            raise ValueError(
                f"Unknown status '{v}'. Must be one of {sorted(_VALID_STEP_STATUSES)}"
            )
        return normalized


class ExecutionPlan(BaseModel):
    """A complete execution plan for a parsed query."""

    plan_id: str
    query_id: str
    query_type: str
    steps: list[PlanStep]
    total_steps: int = 0
    parallel_groups: list[list[str]] = Field(default_factory=list)
    estimated_complexity: str = "low"
    warnings: list[str] = Field(default_factory=list)

    @field_validator("estimated_complexity")
    @classmethod
    def _validate_complexity(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in ("low", "medium", "high"):
            raise ValueError(
                f"Unknown complexity '{v}'. Must be 'low', 'medium', or 'high'"
            )
        return normalized

    @model_validator(mode="after")
    def _validate_steps(self) -> ExecutionPlan:
        step_ids = set()
        deps_set = {}

        for step in self.steps:
            sid = step.step_id
            if not sid:
                raise ValueError("Every PlanStep must have a non-empty step_id")
            if sid in step_ids:
                raise ValueError(f"Duplicate step_id '{sid}' in ExecutionPlan")
            step_ids.add(sid)
            deps_set[sid] = step.dependencies

        # Verify every dependency reference exists
        all_ids = set(step_ids)
        for sid, deps in deps_set.items():
            for dep_id in deps:
                if dep_id not in all_ids:
                    raise ValueError(
                        f"PlanStep '{sid}' depends on '{dep_id}' "
                        f"which does not exist in the plan"
                    )

        # Auto-compute total_steps if mismatched
        if self.total_steps != len(self.steps):
            object.__setattr__(self, "total_steps", len(self.steps))

        return self


# ---------------------------------------------------------------------------
# Plan result (architecture 5.5)
# ---------------------------------------------------------------------------


class PlanResult(BaseModel):
    """The accumulated result of executing a plan."""

    plan: ExecutionPlan
    step_results: dict[str, Any] = Field(default_factory=dict)
    final_confidence: float = 0.0
    merged_evidence: list = Field(default_factory=list)
    plan_warnings: list[str] = Field(default_factory=list)
    execution_time_ms: int = 0
    all_steps_completed: bool = False
    failed_steps: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Evidence aggregation
# ---------------------------------------------------------------------------


class AggregatedEvidence(BaseModel):
    """A single piece of aggregated, deduplicated evidence with traceability."""

    evidence_id: str = ""
    source_text: str = ""
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_engine: str = ""
    source_document_id: str = ""
    source_document_title: str = ""
    relation_type: str | None = None
    evidence_type: str = ""
    trace: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_trace(self) -> AggregatedEvidence:
        evidence_type = self.evidence_type
        requires_trace = {"path_edge", "contradiction", "consensus_entry"}
        if evidence_type in requires_trace and not self.trace:
            raise ValueError(
                f"Evidence type '{evidence_type}' requires a non-empty trace chain"
            )
        return self


# ---------------------------------------------------------------------------
# Reasoning trace
# ---------------------------------------------------------------------------


class ReasoningStep(BaseModel):
    """A single step in the reasoning trace (M5 plan execution record)."""

    step_id: str
    engine: str
    description: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Final answer
# ---------------------------------------------------------------------------


class ResearchAnswer(BaseModel):
    """The final response from the Research Assistant."""

    answer_id: str
    query: ResearchQuery
    plan: ExecutionPlan | None = None

    # Core answer
    answer: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    classification: str | None = None

    # Evidence
    evidence: list[AggregatedEvidence] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    supporting_documents: list[str] = Field(default_factory=list)
    supporting_document_titles: list[str] = Field(default_factory=list)

    # Reasoning trace
    reasoning_trace: list[ReasoningStep] = Field(default_factory=list)

    # Sources
    sources: list[str] = Field(default_factory=list)
    source_attribution: dict[str, list[str]] = Field(default_factory=dict)

    # Metadata
    query_type: str = ""
    generated_at: datetime
    processing_time_ms: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    # Traceability
    traceability_verified: bool = False
    traceability_failures: list[str] = Field(default_factory=list)

    # Engines
    engines_invoked: list[str] = Field(default_factory=list)
    steps_executed: int = 0
    steps_failed: int = 0

    @field_validator("answer")
    @classmethod
    def _validate_non_empty_answer(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("answer must be non-empty")
        return stripped

    @field_validator("evidence_ids")
    @classmethod
    def _dedup_evidence_ids(cls, v: list[str]) -> list[str]:
        seen = set()
        result = []
        for eid in v:
            if eid and eid not in seen:
                seen.add(eid)
                result.append(eid)
        return result

    @field_validator("supporting_documents")
    @classmethod
    def _dedup_documents(cls, v: list[str]) -> list[str]:
        seen = set()
        result = []
        for doc_id in v:
            if doc_id and doc_id not in seen:
                seen.add(doc_id)
                result.append(doc_id)
        return result

    @model_validator(mode="after")
    def _validate_traceability_flag(self) -> ResearchAnswer:
        if self.traceability_failures and self.traceability_verified:
            raise ValueError(
                "traceability_verified must be False when traceability_failures is non-empty"
            )
        return self

    @model_validator(mode="after")
    def _validate_evidence_consistency(self) -> ResearchAnswer:
        ev_ids_from_evidence = {ev.evidence_id for ev in self.evidence if ev.evidence_id}
        ev_ids_flat = set(self.evidence_ids)
        if ev_ids_from_evidence and ev_ids_flat and ev_ids_from_evidence != ev_ids_flat:
            raise ValueError(
                "evidence_ids field does not match evidence[].evidence_id values"
            )
        return self
