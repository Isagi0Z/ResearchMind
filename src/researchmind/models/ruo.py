"""RUO v2.1.0 — ResearchMind Unified Object schema.

Executable Pydantic models implementing the architecture defined in
architecture/ruo_schema_v2_1.md. No pipeline integration, no extraction logic.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from researchmind.models.enums import (
    ExtractionMethod,
    ExtractionRoute,
    StageStatus,
)
from researchmind.models.ruo_enums import (
    AggregationMethod,
    AnnotationStatus,
    AnnotationType,
    CanonicalLabel,
    CitationIntent,
    ClaimType,
    ConsensusStatus,
    DataSource,
    DocumentType,
    EntityLabel,
    EvidenceTargetType,
    EvidenceType,
    ProvenanceAction,
    ProvenanceAgentType,
    RelationType,
    ResolutionSource,
    ResolutionStatus,
    UncertaintyType,
    ValidationSeverity,
    VenueType,
)
from researchmind.models.sro import (
    SROLLMCall,
    SROPipelineLogEntry,
)

# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

RUO_SCHEMA_VERSION = "2.1.0"


# ---------------------------------------------------------------------------
# 6.2 Source file & Meta
# ---------------------------------------------------------------------------


class RUOSourceFile(BaseModel):
    """Identity and physical properties of the source PDF."""

    filename: str
    sha256: str = Field(..., min_length=64, max_length=64)
    page_count: int = Field(..., ge=1)
    has_text_layer: bool
    is_scanned: bool
    size_bytes: int | None = None

    @field_validator("sha256")
    @classmethod
    def _validate_sha256(cls, v: str) -> str:
        if not re.fullmatch(r"[a-f0-9]{64}", v):
            raise ValueError("sha256 must be 64 lowercase hex characters")
        return v


class RUOMeta(BaseModel):
    """Identity, lifecycle, and classification metadata."""

    ruo_id: str
    sro_id: str | None = None
    corpus_ids: list[str] = Field(default_factory=list)

    schema_version: str = RUO_SCHEMA_VERSION
    created_at: datetime
    updated_at: datetime
    pipeline_version: str

    source_file: RUOSourceFile
    extraction_route: ExtractionRoute

    document_type: DocumentType = DocumentType.RESEARCH_ARTICLE
    language: str = Field(default="en", min_length=2, max_length=5)

    arxiv_categories: list[str] = Field(default_factory=list)
    research_fields: list[str] = Field(default_factory=list)

    processing_time_ms: int | None = None
    pipeline_stages: list[StageStatus] = Field(default_factory=list)

    @field_validator("ruo_id")
    @classmethod
    def _ruo_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("ruo_id must not be empty")
        return v

    @field_validator("language")
    @classmethod
    def _language_code(cls, v: str) -> str:
        allowed = {
            "en", "fr", "de", "es", "it", "pt",
            "zh", "ja", "ko", "ru", "ar", "other",
        }
        if v not in allowed and not re.fullmatch(r"[a-z]{2}(-[A-Z]{2})?", v):
            raise ValueError(
                f"language must be a valid BCP-47 tag or one of {allowed}"
            )
        return v


# ---------------------------------------------------------------------------
# 3.1 EvidenceSpan & EvidenceRecord
# ---------------------------------------------------------------------------


class EvidenceSpan(BaseModel):
    """Exact location of evidence in the source document."""

    chunk_id: str | None = None
    section_id: str | None = None
    paragraph_index: int | None = Field(default=None, ge=0)
    sentence_index: int | None = Field(default=None, ge=0)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    page: int | None = Field(default=None, ge=0)

    source_text_sha256: str | None = Field(
        default=None, min_length=64, max_length=64
    )

    @model_validator(mode="after")
    def _at_least_one_location(self) -> EvidenceSpan:
        if all(
            v is None
            for v in [
                self.chunk_id,
                self.section_id,
                self.paragraph_index,
                self.sentence_index,
                self.page,
            ]
        ):
            raise ValueError("At least one location field must be set")
        return self


class EvidenceRecord(BaseModel):
    """A single piece of evidence supporting a fact."""

    evidence_id: str
    evidence_type: EvidenceType
    source_text: str = Field(..., min_length=1)
    location: EvidenceSpan | None = None
    data_source: DataSource
    extraction_method: ExtractionMethod

    confidence: float = Field(..., ge=0.0, le=1.0)
    uncertainty: str | None = None

    provenance_ref: str | None = None
    timestamp: datetime

    @field_validator("source_text")
    @classmethod
    def _source_text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("source_text must not be empty or whitespace-only")
        return v


# ---------------------------------------------------------------------------
# 3.2 EvidenceChain
# ---------------------------------------------------------------------------


class EvidenceChain(BaseModel):
    """An ordered list of evidence supporting a single fact or conclusion."""

    target_id: str
    target_type: EvidenceTargetType

    chain: list[EvidenceRecord] = Field(..., min_length=1)
    aggregate_confidence: float = Field(..., ge=0.0, le=1.0)

    aggregation_method: AggregationMethod = AggregationMethod.WEIGHTED_AVERAGE

    supporting_document_ids: list[str] = Field(default_factory=list)

    @field_validator("chain")
    @classmethod
    def _chain_ordered_by_provenance(
        cls, v: list[EvidenceRecord]
    ) -> list[EvidenceRecord]:
        for i in range(1, len(v)):
            if (
                v[i].timestamp
                and v[i - 1].timestamp
                and v[i].timestamp < v[i - 1].timestamp
            ):
                raise ValueError(
                    f"Evidence chain should follow chronological order: "
                    f"{v[i - 1].evidence_id} @ {v[i - 1].timestamp} before "
                    f"{v[i].evidence_id} @ {v[i].timestamp}"
                )
        return v

    @model_validator(mode="after")
    def _aggregate_confidence_consistent(self) -> EvidenceChain:
        if not self.chain:
            return self
        if self.aggregate_confidence > max(e.confidence for e in self.chain) * 1.05:
            raise ValueError(
                "aggregate_confidence cannot exceed the maximum evidence confidence "
                "(within rounding tolerance)"
            )
        return self


# ---------------------------------------------------------------------------
# 3.3 ProvenanceRecord
# ---------------------------------------------------------------------------


class ProvenanceRecord(BaseModel):
    """Record of who/what/when/how produced a piece of data."""

    provenance_id: str
    action: ProvenanceAction
    agent_type: ProvenanceAgentType
    agent_name: str
    pipeline_stage: str | None = None
    pipeline_version: str | None = None
    configuration_snapshot: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
    notes: str | None = None
    supersedes_id: str | None = None


# ---------------------------------------------------------------------------
# 3.4 Uncertainty
# ---------------------------------------------------------------------------


class Uncertainty(BaseModel):
    """Representation of uncertainty for a confidence score or fact."""

    uncertainty_type: UncertaintyType
    magnitude: float = Field(..., ge=0.0, le=1.0)
    explanation: str | None = None


# ---------------------------------------------------------------------------
# 4.1 ComponentSubscore & ComponentConfidence
# ---------------------------------------------------------------------------


class ComponentSubscore(BaseModel):
    """A single sub-metric contributing to a component confidence score."""

    name: str
    value: float = Field(..., ge=0.0, le=1.0)
    weight: float = Field(..., ge=0.0, le=1.0)
    explanation: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class ComponentConfidence(BaseModel):
    """Confidence score for one logical component."""

    component: str
    score: float = Field(..., ge=0.0, le=1.0)
    subscores: list[ComponentSubscore] = Field(default_factory=list)
    uncertainty: Uncertainty | None = None
    evidence_chain_id: str | None = None

    @model_validator(mode="after")
    def _weight_sum(self) -> ComponentConfidence:
        if self.subscores:
            total_weight = sum(s.weight for s in self.subscores)
            if abs(total_weight - 1.0) > 1e-6:
                raise ValueError(
                    f"Subscore weights for '{self.component}' must sum to 1.0 "
                    f"(got {total_weight})"
                )
        return self

    @model_validator(mode="after")
    def _score_consistent_with_subscores(self) -> ComponentConfidence:
        if self.subscores:
            weighted = sum(s.value * s.weight for s in self.subscores)
            if abs(self.score - weighted) > 0.01:
                raise ValueError(
                    f"score ({self.score:.4f}) must equal weighted sum of subscores "
                    f"({weighted:.4f}) for component '{self.component}'"
                )
        return self


# ---------------------------------------------------------------------------
# 4.2 ConfidenceBreakdown
# ---------------------------------------------------------------------------


class ConfidenceBreakdown(BaseModel):
    """Full hierarchical breakdown of confidence for a RUODocument."""

    components: list[ComponentConfidence] = Field(..., min_length=1)

    overall: float = Field(..., ge=0.0, le=1.0)
    overall_uncertainty: Uncertainty | None = None
    overall_evidence_chain_id: str | None = None

    component_weights: dict[str, float]

    @model_validator(mode="after")
    def _weight_keys_match_components(self) -> ConfidenceBreakdown:
        component_names = {c.component for c in self.components}
        weight_keys = set(self.component_weights.keys())
        if component_names != weight_keys:
            missing_components = component_names - weight_keys
            extra_weights = weight_keys - component_names
            msg_parts = []
            if missing_components:
                msg_parts.append(f"components without weights: {missing_components}")
            if extra_weights:
                msg_parts.append(f"weights without components: {extra_weights}")
            if msg_parts:
                raise ValueError(
                    "ConfidenceBreakdown weight/component mismatch: "
                    + "; ".join(msg_parts)
                )
        return self

    @model_validator(mode="after")
    def _overall_consistent(self) -> ConfidenceBreakdown:
        weighted = 0.0
        for comp in self.components:
            w = self.component_weights.get(comp.component, 0.0)
            weighted += w * comp.score
        if abs(weighted - self.overall) > 0.02:
            raise ValueError(
                f"Overall confidence {self.overall:.4f} does not match "
                f"weighted sum of components {weighted:.4f}"
            )
        return self


# ---------------------------------------------------------------------------
# 4.3 EvidenceCoverage
# ---------------------------------------------------------------------------


class EvidenceCoverage(BaseModel):
    """What fraction of elements have supporting evidence."""

    total_claims: int = 0
    claims_with_evidence: int = 0
    claims_evidence_rate: float = Field(0.0, ge=0.0, le=1.0)

    total_entities: int = 0
    entities_with_evidence: int = 0
    entities_evidence_rate: float = Field(0.0, ge=0.0, le=1.0)

    total_citations: int = 0
    citations_with_intent_evidence: int = 0
    citation_intent_evidence_rate: float = Field(0.0, ge=0.0, le=1.0)

    total_references: int = 0
    references_with_resolution_evidence: int = 0
    reference_resolution_evidence_rate: float = Field(0.0, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# 5. Validation Framework
# ---------------------------------------------------------------------------


class ValidationRule(BaseModel):
    """A single validation rule defined as data."""

    rule_id: str
    description: str
    severity: ValidationSeverity
    category: str
    message_template: str
    enabled: bool = True


class ValidationResult(BaseModel):
    """Outcome of applying a validation rule."""

    rule_id: str
    passed: bool
    severity: ValidationSeverity
    message: str
    affected_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class ValidationReport(BaseModel):
    """Complete validation output for a RUODocument or RUOCorpus."""

    results: list[ValidationResult] = Field(default_factory=list)
    summary: dict[ValidationSeverity, int] = Field(default_factory=dict)
    is_valid: bool = True

    @model_validator(mode="after")
    def _compute_summary(self) -> ValidationReport:
        counts: dict[str, int] = {}
        for r in self.results:
            key = r.severity.value
            counts[key] = counts.get(key, 0) + 1
        self.summary = {}
        for k, v in counts.items():
            self.summary[ValidationSeverity(k)] = v
        error_count = sum(
            1
            for r in self.results
            if r.severity == ValidationSeverity.ERROR and not r.passed
        )
        self.is_valid = error_count == 0
        return self


# ---------------------------------------------------------------------------
# 6.3 RUOAuthor & RUOHeader
# ---------------------------------------------------------------------------


class RUOAuthor(BaseModel):
    """Author with structured name parts and evidence."""

    full_name: str = Field(..., min_length=1)
    given_name: str | None = None
    surname: str | None = None
    affiliations: list[str] = Field(default_factory=list)
    email: str | None = None
    orcid: str | None = None
    is_corresponding: bool | None = None
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("orcid")
    @classmethod
    def _orcid_format(cls, v: str | None) -> str | None:
        if v is not None:
            if not re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", v):
                raise ValueError("orcid must match 0000-0002-1825-0097 format")
        return v


class RUOHeader(BaseModel):
    """Bibliographic metadata with confidence and evidence."""

    title: str = Field(..., min_length=3)
    authors: list[RUOAuthor] = Field(default_factory=list)
    document_type: DocumentType = DocumentType.RESEARCH_ARTICLE

    doi: str | None = None
    arxiv_id: str | None = None
    pmid: str | None = None
    publication_date: str | None = None
    venue: str | None = None
    venue_type: VenueType | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    keywords: list[str] = Field(default_factory=list)

    confidence: ComponentConfidence
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("doi")
    @classmethod
    def _doi_lowercase(cls, v: str | None) -> str | None:
        if v is not None:
            return v.lower().strip()
        return v


# ---------------------------------------------------------------------------
# 6.4 RUOAbstract
# ---------------------------------------------------------------------------


class RUOStructuredAbstract(BaseModel):
    """Structured abstract with per-field evidence."""

    background: str | None = None
    objective: str | None = None
    methods: str | None = None
    results: str | None = None
    conclusion: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class RUOAbstract(BaseModel):
    """Abstract with evidence and confidence."""

    raw_text: str
    is_structured: bool = False
    structured: RUOStructuredAbstract | None = None
    confidence: ComponentConfidence
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _structured_consistency(self) -> RUOAbstract:
        if self.is_structured and self.structured is None:
            raise ValueError(
                "structured must be provided when is_structured is True"
            )
        return self


# ---------------------------------------------------------------------------
# 6.5 RUOBody, RUOTable, RUOFigure
# ---------------------------------------------------------------------------


class RUOTable(BaseModel):
    """Table with evidence."""

    table_id: str
    caption: str
    section_id: str
    page: int = Field(..., ge=0)
    raw_content: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)


class RUOFigure(BaseModel):
    """Figure with evidence."""

    figure_id: str
    caption: str
    section_id: str
    page: int = Field(..., ge=0)
    image_path: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class RUOSection(BaseModel):
    """Section with hierarchy, label confidence, and evidence."""

    section_id: str
    parent_section_id: str | None = None
    level: int = Field(..., ge=1, le=6)
    position: int = Field(..., ge=0)
    original_header: str
    canonical_label: CanonicalLabel
    label_confidence: float = Field(..., ge=0.0, le=1.0)
    page_start: int = Field(..., ge=0)
    page_end: int = Field(..., ge=0)
    content: str
    extraction_method: ExtractionMethod
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _page_order(self) -> RUOSection:
        if self.page_end < self.page_start:
            raise ValueError("page_end must be >= page_start")
        return self

    @model_validator(mode="after")
    def _label_confidence_unresolved(self) -> RUOSection:
        if (
            self.canonical_label == CanonicalLabel.OTHER
            and self.label_confidence > 0.99
        ):
            raise ValueError(
                "label_confidence should not be near 1.0 for OTHER — "
                "OTHER is a fallback, not a positive classification"
            )
        return self


class RUOChunk(BaseModel):
    """Paragraph-level atomic retrieval unit with full provenance."""

    chunk_id: str
    text: str = Field(..., min_length=1)
    word_count: int = Field(..., ge=1)
    section_id: str
    canonical_label: CanonicalLabel
    page_start: int = Field(..., ge=0)
    page_end: int = Field(..., ge=0)
    paragraph_index: int = Field(..., ge=0)
    reading_order: int = Field(..., ge=0)

    extraction_method: ExtractionMethod
    extraction_confidence: float = Field(..., ge=0.0, le=1.0)

    entity_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)

    evidence_ids: list[str] = Field(default_factory=list)

    embedding: list[float] | None = None
    embedding_model: str | None = None

    @field_validator("text")
    @classmethod
    def _text_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("chunk text must not be empty or whitespace-only")
        return stripped


class RUOBody(BaseModel):
    """The paper's structured content, enriched with evidence."""

    sections: list[RUOSection] = Field(..., min_length=1)
    chunks: list[RUOChunk] = Field(..., min_length=1)
    tables: list[RUOTable] = Field(default_factory=list)
    figures: list[RUOFigure] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _section_ids_unique(self) -> RUOBody:
        ids = [s.section_id for s in self.sections]
        if len(ids) != len(set(ids)):
            raise ValueError("section_id values must be unique within a document")
        return self

    @model_validator(mode="after")
    def _chunk_ids_unique(self) -> RUOBody:
        ids = [c.chunk_id for c in self.chunks]
        if len(ids) != len(set(ids)):
            raise ValueError("chunk_id values must be unique within a document")
        return self


