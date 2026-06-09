# ResearchMind Unified Object (RUO) — Schema v2.1.0

> **Architecture remediation addressing findings from the M2-0 design audit.**  
> Derived from v2.0.0. All mandatory fixes from `ruo_schema_v2.md` are applied.
> No pipeline changes, no extraction logic, no Module 1 modifications.

---

## Change Log (v2.0.0 → v2.1.0)

| # | Change | Rationale | Section |
|---|--------|-----------|---------|
| 1 | **`RUOSourceFile` defined** | Model was referenced but undefined in v2.0.0. | 6.2 |
| 2 | **`DocumentStore` abstraction** | Replaces eager `dict[str, RUODocument]` in `RUOCorpus` to enable lazy loading and database-backed storage at scale. | 7.1 |
| 3 | **`RUOCorpus.document_ids` replaces `documents`** | Corpus holds only document IDs + lightweight indices; full documents live in the store. | 7.1 |
| 4 | **`relations` removed from `RUODocument`** | Cross-document relations belong only in `RUOCorpus`. Removes circular dependency and separation-of-concerns violation. | 6.1 |
| 5 | **`AnnotationStatus` enum** | Replaces free-string `status` field on `Annotation`. | 2.3 |
| 6 | **`EvidenceTargetType` enum** | Replaces free-string `target_type` on `EvidenceChain`. | 2.1 |
| 7 | **`ConsensusStatus` enum** | Replaces free-string `consensus` on `RUOEvidenceReport`. | 2.1 |
| 8 | **Confidence integrity validator** | Checks `ComponentConfidence.score == weighted_sum(subscores)`. Was missing in v2.0.0 — score could be arbitrary. | 4.1 |
| 9 | **`SemanticTriple.is_negated`** | Enables representation of negative claims (e.g. "X does NOT improve Y") for contradiction detection. | 6.12 |
| 10 | **`embedding` + `embedding_model` on chunks/entities/claims** | Optional vector embeddings for GraphRAG semantic search. | 6.7, 6.10, 6.11 |
| 11 | **`EvidenceRecord.extraction_method` type fix** | Fixed `ExtractionMethod | ExtractionMethod` → `DataSource`. | 3.1 |
| 12 | **`aggregation_method` enum** | Replaces free-string `aggregation_method` on `EvidenceChain`. | 3.2 |
| 13 | **RUO quality store validation** | Validator added to `ComponentConfidence`; `component_weights` made required on `ConfidenceBreakdown`. | 4.1, 4.2 |

---

## Migration Impact (v2.0.0 → v2.1.0)

| Impact | Items | Details |
|--------|-------|---------|
| **Breaking** | 4 | `relations` field removed from `RUODocument`; `Annotation.status` → enum; `EvidenceChain.target_type` → enum; `EvidenceChain.aggregation_method` → enum; `RUOEvidenceReport.consensus` → enum; `EvidenceRecord.extraction_method` type change |
| **Additive** | 5 | `SemanticTriple.is_negated`; embedding fields on 3 models; `DocumentStore` interface; confidence validators; `RUOSourceFile` model |
| **Structural** | 1 | `RUOCorpus` — `documents: dict` → `document_ids: list[str]` + `DocumentStore` injection. All callers must update. |
| **Zero-impact** | 3 | Enum additions don't affect existing data; new validators only reject already-invalid states |

---

## 1. Design Principles (unchanged from v2.0.0)

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

### 2.1 Evidence, Uncertainty, and Consensus

