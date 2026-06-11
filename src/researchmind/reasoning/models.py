"""Data models for the Reasoning Engine (Module 4).

Query types, query/result models, evidence models, sub-engine result models,
and gap analysis models — all Pydantic, all deterministic.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from researchmind.models.enums import ClaimType, EntityLabel
from researchmind.models.ruo_enums import (
    EvidenceType,
    RelationType,
)
from researchmind.models.ruo import EvidenceSpan


# ---------------------------------------------------------------------------
# Query types
# ---------------------------------------------------------------------------


class QueryType:
    ENTITY_LOOKUP = "entity_lookup"
    DOCUMENT_LOOKUP = "document_lookup"
    PATH_REASONING = "path_reasoning"
    CONSENSUS_ANALYSIS = "consensus_analysis"
    CONTRADICTION_ANALYSIS = "contradiction_analysis"
    GAP_ANALYSIS = "gap_analysis"
    GRAPH_EXPLORATION = "graph_exploration"


# ---------------------------------------------------------------------------
# Gap types (used in ResearchGapEngine)
# ---------------------------------------------------------------------------


class GapType:
    ISOLATED_ENTITY = "isolated_entity"
    MISSING_COMPARISON = "missing_comparison"
    LOW_CONFIDENCE_CLAIM = "low_confidence_claim"
    UNDER_STUDIED_DATASET = "under_studied_dataset"
    UNCONNECTED_DOCUMENT = "unconnected_document"


# ---------------------------------------------------------------------------
# Consensus result models
# ---------------------------------------------------------------------------


class DocumentConsensusEntry(BaseModel):
    """Per-document stance toward a claim or entity."""

    document_id: str
    document_title: str = ""
    stance: str  # "supports" | "contradicts" | "neutral"
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    mixed_evidence: bool = False


class ConsensusResult(BaseModel):
    """Aggregate cross-document agreement analysis."""

    target_id: str
    target_label: str = ""
    total_documents: int = 0
    supporting_documents: int = 0
    contradicting_documents: int = 0
    neutral_documents: int = 0
    support_ratio: float = 0.0
    contradiction_ratio: float = 0.0
    neutral_ratio: float = 0.0
    consensus_confidence: float = 0.0
    classification: str = "insufficient_evidence"
    warnings: list[str] = Field(default_factory=list)
    per_document: list[DocumentConsensusEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Contradiction result models
# ---------------------------------------------------------------------------


class DirectContradiction(BaseModel):
    """A directly attested contradiction via a CONTRADICTS edge."""

    source_document_id: str
    source_document_title: str = ""
    target_document_id: str
    target_document_title: str = ""
    edge_id: str = ""
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    source_text: str | None = None


class IndirectContradiction(BaseModel):
    """An inferred contradiction via polarity mismatch or triple conflict."""

    description: str = ""
    subject_id: str = ""
    subject_label: str = ""
    claim_a: str = ""
    claim_a_document: str = ""
    claim_b: str = ""
    claim_b_document: str = ""
    confidence: float = Field(..., ge=0.0, le=1.0)


class ContradictionResult(BaseModel):
    """Full contradiction analysis for a target."""

    target_id: str
    target_label: str = ""
    direct_contradictions: list[DirectContradiction] = Field(default_factory=list)
    indirect_contradictions: list[IndirectContradiction] = Field(default_factory=list)
    contradiction_count: int = 0
    aggregate_confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Gap analysis result models
# ---------------------------------------------------------------------------


class GapItem(BaseModel):
    """A single detected research gap."""

    gap_type: str  # one of GapType.*
    node_id: str = ""
    label: str = ""
    description: str = ""
    confidence: float = Field(..., ge=0.0, le=1.0)
    supporting_metrics: dict[str, Any] = Field(default_factory=dict)
    suggestion: str = ""


class GapAnalysisResult(BaseModel):
    """Full gap analysis for a corpus."""

    isolated_entities: list[GapItem] = Field(default_factory=list)
    missing_comparisons: list[GapItem] = Field(default_factory=list)
    low_confidence_claims: list[GapItem] = Field(default_factory=list)
    under_studied_datasets: list[GapItem] = Field(default_factory=list)
    unconnected_documents: list[GapItem] = Field(default_factory=list)
    total_gaps: int = 0
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Reasoning step (trace)
# ---------------------------------------------------------------------------


class ReasoningStep(BaseModel):
    """A single step in a multi-hop reasoning trace."""

    step_number: int = Field(..., ge=1)
    description: str = ""
    source_node_id: str = ""
    target_node_id: str = ""
    relation_type: RelationType | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Evidence model
# ---------------------------------------------------------------------------


class AnswerEvidence(BaseModel):
    """A piece of evidence supporting a reasoning answer."""

    evidence_id: str = ""
    source_text: str = ""
    confidence: float = Field(..., ge=0.0, le=1.0)
    document_id: str = ""
    evidence_type: EvidenceType = EvidenceType.DIRECT_QUOTE
    location: EvidenceSpan | None = None
    relation_type: RelationType | None = None
    chain_id: str | None = None
    triple_id: str | None = None


# ---------------------------------------------------------------------------
# Query & Result (top-level)
# ---------------------------------------------------------------------------


class ReasoningQuery(BaseModel):
    """A query submitted to the Reasoning Engine."""

    query_type: str  # one of QueryType.*
    source_id: str | None = None
    target_id: str | None = None
    node_ids: list[str] | None = None
    entity_label: EntityLabel | None = None
    claim_type: ClaimType | None = None
    relation_types: list[RelationType] | None = None
    max_depth: int = Field(default=3, ge=1, le=100)
    min_confidence: float = Field(default=0.3, ge=0.0, le=1.0)
    max_results: int = Field(default=100, ge=1, le=10000)
    include_evidence: bool = True
    include_trace: bool = True
    include_graph_paths: bool = True
    gap_types: list[str] | None = None

    @model_validator(mode="after")
    def _validate_by_type(self) -> ReasoningQuery:
        qt = self.query_type
        if qt in (QueryType.PATH_REASONING,):
            if not self.source_id:
                raise ValueError(
                    f"source_id is required for query_type={qt}"
                )
        return self


class ReasoningResult(BaseModel):
    """The result of a reasoning query."""

    query: ReasoningQuery
    answer: str = ""
    confidence: float = 0.0
    supporting_evidence: list[AnswerEvidence] = Field(default_factory=list)
    supporting_documents: list[str] = Field(default_factory=list)
    graph_paths: list = Field(default_factory=list)
    reasoning_trace: list[ReasoningStep] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