# ---------------------------------------------------------------------------
# 6.8 RUOReference
# ---------------------------------------------------------------------------


class RUOReference(BaseModel):
    """Bibliography entry with resolution evidence."""

    ref_id: str
    raw_text: str

    resolution_status: ResolutionStatus
    resolution_source: ResolutionSource = ResolutionSource.NONE
    ref_confidence: float = Field(..., ge=0.0, le=1.0)

    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: str | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    arxiv_id: str | None = None
    pmid: str | None = None

    evidence_ids: list[str] = Field(default_factory=list)
    target_ruo_id: str | None = None

    @field_validator("doi")
    @classmethod
    def _doi_normalize(cls, v: str | None) -> str | None:
        if v is not None:
            return v.lower().strip()
        return v

    @model_validator(mode="after")
    def _resolved_has_source(self) -> RUOReference:
        if self.resolution_status == ResolutionStatus.RESOLVED:
            if self.resolution_source == ResolutionSource.NONE:
                raise ValueError(
                    "resolution_source must be set when resolution_status "
                    "is RESOLVED"
                )
        return self

    @model_validator(mode="after")
    def _target_consistent(self) -> RUOReference:
        if (
            self.target_ruo_id is not None
            and self.resolution_status != ResolutionStatus.RESOLVED
        ):
            raise ValueError(
                "target_ruo_id can only be set when resolution_status "
                "is RESOLVED"
            )
        return self