```python
class EvidenceType(StrEnum):
    """The nature of the evidence supporting a fact."""
    DIRECT_QUOTE          = "direct_quote"
    PARAPHRASE            = "paraphrase"
    STATISTICAL           = "statistical"
    DERIVED               = "derived"
    EXTERNAL              = "external"
    LLM_GENERATED         = "llm_generated"
    HUMAN_ANNOTATED       = "human_annotated"


class EvidenceTargetType(StrEnum):
    """What kind of fact an EvidenceChain supports."""
    CLAIM                 = "claim"
    ENTITY                = "entity"
    CITATION_INTENT       = "citation_intent"
    CONFIDENCE            = "confidence"


class AggregationMethod(StrEnum):
    """How multiple evidence confidences are combined into an aggregate."""
    MINIMUM               = "minimum"
    PRODUCT               = "product"
    WEIGHTED_AVERAGE      = "weighted_average"


class UncertaintyType(StrEnum):
    """Category of uncertainty associated with a fact or score."""
    MEASUREMENT_ERROR     = "measurement_error"
    MISSING_DATA          = "missing_data"
    CONTRADICTORY_EVIDENCE= "contradictory_evidence"
    MODEL_UNCERTAINTY     = "model_uncertainty"
    AMBIGUOUS_SOURCE      = "ambiguous_source"
    EXTRACTION_ARTIFACT   = "extraction_artifact"
    NOT_APPLICABLE        = "not_applicable"


class ConsensusStatus(StrEnum):
    """Overall agreement level across multiple sources of evidence."""
    CONSISTENT            = "consistent"
    CONTRADICTORY         = "contradictory"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
```

### 2.2 Provenance (unchanged from v2.0.0)

```python
class ProvenanceAction(StrEnum):
    CREATED               = "created"
    UPDATED               = "updated"
    VALIDATED             = "validated"
    CORRECTED             = "corrected"
    REJECTED              = "rejected"
    ANNOTATED             = "annotated"
    MERGED                = "merged"


class ProvenanceAgentType(StrEnum):
    PIPELINE_STAGE        = "pipeline_stage"
    LLM                   = "llm"
    HUMAN_REVIEWER        = "human_reviewer"
    EXTERNAL_SERVICE      = "external_service"
    RULE_BASED            = "rule_based"


class DataSource(StrEnum):
    GROBID                = "grobid"
    PYMUPDF               = "pymupdf"
    OCR_SURYA             = "ocr_surya"
    OCR_TESSERACT         = "ocr_tesseract"
    CROSSREF              = "crossref"
    PUBMED                = "pubmed"
    LLM                   = "llm"
    MANUAL_REVIEW         = "manual_review"
    INFERRED              = "inferred"
    UNKNOWN               = "unknown"
```

### 2.3 Relations, Annotation & Validation

```python
class RelationType(StrEnum):
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
    HUMAN_REVIEW          = "human_review"
    HUMAN_CORRECTION      = "human_correction"
    LLM_SUGGESTION        = "llm_suggestion"
    AUTOMATED_FLAG        = "automated_flag"
    QUALITY_ISSUE         = "quality_issue"
    MANUAL_OVERRIDE       = "manual_override"


class AnnotationStatus(StrEnum):
    OPEN                  = "open"
    ACCEPTED              = "accepted"
    REJECTED              = "rejected"
    SUPERSEDED            = "superseded"


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

    # Content-addressing — verifies evidence hasn't drifted from source
    source_text_sha256: str | None = Field(default=None, min_length=64, max_length=64)

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
    data_source: DataSource                              # was ExtractionMethod | ExtractionMethod (bug fixed)
    extraction_method: ExtractionMethod                  # which tool extracted this text

    # Confidence in this specific piece of evidence
    confidence: float = Field(..., ge=0.0, le=1.0)
    uncertainty: str | None = None

    # When this evidence was produced
    provenance_ref: str | None = None
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

    target_id: str
    target_type: EvidenceTargetType                       # was free string

    chain: list[EvidenceRecord] = Field(..., min_length=1)
    aggregate_confidence: float = Field(..., ge=0.0, le=1.0)

    # How the aggregate was computed
    aggregation_method: AggregationMethod = AggregationMethod.WEIGHTED_AVERAGE  # was free string

    # Cross-document support
    supporting_document_ids: list[str] = Field(default_factory=list)

    @field_validator("chain")
    @classmethod
    def _chain_ordered_by_provenance(cls, v: list[EvidenceRecord]) -> list[EvidenceRecord]:
        """Evidence records should be in logical processing order.
        Equal timestamps are permitted (parallel pipeline stages).
        """
        for i in range(1, len(v)):
            if v[i].timestamp and v[i-1].timestamp and v[i].timestamp < v[i-1].timestamp:
                raise ValueError(
                    f"Evidence chain should follow chronological order: "
                    f"{v[i-1].evidence_id} @ {v[i-1].timestamp} before "
                    f"{v[i].evidence_id} @ {v[i].timestamp}"
                )
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
    agent_name: str
    pipeline_stage: str | None
    pipeline_version: str | None
    configuration_snapshot: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
    notes: str | None = None
    supersedes_id: str | None = None       # NEW: link to the provenance record this replaces
```

