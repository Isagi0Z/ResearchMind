"""Data models for the Synthesis Engine (Module 6).

Review types, requests, findings, sections, results, and supporting models —
all Pydantic, all deterministic, no timestamps, no UUIDs.
"""

from __future__ import annotations

import zlib
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from researchmind.query.models import AggregatedEvidence

try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, Enum):
        pass


# ---------------------------------------------------------------------------
# Deterministic ID generation (consistent with M5 pattern)
# ---------------------------------------------------------------------------

def _generate_id(prefix: str, *parts: str) -> str:
    """Deterministic ID generation via CRC32.

    Consistent with M5 pattern (query/engine.py, query/synthesizer.py).
    """
    raw = "::".join(parts)
    h = zlib.crc32(raw.encode()) & 0xFFFFFFFF
    return f"{prefix}_{h:012x}"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ReviewType(StrEnum):
    """Review categories that Module 6 can generate."""

    GENERAL = "general"
    METHOD = "method"
    DATASET = "dataset"
    CONSENSUS = "consensus"
    CONTRADICTION = "contradiction"
    RESEARCH_GAP = "research_gap"
    COMPARATIVE = "comparative"
    LANDSCAPE = "landscape"


class ThemeType(StrEnum):
    """Classification for detected research themes."""

    METHOD = "method"
    DATASET = "dataset"
    METRIC = "metric"
    CONCEPT = "concept"
    MIXED = "mixed"


# ---------------------------------------------------------------------------
# Section requirements per review type
# ---------------------------------------------------------------------------

_SECTION_REQUIREMENTS: dict[str, tuple[list[str], list[str]]] = {
    "general": (
        ["abstract", "introduction", "methods_landscape", "conclusion"],
        ["datasets", "consensus", "contradictions", "research_gaps"],
    ),
    "method": (
        ["abstract", "methods_landscape", "comparative"],
        ["introduction", "datasets", "research_gaps", "conclusion"],
    ),
    "dataset": (
        ["abstract", "datasets"],
        ["introduction", "methods_landscape", "research_gaps", "conclusion"],
    ),
    "consensus": (
        ["abstract", "consensus"],
        ["introduction", "methods_landscape", "conclusion"],
    ),
    "contradiction": (
        ["abstract", "contradictions"],
        ["introduction", "methods_landscape", "conclusion"],
    ),
    "research_gap": (
        ["abstract", "research_gaps"],
        ["introduction", "methods_landscape", "future_work", "conclusion"],
    ),
    "comparative": (
        ["abstract", "comparative"],
        ["introduction", "methods_landscape", "datasets", "conclusion"],
    ),
    "landscape": (
        ["abstract", "introduction", "conclusion"],
        [
            "methods_landscape",
            "datasets",
            "consensus",
            "contradictions",
            "research_gaps",
        ],
    ),
}

_SECTION_ORDER: list[str] = [
    "abstract",
    "introduction",
    "methods_landscape",
    "datasets",
    "consensus",
    "contradictions",
    "comparative",
    "research_gaps",
    "future_work",
    "conclusion",
]

_SECTION_TITLES: dict[str, str] = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "methods_landscape": "Methods Landscape",
    "datasets": "Datasets",
    "consensus": "Consensus Analysis",
    "contradictions": "Contradictions",
    "comparative": "Comparative Analysis",
    "research_gaps": "Research Gaps",
    "future_work": "Future Work Directions",
    "conclusion": "Conclusion",
}

# Evidence types whose traceability must be enforced
_TRACE_REQUIRED_TYPES: set[str] = {"path_edge", "contradiction", "consensus_entry"}


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class ReviewRequest(BaseModel):
    """Request to generate a literature review / synthesis document."""

    review_id: str
    review_type: str
    title: str = ""
    query: str = ""
    target_entities: list[str] = Field(default_factory=list)
    target_documents: list[str] = Field(default_factory=list)
    min_confidence: float = Field(default=0.3, ge=0.0, le=1.0)
    max_documents: int = Field(default=10, gt=0)
    include_contradictions: bool = True
    include_gaps: bool = True
    include_consensus: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("review_type")
    @classmethod
    def _validate_review_type(cls, v: str) -> str:
        normalized = v.strip().lower()
        known = {rt.value for rt in ReviewType}
        if normalized not in known:
            raise ValueError(
                f"Unknown review_type '{v}'. Must be one of {sorted(known)}"
            )
        return normalized

    @field_validator("title")
    @classmethod
    def _validate_title(cls, v: str) -> str:
        stripped = v.strip()
        if stripped and v != stripped:
            return stripped
        return v

    @field_validator("query")
    @classmethod
    def _validate_query(cls, v: str) -> str:
        if v and not v.strip():
            raise ValueError("query must not be whitespace-only")
        return v


# ---------------------------------------------------------------------------
# Finding model
# ---------------------------------------------------------------------------