# ---------------------------------------------------------------------------
# 6.9 RUOCitation
# ---------------------------------------------------------------------------


class RUOCitation(BaseModel):
    """An inline citation with intent evidence."""

    citation_id: str
    ref_id: str | None = None
    chunk_id: str
    section_id: str
    context_sentence: str
    page: int = Field(..., ge=0)

    citation_intent: CitationIntent | None = None
    intent_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    intent_evidence_ids: list[str] = Field(default_factory=list)

    raw_marker: str | None = None

    @model_validator(mode="after")
    def _intent_requires_confidence(self) -> RUOCitation:
        if self.citation_intent is not None and self.intent_confidence is None:
            raise ValueError(
                "intent_confidence is required when citation_intent is set"
            )
        return self

    @model_validator(mode="after")
    def _intent_requires_evidence(self) -> RUOCitation:
        if self.citation_intent is not None and not self.intent_evidence_ids:
            raise ValueError(
                "At least one evidence record is required when citation_intent "
                "is set"
            )
        return self


# ---------------------------------------------------------------------------
# 6.10 RUOEntity
# ---------------------------------------------------------------------------


class RUOEntity(BaseModel):
    """A named entity with extraction evidence."""

    entity_id: str
    text: str
    label: EntityLabel
    chunk_id: str
    sentence: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: str

    normalized_id: str | None = None
    normalized_label: str | None = None
    kb_source: str | None = None

    evidence_ids: list[str] = Field(default_factory=list)

    embedding: list[float] | None = None
    embedding_model: str | None = None

    @field_validator("text")
    @classmethod
    def _text_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("entity text must not be empty")
        return v