### 3.4 Uncertainty

```python
class Uncertainty(BaseModel):
    """Representation of uncertainty for a confidence score or fact."""

    uncertainty_type: UncertaintyType
    magnitude: float = Field(..., ge=0.0, le=1.0)
    explanation: str | None = None

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

    name: str
    value: float = Field(..., ge=0.0, le=1.0)
    weight: float = Field(..., ge=0.0, le=1.0)
    explanation: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class ComponentConfidence(BaseModel):
    """Confidence score for one logical component (title, authors, sections, etc.)."""

    component: str
    score: float = Field(..., ge=0.0, le=1.0)
    subscores: list[ComponentSubscore] = Field(default_factory=list)
    uncertainty: Uncertainty | None = None
    evidence_chain_id: str | None = None

    @model_validator(mode="after")
    def _weight_sum(self) -> "ComponentConfidence":
        """Subscore weights must sum to 1.0."""
        if self.subscores:
            total_weight = sum(s.weight for s in self.subscores)
            if abs(total_weight - 1.0) > 1e-6:            # tighter tolerance via rel
                raise ValueError(
                    f"Subscore weights for '{self.component}' must sum to 1.0 "
                    f"(got {total_weight})"
                )
        return self

    @model_validator(mode="after")
    def _score_consistent_with_subscores(self) -> "ComponentConfidence":
        """NEW: score must equal the weighted sum of subscores (ensures integrity)."""
        if self.subscores:
            weighted = sum(s.value * s.weight for s in self.subscores)
            if abs(self.score - weighted) > 0.01:
                raise ValueError(
                    f"score ({self.score:.4f}) must equal weighted sum of subscores "
                    f"({weighted:.4f}) for component '{self.component}'"
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

    # Weights used for overall aggregation — REQUIRED (no longer optional)
    component_weights: dict[str, float]   # e.g. {"title": 0.20, "authors": 0.15, ...}

    @model_validator(mode="after")
    def _weight_keys_match_components(self) -> "ConfidenceBreakdown":
        """Every component must have a weight; every weight must have a component."""
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
                raise ValueError("ConfidenceBreakdown weight/component mismatch: " + "; ".join(msg_parts))
        return self

    @model_validator(mode="after")
    def _overall_consistent(self) -> "ConfidenceBreakdown":
        """Overall must match the weighted sum of component scores."""
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

## 5. Validation Framework (unchanged from v2.0.0)

```python
class ValidationRule(BaseModel):
    rule_id: str
    description: str
    severity: ValidationSeverity
    category: str
    message_template: str
    enabled: bool = True


