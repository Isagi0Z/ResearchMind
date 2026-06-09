"""Shared enumerations used across the entire ResearchMind pipeline."""

from __future__ import annotations

try:
    from enum import StrEnum
except ImportError:
    # Python < 3.11 fallback
    from enum import Enum

    class StrEnum(str, Enum):
        """Backport of StrEnum for Python < 3.11."""
        pass


class ExtractionRoute(StrEnum):
    """How the PDF was routed through the extraction pipeline."""

    GROBID_PRIMARY = "grobid_primary"
    GROBID_WITH_FALLBACK = "grobid_with_fallback"
    OCR_PRIMARY = "ocr_primary"
    HYBRID = "hybrid"


class ExtractionMethod(StrEnum):
    """Which tool produced a specific piece of extracted content."""

    GROBID = "grobid"
    PYMUPDF_FALLBACK = "pymupdf_fallback"
    OCR_SURYA = "ocr_surya"
    OCR_TESSERACT = "ocr_tesseract"
    LLM_REPAIR = "llm_repair"


class CanonicalLabel(StrEnum):
    """Normalized section labels from the canonical taxonomy."""

    INTRODUCTION = "introduction"
    RELATED_WORK = "related_work"
    METHODOLOGY = "methodology"
    RESULTS = "results"
    DISCUSSION = "discussion"
    CONCLUSION = "conclusion"
    LIMITATIONS = "limitations"
    FUTURE_WORK = "future_work"
    ACKNOWLEDGMENTS = "acknowledgments"
    APPENDIX = "appendix"
    OTHER = "other"


class DocumentType(StrEnum):
    """Classification of the paper's type."""

    RESEARCH_ARTICLE = "research_article"
    REVIEW = "review"
    META_ANALYSIS = "meta_analysis"
    PREPRINT = "preprint"
    THESIS = "thesis"
    CASE_STUDY = "case_study"
    TECHNICAL_REPORT = "technical_report"
    OTHER = "other"


class VenueType(StrEnum):
    """Classification of where the paper was published."""

    JOURNAL = "journal"
    CONFERENCE = "conference"
    WORKSHOP = "workshop"
    PREPRINT_SERVER = "preprint_server"
    THESIS = "thesis"
    UNKNOWN = "unknown"


class ResolutionStatus(StrEnum):
    """Whether a bibliographic reference was successfully resolved."""

    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


class ResolutionSource(StrEnum):
    """How a reference was resolved to a canonical identifier."""

    GROBID_CONSOLIDATION = "grobid_consolidation"
    CROSSREF_LOOKUP = "crossref_lookup"
    MANUAL = "manual"
    NONE = "none"


class CitationIntent(StrEnum):
    """Why the author cited a particular reference."""

    SUPPORTS = "supports"
    CONTRASTS = "contrasts"
    EXTENDS = "extends"
    USES_METHOD = "uses_method"
    BACKGROUND = "background"
    COMPARES = "compares"
    UNKNOWN = "unknown"


class ClaimType(StrEnum):
    """Category of a detected candidate claim."""

    STATISTICAL = "statistical"
    CAUSAL = "causal"
    COMPARATIVE = "comparative"
    METHODOLOGICAL = "methodological"
    EXISTENCE = "existence"
    NEGATION = "negation"


class EntityLabel(StrEnum):
    """Named entity type taxonomy."""

    METHOD = "method"
    DATASET = "dataset"
    METRIC = "metric"
    TOOL = "tool"
    MATERIAL = "material"
    DISEASE = "disease"
    DRUG = "drug"
    GENE_PROTEIN = "gene_protein"
    ORGANISM = "organism"
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    OTHER = "other"


class StageStatus(StrEnum):
    """Outcome of a pipeline stage execution."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
