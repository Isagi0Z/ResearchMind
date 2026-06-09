"""Pydantic models for the Structured Research Object (SRO) — v1.0.0.

This is the canonical schema. Every field has been justified in the SRO design
document. Do not add fields without updating the design document first.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


from researchmind.models.enums import (
    CanonicalLabel,
    CitationIntent,
    ClaimType,
    DocumentType,
    EntityLabel,
    ExtractionMethod,
    ExtractionRoute,
    ResolutionSource,
    ResolutionStatus,
    StageStatus,
    VenueType,
)

# ---------------------------------------------------------------------------
# Schema version constant
# ---------------------------------------------------------------------------
SCHEMA_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# meta
# ---------------------------------------------------------------------------


class SROSourceFile(BaseModel):
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


class SROMeta(BaseModel):
    """Identity and lifecycle of the SRO itself."""

    sro_id: str
    schema_version: str = SCHEMA_VERSION
    created_at: datetime
    updated_at: datetime
    pipeline_version: str
    extraction_route: ExtractionRoute
    source_file: SROSourceFile
    processing_time_ms: int | None = None


# ---------------------------------------------------------------------------
# header
# ---------------------------------------------------------------------------


class SROAuthor(BaseModel):
    """A single author with optional structured name parts."""

    full_name: str = Field(..., min_length=1)
    given_name: str | None = None
    surname: str | None = None
    affiliations: list[str] = Field(default_factory=list)
    email: str | None = None
    orcid: str | None = None
    is_corresponding: bool | None = None


class SROHeader(BaseModel):
    """Bibliographic metadata for the paper."""

    title: str = Field(..., min_length=3)
    title_confidence: float = Field(..., ge=0.0, le=1.0)
    authors: list[SROAuthor] = Field(default_factory=list)
    authors_confidence: float = Field(..., ge=0.0, le=1.0)
    document_type: DocumentType = DocumentType.RESEARCH_ARTICLE
    language: str = Field(default="en", min_length=2, max_length=5)

    # Optional bibliographic identifiers
    doi: str | None = None
    arxiv_id: str | None = None
    pmid: str | None = None
    publication_date: str | None = None
    publication_date_raw: str | None = None
    venue: str | None = None
    venue_type: VenueType | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    keywords: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# abstract
# ---------------------------------------------------------------------------


class SROStructuredAbstract(BaseModel):
    """Structured abstract sub-fields (common in biomedical papers)."""

    background: str | None = None
    objective: str | None = None
    methods: str | None = None
    results: str | None = None
    conclusion: str | None = None


class SROAbstract(BaseModel):
    """First-class representation of the abstract."""

    raw_text: str
    is_structured: bool = False
    structured: SROStructuredAbstract | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _structured_consistency(self) -> "SROAbstract":
        if self.is_structured and self.structured is None:
            raise ValueError(
                "structured must be provided when is_structured is True"
            )
        return self


# ---------------------------------------------------------------------------
# body: sections, chunks, tables, figures
# ---------------------------------------------------------------------------


class SROSection(BaseModel):
    """A single section in the flat section list with hierarchy via parent_section_id."""

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

    @model_validator(mode="after")
    def _page_order(self) -> "SROSection":
        if self.page_end < self.page_start:
            raise ValueError("page_end must be >= page_start")
        return self


class SROChunk(BaseModel):
    """Paragraph-level text unit — the atomic retrieval unit for downstream modules."""

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

    # Derived indices — populated during validation
    entity_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)


class SROTable(BaseModel):
    """Extracted table metadata and best-effort content."""

    table_id: str
    caption: str
    section_id: str
    page: int = Field(..., ge=0)
    extraction_confidence: float = Field(..., ge=0.0, le=1.0)
    raw_content: str | None = None


class SROFigure(BaseModel):
    """Extracted figure metadata and caption."""

    figure_id: str
    caption: str
    section_id: str
    page: int = Field(..., ge=0)
    image_path: str | None = None


class SROBody(BaseModel):
    """The paper's structured content."""

    sections: list[SROSection] = Field(..., min_length=1)
    chunks: list[SROChunk] = Field(..., min_length=1)
    tables: list[SROTable] = Field(default_factory=list)
    figures: list[SROFigure] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# references
# ---------------------------------------------------------------------------