class ValidationResult(BaseModel):
    rule_id: str
    passed: bool
    severity: ValidationSeverity
    message: str
    affected_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class ValidationReport(BaseModel):
    results: list[ValidationResult] = Field(default_factory=list)
    summary: dict[ValidationSeverity, int] = Field(default_factory=dict)
    is_valid: bool = True

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

    This is the fundamental unit of the ResearchMind ecosystem.
    Cross-document relations are stored in RUOCorpus, not here.
    """

    # Identity & lifecycle
    meta: RUOMeta

    # Provenance chain
    provenance: list[ProvenanceRecord] = Field(default_factory=list)

    # Extracted content
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

    # NOTE: relations moved to RUOCorpus (v2.1.0 remediation)

    # Quality & confidence
    quality: RUOQuality

    # Human & automated annotations
    annotations: list[Annotation] = Field(default_factory=list)

    # Schema evolution
    schema_version: str = "2.1.0"
    lineage: list[str] = Field(default_factory=list)

    @field_validator("schema_version")
    @classmethod
    def _schema_version_format(cls, v: str) -> str:
        if not re.fullmatch(r"\d+\.\d+\.\d+", v):
            raise ValueError("schema_version must be in semver format (e.g. 2.1.0)")
        return v

    def get_provenance_by_action(self, action: ProvenanceAction) -> list[ProvenanceRecord]:
        return [p for p in self.provenance if p.action == action]
```

### 6.2 RUOMeta

```python
class RUOSourceFile(BaseModel):
    """Identity and physical properties of the source PDF.
    (Defined explicitly in v2.1.0 — was undefined in v2.0.0.)
    """
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

    schema_version: str = "2.1.0"
    created_at: datetime
    updated_at: datetime
    pipeline_version: str

    source_file: RUOSourceFile     # now explicitly defined
    extraction_route: ExtractionRoute

    document_type: DocumentType = DocumentType.RESEARCH_ARTICLE
    language: str = Field(default="en", min_length=2, max_length=5)

    # Research field classification (for Module 3)
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
        allowed = {"en", "fr", "de", "es", "it", "pt", "zh", "ja", "ko", "ru", "ar", "other"}
        if v not in allowed and not re.fullmatch(r"[a-z]{2}(-[A-Z]{2})?", v):
            raise ValueError(f"language must be a valid BCP-47 tag or one of {allowed}")
        return v
```

### 6.3 RUOHeader (unchanged from v2.0.0)

```python
class RUOAuthor(BaseModel):
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
```

### 6.4 RUOAbstract (unchanged)

```python
class RUOStructuredAbstract(BaseModel):
    background: str | None = None
    objective: str | None = None
    methods: str | None = None
    results: str | None = None
    conclusion: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class RUOAbstract(BaseModel):
    raw_text: str
    is_structured: bool = False
    structured: RUOStructuredAbstract | None = None
    confidence: ComponentConfidence
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _structured_consistency(self) -> "RUOAbstract":
        if self.is_structured and self.structured is None:
            raise ValueError("structured must be provided when is_structured is True")
        return self
```

### 6.5 RUOBody (unchanged except embedding on RUOChunk)

```python
class RUOTable(BaseModel):
    table_id: str
    caption: str
    section_id: str
    page: int = Field(..., ge=0)
    raw_content: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)


class RUOFigure(BaseModel):
    figure_id: str
    caption: str
    section_id: str
    page: int = Field(..., ge=0)
    image_path: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class RUOBody(BaseModel):
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

### 6.6 RUOSection (unchanged)

```python
class RUOSection(BaseModel):
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

### 6.7 RUOChunk (NEW: embedding fields)

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

    extraction_method: ExtractionMethod
    extraction_confidence: float = Field(..., ge=0.0, le=1.0)

    # Derived indices — populated during validation
    entity_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)

    # Evidence
    evidence_ids: list[str] = Field(default_factory=list)

    # GraphRAG embeddings (NEW — optional, populated downstream)
    embedding: list[float] | None = None
    embedding_model: str | None = None

    @field_validator("text")
    @classmethod
    def _text_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("chunk text must not be empty or whitespace-only")
        return stripped
```

### 6.8 RUOReference (unchanged)

```python
class RUOReference(BaseModel):
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
    def _resolved_has_source(self) -> "RUOReference":
        if self.resolution_status == ResolutionStatus.RESOLVED:
            if self.resolution_source == ResolutionSource.NONE:
                raise ValueError("resolution_source must be set when resolution_status is RESOLVED")
        return self

    @model_validator(mode="after")
    def _target_consistent(self) -> "RUOReference":
        if self.target_ruo_id is not None and self.resolution_status != ResolutionStatus.RESOLVED:
            raise ValueError("target_ruo_id can only be set when resolution_status is RESOLVED")
        return self
```

### 6.9 RUOCitation (unchanged)

```python
class RUOCitation(BaseModel):
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
    def _intent_requires_confidence(self) -> "RUOCitation":
        if self.citation_intent is not None and self.intent_confidence is None:
            raise ValueError("intent_confidence is required when citation_intent is set")
        return self

    @model_validator(mode="after")
    def _intent_requires_evidence(self) -> "RUOCitation":
        if self.citation_intent is not None and not self.intent_evidence_ids:
            raise ValueError("At least one evidence record is required when citation_intent is set")
        return self
```

### 6.10 RUOEntity (NEW: embedding fields)

```python
class RUOEntity(BaseModel):
    """A named entity with extraction evidence."""

    entity_id: str
    text: str
    label: EntityLabel
    chunk_id: str
    sentence: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: str

    # Normalization / linking
    normalized_id: str | None = None
    normalized_label: str | None = None
    kb_source: str | None = None

    # Evidence
    evidence_ids: list[str] = Field(default_factory=list)

    # GraphRAG embeddings (NEW — optional, populated downstream)
    embedding: list[float] | None = None
    embedding_model: str | None = None

    @field_validator("text")
    @classmethod
    def _text_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("entity text must not be empty")
        return v
```

### 6.11 RUOClaim (NEW: embedding fields, temporal metadata)

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
    evidence_chain_id: str

    # Cross-document status
    is_contradicted: bool = False
    contradiction_detected_at: datetime | None = None       # NEW: temporal tracking
    is_supported_by: list[str] = Field(default_factory=list)
    is_replicated: bool | None = None

    # Normalized form for comparison
    normalized_statement: str | None = None

    # GraphRAG embeddings (NEW — optional, populated downstream)
    embedding: list[float] | None = None
    embedding_model: str | None = None

    @field_validator("matched_patterns")
    @classmethod
    def _patterns_non_empty(cls, v: list[str]) -> list[str]:
        if not v or not all(p.strip() for p in v):
            raise ValueError("matched_patterns must contain at least one non-empty pattern")
        return v
```

### 6.12 SemanticTriple (NEW: negation support)

```python
class SemanticTriple(BaseModel):
    """A subject-predicate-object triple for knowledge graph construction.

    Supports positive and negative statements for contradiction detection.
    """

    triple_id: str
    subject_id: str
    subject_text: str
    predicate: str                   # from controlled vocabulary (PredicateRegistry)
    object_id: str
    object_text: str
    is_negated: bool = False         # NEW: True means "subject does NOT predicate object"
    confidence: float = Field(..., ge=0.0, le=1.0)
    chunk_id: str

    # Evidence
    evidence_ids: list[str] = Field(default_factory=list)

    # Optional quantification
    quantification: str | None = None

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
    Stored in RUOCorpus only (removed from RUODocument in v2.1.0).
    """

    relation_id: str
    source_ruo_id: str
    target_ruo_id: str
    relation_type: RelationType

    # Supporting evidence
    source_chunk_id: str | None = None
    target_chunk_id: str | None = None
    source_claim_id: str | None = None
    target_claim_id: str | None = None

    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)

    # Directionality
    is_directed: bool = True

    # Temporal tracking (NEW — for Module 3 evolution mapping)
    detected_at: datetime
    valid_until: datetime | None = None

    @model_validator(mode="after")
    def _self_relation(self) -> "DocumentRelation":
        if self.source_ruo_id == self.target_ruo_id:
            raise ValueError("source_ruo_id and target_ruo_id must differ")
        return self