# ---------------------------------------------------------------------------
# 6.11 RUOClaim
# ---------------------------------------------------------------------------


class RUOClaim(BaseModel):
    """A scientific claim with full evidence chain."""

    claim_id: str
    sentence: str
    chunk_id: str
    section_id: str
    canonical_label: CanonicalLabel
    claim_type: ClaimType
    matched_patterns: list[str] = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    page: int = Field(..., ge=0)

    evidence_chain_id: str

    is_contradicted: bool = False
    contradiction_detected_at: datetime | None = None
    is_supported_by: list[str] = Field(default_factory=list)
    is_replicated: bool | None = None

    normalized_statement: str | None = None

    embedding: list[float] | None = None
    embedding_model: str | None = None

    @field_validator("matched_patterns")
    @classmethod
    def _patterns_non_empty(cls, v: list[str]) -> list[str]:
        if not v or not all(p.strip() for p in v):
            raise ValueError(
                "matched_patterns must contain at least one non-empty pattern"
            )
        return v


# ---------------------------------------------------------------------------
# 6.12 SemanticTriple
# ---------------------------------------------------------------------------


class SemanticTriple(BaseModel):
    """A subject-predicate-object triple for knowledge graph construction."""

    triple_id: str
    subject_id: str
    subject_text: str
    predicate: str
    object_id: str
    object_text: str
    is_negated: bool = False
    confidence: float = Field(..., ge=0.0, le=1.0)
    chunk_id: str

    evidence_ids: list[str] = Field(default_factory=list)

    quantification: str | None = None

    @field_validator("predicate")
    @classmethod
    def _predicate_format(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z_]+", v):
            raise ValueError("predicate must be snake_case lowercase")
        return v


