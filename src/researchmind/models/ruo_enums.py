"""RUO-specific enumerations (v2.1.0).

All new enums defined in the RUO schema architecture document.
Re-exports SRO enums for convenience.
"""

from __future__ import annotations

from enum import Enum

try:
    from enum import StrEnum
except ImportError:
    # Python < 3.11 fallback
    class StrEnum(str, Enum):
        pass


# ---------------------------------------------------------------------------
# Evidence & Uncertainty
# ---------------------------------------------------------------------------


class EvidenceType(StrEnum):
    DIRECT_QUOTE = "direct_quote"
    PARAPHRASE = "paraphrase"
    STATISTICAL = "statistical"
    DERIVED = "derived"
    EXTERNAL = "external"
    LLM_GENERATED = "llm_generated"
    HUMAN_ANNOTATED = "human_annotated"


class EvidenceTargetType(StrEnum):
    CLAIM = "claim"
    ENTITY = "entity"
    CITATION_INTENT = "citation_intent"
    CONFIDENCE = "confidence"


class AggregationMethod(StrEnum):
    MINIMUM = "minimum"
    PRODUCT = "product"
    WEIGHTED_AVERAGE = "weighted_average"


class UncertaintyType(StrEnum):
    MEASUREMENT_ERROR = "measurement_error"
    MISSING_DATA = "missing_data"
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"
    MODEL_UNCERTAINTY = "model_uncertainty"
    AMBIGUOUS_SOURCE = "ambiguous_source"
    EXTRACTION_ARTIFACT = "extraction_artifact"
    NOT_APPLICABLE = "not_applicable"


class ConsensusStatus(StrEnum):
    CONSISTENT = "consistent"
    CONTRADICTORY = "contradictory"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


class ProvenanceAction(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    VALIDATED = "validated"
    CORRECTED = "corrected"
    REJECTED = "rejected"
    ANNOTATED = "annotated"
    MERGED = "merged"


class ProvenanceAgentType(StrEnum):
    PIPELINE_STAGE = "pipeline_stage"
    LLM = "llm"
    HUMAN_REVIEWER = "human_reviewer"
    EXTERNAL_SERVICE = "external_service"
    RULE_BASED = "rule_based"


class DataSource(StrEnum):
    GROBID = "grobid"
    PYMUPDF = "pymupdf"
    OCR_SURYA = "ocr_surya"
    OCR_TESSERACT = "ocr_tesseract"
    CROSSREF = "crossref"
    PUBMED = "pubmed"
    LLM = "llm"
    MANUAL_REVIEW = "manual_review"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Relations, Annotation & Validation
# ---------------------------------------------------------------------------


class RelationType(StrEnum):
    CITES = "cites"
    CITED_BY = "cited_by"
    CONTRADICTS = "contradicts"
    SUPPORTS = "supports"
    EXTENDS = "extends"
    SUPERSEDES = "supersedes"
    REPRODUCES = "reproduces"
    USES_METHOD = "uses_method"
    USES_DATASET = "uses_dataset"
    COMPARES_WITH = "compares_with"
    REVIEWS = "reviews"
    META_ANALYSIS_INCLUDES = "meta_analysis_includes"
    UNKNOWN = "unknown"


class AnnotationType(StrEnum):
    HUMAN_REVIEW = "human_review"
    HUMAN_CORRECTION = "human_correction"
    LLM_SUGGESTION = "llm_suggestion"
    AUTOMATED_FLAG = "automated_flag"
    QUALITY_ISSUE = "quality_issue"
    MANUAL_OVERRIDE = "manual_override"


class AnnotationStatus(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ---------------------------------------------------------------------------
# Re-exports from SRO enums (unchanged)
# ---------------------------------------------------------------------------

from researchmind.models.enums import (  # noqa: E402, F401
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