```

### 6.14 Annotation (UPDATED: enum status)

```python
class Annotation(BaseModel):
    """A human or automated annotation attached to any element in the RUO.
    Annotations do NOT modify the underlying data — they overlay on top.
    """

    annotation_id: str
    annotation_type: AnnotationType

    # What is being annotated
    target_id: str
    target_type: str

    # The annotation content
    field: str
    previous_value: Any | None = None
    suggested_value: Any | None = None

    # Who made it
    author: str
    timestamp: datetime
    reason: str | None = None
    status: AnnotationStatus = AnnotationStatus.OPEN    # was free string

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

### 7.1 RUOCorpus (REDESIGNED: DocumentStore abstraction)

```python
class DocumentStore(ABC):
    """Abstract document storage backend.

    Implementations may use a database, filesystem, or cloud storage.
    Documents are loaded lazily — only when accessed. This replaces
    the eager dict[str, RUODocument] design that does not scale.

    Methods
    -------
    get(id)          — load a single document (returns None if not found)
    get_batch(ids)   — load multiple documents in one operation
    put(doc)         — store or update a document
    delete(id)       — remove a document (returns False if not found)
    contains(id)     — check existence without loading
    list_ids()       — enumerate all document IDs in the store
    count()          — total number of documents
    """

    @abstractmethod
    def get(self, ruo_id: str) -> RUODocument | None: ...

    @abstractmethod
    def get_batch(self, ruo_ids: list[str]) -> dict[str, RUODocument]: ...

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

    RUOCorpus is a lightweight metadata container. The actual document
    data lives in a DocumentStore, which is injected at runtime and
    not serialized as part of this model's JSON representation.

    REDESIGNED in v2.1.0:
    - documents: dict[str, RUODocument] → document_ids: list[str] + DocumentStore
    - relations validated at query time, not at model construction
    - global_entities / global_claims retained as lightweight indices
    """

    corpus_id: str
    name: str
    description: str | None = None
    schema_version: str = "2.1.0"
    created_at: datetime
    updated_at: datetime

    # Document IDs (not full documents — those are in DocumentStore)
    document_ids: list[str] = Field(default_factory=list)

    # Cross-document relations (metadata only — validation deferred)
    relations: list[DocumentRelation] = Field(default_factory=list)

    # Global indices (lightweight — populated on corpus build)
    global_entities: dict[str, list[str]] = Field(default_factory=dict)
    global_claims: dict[str, list[str]] = Field(default_factory=dict)

    # Quality & validation
    quality: RUOQuality
    validation: ValidationReport | None = None
    provenance: list[ProvenanceRecord] = Field(default_factory=list)

    # Document store — injected at runtime, not serialized with the model
    _document_store: DocumentStore | None = None

    @model_validator(mode="after")
    def _relation_ids_in_corpus(self) -> "RUOCorpus":
        """Validate that relation IDs reference documents known to the corpus.
        This performs a quick check against document_ids (IDs only, not full documents).
        Full cross-reference resolution (chunk/claim existence) is deferred to query time
        to avoid O(n·m) load-time cost.
        """
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

    # --- Document access delegation ---

    def get_document(self, ruo_id: str) -> RUODocument | None:
        """Lazily load a document from the store."""
        if self._document_store is None:
            raise RuntimeError("DocumentStore not configured on this corpus")
        return self._document_store.get(ruo_id)

    def has_document(self, ruo_id: str) -> bool:
        """Check document existence without loading its full content."""
        if self._document_store is not None:
            return self._document_store.contains(ruo_id)
        return ruo_id in self.document_ids

    def attach_store(self, store: DocumentStore) -> None:
        """Inject a DocumentStore at runtime. Not serialized."""
        self._document_store = store
```