# ---------------------------------------------------------------------------
# 6.13 DocumentRelation
# ---------------------------------------------------------------------------


class DocumentRelation(BaseModel):
    """A semantic relationship between two RUO documents."""

    relation_id: str
    source_ruo_id: str
    target_ruo_id: str
    relation_type: RelationType

    source_chunk_id: str | None = None
    target_chunk_id: str | None = None
    source_claim_id: str | None = None
    target_claim_id: str | None = None

    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)

    is_directed: bool = True

    detected_at: datetime
    valid_until: datetime | None = None

    @model_validator(mode="after")
    def _self_relation(self) -> DocumentRelation:
        if self.source_ruo_id == self.target_ruo_id:
            raise ValueError("source_ruo_id and target_ruo_id must differ")
        return self


# ---------------------------------------------------------------------------
# 6.14 Annotation
# ---------------------------------------------------------------------------


class Annotation(BaseModel):
    """A human or automated annotation attached to any element in the RUO."""

    annotation_id: str
    annotation_type: AnnotationType

    target_id: str
    target_type: str

    field: str
    previous_value: Any | None = None
    suggested_value: Any | None = None

    author: str
    timestamp: datetime
    reason: str | None = None
    status: AnnotationStatus = AnnotationStatus.OPEN

    @field_validator("target_type")
    @classmethod
    def _valid_target(cls, v: str) -> str:
        allowed = {
            "chunk", "entity", "claim", "citation", "section", "header",
            "reference", "abstract", "table", "figure", "relation", "triple",
            "quality", "document",
        }
        if v not in allowed:
            raise ValueError(f"target_type must be one of {allowed}")
        return v


