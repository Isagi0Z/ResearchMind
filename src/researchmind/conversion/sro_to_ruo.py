"""SRO → RUO converter.

Converts a complete StructuredResearchObject plus optional Module 2 outputs
(ExtractedFact, SemanticTriple, EvidenceRecord) into a fully validated
RUODocument. Every mapping preserves source IDs and cross-references.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from researchmind.models.enums import (
    CanonicalLabel,
    CitationIntent,
    DocumentType,
    ExtractionMethod,
    ExtractionRoute,
    StageStatus,
)
from researchmind.models.ruo import (
    Annotation,
    ComponentConfidence,
    ComponentSubscore,
    ConfidenceBreakdown,
    EvidenceChain,
    EvidenceCoverage,
    EvidenceRecord,
    ProvenanceRecord,
    RUOAbstract,
    RUOAuthor,
    RUOBody,
    RUOChunk,
    RUOCitation,
    RUOClaim,
    RUODocument,
    RUOEntity,
    RUOEvidenceReport,
    RUOFigure,
    RUOHeader,
    RUOMeta,
    RUOQuality,
    RUOReference,
    RUOSection,
    RUOSourceFile,
    RUOStructuredAbstract,
    RUOTable,
    SemanticTriple,
    ValidationReport,
    ValidationResult,
    RUO_SCHEMA_VERSION,
)
from researchmind.models.ruo_enums import (
    ConsensusStatus,
    EvidenceTargetType,
    ProvenanceAction,
    ProvenanceAgentType,
    ValidationSeverity,
)
from researchmind.models.sro import (
    SROAbstract,
    SROAuthor,
    SROBody,
    SROCandidateClaim,
    SROChunk,
    SROCitation,
    SROEntity,
    SROFigure,
    SROHeader,
    SROMeta,
    SROQuality,
    SROReference,
    SROSection,
    SROSourceFile,
    SROTable,
    StructuredResearchObject,
)
from researchmind.understanding.evidence_builder import EvidenceBuildResult
from researchmind.understanding.fact_extractor import ExtractedFact, FactExtractionResult
from researchmind.understanding.triple_extractor import TripleExtractionResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Outcome model
# ---------------------------------------------------------------------------


class ConversionResult(BaseModel):
    document: RUODocument
    report: RUOEvidenceReport | None = None
    conversion_notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ruo_id(sro_id: str) -> str:
    return f"ruo_{sro_id}"


def _default_confidence(score: float, component: str) -> ComponentConfidence:
    return ComponentConfidence(
        component=component,
        score=round(score, 4),
        subscores=[ComponentSubscore(
            name=component, value=round(score, 4), weight=1.0,
        )],
    )


# ---------------------------------------------------------------------------
# Meta & Source File
# ---------------------------------------------------------------------------


def _convert_source_file(sf: SROSourceFile) -> RUOSourceFile:
    return RUOSourceFile(
        filename=sf.filename,
        sha256=sf.sha256,
        page_count=sf.page_count,
        has_text_layer=sf.has_text_layer,
        is_scanned=sf.is_scanned,
        size_bytes=sf.size_bytes,
    )


def _convert_meta(sro: StructuredResearchObject) -> RUOMeta:
    now = datetime.now(timezone.utc)
    return RUOMeta(
        ruo_id=_make_ruo_id(sro.meta.sro_id),
        sro_id=sro.meta.sro_id,
        schema_version=RUO_SCHEMA_VERSION,
        created_at=now,
        updated_at=now,
        pipeline_version=sro.meta.pipeline_version,
        source_file=_convert_source_file(sro.meta.source_file),
        extraction_route=sro.meta.extraction_route,
        document_type=sro.header.document_type,
        language=sro.header.language or "en",
        processing_time_ms=sro.meta.processing_time_ms,
        pipeline_stages=[StageStatus.SUCCESS],
    )


# ---------------------------------------------------------------------------
# Header & Authors
# ---------------------------------------------------------------------------


def _convert_author(a: SROAuthor) -> RUOAuthor:
    return RUOAuthor(
        full_name=a.full_name,
        given_name=a.given_name,
        surname=a.surname,
        affiliations=list(a.affiliations),
        email=a.email,
        orcid=a.orcid,
        is_corresponding=a.is_corresponding,
    )


def _convert_header(sro: StructuredResearchObject) -> RUOHeader:
    authors = [_convert_author(a) for a in sro.header.authors]
    header_conf = round(
        (sro.header.title_confidence + sro.header.authors_confidence) / 2.0, 4
    )
    return RUOHeader(
        title=sro.header.title,
        authors=authors,
        document_type=sro.header.document_type,
        doi=sro.header.doi,
        arxiv_id=sro.header.arxiv_id,
        pmid=sro.header.pmid,
        publication_date=sro.header.publication_date,
        venue=sro.header.venue,
        venue_type=sro.header.venue_type,
        volume=sro.header.volume,
        issue=sro.header.issue,
        pages=sro.header.pages,
        keywords=list(sro.header.keywords),
        confidence=_default_confidence(header_conf, "header"),
    )


# ---------------------------------------------------------------------------
# Abstract
# ---------------------------------------------------------------------------


def _convert_abstract(
    sro_abs: SROAbstract | None,
) -> RUOAbstract | None:
    if sro_abs is None:
        return None
    structured = None
    if sro_abs.structured is not None:
        structured = RUOStructuredAbstract(
            background=sro_abs.structured.background,
            objective=sro_abs.structured.objective,
            methods=sro_abs.structured.methods,
            results=sro_abs.structured.results,
            conclusion=sro_abs.structured.conclusion,
        )
    return RUOAbstract(
        raw_text=sro_abs.raw_text,
        is_structured=sro_abs.is_structured,
        structured=structured,
        confidence=_default_confidence(sro_abs.confidence, "abstract"),
    )


# ---------------------------------------------------------------------------
# Body: Sections, Chunks, Tables, Figures
# ---------------------------------------------------------------------------


def _convert_section(s: SROSection) -> RUOSection:
    return RUOSection(
        section_id=s.section_id,
        parent_section_id=s.parent_section_id,
        level=s.level,
        position=s.position,
        original_header=s.original_header,
        canonical_label=s.canonical_label,
        label_confidence=s.label_confidence,
        page_start=s.page_start,
        page_end=s.page_end,
        content=s.content,
        extraction_method=ExtractionMethod.GROBID,
    )


def _convert_chunk(
    c: SROChunk,
    entity_ids: list[str] | None = None,
    claim_ids: list[str] | None = None,
) -> RUOChunk:
    return RUOChunk(
        chunk_id=c.chunk_id,
        text=c.text,
        word_count=c.word_count,
        section_id=c.section_id,
        canonical_label=c.canonical_label,
        page_start=c.page_start,
        page_end=c.page_end,
        paragraph_index=c.paragraph_index,
        reading_order=c.reading_order,
        extraction_method=c.extraction_method,
        extraction_confidence=c.extraction_confidence,
        entity_ids=list(entity_ids or c.entity_ids),
        claim_ids=list(claim_ids or c.claim_ids),
    )


def _convert_table(t: SROTable) -> RUOTable:
    return RUOTable(
        table_id=t.table_id,
        caption=t.caption,
        section_id=t.section_id,
        page=t.page,
        raw_content=t.raw_content,
        confidence=t.extraction_confidence,
    )


def _convert_figure(f: SROFigure) -> RUOFigure:
    return RUOFigure(
        figure_id=f.figure_id,
        caption=f.caption,
        section_id=f.section_id,
        page=f.page,
        image_path=f.image_path,
    )


def _convert_body(sro: StructuredResearchObject) -> RUOBody:
    return RUOBody(
        sections=[_convert_section(s) for s in sro.body.sections],
        chunks=[_convert_chunk(c) for c in sro.body.chunks],
        tables=[_convert_table(t) for t in sro.body.tables],
        figures=[_convert_figure(f) for f in sro.body.figures],
    )


# ---------------------------------------------------------------------------
# References & Citations
# ---------------------------------------------------------------------------


def _convert_reference(r: SROReference) -> RUOReference:
    return RUOReference(
        ref_id=r.ref_id,
        raw_text=r.raw_text,
        resolution_status=r.resolution_status,
        resolution_source=r.resolution_source,
        ref_confidence=r.ref_confidence,
        title=r.title,
        authors=list(r.authors),
        year=r.year,
        venue=r.venue,
        doi=r.doi,
        url=r.url,
    )


def _convert_citation(
    c: SROCitation,
    evidence_by_chunk: dict[str, list[str]] | None = None,
) -> RUOCitation:
    intent_evidence_ids: list[str] = []
    if c.citation_intent is not None and evidence_by_chunk is not None:
        intent_evidence_ids = evidence_by_chunk.get(c.chunk_id, [])
    return RUOCitation(
        citation_id=c.citation_id,
        ref_id=c.ref_id,
        chunk_id=c.chunk_id,
        section_id=c.section_id,
        context_sentence=c.context_sentence,
        page=c.page,
        citation_intent=c.citation_intent,
        intent_confidence=c.intent_confidence,
        intent_evidence_ids=intent_evidence_ids,
    )


# ---------------------------------------------------------------------------
# Entities & Claims
# ---------------------------------------------------------------------------


def _convert_entity(e: SROEntity) -> RUOEntity:
    return RUOEntity(
        entity_id=e.entity_id,
        text=e.text,
        label=e.label,
        chunk_id=e.chunk_id,
        sentence=e.sentence,
        confidence=e.confidence,
        source=e.source,
    )


def _convert_claim(
    c: SROCandidateClaim,
    evidence_chain_id: str | None = None,
) -> RUOClaim:
    return RUOClaim(
        claim_id=c.claim_id,
        sentence=c.sentence,
        chunk_id=c.chunk_id,
        section_id=c.section_id,
        canonical_label=c.canonical_label,
        claim_type=c.claim_type,
        matched_patterns=list(c.matched_patterns),
        confidence=c.confidence,
        page=c.page,
        evidence_chain_id=evidence_chain_id or f"ec_{c.claim_id}",
    )


# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------


def _build_field_components(sro: StructuredResearchObject) -> list[ComponentConfidence]:
    components: list[ComponentConfidence] = []
    fs = sro.quality.field_scores
    for name, val in [
        ("title", fs.title),
        ("authors", fs.authors),
        ("abstract", fs.abstract),
        ("sections", fs.sections),
        ("references", fs.references),
        ("citations", fs.citations),
        ("entities", fs.entities),
        ("claims", fs.claims),
    ]:
        components.append(_default_confidence(val, name))
    return components


def _build_validation_report(sro: StructuredResearchObject) -> ValidationReport:
    results: list[ValidationResult] = []
    for err in sro.quality.validation_errors:
        results.append(ValidationResult(
            rule_id="sro_error", passed=False,
            severity=ValidationSeverity.ERROR, message=err,
        ))
    for warn in sro.quality.validation_warnings:
        results.append(ValidationResult(
            rule_id="sro_warning", passed=True,
            severity=ValidationSeverity.WARNING, message=warn,
        ))
    return ValidationReport(results=results)


def _convert_quality(
    sro: StructuredResearchObject,
    evidence_coverage: EvidenceCoverage | None = None,
) -> RUOQuality:
    field_comps = _build_field_components(sro)
    comp_weights = {c.component: 1.0 / max(len(field_comps), 1) for c in field_comps}
    overall = round(
        sum(c.score * comp_weights[c.component] for c in field_comps), 4
    ) if field_comps else sro.quality.overall_confidence
    confidence = ConfidenceBreakdown(
        components=field_comps,
        overall=overall,
        component_weights=comp_weights,
    )
    validation = _build_validation_report(sro)
    return RUOQuality(
        confidence=confidence,
        evidence_coverage=evidence_coverage or EvidenceCoverage(),
        validation=validation,
        pipeline_log=list(sro.quality.pipeline_log),
        llm_calls=list(sro.quality.llm_calls),
        requires_manual_review=sro.quality.requires_manual_review,
        manual_review_reasons=list(sro.quality.manual_review_reasons),
        overall_confidence=overall,
    )


# ---------------------------------------------------------------------------
# Evidence Report
# ---------------------------------------------------------------------------


def _build_evidence_report(
    document: RUODocument,
    chains: list[EvidenceChain],
) -> RUOEvidenceReport | None:
    if not chains:
        return None
    supporting = list(set(
        cid for chain in chains
        for cid in chain.supporting_document_ids
    ))
    contradicting: list[str] = []
    confs = [c.aggregate_confidence for c in chains if c.aggregate_confidence > 0]
    agg_conf = round(sum(confs) / len(confs), 4) if confs else 0.0
    has_contradiction = any(
        cid for chain in chains
        for cid in chain.supporting_document_ids
    )
    return RUOEvidenceReport(
        report_id=f"report_{document.meta.ruo_id}",
        target_id=document.meta.ruo_id,
        target_type="document",
        target_text=document.header.title,
        evidence_chains=list(chains),
        supporting_documents=supporting,
        contradicting_documents=contradicting,
        aggregate_confidence=agg_conf,
        consensus=ConsensusStatus.CONSISTENT if not contradicting
        else ConsensusStatus.CONTRADICTORY,
        generated_at=datetime.now(timezone.utc),
        generator="sro_to_ruo_converter",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def convert_sro_to_ruo(
    sro: StructuredResearchObject,
    fact_result: FactExtractionResult | None = None,
    triple_result: TripleExtractionResult | None = None,
    evidence_result: EvidenceBuildResult | None = None,
) -> ConversionResult:
    """Convert a StructuredResearchObject plus optional Module 2 enrichments
    into a fully validated RUODocument.

    Parameters
    ----------
    sro:
        The Module 1 extraction output.
    fact_result:
        Pre-extracted facts. If ``None``, facts are extracted internally
        (lazy import).
    triple_result:
        Pre-extracted semantic triples. If ``None``, triples are extracted
        internally.
    evidence_result:
        Pre-built evidence records/chains/provenance. If ``None``, evidence
        is built internally.

    Returns
    -------
    ConversionResult
        The validated RUODocument, optional evidence report, and conversion
        notes.
    """
    notes: list[str] = []

    # --- Lazy extraction if not provided ---
    if fact_result is None:
        from researchmind.understanding.fact_extractor import extract_facts
        fact_result = extract_facts(sro)
        notes.append("Facts extracted internally during conversion")
    if triple_result is None:
        from researchmind.understanding.triple_extractor import extract_triples
        triple_result = extract_triples(sro, fact_result)
        notes.append("Triples extracted internally during conversion")
    if evidence_result is None:
        from researchmind.understanding.evidence_builder import build_evidence
        evidence_result = build_evidence(sro, fact_result, triple_result)
        notes.append("Evidence built internally during conversion")

    # --- Build core RUO document ---
    meta = _convert_meta(sro)
    header = _convert_header(sro)
    abstract = _convert_abstract(sro.abstract)
    body = _convert_body(sro)

    # Build chunk→evidence lookup so citations can reference supporting evidence
    evidence_by_chunk: dict[str, list[str]] = {}
    if evidence_result is not None:
        for ev in evidence_result.evidence_records:
            if ev.location and ev.location.chunk_id:
                evidence_by_chunk.setdefault(ev.location.chunk_id, []).append(ev.evidence_id)

    # --- References & Citations ---
    references = [_convert_reference(r) for r in sro.references]
    citations = [_convert_citation(c, evidence_by_chunk) for c in sro.citations]

    # --- Entities (SRO → RUO) ---
    entities = [_convert_entity(e) for e in sro.entities]

    # --- Claims (SRO → RUO) with evidence chain IDs ---
    claim_chain_map: dict[str, str] = {}
    for chain in evidence_result.evidence_chains:
        if chain.target_type == EvidenceTargetType.CLAIM:
            claim_chain_map[chain.target_id] = chain.target_id
    claims = [
        _convert_claim(c, evidence_chain_id=claim_chain_map.get(c.claim_id))
        for c in sro.candidate_claims
    ]

    # --- Facts as annotations ---
    annotations: list[Annotation] = []
    for i, fact in enumerate(fact_result.facts):
        annotations.append(Annotation(
            annotation_id=f"fact_{fact.fact_id}",
            annotation_type="automated_flag",
            target_id=fact.fact_id,
            target_type="entity",
            field="fact_type",
            suggested_value=fact.fact_type.value,
            author="fact_extractor",
            timestamp=datetime.now(timezone.utc),
            reason=f"Extracted fact type={fact.fact_type.value}",
        ))

    # --- Evidence, Chains, Provenance pass-through ---
    quality = _convert_quality(sro, evidence_result.coverage)
    provenance = list(evidence_result.provenance_records)

    # --- Build Evidence Report ---
    report = _build_evidence_report(
        RUODocument(
            meta=meta, header=header, abstract=abstract, body=body,
            references=references, citations=citations,
            entities=entities, claims=claims,
            triples=list(triple_result.triples),
            quality=quality, provenance=provenance,
            annotations=annotations,
        ),
        evidence_result.evidence_chains,
    )

    # --- Final document ---
    document = RUODocument(
        meta=meta,
        provenance=provenance,
        header=header,
        abstract=abstract,
        body=body,
        references=references,
        citations=citations,
        entities=entities,
        claims=claims,
        triples=list(triple_result.triples),
        quality=quality,
        annotations=annotations,
        schema_version=RUO_SCHEMA_VERSION,
        lineage=[sro.meta.sro_id],
    )

    logger.info(
        "SRO→RUO conversion complete: %d entities, %d claims, "
        "%d triples, %d evidence records, %d chains",
        len(entities), len(claims),
        len(triple_result.triples),
        len(evidence_result.evidence_records),
        len(evidence_result.evidence_chains),
    )

    return ConversionResult(
        document=document,
        report=report,
        conversion_notes=notes,
    )