### 7.2 RUOQuality (unchanged)

```python
class RUOQuality(BaseModel):
    confidence: ConfidenceBreakdown
    evidence_coverage: EvidenceCoverage
    validation: ValidationReport | None = None
    pipeline_log: list[SROPipelineLogEntry] = Field(default_factory=list)
    llm_calls: list[SROLLMCall] = Field(default_factory=list)
    requires_manual_review: bool = False
    manual_review_reasons: list[str] = Field(default_factory=list)
    overall_confidence: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _overall_matches_breakdown(self) -> "RUOQuality":
        if abs(self.overall_confidence - self.confidence.overall) > 0.01:
            raise ValueError("overall_confidence must match confidence.overall")
        return self
```

### 7.3 RUOEvidenceReport (UPDATED: enum consensus)

```python
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
    consensus: ConsensusStatus | None = None            # was free string

    # Provenance of the report itself (NEW)
    generated_at: datetime
    generator: str                                      # e.g. "evidence_synthesizer_v1"
```

---

## Appendix A: Migration Path from v2.0.0

| v2.0.0 Model | v2.1.0 Change | Migration |
|---|---|---|
| `RUOSourceFile` | **Added** (was missing/undefined) | All callers must provide this model |
| `RUODocument.relations` | **Removed** | Move relations to `RUOCorpus.relations` |
| `RUOCorpus.documents: dict` | **Replaced** with `document_ids: list[str]` + `DocumentStore` | Structural redesign |
| `Annotation.status: str` | **Changed** to `AnnotationStatus` enum | Update all callers |
| `EvidenceChain.target_type: str` | **Changed** to `EvidenceTargetType` enum | Update all callers |
| `EvidenceChain.aggregation_method: str` | **Changed** to `AggregationMethod` enum | Update all callers |
| `RUOEvidenceReport.consensus: str` | **Changed** to `ConsensusStatus` enum | Update all callers |
| `EvidenceRecord.extraction_method` | **Changed** type to `DataSource` | Update all callers |
| `SemanticTriple` | **Added** `is_negated: bool` | Additive — default False |
| `RUOChunk` | **Added** `embedding`, `embedding_model` | Additive — optional |
| `RUOEntity` | **Added** `embedding`, `embedding_model` | Additive — optional |
| `RUOClaim` | **Added** `embedding`, `embedding_model`, `contradiction_detected_at` | Additive — optional |
| `DocumentRelation` | **Added** `detected_at`, `valid_until` | Additive |
| `ConfidenceBreakdown.component_weights` | **Changed** from optional to required | All callers must provide weights |
| `ComponentConfidence` | **Added** `_score_consistent_with_subscores` validator | Enforces existing constraint — no data change if already correct |
| `ProvenanceRecord` | **Added** `supersedes_id` | Additive |
| `RUOMeta` | **Added** `arxiv_categories`, `research_fields` | Additive |
| `RUOEvidenceReport` | **Added** `generated_at`, `generator` | Additive |

