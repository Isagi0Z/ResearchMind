"""Intermediate data contracts passed between pipeline stages.

These models are internal — they never appear in the final SRO output. They
exist to enforce type safety between stages and make each stage independently
testable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from researchmind.models.enums import (
    ExtractionMethod,
    ExtractionRoute,
    StageStatus,
)


# ---------------------------------------------------------------------------
# Pipeline-level types
# ---------------------------------------------------------------------------


class StageLog(BaseModel):
    """Execution record for a single pipeline stage (internal form)."""

    stage: str
    status: StageStatus = StageStatus.SUCCESS
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    duration_ms: int | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)

    def finish(self, status: StageStatus | None = None) -> None:
        """Mark the stage as completed and compute duration."""
        self.completed_at = datetime.now(timezone.utc)
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)
        if status is not None:
            self.status = status


class PipelineError(Exception):
    """Raised when a pipeline stage fails in a non-recoverable way."""

    def __init__(self, stage: str, message: str) -> None:
        self.stage = stage
        self.message = message
        super().__init__(f"[{stage}] {message}")


# ---------------------------------------------------------------------------
# Stage 0: Intake
# ---------------------------------------------------------------------------


class IntakeResult(BaseModel):
    """Output of Stage 0 — PDF classification and routing decision."""

    file_path: Path
    sha256: str
    page_count: int
    file_size_bytes: int
    has_text_layer: bool
    is_scanned: bool
    text_density: float  # average chars per page (sampled)
    extraction_route: ExtractionRoute
    duplicate_of: str | None = None  # sro_id if duplicate detected


# ---------------------------------------------------------------------------
# Stage 1: Extraction — raw parsed data from PDF
# ---------------------------------------------------------------------------


class RawAuthor(BaseModel):
    """Author as extracted from GROBID or fallback — minimal parsing."""

    full_name: str
    given_name: str | None = None
    surname: str | None = None
    affiliations: list[str] = Field(default_factory=list)
    email: str | None = None
    orcid: str | None = None
    is_corresponding: bool = False


class RawSection(BaseModel):
    """A section as extracted from the PDF before normalization."""

    header: str  # raw header text (may be empty for untitled sections)
    level: int = 1  # nesting depth (1 = top-level)
    parent_index: int | None = None  # index into the raw_sections list
    paragraphs: list[str] = Field(default_factory=list)
    page_start: int = 0
    page_end: int = 0
    extraction_method: ExtractionMethod = ExtractionMethod.GROBID


class RawReference(BaseModel):
    """A bibliography entry as extracted from GROBID."""

    grobid_id: str | None = None  # GROBID's internal ref ID (e.g. "b12")
    raw_text: str = ""
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: str | None = None
    venue: str | None = None
    volume: str | None = None
    pages: str | None = None
    doi: str | None = None
    url: str | None = None


class RawCitation(BaseModel):
    """An inline citation marker as extracted from GROBID TEI."""

    grobid_ref_target: str | None = None  # e.g. "#b12"
    raw_marker: str = ""  # e.g. "[12]" or "(Smith, 2024)"
    section_index: int = 0
    paragraph_index: int = 0
    sentence: str = ""


class RawTable(BaseModel):
    """Table extracted from the PDF."""

    grobid_id: str | None = None
    caption: str = ""
    page: int = 0
    raw_content: str | None = None  # pipe-delimited text dump
    extraction_method: ExtractionMethod = ExtractionMethod.GROBID


class RawFigure(BaseModel):
    """Figure extracted from the PDF."""

    grobid_id: str | None = None
    caption: str = ""
    page: int = 0
    image_path: str | None = None


class ExtractionResult(BaseModel):
    """Output of Stage 1 — raw extracted content before normalization."""

    intake: IntakeResult

    # Header fields
    raw_title: str | None = None
    raw_authors: list[RawAuthor] = Field(default_factory=list)
    raw_abstract: str | None = None
    raw_keywords: list[str] = Field(default_factory=list)
    raw_doi: str | None = None
    raw_arxiv_id: str | None = None
    raw_pmid: str | None = None
    raw_pub_date: str | None = None

    # Body
    raw_sections: list[RawSection] = Field(default_factory=list)

    # Bibliography
    raw_references: list[RawReference] = Field(default_factory=list)

    # Inline citations
    raw_citations: list[RawCitation] = Field(default_factory=list)

    # Tables & figures
    raw_tables: list[RawTable] = Field(default_factory=list)
    raw_figures: list[RawFigure] = Field(default_factory=list)

    # Provenance
    extraction_method: ExtractionRoute = ExtractionRoute.GROBID_PRIMARY
    grobid_quality: float | None = None
    fallback_used: bool = False
    stage_log: StageLog = Field(default_factory=lambda: StageLog(stage="extraction"))


# ---------------------------------------------------------------------------
# Pipeline configuration (loaded from YAML)
# ---------------------------------------------------------------------------


class GrobidConfig(BaseModel):
    url: str = "http://localhost:8070"
    timeout_seconds: int = 120
    consolidate_header: bool = True
    consolidate_citations: bool = True
    retry_attempts: int = Field(3, ge=1)
    retry_backoff_initial_seconds: float = Field(2.0, ge=0.0)
    retry_backoff_max_seconds: float = Field(30.0, ge=0.0)
    retry_status_codes: list[int] = Field(
        default_factory=lambda: [408, 429, 500, 502, 503, 504]
    )


class ExtractionConfig(BaseModel):
    fallback_threshold: float = 0.5
    ocr_engine: str = "tesseract"
    ocr_dpi: int = 300
    max_pages: int = 200
    page_size_warning: int = 80
    text_density_threshold: float = 50.0


class ChunkingConfig(BaseModel):
    min_words: int = 150
    max_words: int = 600
    sentence_tokenizer: str = "nltk"


class NERConfig(BaseModel):
    general_model: str = "en_core_web_trf"
    biomedical_model: str = "en_core_sci_lg"
    enable_biomedical: bool = False
    enable_custom_patterns: bool = True


class CrossRefConfig(BaseModel):
    enabled: bool = True
    rate_limit: int = 10
    mailto: str = ""
    retry_attempts: int = 2
    retry_backoff_seconds: float = 2.0
    resolve_threshold: float = 0.70
    ambiguous_threshold: float = 0.50


class LLMFallbackConfig(BaseModel):
    enabled: bool = False
    model: str = "gemini-2.0-flash"
    max_calls_per_paper: int = 5
    api_key_env: str = "GEMINI_API_KEY"


class QualityConfig(BaseModel):
    manual_review_threshold: float = 0.5
    citation_unlinked_warning: float = 0.3


class StorageConfig(BaseModel):
    output_dir: str = "./output"
    db_path: str = "./researchmind.db"


class PipelineConfig(BaseModel):
    """Top-level configuration loaded from config/default.yaml."""

    grobid: GrobidConfig = Field(default_factory=GrobidConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    ner: NERConfig = Field(default_factory=NERConfig)
    crossref: CrossRefConfig = Field(default_factory=CrossRefConfig)
    llm_fallback: LLMFallbackConfig = Field(default_factory=LLMFallbackConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)

    @classmethod
    def load(cls, path: str | Path = "config/default.yaml") -> "PipelineConfig":
        """Load configuration from a YAML file."""
        import yaml

        p = Path(path)
        if not p.exists():
            return cls()
        with open(p) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)