class ReviewFinding(BaseModel):
    """A single evidence-backed finding in a review section."""

    finding_id: str
    finding_type: str
    statement: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    source_document_ids: list[str] = Field(default_factory=list)
    source_document_titles: list[str] = Field(default_factory=list)
    supporting_count: int = 0
    contradicting_count: int = 0
    neutral_count: int = 0
    trace: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("finding_id")
    @classmethod
    def _validate_finding_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("finding_id must be non-empty")
        return v

    @field_validator("statement")
    @classmethod
    def _validate_statement(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("statement must be non-empty")
        return v

    @model_validator(mode="after")
    def _validate_evidence_references(self) -> ReviewFinding:
        for eid in self.evidence_ids:
            if not eid.strip():
                raise ValueError(
                    "evidence_ids must not contain empty strings"
                )
        return self

    @model_validator(mode="after")
    def _validate_traceability(self) -> ReviewFinding:
        if self.finding_type in _TRACE_REQUIRED_TYPES:
            if not self.trace:
                raise ValueError(
                    f"finding_type '{self.finding_type}' "
                    f"requires a non-empty trace chain"
                )
        return self


# ---------------------------------------------------------------------------
# Section model
# ---------------------------------------------------------------------------

class ReviewSection(BaseModel):
    """A section of a literature review document."""

    section_id: str
    section_type: str
    title: str
    content: str = ""
    summary: str = ""
    findings: list[ReviewFinding] = Field(default_factory=list)
    paragraphs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    word_count: int = 0
    is_mandatory: bool = False
    statistics: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("section_id")
    @classmethod
    def _validate_section_id_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("section_id must be non-empty")
        return v

    @field_validator("title")
    @classmethod
    def _validate_title_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must be non-empty")
        return v

    @model_validator(mode="after")
    def _validate_confidence_consistency(self) -> ReviewSection:
        if self.findings:
            min_finding_conf = min(f.confidence for f in self.findings)
            if self.confidence > min_finding_conf:
                raise ValueError(
                    f"section confidence ({self.confidence}) exceeds "
                    f"minimum finding confidence ({min_finding_conf})"
                )
        return self


# ---------------------------------------------------------------------------
# Supporting models
# ---------------------------------------------------------------------------

class EvidenceBundle(BaseModel):
    """A group of related evidence items for a single theme or finding."""

    bundle_id: str
    theme: str
    evidence_items: list[AggregatedEvidence] = Field(default_factory=list)
    source_document_ids: list[str] = Field(default_factory=list)
    source_entities: list[str] = Field(default_factory=list)
    aggregate_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    finding_type: str = ""
    evidence_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_evidence_count(self) -> EvidenceBundle:
        if self.evidence_count != len(self.evidence_items):
            raise ValueError(
                f"evidence_count ({self.evidence_count}) must equal "
                f"len(evidence_items) ({len(self.evidence_items)})"
            )
        return self

    @model_validator(mode="after")
    def _validate_deduplication(self) -> EvidenceBundle:
        seen: set[str] = set()
        for item in self.evidence_items:
            eid = item.evidence_id
            if not eid:
                raise ValueError("evidence_items must all have non-empty evidence_id")
            if eid in seen:
                raise ValueError(
                    f"duplicate evidence_id '{eid}' in evidence_items"
                )
            seen.add(eid)
        return self


class ThemeCluster(BaseModel):
    """A detected research theme with associated entities and evidence."""

    cluster_id: str
    theme_type: str = ""
    label: str
    entities: list[str] = Field(default_factory=list)
    documents: list[str] = Field(default_factory=list)
    entity_cluster_ids: list[str] = Field(default_factory=list)
    entity_labels: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    relation_types: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("label")
    @classmethod
    def _validate_label_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("label must be non-empty")
        return v

    @model_validator(mode="after")
    def _validate_cluster_consistency(self) -> ThemeCluster:
        if self.theme_type and not self.entities:
            raise ValueError(
                f"theme_type '{self.theme_type}' requires at least one entity"
            )
        return self


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class ReviewResult(BaseModel):
    """The complete output of the synthesis engine.

    review_id is copied from ReviewRequest.review_id (caller-provided).
    No timestamps, no UUIDs — deterministic by design.
    """

    review_id: str
    review_type: str
    title: str

    abstract: str = ""
    sections: list[ReviewSection] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)

    total_findings: int = 0
    total_evidence_items: int = 0
    total_documents_cited: int = 0
    total_words: int = 0

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    traceability_verified: bool = False
    traceability_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    bibliography: list[str] = Field(default_factory=list)
    source_attribution: dict[str, list[str]] = Field(default_factory=dict)
    statistics: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def _validate_title(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must be non-empty")
        return v

    @field_validator("review_type")
    @classmethod
    def _validate_review_type(cls, v: str) -> str:
        normalized = v.strip().lower()
        known = {rt.value for rt in ReviewType}
        if normalized not in known:
            raise ValueError(f"Unknown review_type '{v}'")
        return normalized

    @model_validator(mode="after")
    def _validate_abstract(self) -> ReviewResult:
        if self.sections and not self.abstract.strip():
            raise ValueError(
                "abstract must be non-empty when sections are present"
            )
        return self

    @model_validator(mode="after")
    def _validate_review_consistency(self) -> ReviewResult:
        if self.sections:
            computed_findings = sum(len(s.findings) for s in self.sections)
            if self.total_findings != computed_findings:
                raise ValueError(
                    f"total_findings ({self.total_findings}) does not match "
                    f"sum of section findings ({computed_findings})"
                )
            computed_words = sum(s.word_count for s in self.sections)
            if self.total_words != computed_words:
                raise ValueError(
                    f"total_words ({self.total_words}) does not match "
                    f"sum of section word counts ({computed_words})"
                )
        return self
