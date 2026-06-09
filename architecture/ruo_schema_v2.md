# ResearchMind Unified Object (RUO) — Schema v2.0.0

> **One unified representation for everything ResearchMind knows about a paper (or corpus).**  
> Evolves from SRO v1.0.0 by adding first-class evidence, hierarchical confidence, provenance,
> cross-document relations, semantic triples, and annotation surfaces — without changing
> the extraction pipeline itself.

---

## Table of Contents

1. [Design Principles](#1-design-principles)
2. [Enum Taxonomy](#2-enum-taxonomy)
3. [Evidence & Provenance](#3-evidence--provenance)
4. [Confidence Model](#4-confidence-model)
5. [Validation Framework](#5-validation-framework)
6. [Core Models](#6-core-models)
   - [RUODocument](#61-ruodocument)
   - [RUOMeta](#62-ruometa)
   - [RUOHeader](#63-ruoheader)
   - [RUOAbstract](#64-ruoabstract)
   - [RUOBody](#65-ruobody)
   - [RUOSection](#66-ruosection)
   - [RUOChunk](#67-ruochunk)
   - [RUOReference](#68-ruoreference)
   - [RUOCitation](#69-ruocitation)
   - [RUOEntity](#610-ruoentity)
   - [RUOClaim](#611-ruoclaim)
   - [SemanticTriple](#612-semantictriple)
   - [DocumentRelation](#613-documentrelation)
   - [Annotation](#614-annotation)
7. [Aggregate Models](#7-aggregate-models)
   - [RUOCorpus](#71-ruocorpus)
   - [RUOQuality](#72-ruoquality)
   - [RUOEvidenceReport](#73-ruoevidencereport)

---

## 1. Design Principles

| Principle | Rationale |
|-----------|-----------|
| **Every fact has evidence** | No confidence score exists without an `EvidenceRecord` backing it. |
| **Confidence is hierarchical** | Component scores → weighted aggregates → overall. Never a single opaque number. |
| **Provenance is mandatory** | Every model carries `provenance: list[ProvenanceRecord]` showing who/what/when produced it. |
| **Cross-document by default** | `DocumentRelation` and `RUOCorpus` make multi-paper analysis a first-class concern. |
| **Open to human intervention** | `Annotation` model supports human review, correction, and LLM suggestions without mutating extracted data. |
| **Schema evolution tracked** | `schema_version`, `lineage` fields ensure every RUO knows its ancestry. |
| **Validation is declarative** | Rules are defined as data (`ValidationRule`), not scattered across validators. |

---

## 2. Enum Taxonomy

### 2.1 Evidence & Uncertainty

```python
class EvidenceType(StrEnum):
    """The nature of the evidence supporting a fact."""
    DIRECT_QUOTE          = "direct_quote"           # verbatim from source text
    PARAPHRASE            = "paraphrase"             # reworded but faithful
    STATISTICAL           = "statistical"            # p-value, CI, effect size
    DERIVED               = "derived"                # inferred by pipeline logic
    EXTERNAL              = "external"               # from CrossRef, PubMed, etc.
    LLM_GENERATED         = "llm_generated"          # produced by an LLM
    HUMAN_ANNOTATED       = "human_annotated"        # verified by a human


class UncertaintyType(StrEnum):
    """Category of uncertainty associated with a fact or score."""
    MEASUREMENT_ERROR     = "measurement_error"
    MISSING_DATA          = "missing_data"
    CONTRADICTORY_EVIDENCE= "contradictory_evidence"
    MODEL_UNCERTAINTY     = "model_uncertainty"
    AMBIGUOUS_SOURCE      = "ambiguous_source"
    EXTRACTION_ARTIFACT   = "extraction_artifact"
    NOT_APPLICABLE        = "not_applicable"
```

### 2.2 Provenance

```python
class ProvenanceAction(StrEnum):
    """What happened to the data at this point in the provenance chain."""
    CREATED               = "created"
    UPDATED               = "updated"
    VALIDATED             = "validated"
    CORRECTED             = "corrected"
    REJECTED              = "rejected"
    ANNOTATED             = "annotated"
    MERGED                = "merged"


class ProvenanceAgentType(StrEnum):
    """Who or what performed the action."""
    PIPELINE_STAGE        = "pipeline_stage"
    LLM                   = "llm"
    HUMAN_REVIEWER        = "human_reviewer"
    EXTERNAL_SERVICE      = "external_service"       # CrossRef, PubMed, etc.
    RULE_BASED            = "rule_based"


class DataSource(StrEnum):
    """Origin of a piece of data."""
    GROBID                = "grobid"
    PYMUPDF               = "pymupdf"
    OCR_SURYA             = "ocr_surya"
    OCR_TESSERACT         = "ocr_tesseract"
    CROSSREF              = "crossref"
    PUBMED                = "pubmed"
    LLM                   = "llm"
    MANUAL_REVIEW         = "manual_review"
    INFERRED              = "inferred"               # derived by pipeline logic
    UNKNOWN               = "unknown"
```

### 2.3 Relations & Annotation

```python
class RelationType(StrEnum):
    """Semantic relationship between two documents."""
    CITES                 = "cites"
    CITED_BY              = "cited_by"
    CONTRADICTS           = "contradicts"
    SUPPORTS              = "supports"
    EXTENDS               = "extends"
    SUPERSEDES            = "supersedes"
    REPRODUCES            = "reproduces"
    USES_METHOD           = "uses_method"
    USES_DATASET          = "uses_dataset"
    COMPARES_WITH         = "compares_with"
    REVIEWS               = "reviews"
    META_ANALYSIS_INCLUDES= "meta_analysis_includes"
    UNKNOWN               = "unknown"


class AnnotationType(StrEnum):
    """What kind of annotation is attached to an element."""
    HUMAN_REVIEW          = "human_review"
    HUMAN_CORRECTION      = "human_correction"
    LLM_SUGGESTION        = "llm_suggestion"
    AUTOMATED_FLAG        = "automated_flag"
    QUALITY_ISSUE         = "quality_issue"
    MANUAL_OVERRIDE       = "manual_override"


class ValidationSeverity(StrEnum):
    ERROR                 = "error"
    WARNING               = "warning"
    INFO                  = "info"


# Re-exported from SRO enums (unchanged):
# ExtractionRoute, ExtractionMethod, CanonicalLabel, DocumentType, VenueType,
# ResolutionStatus, ResolutionSource, CitationIntent, ClaimType, EntityLabel, StageStatus
```

---

## 3. Evidence & Provenance

### 3.1 EvidenceRecord

```python
class EvidenceSpan(BaseModel):
    """Exact location of evidence in the source document."""

    chunk_id: str | None = None
    section_id: str | None = None
    paragraph_index: int | None = Field(default=None, ge=0)
    sentence_index: int | None = Field(default=None, ge=0)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    page: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _at_least_one_location(self) -> "EvidenceSpan":
        if all(v is None for v in [
            self.chunk_id, self.section_id, self.paragraph_index,
            self.sentence_index, self.page
        ]):
            raise ValueError("At least one location field must be set")
        return self


class EvidenceRecord(BaseModel):
    """A single piece of evidence supporting a fact.

    Every claim, entity, citation intent, and confidence score in the RUO
    is backed by at least one EvidenceRecord.
    """

    evidence_id: str
    evidence_type: EvidenceType
    source_text: str = Field(..., min_length=1)
    location: EvidenceSpan | None = None
    data_source: DataSource
    extraction_method: ExtractionMethod | ExtractionMethod  # re-use existing enum

    # Confidence in this specific piece of evidence
    confidence: float = Field(..., ge=0.0, le=1.0)
    uncertainty: str | None = None                    # free-text explanation

    # When this evidence was produced
    provenance_ref: str | None = None                  # foreign key → ProvenanceRecord.id
    timestamp: datetime

    @field_validator("source_text")
    @classmethod
    def _source_text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("source_text must not be empty or whitespace-only")
        return v
```

### 3.2 EvidenceChain

```python
class EvidenceChain(BaseModel):
    """An ordered list of evidence supporting a single fact or conclusion.

    The chain preserves the reasoning path: raw text → extracted fact →
    normalized fact → interpreted conclusion.
    """

    target_id: str        # id of the fact/entity/claim this chain supports
    target_type: str      # "claim", "entity", "citation_intent", "confidence"

    chain: list[EvidenceRecord] = Field(..., min_length=1)
    aggregate_confidence: float = Field(..., ge=0.0, le=1.0)

    # How the aggregate was computed
    aggregation_method: str = "weighted_average"       # "minimum", "product", "weighted_average", "llm_judged"

    # Cross-document support
    supporting_document_ids: list[str] = Field(default_factory=list)

    @field_validator("chain")
    @classmethod
    def _chain_ordered_by_provenance(cls, v: list[EvidenceRecord]) -> list[EvidenceRecord]:
        for i in range(1, len(v)):
            if v[i].timestamp < v[i-1].timestamp:
                raise ValueError(f"Evidence chain must be in chronological order: "
                                 f"{v[i-1].evidence_id} @ {v[i-1].timestamp} before "
                                 f"{v[i].evidence_id} @ {v[i].timestamp}")
        return v

    @model_validator(mode="after")
    def _aggregate_confidence_consistent(self) -> "EvidenceChain":
        if self.aggregate_confidence > max(e.confidence for e in self.chain) * 1.05:
            raise ValueError(
                "aggregate_confidence cannot exceed the maximum evidence confidence "
                "(within rounding tolerance)"
            )
        return self
```

### 3.3 ProvenanceRecord

```python
class ProvenanceRecord(BaseModel):
    """Record of who/what/when/how produced a piece of data."""

    provenance_id: str
    action: ProvenanceAction
    agent_type: ProvenanceAgentType
    agent_name: str               # e.g. "grobid_client", "crossref_resolver", "reviewer@example.com"
    pipeline_stage: str | None    # e.g. "extraction", "structuring", "enrichment"
    pipeline_version: str | None
    configuration_snapshot: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
    notes: str | None = None
```

### 3.4 Uncertainty

```python
class Uncertainty(BaseModel):
    """Representation of uncertainty for a confidence score or fact."""

    uncertainty_type: UncertaintyType
    magnitude: float = Field(..., ge=0.0, le=1.0)     # 0 = certain, 1 = maximally uncertain
    explanation: str | None = None
    confidence_interval: tuple[float, float] | None = None  # (lower, upper)

    @model_validator(mode="after")
    def _ci_ordered(self) -> "Uncertainty":
        if self.confidence_interval:
            lo, hi = self.confidence_interval
            if not (0.0 <= lo <= hi <= 1.0):
                raise ValueError(
                    "confidence_interval must satisfy 0.0 <= lo <= hi <= 1.0"
                )
        return self
```

---

## 4. Confidence Model

### 4.1 ComponentConfidence

```python
class ComponentSubscore(BaseModel):
    """A single sub-metric contributing to a component confidence score."""

    name: str                     # e.g. "title_length", "authors_surname_ratio"
    value: float = Field(..., ge=0.0, le=1.0)
    weight: float = Field(..., ge=0.0, le=1.0)
    explanation: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)   # → EvidenceRecord.evidence_id


class ComponentConfidence(BaseModel):
    """Confidence score for one logical component (title, authors, sections, etc.)."""

    component: str                # e.g. "title", "authors", "abstract", "sections", etc.
    score: float = Field(..., ge=0.0, le=1.0)
    subscores: list[ComponentSubscore] = Field(default_factory=list)
    uncertainty: Uncertainty | None = None
    evidence_chain_id: str | None = None   # → EvidenceChain.target_id

    @model_validator(mode="after")
    def _weight_sum(self) -> "ComponentConfidence":
        if self.subscores:
            total_weight = sum(s.weight for s in self.subscores)
            if abs(total_weight - 1.0) > 0.01:
                raise ValueError(
                    f"Subscore weights for '{self.component}' must sum to 1.0 "
                    f"(got {total_weight})"
                )
        return self
```

### 4.2 ConfidenceBreakdown

```python
class ConfidenceBreakdown(BaseModel):
    """Full hierarchical breakdown of confidence for a RUODocument."""

    components: list[ComponentConfidence] = Field(..., min_length=1)

    overall: float = Field(..., ge=0.0, le=1.0)
    overall_uncertainty: Uncertainty | None = None
    overall_evidence_chain_id: str | None = None

    # Weights used for overall aggregation
    component_weights: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _overall_consistent(self) -> "ConfidenceBreakdown":
        if self.component_weights and self.components:
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
```

### 4.3 EvidenceCoverage

```python
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
```

---

## 5. Validation Framework

### 5.1 ValidationRule

```python
class ValidationRule(BaseModel):
    """A single validation rule defined as data."""

    rule_id: str
    description: str
    severity: ValidationSeverity
    category: str                  # "cross_reference", "completeness", "consistency", "evidence"
    message_template: str          # Python format string, receives field values

    # The rule logic is implemented in a separate validator module.
    # This model exists so rules can be listed, versioned, and configured
    # without changing code.
    enabled: bool = True
```

### 5.2 ValidationResult

```python
class ValidationResult(BaseModel):
    """Outcome of applying a validation rule."""

    rule_id: str
    passed: bool
    severity: ValidationSeverity
    message: str                   # rendered from template
    affected_ids: list[str] = Field(default_factory=list)   # chunk_ids, ref_ids, etc.
    evidence_ids: list[str] = Field(default_factory=list)   # supporting evidence
```

### 5.3 ValidationReport

```python
class ValidationReport(BaseModel):
    """Complete validation output for a RUODocument or RUOCorpus."""

    results: list[ValidationResult] = Field(default_factory=list)
    summary: dict[ValidationSeverity, int] = Field(default_factory=dict)

    # Derived fields
    is_valid: bool = True          # False if any ERROR-level rule fails

    @model_validator(mode="after")
    def _compute_summary(self) -> "ValidationReport":
        counts: dict[str, int] = {}
        for r in self.results:
            key = r.severity.value if isinstance(r.severity, StrEnum) else str(r.severity)
            counts[key] = counts.get(key, 0) + 1
        self.summary = {ValidationSeverity(k): v for k, v in counts.items()}
        error_count = sum(1 for r in self.results if r.severity == ValidationSeverity.ERROR and not r.passed)
        self.is_valid = error_count == 0
        return self
```

---

## 6. Core Models

### 6.1 RUODocument

```python
class RUODocument(BaseModel):
    """Top-level unified representation of a single research paper.

    This is the fundamental unit of the ResearchMind ecosystem — the single
    source of truth for everything the system knows about a paper.
    """

    # Identity & lifecycle
    meta: RUOMeta

    # Provenance chain — every field below is backed by entries here
    provenance: list[ProvenanceRecord] = Field(default_factory=list)

    # Extracted content (evolved from SRO)
    header: RUOHeader
    abstract: RUOAbstract | None = None
    body: RUOBody

    # Bibliography & citations
    references: list[RUOReference] = Field(default_factory=list)
    citations: list[RUOCitation] = Field(default_factory=list)

    # Enrichment
    entities: list[RUOEntity] = Field(default_factory=list)
    claims: list[RUOClaim] = Field(default_factory=list)

    # Knowledge graph integration
    triples: list[SemanticTriple] = Field(default_factory=list)

    # Cross-document relationships
    relations: list[DocumentRelation] = Field(default_factory=list)

    # Quality & confidence
    quality: RUOQuality

    # Human & automated annotations
    annotations: list[Annotation] = Field(default_factory=list)

    # Schema evolution
    schema_version: str = "2.0.0"
    lineage: list[str] = Field(default_factory=list)   # ancestor RUO IDs

    @field_validator("schema_version")
    @classmethod
    def _schema_version_format(cls, v: str) -> str:
        if not re.fullmatch(r"\d+\.\d+\.\d+", v):
            raise ValueError("schema_version must be in semver format (e.g. 2.0.0)")
        return v

    def get_provenance_by_action(self, action: ProvenanceAction) -> list[ProvenanceRecord]:
        """Convenience: filter provenance by action type."""
        return [p for p in self.provenance if p.action == action]
```

### 6.2 RUOMeta

```python
class RUOMeta(BaseModel):
    """Identity, lifecycle, and classification metadata."""

    # Identity
    ruo_id: str                   # canonical ID (UUID or hash-based)
    sro_id: str | None = None     # original SRO ID if migrated
    corpus_ids: list[str] = Field(default_factory=list)

    # Lifecycle
    schema_version: str = "2.0.0"
    created_at: datetime
    updated_at: datetime
    pipeline_version: str

    # Source
    source_file: RUOSourceFile    # (same as SROSourceFile, renamed)
    extraction_route: ExtractionRoute

    # Classification
    document_type: DocumentType = DocumentType.RESEARCH_ARTICLE
    language: str = Field(default="en", min_length=2, max_length=5)

    # Processing
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
        allowed = {"en", "fr", "de", "es", "it", "pt", "zh", "ja", "ko", "ru", "ar", "other"}
        if v not in allowed and not re.fullmatch(r"[a-z]{2}(-[A-Z]{2})?", v):
            raise ValueError(f"language must be a valid BCP-47 tag or one of {allowed}")
        return v
```

### 6.3 RUOHeader

```python
class RUOAuthor(BaseModel):
    """Author with structured name parts and evidence."""

    full_name: str = Field(..., min_length=1)
    given_name: str | None = None
    surname: str | None = None
    affiliations: list[str] = Field(default_factory=list)
    email: str | None = None
    orcid: str | None = None
    is_corresponding: bool | None = None

    # Evidence for this author's extracted data
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("orcid")
    @classmethod
    def _orcid_format(cls, v: str | None) -> str | None:
        if v is not None:
            # ORCID format: 0000-0002-1825-0097
            if not re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", v):
                raise ValueError("orcid must match 0000-0002-1825-0097 format")
        return v


class RUOHeader(BaseModel):
    """Bibliographic metadata with confidence and evidence."""

    title: str = Field(..., min_length=3)
    authors: list[RUOAuthor] = Field(default_factory=list)
    document_type: DocumentType = DocumentType.RESEARCH_ARTICLE

    # Bibliographic identifiers
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

    # Confidence (evolved from flat fields in SRO)
    confidence: ComponentConfidence   # replaces title_confidence + authors_confidence

    # Evidence
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("doi")
    @classmethod
    def _doi_lowercase(cls, v: str | None) -> str | None:
        if v is not None:
            return v.lower().strip()
        return v
```

### 6.4 RUOAbstract

```python
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
    def _structured_consistency(self) -> "RUOAbstract":
        if self.is_structured and self.structured is None:
            raise ValueError(
                "structured must be provided when is_structured is True"
            )
        return self
```

### 6.5 RUOBody

```python
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


class RUOBody(BaseModel):
    """The paper's structured content, enriched with evidence."""

    sections: list[RUOSection] = Field(..., min_length=1)
    chunks: list[RUOChunk] = Field(..., min_length=1)
    tables: list[RUOTable] = Field(default_factory=list)
    figures: list[RUOFigure] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _section_ids_unique(self) -> "RUOBody":
        ids = [s.section_id for s in self.sections]
        if len(ids) != len(set(ids)):
            raise ValueError("section_id values must be unique within a document")
        return self

    @model_validator(mode="after")
    def _chunk_ids_unique(self) -> "RUOBody":
        ids = [c.chunk_id for c in self.chunks]
        if len(ids) != len(set(ids)):
            raise ValueError("chunk_id values must be unique within a document")
        return self
```

### 6.6 RUOSection

```python
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

    # Provenance & evidence
    extraction_method: ExtractionMethod
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _page_order(self) -> "RUOSection":
        if self.page_end < self.page_start:
            raise ValueError("page_end must be >= page_start")
        return self

    @model_validator(mode="after")
    def _label_confidence_unresolved(self) -> "RUOSection":
        if self.canonical_label == CanonicalLabel.OTHER and self.label_confidence > 0.99:
            raise ValueError(
                "label_confidence should not be near 1.0 for OTHER — "
                "OTHER is a fallback, not a positive classification"
            )
        return self
```

### 6.7 RUOChunk

```python
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

    # Extraction quality
    extraction_method: ExtractionMethod
    extraction_confidence: float = Field(..., ge=0.0, le=1.0)

    # Derived indices — populated during validation
    entity_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)

    # Evidence
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def _text_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("chunk text must not be empty or whitespace-only")
        return stripped
```

### 6.8 RUOReference

```python
class RUOReference(BaseModel):
    """Bibliography entry with resolution evidence."""

    ref_id: str
    raw_text: str

    # Resolution
    resolution_status: ResolutionStatus
    resolution_source: ResolutionSource = ResolutionSource.NONE
    ref_confidence: float = Field(..., ge=0.0, le=1.0)

    # Parsed fields
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: str | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    arxiv_id: str | None = None
    pmid: str | None = None

    # Evidence chain for resolution
    evidence_ids: list[str] = Field(default_factory=list)

    # For cross-document linking
    target_ruo_id: str | None = None    # resolved → linked RUO document

    @field_validator("doi")
    @classmethod
    def _doi_normalize(cls, v: str | None) -> str | None:
        if v is not None:
            return v.lower().strip()
        return v

    @model_validator(mode="after")
    def _resolved_has_source(self) -> "RUOReference":
        if self.resolution_status == ResolutionStatus.RESOLVED:
            if self.resolution_source == ResolutionSource.NONE:
                raise ValueError(
                    "resolution_source must be set when resolution_status is RESOLVED"
                )
        return self

    @model_validator(mode="after")
    def _target_consistent(self) -> "RUOReference":
        if self.target_ruo_id is not None and self.resolution_status != ResolutionStatus.RESOLVED:
            raise ValueError(
                "target_ruo_id can only be set when resolution_status is RESOLVED"
            )
        return self
```

### 6.9 RUOCitation

```python
class RUOCitation(BaseModel):
    """An inline citation with intent evidence."""

    citation_id: str
    ref_id: str | None = None        # None if unresolved
    chunk_id: str
    section_id: str
    context_sentence: str
    page: int = Field(..., ge=0)

    # Intent classification with evidence
    citation_intent: CitationIntent | None = None
    intent_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    intent_evidence_ids: list[str] = Field(default_factory=list)

    # Raw marker for provenance
    raw_marker: str | None = None

    @model_validator(mode="after")
    def _intent_requires_confidence(self) -> "RUOCitation":
        if self.citation_intent is not None and self.intent_confidence is None:
            raise ValueError(
                "intent_confidence is required when citation_intent is set"
            )
        return self

    @model_validator(mode="after")
    def _intent_requires_evidence(self) -> "RUOCitation":
        if self.citation_intent is not None and not self.intent_evidence_ids:
            raise ValueError(
                "At least one evidence record is required when citation_intent is set"
            )
        return self
```

### 6.10 RUOEntity

```python
class RUOEntity(BaseModel):
    """A named entity with extraction evidence."""

    entity_id: str
    text: str
    label: EntityLabel
    chunk_id: str
    sentence: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: str                     # "spacy", "scispacy", "pattern_match", "llm"

    # Normalization / linking
    normalized_id: str | None = None     # ID in a knowledge base (UMLS, Wikidata, etc.)
    normalized_label: str | None = None  # canonical name
    kb_source: str | None = None         # "umls", "wikidata", "custom"

    # Evidence
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def _text_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("entity text must not be empty")
        return v
```

### 6.11 RUOClaim

```python
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

    # Evidence chain — every claim must be backed by evidence
    evidence_chain_id: str          # → EvidenceChain.target_id

    # Cross-document status
    is_contradicted: bool = False
    is_supported_by: list[str] = Field(default_factory=list)  # RUO IDs
    is_replicated: bool | None = None

    # Normalized form for comparison
    normalized_statement: str | None = None

    @field_validator("matched_patterns")
    @classmethod
    def _patterns_non_empty(cls, v: list[str]) -> list[str]:
        if not v or not all(p.strip() for p in v):
            raise ValueError("matched_patterns must contain at least one non-empty pattern")
        return v
```

### 6.12 SemanticTriple

```python
class SemanticTriple(BaseModel):
    """A subject-predicate-object triple for knowledge graph construction.

    Enables GraphRAG, contradiction detection, and cross-document reasoning
    without parsing natural language at query time.
    """

    triple_id: str
    subject_id: str                  # entity_id or claim_id
    subject_text: str
    predicate: str                   # normalized relation (e.g. "achieves", "uses", "improves")
    object_id: str                   # entity_id or claim_id
    object_text: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    chunk_id: str                    # source chunk

    # Evidence
    evidence_ids: list[str] = Field(default_factory=list)

    # Optional quantification
    quantification: str | None = None   # e.g. "5.2% improvement", "p < 0.01"

    @field_validator("predicate")
    @classmethod
    def _predicate_format(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z_]+", v):
            raise ValueError("predicate must be snake_case lowercase")
        return v
```

### 6.13 DocumentRelation

```python
class DocumentRelation(BaseModel):
    """A semantic relationship between two RUO documents.

    Enables cross-paper analysis: citation graphs, contradiction maps,
    support networks, and evolution tracking.
    """

    relation_id: str
    source_ruo_id: str
    target_ruo_id: str
    relation_type: RelationType

    # Supporting evidence
    source_chunk_id: str | None = None   # specific chunk in source
    target_chunk_id: str | None = None   # specific chunk in target
    source_claim_id: str | None = None
    target_claim_id: str | None = None

    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)

    # Directionality
    is_directed: bool = True             # False for symmetric relations (e.g. "reproduces")

    @model_validator(mode="after")
    def _self_relation(self) -> "DocumentRelation":
        if self.source_ruo_id == self.target_ruo_id:
            raise ValueError("source_ruo_id and target_ruo_id must differ")
        return self
```

### 6.14 Annotation

```python
class Annotation(BaseModel):
    """A human or automated annotation attached to any element in the RUO.

    Annotations do NOT modify the underlying data — they overlay on top,
    preserving the original extraction while enabling correction, review,
    and discussion.
    """

    annotation_id: str
    annotation_type: AnnotationType

    # What is being annotated
    target_id: str                    # id of the annotated element
    target_type: str                  # "chunk", "entity", "claim", "citation", "section", "header", "reference"

    # The annotation content
    field: str                        # which field is being annotated (e.g. "canonical_label", "confidence")
    previous_value: Any | None = None
    suggested_value: Any | None = None

    # Who made it
    author: str                       # "human:user@example.com" or "llm:gemini-2.0-flash"
    timestamp: datetime
    reason: str | None = None
    status: str = "open"              # "open", "accepted", "rejected", "superseded"

    @field_validator("target_type")
    @classmethod
    def _valid_target(cls, v: str) -> str:
        allowed = {"chunk", "entity", "claim", "citation", "section", "header", "reference",
                   "abstract", "table", "figure", "relation", "triple", "quality", "document"}
        if v not in allowed:
            raise ValueError(f"target_type must be one of {allowed}")
        return v
```

---

## 7. Aggregate Models

### 7.1 RUOCorpus

```python
class RUOCorpus(BaseModel):
    """A collection of RUO documents for cross-paper analysis.

    This is the unit of input for Module 2+ operations: GraphRAG,
    contradiction detection, gap discovery, evidence-based QA,
    and research evolution mapping.
    """

    corpus_id: str
    name: str
    description: str | None = None
    schema_version: str = "2.0.0"
    created_at: datetime
    updated_at: datetime

    # Documents
    documents: dict[str, RUODocument] = Field(default_factory=dict)    # ruo_id → document

    # Cross-document relations
    relations: list[DocumentRelation] = Field(default_factory=list)

    # Global index
    global_entities: dict[str, list[str]] = Field(default_factory=dict)   # normalized_label → [ruo_id]
    global_claims: dict[str, list[str]] = Field(default_factory=dict)     # claim_id → [ruo_id]

    # Quality
    quality: RUOQuality
    validation: ValidationReport | None = None

    # Provenance
    provenance: list[ProvenanceRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def _relation_ids_in_corpus(self) -> "RUOCorpus":
        for rel in self.relations:
            if rel.source_ruo_id not in self.documents:
                raise ValueError(
                    f"DocumentRelation.source_ruo_id '{rel.source_ruo_id}' "
                    f"not found in corpus"
                )
            if rel.target_ruo_id not in self.documents:
                raise ValueError(
                    f"DocumentRelation.target_ruo_id '{rel.target_ruo_id}' "
                    f"not found in corpus"
                )
        return self
```

### 7.2 RUOQuality

```python
class RUOQuality(BaseModel):
    """Quality assessment for a single RUODocument or RUOCorpus.

    Replaces SROQuality with the hierarchical confidence model,
    evidence coverage metrics, and declarative validation.
    """

    # Hierarchical confidence
    confidence: ConfidenceBreakdown

    # Evidence coverage
    evidence_coverage: EvidenceCoverage

    # Validation
    validation: ValidationReport | None = None

    # Pipeline execution
    pipeline_log: list[SROPipelineLogEntry] = Field(default_factory=list)
    llm_calls: list[SROLLMCall] = Field(default_factory=list)

    # Manual review
    requires_manual_review: bool = False
    manual_review_reasons: list[str] = Field(default_factory=list)

    # Summary
    overall_confidence: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _overall_matches_breakdown(self) -> "RUOQuality":
        if abs(self.overall_confidence - self.confidence.overall) > 0.01:
            raise ValueError(
                "overall_confidence must match confidence.overall"
            )
        return self
```

### 7.3 RUOEvidenceReport

```python
class RUOEvidenceReport(BaseModel):
    """A standalone report summarizing evidence for a claim, entity, or fact.

    This model exists to serve GraphRAG and QA interfaces — it collects
    all evidence for a given target across documents.
    """

    report_id: str
    target_id: str
    target_type: str                 # "claim", "entity", "citation_intent"
    target_text: str

    # All evidence across documents
    evidence_chains: list[EvidenceChain] = Field(default_factory=list)

    # Cross-document aggregation
    supporting_documents: list[str] = Field(default_factory=list)   # RUO IDs
    contradicting_documents: list[str] = Field(default_factory=list)

    # Aggregate
    aggregate_confidence: float = Field(..., ge=0.0, le=1.0)
    consensus: str | None = None     # "consistent", "contradictory", "insufficient_evidence"
```

---

## Appendix A: Migration Path from SRO v1.0.0

| SRO Field | RUO Equivalent | Notes |
|-----------|---------------|-------|
| `SROSourceFile` | `RUOSourceFile` (renamed in `RUOMeta`) | Identical schema |
| `SROMeta` | `RUOMeta` + `RUODocument.provenance` | Added corpus_ids, pipeline_stages |
| `SROHeader` | `RUOHeader` | `title_confidence`/`authors_confidence` → `ComponentConfidence` |
| `SROAbstract` | `RUOAbstract` |  |
| `SROSection` | `RUOSection` | Added `extraction_method`, `evidence_ids` |
| `SROChunk` | `RUOChunk` |  |
| `SROTable`/`SROFigure` | `RUOTable`/`RUOFigure` |  |
| `SROReference` | `RUOReference` | Added `arxiv_id`, `pmid`, `target_ruo_id`, `evidence_ids` |
| `SROCitation` | `RUOCitation` | Added `intent_evidence_ids`, `raw_marker` |
| `SROEntity` | `RUOEntity` | Added `normalized_id`, `normalized_label`, `kb_source`, `evidence_ids` |
| `SROCandidateClaim` | `RUOClaim` | Added `evidence_chain_id`, cross-document fields |
| `SROPipelineLogEntry` | unchanged | Re-exported from SRO |
| `SROLLMCall` | unchanged | Re-exported from SRO |
| `SROFieldScores` | `ConfidenceBreakdown` | Hierarchical with sub-scores |
| `SROExtractionCompleteness` | `EvidenceCoverage` | Evidence-focused |
| `SROQuality` | `RUOQuality` | Uses `ConfidenceBreakdown` + `EvidenceCoverage` |

New in RUO (no SRO equivalent): `EvidenceRecord`, `EvidenceChain`, `ProvenanceRecord`, `Uncertainty`, `SemanticTriple`, `DocumentRelation`, `Annotation`, `RUOCorpus`, `RUOEvidenceReport`

---

## Appendix B: Validation Rules (Declarative)

The following rules are defined for the validator module (implementation TBD):

| Rule ID | Description | Severity | Category |
|---------|------------|----------|----------|
| `XREF-001` | Every chunk.section_id references an existing section | ERROR | cross_reference |
| `XREF-002` | Every citation.chunk_id references an existing chunk | ERROR | cross_reference |
| `XREF-003` | Every citation.ref_id references an existing reference | ERROR | cross_reference |
| `XREF-004` | Every entity.chunk_id references an existing chunk | ERROR | cross_reference |
| `XREF-005` | Every claim.chunk_id references an existing chunk | ERROR | cross_reference |
| `XREF-006` | Every claim.evidence_chain_id references an existing EvidenceChain | ERROR | cross_reference |
| `COMP-001` | At least one section exists | ERROR | completeness |
| `COMP-002` | At least one chunk exists | ERROR | completeness |
| `COMP-003` | Confidence scores are present for all required components | WARNING | completeness |
| `COMP-004` | Evidence exists for at least 50% of claims | WARNING | evidence |
| `COMP-005` | Evidence exists for at least 50% of citations with intent | WARNING | evidence |
| `CONS-001` | Section.page_end >= section.page_start | ERROR | consistency |
| `CONS-002` | Chunk.word_count >= 1 | ERROR | consistency |
| `CONS-003` | Resolved references have non-NONE resolution_source | ERROR | consistency |
| `CONS-004` | reading_order is contiguous | WARNING | consistency |
| `CONS-005` | chunk_id values are unique | ERROR | consistency |
| `EVID-001` | Every claim has at least one evidence chain entry | WARNING | evidence |
| `EVID-002` | Evidence chain is in chronological order | ERROR | evidence |
| `EVID-003` | aggregate_confidence <= max(evidence.confidence) | ERROR | evidence |

---

## Appendix C: File Layout

```
src/researchmind/models/ruo/        # RUO schema package
├── __init__.py                     # Re-exports all models
├── enums.py                        # All enums (new + re-exports from models/enums.py)
├── evidence.py                     # EvidenceRecord, EvidenceChain, EvidenceSpan
├── provenance.py                   # ProvenanceRecord
├── confidence.py                   # ComponentConfidence, ComponentSubscore, ConfidenceBreakdown, EvidenceCoverage, Uncertainty
├── validation.py                   # ValidationRule, ValidationResult, ValidationReport
├── core.py                         # RUODocument, RUOMeta, RUOHeader, RUOAuthor, etc.
├── relations.py                    # SemanticTriple, DocumentRelation
├── annotation.py                   # Annotation
├── corpus.py                       # RUOCorpus
└── reports.py                      # RUOEvidenceReport, RUOQuality

config/
└── ruo_default.yaml                # RUO-specific configuration defaults
```

This file layout is a suggestion for implementation. The architecture document
defines the schema — the exact packaging can adapt to the existing codebase
conventions during implementation.
