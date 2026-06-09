"""Pipeline orchestrator — wires intake → extraction → structuring → enrichment → quality.

This is the central coordinator for Module 1.  It processes a single PDF and
returns a fully-assembled :class:`StructuredResearchObject`.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from researchmind.models.enums import (
    CanonicalLabel,
    CitationIntent,
    ExtractionMethod,
    ExtractionRoute,
    ResolutionSource,
    ResolutionStatus,
    StageStatus,
)
from researchmind.models.intermediates import (
    ExtractionResult,
    IntakeResult,
    PipelineConfig,
    PipelineError,
    StageLog,
)
from researchmind.models.sro import (
    SCHEMA_VERSION,
    SROAbstract,
    SROAuthor,
    SROBody,
    SROCandidateClaim,
    SROChunk,
    SROCitation,
    SROEntity,
    SROExtractionCompleteness,
    SROFieldScores,
    SROFigure,
    SROHeader,
    SROLLMCall,
    SROMeta,
    SROPipelineLogEntry,
    SROQuality,
    SROReference,
    SROSection,
    SROSourceFile,
    SROStructuredAbstract,
    SROTable,
    StructuredResearchObject,
)

# ---------------------------------------------------------------------------
# Stage imports — each stage is a thin function or class in its own module.
# ---------------------------------------------------------------------------
from researchmind.intake.fingerprint import fingerprint
from researchmind.intake.router import route
from researchmind.extraction.grobid_client import GrobidClient
from researchmind.extraction.tei_parser import parse_tei_xml
from researchmind.extraction.pymupdf_extractor import extract_with_pymupdf
from researchmind.extraction.ocr_extractor import extract_with_ocr
from researchmind.structuring.section_normalizer import normalize_sections
from researchmind.structuring.reference_resolver import resolve_references
from researchmind.structuring.citation_linker import link_citations
from researchmind.structuring.chunker import chunk_sections
from researchmind.structuring.table_figure_extractor import process_tables, process_figures
from researchmind.enrichment.ner_extractor import extract_entities
from researchmind.enrichment.claim_detector import detect_claims
from researchmind.quality.confidence_scorer import compute_quality
from researchmind.quality.validator import validate_sro, compute_derived_indices

logger = logging.getLogger(__name__)

PIPELINE_VERSION = "0.1.0"

# Regex patterns for detecting structured abstracts
_STRUCTURED_ABSTRACT_PATTERNS = re.compile(
    r"(?:^|\n)\s*"
    r"(Background|Objective|Purpose|Aim|Methods?|Materials?\s*(?:and|&)\s*Methods?|"
    r"Results?|Findings?|Conclusion|Discussion|Significance|Context|Design|Setting|"
    r"Participants?|Interventions?|Main\s*Outcome\s*Measures?|Measurements?)"
    r"\s*[:.] ",
    re.IGNORECASE | re.MULTILINE,
)


def _now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


def _make_stage_log(stage_name: str) -> StageLog:
    """Create a new stage-log entry with started_at = now."""
    return StageLog(stage=stage_name, started_at=_now())


def _finish_stage(
    log: StageLog,
    status: StageStatus = StageStatus.SUCCESS,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    details: dict[str, Any] | None = None,
) -> StageLog:
    """Finalise a stage log entry."""
    if warnings:
        log.warnings.extend(warnings)
    if errors:
        log.errors.extend(errors)
    if details:
        log.details.update(details)
    log.finish(status)
    return log


def _to_pipeline_log_entry(log: StageLog) -> SROPipelineLogEntry:
    """Convert an internal StageLog to the SRO's public pipeline-log model."""
    return SROPipelineLogEntry(
        stage=log.stage,
        status=log.status,
        started_at=log.started_at,
        completed_at=log.completed_at or _now(),
        duration_ms=log.duration_ms,
        warnings=log.warnings,
        errors=log.errors,
        details=log.details,
    )