# ---------------------------------------------------------------------------
# 7.1 DocumentStore & RUOCorpus
# ---------------------------------------------------------------------------


class DocumentStore(ABC):
    """Abstract document storage backend.

    Implementations may use a database, filesystem, or cloud storage.
    Documents are loaded lazily — only when accessed.
    """

    @abstractmethod
    def get(self, ruo_id: str) -> RUODocument | None: ...

    @abstractmethod
    def get_batch(
        self, ruo_ids: list[str]
    ) -> dict[str, RUODocument]: ...

    @abstractmethod
    def put(self, doc: RUODocument) -> None: ...

    @abstractmethod
    def delete(self, ruo_id: str) -> bool: ...

    @abstractmethod
    def contains(self, ruo_id: str) -> bool: ...

    @abstractmethod
    def list_ids(self) -> list[str]: ...

    @abstractmethod
    def count(self) -> int: ...


class RUOCorpus(BaseModel):
    """A collection of RUO documents for cross-paper analysis.

    Lightweight metadata container. Document data lives in a DocumentStore,
    injected at runtime and not serialized as part of this model.
    """

    corpus_id: str
    name: str
    description: str | None = None
    schema_version: str = RUO_SCHEMA_VERSION
    created_at: datetime
    updated_at: datetime

    document_ids: list[str] = Field(default_factory=list)

    relations: list[DocumentRelation] = Field(default_factory=list)

    global_entities: dict[str, list[str]] = Field(default_factory=dict)
    global_claims: dict[str, list[str]] = Field(default_factory=dict)

    quality: RUOQuality
    validation: ValidationReport | None = None
    provenance: list[ProvenanceRecord] = Field(default_factory=list)

    _document_store: DocumentStore | None = None

    @model_validator(mode="after")
    def _relation_ids_in_corpus(self) -> RUOCorpus:
        known_ids = set(self.document_ids)
        for rel in self.relations:
            if rel.source_ruo_id not in known_ids:
                raise ValueError(
                    f"DocumentRelation.source_ruo_id '{rel.source_ruo_id}' "
                    f"not found in corpus document_ids"
                )
            if rel.target_ruo_id not in known_ids:
                raise ValueError(
                    f"DocumentRelation.target_ruo_id '{rel.target_ruo_id}' "
                    f"not found in corpus document_ids"
                )
        return self

    def get_document(self, ruo_id: str) -> RUODocument | None:
        if self._document_store is None:
            raise RuntimeError("DocumentStore not configured on this corpus")
        return self._document_store.get(ruo_id)

    def has_document(self, ruo_id: str) -> bool:
        if self._document_store is not None:
            return self._document_store.contains(ruo_id)
        return ruo_id in self.document_ids

    def attach_store(self, store: DocumentStore) -> None:
        self._document_store = store