---

## Appendix B: Validation Rules (Updated)

### New rules added in v2.1.0

| Rule ID | Description | Severity | Category |
|---------|------------|----------|----------|
| `CONS-006` | ComponentConfidence.score equals weighted sum of subscores | ERROR | consistency |
| `CONS-007` | ConfidenceBreakdown.component_weights cover all components | ERROR | consistency |
| `CONS-008` | ConfidenceBreakdown.overall matches weighted sum | ERROR | consistency |
| `EVID-004` | EvidenceSpan.source_text_sha256 is consistent with content | WARNING | evidence |
| `EVID-005` | ProvenanceRecord.supersedes_id references an existing record | ERROR | cross_reference |

### Existing rules (unchanged)

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
| `EVID-002` | Evidence chain follows chronological order | ERROR | evidence |
| `EVID-003` | aggregate_confidence <= max(evidence.confidence) | ERROR | evidence |

---

## Appendix C: File Layout (unchanged)

```
src/researchmind/models/ruo/
├── __init__.py
├── enums.py
├── evidence.py
├── provenance.py
├── confidence.py
├── validation.py
├── core.py
├── relations.py
├── annotation.py
├── corpus.py                  # includes DocumentStore interface
└── reports.py
```

---

## Appendix D: Known Gaps (Deferred from v2.1.0)

The following are acknowledged gaps from the design audit that are explicitly deferred to a future schema version:

| Gap | Requiring Module | Reason for Deferral |
|-----|-----------------|---------------------|
| Math expression model (`MathExpression`) | 3 (Research Graph) | No extraction pipeline produces this yet |
| Argumentation graph (premise → conclusion) | 4 (Reasoning Engine) | Requires reasoning infrastructure |
| Query / task models | 4, 5 | Agent workflows not yet designed |
| Hypothesis model | 5 (Research Agent) | Agent workflows not yet designed |
| Agent plan / tool-call models | 5 (Research Agent) | Agent workflows not yet designed |
| Content deduplication strategy | 2 (RUOCorpus) | Requires production data to tune |
| Named graph support for triples | 3 (KG) | Reification adds complexity; not yet needed |
| PredicateRegistry controlled vocabulary | 2 (KG) | Must be populated by domain analysis, not architecture |