# ---------------------------------------------------------------------------
# Structured-abstract parser
# ---------------------------------------------------------------------------

def _parse_structured_abstract(raw: str) -> tuple[bool, SROStructuredAbstract | None]:
    """Attempt to parse a raw abstract string into structured sub-fields.

    Detects common headings like Background, Methods, Results, Conclusion and
    splits the text accordingly.

    Returns:
        A tuple ``(is_structured, structured_or_none)``.
    """
    # Quick check — do at least two section headings appear?
    headings_found = _STRUCTURED_ABSTRACT_PATTERNS.findall(raw)
    if len(headings_found) < 2:
        return False, None

    # Split by heading patterns and collect text for each known bucket
    background_parts: list[str] = []
    objective_parts: list[str] = []
    methods_parts: list[str] = []
    results_parts: list[str] = []
    conclusion_parts: list[str] = []

    # Mapping heading labels → bucket lists
    heading_map: dict[str, list[str]] = {
        "background": background_parts,
        "context": background_parts,
        "introduction": background_parts,
        "objective": objective_parts,
        "purpose": objective_parts,
        "aim": objective_parts,
        "method": methods_parts,
        "methods": methods_parts,
        "materials and methods": methods_parts,
        "materials & methods": methods_parts,
        "design": methods_parts,
        "setting": methods_parts,
        "participants": methods_parts,
        "interventions": methods_parts,
        "main outcome measures": methods_parts,
        "measurements": methods_parts,
        "result": results_parts,
        "results": results_parts,
        "findings": results_parts,
        "conclusion": conclusion_parts,
        "conclusions": conclusion_parts,
        "discussion": conclusion_parts,
        "significance": conclusion_parts,
    }

    # Split on headings
    parts = re.split(
        r"(?:^|\n)\s*"
        r"(Background|Objective|Purpose|Aim|Methods?|Materials?\s*(?:and|&)\s*Methods?|"
        r"Results?|Findings?|Conclusions?|Discussion|Significance|Context|Design|Setting|"
        r"Participants?|Interventions?|Main\s*Outcome\s*Measures?|Measurements?|Introduction)"
        r"\s*[:.] ",
        raw,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    # parts alternates: [pre-text, heading1, body1, heading2, body2, ...]
    current_bucket: list[str] | None = None
    for i, part in enumerate(parts):
        stripped = part.strip()
        if not stripped:
            continue
        normalised_key = re.sub(r"\s+", " ", stripped.lower())
        if normalised_key in heading_map:
            current_bucket = heading_map[normalised_key]
        elif current_bucket is not None:
            current_bucket.append(stripped)

    structured = SROStructuredAbstract(
        background=" ".join(background_parts).strip() or None,
        objective=" ".join(objective_parts).strip() or None,
        methods=" ".join(methods_parts).strip() or None,
        results=" ".join(results_parts).strip() or None,
        conclusion=" ".join(conclusion_parts).strip() or None,
    )

    # Only treat as structured if at least one field is populated
    has_content = any([
        structured.background,
        structured.objective,
        structured.methods,
        structured.results,
        structured.conclusion,
    ])
    if not has_content:
        return False, None

    return True, structured


# ---------------------------------------------------------------------------
# Pipeline class
# ---------------------------------------------------------------------------


class IngestionPipeline:
    """Orchestrates the five-stage paper ingestion pipeline.

    Stages:
        0. **Intake** — fingerprint, route, duplicate check
        1. **Extraction** — GROBID (with fallback) or OCR
        2. **Structuring** — normalise sections, chunk, resolve refs, link cites
        3. **Enrichment** — NER, claim detection, citation-intent
        4. **Quality** — confidence scoring, validation, derived indices

    The resulting :class:`StructuredResearchObject` is returned to the caller.
    """

    def __init__(self, config: PipelineConfig) -> None:
        """Initialise the pipeline with the given configuration.

        Args:
            config: A :class:`PipelineConfig` instance (usually loaded from
                ``config/default.yaml``).
        """
        self._config = config
        # GrobidClient takes a GrobidConfig object
        self._grobid = GrobidClient(config.grobid)
        logger.info("IngestionPipeline initialised (GROBID → %s)", config.grobid.url)

    # ------------------------------------------------------------------
    # main entry point
    # ------------------------------------------------------------------

    def process(self, pdf_path: Path) -> StructuredResearchObject:
        """Process a single PDF through all pipeline stages.

        Args:
            pdf_path: Path to the PDF file on disk.

        Returns:
            A fully assembled :class:`StructuredResearchObject`.

        Raises:
            PipelineError: If the intake stage fails (non-recoverable).
        """
        pipeline_start = time.monotonic()
        stage_logs: list[StageLog] = []
        sro_id = str(uuid.uuid4())
        now = _now()

        logger.info("Processing %s (sro_id=%s)", pdf_path.name, sro_id)

        # ==================================================================
        # Stage 0 — Intake
        # ==================================================================
        intake_result = self._stage_intake(pdf_path, stage_logs)

        # ==================================================================
        # Stage 1 — Extraction
        # ==================================================================
        extraction = self._stage_extraction(intake_result, pdf_path, stage_logs)

        # ==================================================================
        # Stage 2 — Structuring
        # ==================================================================
        sections, chunks, sro_references, sro_citations, sro_tables, sro_figures = (
            self._stage_structuring(extraction, stage_logs)
        )

        # ==================================================================
        # Stage 3 — Enrichment
        # ==================================================================
        entities, claims, sro_citations = self._stage_enrichment(
            chunks, sections, sro_citations, stage_logs,
        )

        # ==================================================================
        # Assemble the SRO (quality computed post-assembly)
        # ==================================================================
        processing_time_ms = int((time.monotonic() - pipeline_start) * 1000)

        # Build abstract
        abstract = self._build_abstract(extraction)

        # Build header
        header = self._build_header(extraction)

        # Build source file info
        source_file = SROSourceFile(
            filename=pdf_path.name,
            sha256=intake_result.sha256,
            page_count=intake_result.page_count,
            has_text_layer=intake_result.has_text_layer,
            is_scanned=intake_result.is_scanned,
            size_bytes=intake_result.file_size_bytes,
        )

        meta = SROMeta(
            sro_id=sro_id,
            schema_version=SCHEMA_VERSION,
            created_at=now,
            updated_at=_now(),
            pipeline_version=PIPELINE_VERSION,
            extraction_route=extraction.extraction_method,
            source_file=source_file,
            processing_time_ms=processing_time_ms,
        )

        # Convert stage logs to SRO format
        pipeline_log_entries = [_to_pipeline_log_entry(sl) for sl in stage_logs]

        body_sections = sections if sections else [self._fallback_section(extraction)]
        body_chunks = chunks if chunks else [
            self._fallback_chunk(
                extraction,
                section_id=body_sections[0].section_id,
                canonical_label=body_sections[0].canonical_label,
            )
        ]

        body = SROBody(
            sections=body_sections,
            chunks=body_chunks,
            tables=sro_tables,
            figures=sro_figures,
        )

        # Build a placeholder quality object so the SRO can be assembled
        placeholder_quality = SROQuality(
            overall_confidence=0.0,
            field_scores=SROFieldScores(),
            extraction_completeness=SROExtractionCompleteness(),
            pipeline_log=pipeline_log_entries,
        )

        sro = StructuredResearchObject(
            meta=meta,
            header=header,
            abstract=abstract,
            body=body,
            references=sro_references,
            citations=sro_citations,
            entities=entities,
            candidate_claims=claims,
            quality=placeholder_quality,
        )

        # ==================================================================
        # Stage 4 — Quality & Validation (operates on the full SRO)
        # ==================================================================
        sro = self._stage_quality(sro, stage_logs)

        logger.info(
            "Pipeline complete for %s — confidence=%.2f, time=%dms",
            pdf_path.name,
            sro.quality.overall_confidence,
            processing_time_ms,
        )
        return sro

    # ==================================================================
    # Stage implementations
    # ==================================================================

    def _stage_intake(
        self,
        pdf_path: Path,
        stage_logs: list[StageLog],
    ) -> IntakeResult:
        """Stage 0 — Fingerprint the PDF, classify it, decide extraction route."""
        log = _make_stage_log("intake")
        try:
            intake_result = fingerprint(pdf_path)
            # route() takes (IntakeResult, ExtractionConfig)
            intake_result = route(intake_result, self._config.extraction)
            _finish_stage(log, details={
                "sha256": intake_result.sha256,
                "page_count": intake_result.page_count,
                "route": intake_result.extraction_route.value,
                "has_text_layer": intake_result.has_text_layer,
            })
            stage_logs.append(log)
            logger.info(
                "Intake: pages=%d, route=%s, text_layer=%s",
                intake_result.page_count,
                intake_result.extraction_route.value,
                intake_result.has_text_layer,
            )
            return intake_result
        except Exception as exc:
            _finish_stage(log, StageStatus.FAILED, errors=[str(exc)])
            stage_logs.append(log)
            raise PipelineError("intake", str(exc)) from exc

    def _stage_extraction(
        self,
        intake: IntakeResult,
        pdf_path: Path,
        stage_logs: list[StageLog],
    ) -> ExtractionResult:
        """Stage 1 — Extract raw content via GROBID, PyMuPDF fallback, or OCR."""
        log = _make_stage_log("extraction")
        extraction: ExtractionResult | None = None
        warnings: list[str] = []

        try:
            if intake.extraction_route in (
                ExtractionRoute.GROBID_PRIMARY,
                ExtractionRoute.GROBID_WITH_FALLBACK,
                ExtractionRoute.HYBRID,
            ):
                extraction = self._extract_grobid(pdf_path, intake, warnings)
            elif intake.extraction_route == ExtractionRoute.OCR_PRIMARY:
                extraction = self._extract_ocr(pdf_path, intake, warnings)
            else:
                # Shouldn't happen, but fallback to GROBID attempt
                extraction = self._extract_grobid(pdf_path, intake, warnings)

            status = StageStatus.SUCCESS
            if extraction.fallback_used:
                status = StageStatus.PARTIAL
                warnings.append("GROBID quality below threshold; fallback used")

            _finish_stage(log, status, warnings=warnings, details={
                "method": extraction.extraction_method.value,
                "fallback_used": extraction.fallback_used,
                "grobid_quality": extraction.grobid_quality,
                "sections_extracted": len(extraction.raw_sections),
                "references_extracted": len(extraction.raw_references),
            })
        except Exception as exc:
            logger.error("Extraction failed: %s", exc, exc_info=True)
            # Attempt bare minimum fallback
            try:
                extraction = self._extract_pymupdf_minimal(pdf_path, intake)
                warnings.append(f"Primary extraction failed ({exc}); PyMuPDF fallback used")
                _finish_stage(log, StageStatus.PARTIAL, warnings=warnings)
            except Exception as fallback_exc:
                logger.error("Fallback extraction also failed: %s", fallback_exc)
                # Create a minimal extraction result so the pipeline can continue
                extraction = ExtractionResult(
                    intake=intake,
                    raw_title=pdf_path.stem.replace("_", " ").replace("-", " "),
                    extraction_method=ExtractionRoute.GROBID_PRIMARY,
                    grobid_quality=0.0,
                    fallback_used=True,
                )
                _finish_stage(
                    log,
                    StageStatus.FAILED,
                    errors=[str(exc), str(fallback_exc)],
                    warnings=warnings,
                )

        stage_logs.append(log)
        return extraction  # type: ignore[return-value]

    def _extract_grobid(
        self,
        pdf_path: Path,
        intake: IntakeResult,
        warnings: list[str],
    ) -> ExtractionResult:
        """Try GROBID extraction, fall back to PyMuPDF if quality is too low."""
        # GrobidClient.process_fulltext(pdf_path) — returns TEI XML or None
        tei_xml = self._grobid.process_fulltext(pdf_path)

        if tei_xml is None:
            raise RuntimeError("GROBID returned no output — service may be down")

        raw_fields, grobid_quality = parse_tei_xml(tei_xml)
        extraction = ExtractionResult(
            intake=intake,
            **raw_fields,
            extraction_method=ExtractionRoute.GROBID_PRIMARY,
            grobid_quality=grobid_quality,
            fallback_used=False,
        )
        logger.info("GROBID quality score: %.3f", extraction.grobid_quality or 0.0)

        # Check quality threshold
        grobid_quality = extraction.grobid_quality or 0.0
        threshold = self._config.extraction.fallback_threshold

        if grobid_quality < threshold:
            logger.warning(
                "GROBID quality %.3f < threshold %.3f — running PyMuPDF fallback",
                grobid_quality,
                threshold,
            )
            warnings.append(
                f"GROBID quality ({grobid_quality:.3f}) below threshold ({threshold})"
            )
            # extract_with_pymupdf(pdf_path) returns list[RawSection]
            fallback_sections = extract_with_pymupdf(pdf_path)
            # Merge fallback sections into the extraction result
            extraction = self._merge_with_fallback_sections(extraction, fallback_sections)
            extraction.fallback_used = True
            extraction.extraction_method = ExtractionRoute.GROBID_WITH_FALLBACK

        return extraction

    def _extract_ocr(
        self,
        pdf_path: Path,
        intake: IntakeResult,
        warnings: list[str],
    ) -> ExtractionResult:
        """Extract content using OCR (for scanned PDFs)."""
        # extract_with_ocr(pdf_path, config: ExtractionConfig) returns list[RawSection]
        ocr_sections = extract_with_ocr(pdf_path, self._config.extraction)

        extraction = ExtractionResult(
            intake=intake,
            raw_sections=ocr_sections,
            extraction_method=ExtractionRoute.OCR_PRIMARY,
            fallback_used=False,
        )
        return extraction

    def _extract_pymupdf_minimal(
        self,
        pdf_path: Path,
        intake: IntakeResult,
    ) -> ExtractionResult:
        """Emergency fallback — extract whatever PyMuPDF can get."""
        # extract_with_pymupdf(pdf_path) returns list[RawSection]
        fallback_sections = extract_with_pymupdf(pdf_path)

        extraction = ExtractionResult(
            intake=intake,
            raw_sections=fallback_sections,
            extraction_method=ExtractionRoute.GROBID_WITH_FALLBACK,
            fallback_used=True,
        )
        return extraction

    @staticmethod
    def _merge_with_fallback_sections(
        primary: ExtractionResult,
        fallback_sections: list,
    ) -> ExtractionResult:
        """Merge a primary GROBID result with PyMuPDF fallback section data.

        Strategy:
        - Keep GROBID header metadata (title, authors, etc.).
        - If GROBID produced very few sections, augment with fallback sections.
        """
        from researchmind.models.intermediates import RawSection

        # If GROBID produced very few sections, augment with fallback
        if len(primary.raw_sections) < 2 and len(fallback_sections) > len(primary.raw_sections):
            primary.raw_sections = fallback_sections

        return primary

    # ------------------------------------------------------------------
    # Stage 2 — Structuring
    # ------------------------------------------------------------------

    def _stage_structuring(
        self,
        extraction: ExtractionResult,
        stage_logs: list[StageLog],
    ) -> tuple[
        list[SROSection],
        list[SROChunk],
        list[SROReference],
        list[SROCitation],
        list[SROTable],
        list[SROFigure],
    ]:
        """Stage 2 — Normalise sections, chunk, resolve references, link citations."""
        log = _make_stage_log("structuring")
        warnings: list[str] = []

        sections: list[SROSection] = []
        chunks: list[SROChunk] = []
        sro_references: list[SROReference] = []
        sro_citations: list[SROCitation] = []
        sro_tables: list[SROTable] = []
        sro_figures: list[SROFigure] = []

        try:
            # normalize_sections(raw_sections, config_path=None)
            sections = normalize_sections(extraction.raw_sections)
            logger.info("Normalised %d sections", len(sections))

            # chunk_sections(sections, config: ChunkingConfig)
            section_methods = {
                f"sec_{idx + 1:03d}": raw.extraction_method
                for idx, raw in enumerate(extraction.raw_sections)
            }
            chunks = chunk_sections(sections, self._config.chunking, section_methods)
            logger.info("Created %d chunks", len(chunks))

            # resolve_references(raw_refs, config: CrossRefConfig)
            sro_references = resolve_references(
                extraction.raw_references,
                self._config.crossref,
            )
            logger.info(
                "Resolved references: %d/%d",
                sum(1 for r in sro_references if r.resolution_status == ResolutionStatus.RESOLVED),
                len(sro_references),
            )

            # link_citations(raw_citations, references, chunks, sections, raw_refs)
            sro_citations = link_citations(
                raw_citations=extraction.raw_citations,
                references=sro_references,
                chunks=chunks,
                sections=sections,
                raw_refs=extraction.raw_references,
            )
            logger.info("Linked %d citations", len(sro_citations))

            # Tables and figures
            sro_tables = process_tables(extraction.raw_tables, sections)
            sro_figures = process_figures(extraction.raw_figures, sections)

            _finish_stage(log, details={
                "sections": len(sections),
                "chunks": len(chunks),
                "references": len(sro_references),
                "citations": len(sro_citations),
                "tables": len(sro_tables),
                "figures": len(sro_figures),
            })
        except Exception as exc:
            logger.error("Structuring stage failed: %s", exc, exc_info=True)
            warnings.append(f"Structuring error: {exc}")
            _finish_stage(log, StageStatus.PARTIAL, warnings=warnings, errors=[str(exc)])

        stage_logs.append(log)
        return sections, chunks, sro_references, sro_citations, sro_tables, sro_figures

    # ------------------------------------------------------------------
    # Stage 3 — Enrichment
    # ------------------------------------------------------------------

    def _stage_enrichment(
        self,
        chunks: list[SROChunk],
        sections: list[SROSection],
        citations: list[SROCitation],
        stage_logs: list[StageLog],
    ) -> tuple[list[SROEntity], list[SROCandidateClaim], list[SROCitation]]:
        """Stage 3 — NER, claim detection, citation-intent classification."""
        log = _make_stage_log("enrichment")
        entities: list[SROEntity] = []
        claims: list[SROCandidateClaim] = []
        warnings: list[str] = []
        errors: list[str] = []

        # --- NER ---
        try:
            # extract_entities(chunks, config: NERConfig)
            entities = extract_entities(chunks, self._config.ner)
            logger.info("Extracted %d entities", len(entities))
        except Exception as exc:
            logger.error("NER extraction failed: %s", exc, exc_info=True)
            warnings.append(f"NER failed: {exc}")
            errors.append(f"NER: {exc}")

        # --- Claim detection ---
        try:
            # detect_claims(chunks, sections)
            claims = detect_claims(chunks, sections)
            logger.info("Detected %d candidate claims", len(claims))
        except Exception as exc:
            logger.error("Claim detection failed: %s", exc, exc_info=True)
            warnings.append(f"Claim detection failed: {exc}")
            errors.append(f"Claims: {exc}")

        # Determine overall stage status
        if errors and not entities and not claims:
            status = StageStatus.FAILED
        elif errors:
            status = StageStatus.PARTIAL
        else:
            status = StageStatus.SUCCESS

        _finish_stage(log, status, warnings=warnings, errors=errors, details={
            "entities": len(entities),
            "claims": len(claims),
        })
        stage_logs.append(log)

        return entities, claims, citations

    # ------------------------------------------------------------------
    # Stage 4 — Quality
    # ------------------------------------------------------------------

    def _stage_quality(
        self,
        sro: StructuredResearchObject,
        stage_logs: list[StageLog],
    ) -> StructuredResearchObject:
        """Stage 4 — Compute confidence scores, validate, flag for review.

        Operates on the fully-assembled SRO and returns an updated copy.
        """
        log = _make_stage_log("quality")

        try:
            # compute_derived_indices(sro) — mutates in place
            compute_derived_indices(sro)

            # compute_quality(sro: StructuredResearchObject) -> SROQuality
            quality = compute_quality(sro)

            # Run final schema validation
            validation_errors, validation_warnings = validate_sro(sro)
            quality.validation_errors = validation_errors
            quality.validation_warnings = validation_warnings
            if validation_errors:
                quality.requires_manual_review = True
                quality.manual_review_reasons.extend(validation_errors)

            # Preserve pipeline log from the placeholder
            quality.pipeline_log = sro.quality.pipeline_log
            # Add this quality stage's log entry
            _finish_stage(log, details={
                "overall_confidence": quality.overall_confidence,
                "requires_review": quality.requires_manual_review,
            })
            quality.pipeline_log.append(_to_pipeline_log_entry(log))

            sro.quality = quality

        except Exception as exc:
            logger.error("Quality computation failed: %s", exc, exc_info=True)
            # Build a minimal quality object so the SRO is still valid
            quality = self._fallback_quality_from_sro(sro)
            quality.pipeline_log = sro.quality.pipeline_log
            _finish_stage(log, StageStatus.PARTIAL, errors=[str(exc)], details={
                "overall_confidence": quality.overall_confidence,
            })
            quality.pipeline_log.append(_to_pipeline_log_entry(log))
            sro.quality = quality

        stage_logs.append(log)
        return sro

    # ==================================================================
    # Helper builders
    # ==================================================================

    def _build_abstract(self, extraction: ExtractionResult) -> SROAbstract:
        """Build an SROAbstract from the raw extraction result."""
        raw_text = extraction.raw_abstract or ""
        if not raw_text:
            return SROAbstract(
                raw_text="",
                is_structured=False,
                structured=None,
                confidence=0.0,
            )

        is_structured, structured = _parse_structured_abstract(raw_text)

        # Confidence heuristic: if abstract exists, base confidence on its length
        word_count = len(raw_text.split())
        if word_count > 100:
            confidence = 0.9
        elif word_count > 50:
            confidence = 0.7
        elif word_count > 20:
            confidence = 0.5
        else:
            confidence = 0.3

        return SROAbstract(
            raw_text=raw_text,
            is_structured=is_structured,
            structured=structured,
            confidence=confidence,
        )

    def _build_header(self, extraction: ExtractionResult) -> SROHeader:
        """Build an SROHeader from the raw extraction result."""
        # Title confidence heuristic
        title = extraction.raw_title or "Untitled"
        title_conf = 0.9 if extraction.raw_title else 0.1

        # Authors confidence
        authors = [
            SROAuthor(
                full_name=a.full_name,
                given_name=a.given_name,
                surname=a.surname,
                affiliations=a.affiliations,
                email=a.email,
                orcid=a.orcid,
                is_corresponding=a.is_corresponding,
            )
            for a in extraction.raw_authors
        ]
        authors_conf = 0.85 if authors else 0.1

        return SROHeader(
            title=title,
            title_confidence=title_conf,
            authors=authors,
            authors_confidence=authors_conf,
            doi=extraction.raw_doi,
            arxiv_id=extraction.raw_arxiv_id,
            pmid=extraction.raw_pmid,
            publication_date=extraction.raw_pub_date,
            publication_date_raw=extraction.raw_pub_date,
            keywords=extraction.raw_keywords,
        )

    @staticmethod
    def _fallback_section(extraction: ExtractionResult) -> SROSection:
        """Create a minimal fallback section when structuring produces none."""
        full_text = ""
        for rs in extraction.raw_sections:
            full_text += "\n".join(rs.paragraphs) + "\n"
        if not full_text.strip():
            full_text = extraction.raw_abstract or "No content extracted."

        return SROSection(
            section_id="sec-fallback-0",
            parent_section_id=None,
            level=1,
            position=0,
            original_header="Full Text",
            canonical_label=CanonicalLabel.OTHER,
            label_confidence=0.1,
            page_start=0,
            page_end=max(extraction.intake.page_count - 1, 0),
            content=full_text.strip(),
        )

    @staticmethod
    def _fallback_chunk(
        extraction: ExtractionResult,
        section_id: str = "sec-fallback-0",
        canonical_label: CanonicalLabel = CanonicalLabel.OTHER,
    ) -> SROChunk:
        """Create a minimal fallback chunk when chunking produces none."""
        full_text = ""
        for rs in extraction.raw_sections:
            full_text += "\n".join(rs.paragraphs) + "\n"
        if not full_text.strip():
            full_text = extraction.raw_abstract or "No content extracted."

        text = full_text.strip()
        extraction_method = (
            extraction.raw_sections[0].extraction_method
            if extraction.raw_sections
            else (
                ExtractionMethod.OCR_TESSERACT
                if extraction.extraction_method == ExtractionRoute.OCR_PRIMARY
                else ExtractionMethod.GROBID
            )
        )
        return SROChunk(
            chunk_id="chunk-fallback-0",
            text=text,
            word_count=max(len(text.split()), 1),
            section_id=section_id,
            canonical_label=canonical_label,
            page_start=0,
            page_end=max(extraction.intake.page_count - 1, 0),
            paragraph_index=0,
            reading_order=0,
            extraction_method=extraction_method,
            extraction_confidence=0.1,
        )

    @staticmethod
    def _fallback_quality_from_sro(sro: StructuredResearchObject) -> SROQuality:
        """Build a minimal quality object when compute_quality fails."""
        resolved_refs = sum(
            1 for r in sro.references if r.resolution_status == ResolutionStatus.RESOLVED
        )
        linked_cites = sum(1 for c in sro.citations if c.ref_id is not None)

        completeness = SROExtractionCompleteness(
            total_pages=sro.meta.source_file.page_count,
            pages_with_text_extracted=sro.meta.source_file.page_count if sro.meta.source_file.has_text_layer else 0,
            sections_detected=len(sro.body.sections),
            references_total=len(sro.references),
            references_resolved=resolved_refs,
            citations_total=len(sro.citations),
            citations_linked=linked_cites,
            chunks_total=len(sro.body.chunks),
            entities_total=len(sro.entities),
            claims_total=len(sro.candidate_claims),
        )

        # Simple overall confidence
        scores = []
        if sro.header.title and sro.header.title != "Untitled":
            scores.append(0.8)
        if sro.abstract.raw_text:
            scores.append(0.7)
        if sro.body.sections:
            scores.append(0.6)
        if sro.references:
            scores.append(0.5)
        overall = sum(scores) / max(len(scores), 1) if scores else 0.2

        return SROQuality(
            overall_confidence=min(overall, 1.0),
            field_scores=SROFieldScores(
                title=0.8 if sro.header.title and sro.header.title != "Untitled" else 0.1,
                authors=0.7 if sro.header.authors else 0.1,
                abstract=0.7 if sro.abstract.raw_text else 0.1,
                sections=0.5 if sro.body.sections else 0.1,
                references=0.5 if sro.references else 0.0,
                citations=0.5 if sro.citations else 0.0,
                entities=0.5 if sro.entities else 0.0,
                claims=0.5 if sro.candidate_claims else 0.0,
            ),
            extraction_completeness=completeness,
            requires_manual_review=True,
            manual_review_reasons=["Quality computation failed — using fallback scores"],
        )