# ---------------------------------------------------------------------------
# 7.2 RUOQuality
# ---------------------------------------------------------------------------


class RUOQuality(BaseModel):
    """Quality assessment for a single RUODocument or RUOCorpus."""

    confidence: ConfidenceBreakdown
    evidence_coverage: EvidenceCoverage
    validation: ValidationReport | None = None

    pipeline_log: list[SROPipelineLogEntry] = Field(default_factory=list)
    llm_calls: list[SROLLMCall] = Field(default_factory=list)

    requires_manual_review: bool = False
    manual_review_reasons: list[str] = Field(default_factory=list)

    overall_confidence: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _overall_matches_breakdown(self) -> RUOQuality:
        if abs(self.overall_confidence - self.confidence.overall) > 0.01:
            raise ValueError(
                "overall_confidence must match confidence.overall"
            )
        return self


# ---------------------------------------------------------------------------
# 7.3 RUOEvidenceReport
# ---------------------------------------------------------------------------


class RUOEvidenceReport(BaseModel):
    """A standalone report summarizing evidence for a claim, entity, or fact."""

    report_id: str
    target_id: str
    target_type: str
    target_text: str

    evidence_chains: list[EvidenceChain] = Field(default_factory=list)

    supporting_documents: list[str] = Field(default_factory=list)
    contradicting_documents: list[str] = Field(default_factory=list)

    aggregate_confidence: float = Field(..., ge=0.0, le=1.0)
    consensus: ConsensusStatus | None = None

    generated_at: datetime
    generator: str


# ---------------------------------------------------------------------------
# 6.1 RUODocument (top-level)
# ---------------------------------------------------------------------------


class RUODocument(BaseModel):
    """Top-level unified representation of a single research paper."""

    meta: RUOMeta

    provenance: list[ProvenanceRecord] = Field(default_factory=list)

    header: RUOHeader
    abstract: RUOAbstract | None = None
    body: RUOBody

    references: list[RUOReference] = Field(default_factory=list)
    citations: list[RUOCitation] = Field(default_factory=list)

    entities: list[RUOEntity] = Field(default_factory=list)
    claims: list[RUOClaim] = Field(default_factory=list)

    triples: list[SemanticTriple] = Field(default_factory=list)

    quality: RUOQuality

    annotations: list[Annotation] = Field(default_factory=list)

    schema_version: str = RUO_SCHEMA_VERSION
    lineage: list[str] = Field(default_factory=list)

    @field_validator("schema_version")
    @classmethod
    def _schema_version_format(cls, v: str) -> str:
        if not re.fullmatch(r"\d+\.\d+\.\d+", v):
            raise ValueError(
                "schema_version must be in semver format (e.g. 2.1.0)"
            )
        return v

    def get_provenance_by_action(
        self, action: ProvenanceAction
    ) -> list[ProvenanceRecord]:
        return [p for p in self.provenance if p.action == action]