class SROReference(BaseModel):
    """A single bibliography entry."""

    ref_id: str
    raw_text: str
    resolution_status: ResolutionStatus
    ref_confidence: float = Field(..., ge=0.0, le=1.0)

    # Parsed fields (optional — may not be extractable)
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: str | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    resolution_source: ResolutionSource = ResolutionSource.NONE


# ---------------------------------------------------------------------------
# citations
# ---------------------------------------------------------------------------


class SROCitation(BaseModel):
    """An inline citation instance linking a chunk to a reference."""

    citation_id: str
    ref_id: str | None = None  # None if the citation couldn't be resolved
    chunk_id: str
    section_id: str
    context_sentence: str
    page: int = Field(..., ge=0)

    # Optional intent classification
    citation_intent: CitationIntent | None = None
    intent_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _intent_requires_confidence(self) -> "SROCitation":
        if self.citation_intent is not None and self.intent_confidence is None:
            raise ValueError(
                "intent_confidence is required when citation_intent is set"
            )
        return self


# ---------------------------------------------------------------------------
# entities
# ---------------------------------------------------------------------------


class SROEntity(BaseModel):
    """A named entity extracted from a specific chunk."""

    entity_id: str
    text: str
    label: EntityLabel
    chunk_id: str
    sentence: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: str  # "spacy", "scispacy", "pattern_match"


# ---------------------------------------------------------------------------
# candidate_claims
# ---------------------------------------------------------------------------


class SROCandidateClaim(BaseModel):
    """A sentence detected as a potential scientific claim or finding."""

    claim_id: str
    sentence: str
    chunk_id: str
    section_id: str
    canonical_label: CanonicalLabel
    claim_type: ClaimType
    matched_patterns: list[str] = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    page: int = Field(..., ge=0)


# ---------------------------------------------------------------------------
# quality
# ---------------------------------------------------------------------------


class SROPipelineLogEntry(BaseModel):
    """Execution record for a single pipeline stage."""

    stage: str
    status: StageStatus
    started_at: datetime
    completed_at: datetime
    duration_ms: int | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class SROLLMCall(BaseModel):
    """Record of a single LLM invocation during processing."""

    purpose: str
    model: str
    input_tokens: int
    output_tokens: int
    timestamp: datetime


class SROExtractionCompleteness(BaseModel):
    """Raw counts used to assess extraction quality."""

    total_pages: int = 0
    pages_with_text_extracted: int = 0
    sections_detected: int = 0
    references_total: int = 0
    references_resolved: int = 0
    citations_total: int = 0
    citations_linked: int = 0
    chunks_total: int = 0
    entities_total: int = 0
    claims_total: int = 0


class SROFieldScores(BaseModel):
    """Per-field confidence scores."""

    title: float = Field(0.0, ge=0.0, le=1.0)
    authors: float = Field(0.0, ge=0.0, le=1.0)
    abstract: float = Field(0.0, ge=0.0, le=1.0)
    sections: float = Field(0.0, ge=0.0, le=1.0)
    references: float = Field(0.0, ge=0.0, le=1.0)
    citations: float = Field(0.0, ge=0.0, le=1.0)
    entities: float = Field(0.0, ge=0.0, le=1.0)
    claims: float = Field(0.0, ge=0.0, le=1.0)


class SROQuality(BaseModel):
    """Confidence scores, validation results, and pipeline execution log."""

    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    field_scores: SROFieldScores
    extraction_completeness: SROExtractionCompleteness
    validation_errors: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
    requires_manual_review: bool = False
    manual_review_reasons: list[str] = Field(default_factory=list)
    pipeline_log: list[SROPipelineLogEntry] = Field(default_factory=list)
    llm_calls: list[SROLLMCall] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level SRO
# ---------------------------------------------------------------------------


class StructuredResearchObject(BaseModel):
    """The canonical representation of a single research paper.

    This is the final output of the Module 1 ingestion pipeline and the input
    to all downstream modules (Knowledge Graph, GraphRAG, Research Evolution
    Mapping, Contradiction Detection, Gap Discovery, Evidence-Based QA).
    """

    meta: SROMeta
    header: SROHeader
    abstract: SROAbstract
    body: SROBody
    references: list[SROReference] = Field(default_factory=list)
    citations: list[SROCitation] = Field(default_factory=list)
    entities: list[SROEntity] = Field(default_factory=list)
    candidate_claims: list[SROCandidateClaim] = Field(default_factory=list)
    quality: SROQuality
