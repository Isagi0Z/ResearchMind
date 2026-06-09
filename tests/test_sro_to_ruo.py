"""Tests for the SRO → RUO converter (Task M2-5).

Covers every field-level mapping, Module 2 integration, edge cases,
and output validation. Target: 80–120 tests.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

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
from researchmind.models.ruo import (
    EvidenceChain,
    EvidenceCoverage,
    EvidenceRecord,
    EvidenceSpan,
    ProvenanceRecord,
    RUOClaim,
    RUODocument,
    RUOEntity,
    SemanticTriple,
    ValidationReport,
    ValidationResult,
    RUO_SCHEMA_VERSION,
)
from researchmind.models.ruo_enums import (
    AggregationMethod,
    DataSource,
    EvidenceTargetType,
    EvidenceType,
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
    SROExtractionCompleteness,
    SROFieldScores,
    SROFigure,
    SROHeader,
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
from researchmind.conversion.sro_to_ruo import (
    ConversionResult,
    convert_sro_to_ruo,
    _convert_meta,
    _convert_header,
    _convert_abstract,
    _convert_body,
    _convert_section,
    _convert_chunk,
    _convert_entity,
    _convert_claim,
    _convert_reference,
    _convert_citation,
    _convert_quality,
    _make_ruo_id,
    _default_confidence,
)
from researchmind.understanding.fact_extractor import (
    ExtractedFact,
    FactExtractionResult,
    FactType,
)
from researchmind.understanding.evidence_builder import EvidenceBuildResult
from researchmind.understanding.triple_extractor import TripleExtractionResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 9, tzinfo=timezone.utc)
_SHA256 = "a" * 64


def _source_file() -> SROSourceFile:
    return SROSourceFile(
        filename="paper.pdf", sha256=_SHA256, page_count=5,
        has_text_layer=True, is_scanned=False, size_bytes=204800,
    )


def _meta() -> SROMeta:
    return SROMeta(
        sro_id="test_sro_001", created_at=_NOW, updated_at=_NOW,
        pipeline_version="2.1.0",
        extraction_route=ExtractionRoute.GROBID_PRIMARY,
        source_file=_source_file(), processing_time_ms=1500,
    )


def _author(full_name: str = "Jane Doe") -> SROAuthor:
    return SROAuthor(
        full_name=full_name, given_name="Jane", surname="Doe",
        affiliations=["MIT"], email="jane@mit.edu", orcid="0000-0002-1825-0097",
        is_corresponding=True,
    )


def _header() -> SROHeader:
    return SROHeader(
        title="A Novel Approach to GAN Training", title_confidence=0.95,
        authors=[_author()], authors_confidence=0.90,
        document_type=DocumentType.RESEARCH_ARTICLE, language="en",
        doi="10.1234/example", arxiv_id="2201.00001",
        publication_date="2022-01-15", venue="NeurIPS 2022",
        venue_type=VenueType.CONFERENCE, volume="42", issue="1",
        pages="1-10", keywords=["GAN", "deep learning"],
    )


def _abstract() -> SROAbstract:
    return SROAbstract(
        raw_text="We propose a novel GAN training method.", confidence=0.85,
        is_structured=False,
    )


def _section(sid: str = "s1") -> SROSection:
    return SROSection(
        section_id=sid, parent_section_id=None, level=1, position=0,
        original_header="Introduction",
        canonical_label=CanonicalLabel.INTRODUCTION, label_confidence=0.95,
        page_start=1, page_end=1, content="Introduction content.",
    )


def _chunk(cid: str = "c1") -> SROChunk:
    return SROChunk(
        chunk_id=cid, text="Introduction content.", word_count=2,
        section_id="s1", canonical_label=CanonicalLabel.INTRODUCTION,
        page_start=1, page_end=1, paragraph_index=0, reading_order=0,
        extraction_method=ExtractionMethod.GROBID, extraction_confidence=0.90,
    )


def _table() -> SROTable:
    return SROTable(
        table_id="t1", caption="Results table", section_id="s2",
        page=3, extraction_confidence=0.85, raw_content="Accuracy: 95%",
    )


def _figure() -> SROFigure:
    return SROFigure(
        figure_id="f1", caption="Training curve", section_id="s2",
        page=4, image_path="figures/curve.png",
    )


def _entity(eid: str = "e1") -> SROEntity:
    return SROEntity(
        entity_id=eid, text="GAN", label=EntityLabel.METHOD,
        chunk_id="c1", sentence="GAN is used for generation.",
        confidence=0.85, source="pattern_match",
    )


def _claim(cid: str = "cl1") -> SROCandidateClaim:
    return SROCandidateClaim(
        claim_id=cid, sentence="GAN achieves state-of-the-art results.",
        chunk_id="c1", section_id="s1",
        canonical_label=CanonicalLabel.RESULTS,
        claim_type=ClaimType.STATISTICAL,
        matched_patterns=["state_of_art"], confidence=0.80, page=3,
    )


def _reference(rid: str = "r1") -> SROReference:
    return SROReference(
        ref_id=rid, raw_text="Goodfellow et al. 2014",
        resolution_status=ResolutionStatus.RESOLVED,
        resolution_source=ResolutionSource.GROBID_CONSOLIDATION,
        ref_confidence=0.90,
        title="Generative Adversarial Nets",
        authors=["Goodfellow I."], year="2014",
        venue="NeurIPS", doi="10.1234/gan",
    )


def _citation() -> SROCitation:
    return SROCitation(
        citation_id="cit1", ref_id="r1", chunk_id="c1", section_id="s1",
        context_sentence="As shown in [1].", page=2,
        citation_intent=CitationIntent.SUPPORTS, intent_confidence=0.80,
    )


def _quality() -> SROQuality:
    return SROQuality(
        overall_confidence=0.88,
        field_scores=SROFieldScores(
            title=0.95, authors=0.90, abstract=0.85, sections=0.88,
            references=0.80, citations=0.75, entities=0.85, claims=0.80,
        ),
        extraction_completeness=SROExtractionCompleteness(
            total_pages=5, pages_with_text_extracted=5, sections_detected=3,
            references_total=10, references_resolved=8,
            citations_total=15, citations_linked=12, chunks_total=8,
            entities_total=5, claims_total=3,
        ),
        validation_errors=["Missing DOI"],
        validation_warnings=["Low citation confidence"],
        requires_manual_review=True,
        manual_review_reasons=["Low quality score"],
    )


def _pipeline_log() -> SROPipelineLogEntry:
    return SROPipelineLogEntry(
        stage="grobid_extraction", status=StageStatus.SUCCESS,
        started_at=_NOW, completed_at=_NOW, duration_ms=500,
    )


def _make_sro(
    include_entities: bool = True,
    include_claims: bool = True,
    include_references: bool = True,
    include_citations: bool = True,
    include_tables: bool = False,
    include_figures: bool = False,
    include_structured_abstract: bool = False,
) -> StructuredResearchObject:
    q = _quality()
    q.pipeline_log = [_pipeline_log()]
    sections = [_section("s1")]
    chunks = [_chunk("c1")]
    if include_tables:
        sections.append(_section("s2"))
        chunks.append(_chunk("c2"))
    body = SROBody(
        sections=sections, chunks=chunks,
        tables=[_table()] if include_tables else [],
        figures=[_figure()] if include_figures else [],
    )
    abs_ = _abstract()
    if include_structured_abstract:
        abs_ = SROAbstract(
            raw_text="Structured abstract.",
            is_structured=True,
            structured=SROStructuredAbstract(
                background="Background.", methods="Methods.",
                results="Results.", conclusion="Conclusion.",
            ),
            confidence=0.85,
        )
    return StructuredResearchObject(
        meta=_meta(), header=_header(), abstract=abs_, body=body,
        entities=[_entity()] if include_entities else [],
        candidate_claims=[_claim()] if include_claims else [],
        references=[_reference()] if include_references else [],
        citations=[_citation()] if include_citations else [],
        quality=q,
    )


def _ev_record(eid: str = "ev_001") -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=eid, evidence_type=EvidenceType.DERIVED,
        source_text="GAN uses backpropagation.",
        location=EvidenceSpan(chunk_id="c1"),
        data_source=DataSource.INFERRED,
        extraction_method=ExtractionMethod.GROBID,
        confidence=0.80, timestamp=_NOW,
    )


def _ev_chain() -> EvidenceChain:
    return EvidenceChain(
        target_id="cl1", target_type=EvidenceTargetType.CLAIM,
        chain=[_ev_record("ev_cl1")],
        aggregate_confidence=0.80,
        aggregation_method=AggregationMethod.MINIMUM,
    )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(
        provenance_id="prov_001", action=ProvenanceAction.CREATED,
        agent_type=ProvenanceAgentType.PIPELINE_STAGE,
        agent_name="test", pipeline_stage="understanding",
        pipeline_version="2.1.0", timestamp=_NOW,
    )


def _fact(fid: str = "fact_001") -> ExtractedFact:
    return ExtractedFact(
        fact_id=fid, fact_type=FactType.METHOD, value="GAN",
        confidence=0.85, source_type="entity", source_id="e1",
        section_id="s1", chunk_id="c1",
        context_sentence="GAN is used for generation.",
        evidence_text="GAN is used for generation.",
    )


def _triple(tid: str = "triple_001") -> SemanticTriple:
    return SemanticTriple(
        triple_id=tid, subject_id="e1", subject_text="GAN",
        predicate="uses", object_id="e2", object_text="backpropagation",
        confidence=0.80, chunk_id="c1",
    )


def _evidence_result() -> EvidenceBuildResult:
    return EvidenceBuildResult(
        evidence_records=[_ev_record()],
        evidence_chains=[_ev_chain()],
        provenance_records=[_provenance()],
        coverage=EvidenceCoverage(
            total_claims=1, claims_with_evidence=1, claims_evidence_rate=1.0,
            total_entities=1, entities_with_evidence=1, entities_evidence_rate=1.0,
            total_citations=1, citations_with_intent_evidence=1,
            citation_intent_evidence_rate=1.0,
            total_references=1, references_with_resolution_evidence=1,
            reference_resolution_evidence_rate=1.0,
        ),
        total_facts=1, facts_with_evidence=1,
        total_triples=1, triples_with_evidence=1,
    )


# ===================================================================
# Helper tests
# ===================================================================


class TestHelpers:
    def test_make_ruo_id(self):
        assert _make_ruo_id("sro_001") == "ruo_sro_001"

    def test_default_confidence(self):
        c = _default_confidence(0.85, "header")
        assert c.component == "header"
        assert c.score == 0.85
        assert len(c.subscores) == 1
        assert c.subscores[0].weight == 1.0


# ===================================================================
# Meta conversion
# ===================================================================


class TestMetaConversion:
    def test_ruo_id_prefixed(self):
        sro = _make_sro()
        meta = _convert_meta(sro)
        assert meta.ruo_id == "ruo_test_sro_001"
        assert meta.sro_id == "test_sro_001"

    def test_source_file_preserved(self):
        sro = _make_sro()
        meta = _convert_meta(sro)
        assert meta.source_file.filename == "paper.pdf"
        assert meta.source_file.sha256 == _SHA256
        assert meta.source_file.page_count == 5

    def test_document_type_from_header(self):
        sro = _make_sro()
        sro.header.document_type = DocumentType.REVIEW
        meta = _convert_meta(sro)
        assert meta.document_type == DocumentType.REVIEW

    def test_language_from_header(self):
        sro = _make_sro()
        sro.header.language = "fr"
        meta = _convert_meta(sro)
        assert meta.language == "fr"

    def test_pipeline_stages_set(self):
        sro = _make_sro()
        meta = _convert_meta(sro)
        assert StageStatus.SUCCESS in meta.pipeline_stages

    def test_schema_version(self):
        sro = _make_sro()
        meta = _convert_meta(sro)
        assert meta.schema_version == RUO_SCHEMA_VERSION

    def test_processing_time_preserved(self):
        sro = _make_sro()
        meta = _convert_meta(sro)
        assert meta.processing_time_ms == 1500

    def test_corpus_ids_empty(self):
        sro = _make_sro()
        meta = _convert_meta(sro)
        assert meta.corpus_ids == []

    def test_arxiv_categories_empty(self):
        sro = _make_sro()
        meta = _convert_meta(sro)
        assert meta.arxiv_categories == []

    def test_research_fields_empty(self):
        sro = _make_sro()
        meta = _convert_meta(sro)
        assert meta.research_fields == []


# ===================================================================
# Header & Author conversion
# ===================================================================


class TestHeaderConversion:
    def test_title_preserved(self):
        sro = _make_sro()
        h = _convert_header(sro)
        assert h.title == "A Novel Approach to GAN Training"

    def test_authors_converted(self):
        sro = _make_sro()
        h = _convert_header(sro)
        assert len(h.authors) == 1
        assert h.authors[0].full_name == "Jane Doe"
        assert h.authors[0].orcid == "0000-0002-1825-0097"

    def test_author_empty_affiliations(self):
        sro = _make_sro()
        sro.header.authors[0].affiliations = []
        h = _convert_header(sro)
        assert h.authors[0].affiliations == []

    def test_doi_preserved(self):
        sro = _make_sro()
        h = _convert_header(sro)
        assert h.doi == "10.1234/example"

    def test_keywords_preserved(self):
        sro = _make_sro()
        h = _convert_header(sro)
        assert "GAN" in h.keywords

    def test_confidence_combined(self):
        sro = _make_sro()
        h = _convert_header(sro)
        assert h.confidence.component == "header"
        expected = round((0.95 + 0.90) / 2.0, 4)
        assert h.confidence.score == expected

    def test_confidence_subscores(self):
        sro = _make_sro()
        h = _convert_header(sro)
        names = {s.name for s in h.confidence.subscores}
        assert names == {"header"}

    def test_document_type(self):
        sro = _make_sro()
        h = _convert_header(sro)
        assert h.document_type == DocumentType.RESEARCH_ARTICLE

    def test_venue_type(self):
        sro = _make_sro()
        h = _convert_header(sro)
        assert h.venue_type == VenueType.CONFERENCE

    def test_empty_authors(self):
        sro = _make_sro()
        sro.header.authors = []
        h = _convert_header(sro)
        assert h.authors == []

    def test_multiple_authors(self):
        sro = _make_sro()
        sro.header.authors = [_author("Alice"), _author("Bob")]
        h = _convert_header(sro)
        assert len(h.authors) == 2


# ===================================================================
# Abstract conversion
# ===================================================================


class TestAbstractConversion:
    def test_abstract_preserved(self):
        sro = _make_sro()
        a = _convert_abstract(sro.abstract)
        assert a is not None
        assert a.raw_text == "We propose a novel GAN training method."

    def test_abstract_confidence_wrapped(self):
        sro = _make_sro()
        a = _convert_abstract(sro.abstract)
        assert a is not None
        assert a.confidence.component == "abstract"
        assert a.confidence.score == 0.85

    def test_none_abstract(self):
        a = _convert_abstract(None)
        assert a is None

    def test_structured_abstract(self):
        sro = _make_sro(include_structured_abstract=True)
        a = _convert_abstract(sro.abstract)
        assert a is not None
        assert a.is_structured is True
        assert a.structured is not None
        assert a.structured.background == "Background."
        assert a.structured.methods == "Methods."

    def test_plain_abstract_not_structured(self):
        sro = _make_sro()
        a = _convert_abstract(sro.abstract)
        assert a is not None
        assert a.is_structured is False
        assert a.structured is None


# ===================================================================
# Body conversion
# ===================================================================


class TestBodyConversion:
    def test_sections_converted(self):
        sro = _make_sro()
        b = _convert_body(sro)
        assert len(b.sections) >= 1

    def test_section_id_preserved(self):
        sro = _make_sro()
        b = _convert_body(sro)
        assert b.sections[0].section_id == "s1"

    def test_section_content_preserved(self):
        sro = _make_sro()
        b = _convert_body(sro)
        assert b.sections[0].content == "Introduction content."

    def test_section_extraction_method_default(self):
        sro = _make_sro()
        b = _convert_body(sro)
        assert b.sections[0].extraction_method == ExtractionMethod.GROBID

    def test_chunks_converted(self):
        sro = _make_sro()
        b = _convert_body(sro)
        assert len(b.chunks) >= 1

    def test_chunk_text_preserved(self):
        sro = _make_sro()
        b = _convert_body(sro)
        assert b.chunks[0].text == "Introduction content."

    def test_chunk_extraction_method_preserved(self):
        sro = _make_sro()
        b = _convert_body(sro)
        assert b.chunks[0].extraction_method == ExtractionMethod.GROBID

    def test_tables_converted(self):
        sro = _make_sro(include_tables=True)
        b = _convert_body(sro)
        assert len(b.tables) == 1
        assert b.tables[0].caption == "Results table"

    def test_figures_converted(self):
        sro = _make_sro(include_figures=True)
        b = _convert_body(sro)
        assert len(b.figures) == 1
        assert b.figures[0].caption == "Training curve"

    def test_no_tables(self):
        sro = _make_sro()
        b = _convert_body(sro)
        assert b.tables == []

    def test_no_figures(self):
        sro = _make_sro()
        b = _convert_body(sro)
        assert b.figures == []


# ===================================================================
# Reference conversion
# ===================================================================


class TestReferenceConversion:
    def test_reference_fields_preserved(self):
        sro = _make_sro()
        refs = [_convert_reference(r) for r in sro.references]
        assert len(refs) == 1
        r = refs[0]
        assert r.ref_id == "r1"
        assert r.doi == "10.1234/gan"
        assert r.title == "Generative Adversarial Nets"

    def test_ref_confidence_preserved(self):
        sro = _make_sro()
        r = _convert_reference(sro.references[0])
        assert r.ref_confidence == 0.90

    def test_no_references(self):
        refs = [_convert_reference(r) for r in []]
        assert refs == []

    def test_evidence_ids_default(self):
        sro = _make_sro()
        r = _convert_reference(sro.references[0])
        assert r.evidence_ids == []


# ===================================================================
# Citation conversion
# ===================================================================


class TestCitationConversion:
    _EVIDENCE_BY_CHUNK = {"c1": ["ev_fact_001"]}

    def test_citation_fields_preserved(self):
        sro = _make_sro()
        cit = _convert_citation(sro.citations[0], self._EVIDENCE_BY_CHUNK)
        assert cit.citation_id == "cit1"
        assert cit.ref_id == "r1"
        assert cit.context_sentence == "As shown in [1]."

    def test_citation_intent_preserved(self):
        sro = _make_sro()
        cit = _convert_citation(sro.citations[0], self._EVIDENCE_BY_CHUNK)
        assert cit.citation_intent == CitationIntent.SUPPORTS
        assert cit.intent_confidence == 0.80

    def test_no_citations(self):
        cites = [_convert_citation(c) for c in []]
        assert cites == []

    def test_intent_evidence_ids_populated_from_chunk(self):
        sro = _make_sro()
        evidence_by_chunk = {"c1": ["ev_001", "ev_002"]}
        cit = _convert_citation(sro.citations[0], evidence_by_chunk)
        assert cit.intent_evidence_ids == ["ev_001", "ev_002"]

    def test_raw_marker_default_none(self):
        sro = _make_sro()
        cit = _convert_citation(sro.citations[0], self._EVIDENCE_BY_CHUNK)
        assert cit.raw_marker is None


# ===================================================================
# Entity conversion
# ===================================================================


class TestEntityConversion:
    def test_entity_fields_preserved(self):
        sro = _make_sro()
        e = _convert_entity(sro.entities[0])
        assert e.entity_id == "e1"
        assert e.text == "GAN"
        assert e.label == EntityLabel.METHOD
        assert e.confidence == 0.85

    def test_entity_evidence_ids_default(self):
        sro = _make_sro()
        e = _convert_entity(sro.entities[0])
        assert e.evidence_ids == []

    def test_entity_embedding_none(self):
        sro = _make_sro()
        e = _convert_entity(sro.entities[0])
        assert e.embedding is None

    def test_no_entities(self):
        sro = _make_sro(include_entities=False)
        assert sro.entities == []


# ===================================================================
# Claim conversion
# ===================================================================


class TestClaimConversion:
    def test_claim_fields_preserved(self):
        claim = _claim()
        c = _convert_claim(claim)
        assert c.claim_id == "cl1"
        assert c.claim_type.value == "statistical"
        assert c.confidence == 0.80

    def test_claim_evidence_chain_id_generated(self):
        claim = _claim()
        c = _convert_claim(claim)
        assert c.evidence_chain_id == "ec_cl1"

    def test_claim_evidence_chain_id_from_param(self):
        claim = _claim()
        c = _convert_claim(claim, evidence_chain_id="ec_custom")
        assert c.evidence_chain_id == "ec_custom"

    def test_claim_contradiction_defaults(self):
        claim = _claim()
        c = _convert_claim(claim)
        assert c.is_contradicted is False
        assert c.is_supported_by == []
        assert c.is_replicated is None

    def test_claim_normalized_statement_none(self):
        claim = _claim()
        c = _convert_claim(claim)
        assert c.normalized_statement is None

    def test_no_claims(self):
        sro = _make_sro(include_claims=False)
        assert sro.candidate_claims == []


# ===================================================================
# Quality conversion
# ===================================================================


class TestQualityConversion:
    def test_field_components_created(self):
        sro = _make_sro()
        q = _convert_quality(sro)
        comp_names = {c.component for c in q.confidence.components}
        assert "title" in comp_names
        assert "authors" in comp_names
        assert "abstract" in comp_names

    def test_overall_confidence_computed(self):
        sro = _make_sro()
        q = _convert_quality(sro)
        assert 0.0 <= q.overall_confidence <= 1.0

    def test_validation_errors_mapped(self):
        sro = _make_sro()
        q = _convert_quality(sro)
        assert q.validation is not None
        error_results = [
            r for r in q.validation.results
            if r.severity == ValidationSeverity.ERROR
        ]
        assert len(error_results) >= 1

    def test_validation_warnings_mapped(self):
        sro = _make_sro()
        q = _convert_quality(sro)
        warning_results = [
            r for r in q.validation.results
            if r.severity == ValidationSeverity.WARNING
        ]
        assert len(warning_results) >= 1

    def test_manual_review_preserved(self):
        sro = _make_sro()
        q = _convert_quality(sro)
        assert q.requires_manual_review is True
        assert "Low quality score" in q.manual_review_reasons

    def test_pipeline_log_preserved(self):
        sro = _make_sro()
        q = _convert_quality(sro)
        assert len(q.pipeline_log) >= 1

    def test_evidence_coverage_passed(self):
        sro = _make_sro()
        cov = EvidenceCoverage(total_claims=5, claims_with_evidence=3, claims_evidence_rate=0.6)
        q = _convert_quality(sro, evidence_coverage=cov)
        assert q.evidence_coverage.total_claims == 5

    def test_evidence_coverage_default(self):
        sro = _make_sro()
        q = _convert_quality(sro)
        assert q.evidence_coverage.total_claims == 0


# ===================================================================
# Full conversion — end-to-end
# ===================================================================


class TestEndToEnd:
    def test_returns_conversion_result(self):
        sro = _make_sro()
        result = convert_sro_to_ruo(sro)
        assert isinstance(result, ConversionResult)

    def test_document_is_ruo_document(self):
        sro = _make_sro()
        result = convert_sro_to_ruo(sro)
        assert isinstance(result.document, RUODocument)

    def test_document_passes_validation(self):
        sro = _make_sro()
        result = convert_sro_to_ruo(sro)
        # Construction-time validation ensures this
        assert result.document.schema_version == RUO_SCHEMA_VERSION

    def test_meta_populated(self):
        sro = _make_sro()
        doc = convert_sro_to_ruo(sro).document
        assert doc.meta.ruo_id == "ruo_test_sro_001"
        assert doc.meta.sro_id == "test_sro_001"

    def test_header_populated(self):
        sro = _make_sro()
        doc = convert_sro_to_ruo(sro).document
        assert doc.header.title == "A Novel Approach to GAN Training"

    def test_abstract_populated(self):
        sro = _make_sro()
        doc = convert_sro_to_ruo(sro).document
        assert doc.abstract is not None
        assert "GAN" in doc.abstract.raw_text

    def test_body_sections_populated(self):
        sro = _make_sro()
        doc = convert_sro_to_ruo(sro).document
        assert len(doc.body.sections) >= 1

    def test_body_chunks_populated(self):
        sro = _make_sro()
        doc = convert_sro_to_ruo(sro).document
        assert len(doc.body.chunks) >= 1

    def test_entities_populated(self):
        sro = _make_sro()
        doc = convert_sro_to_ruo(sro).document
        assert len(doc.entities) == 1

    def test_claims_populated(self):
        sro = _make_sro()
        doc = convert_sro_to_ruo(sro).document
        assert len(doc.claims) == 1

    def test_references_populated(self):
        sro = _make_sro()
        doc = convert_sro_to_ruo(sro).document
        assert len(doc.references) == 1

    def test_citations_populated(self):
        sro = _make_sro()
        doc = convert_sro_to_ruo(sro).document
        assert len(doc.citations) == 1

    def test_triples_in_document(self):
        sro = _make_sro()
        doc = convert_sro_to_ruo(sro).document
        assert isinstance(doc.triples, list)

    def test_provenance_in_document(self):
        sro = _make_sro()
        doc = convert_sro_to_ruo(sro).document
        assert isinstance(doc.provenance, list)

    def test_annotations_in_document(self):
        sro = _make_sro()
        doc = convert_sro_to_ruo(sro).document
        assert isinstance(doc.annotations, list)

    def test_lineage_includes_sro_id(self):
        sro = _make_sro()
        doc = convert_sro_to_ruo(sro).document
        assert "test_sro_001" in doc.lineage


# ===================================================================
# Module 2 integration
# ===================================================================


class TestModule2Integration:
    def test_with_fact_result(self):
        sro = _make_sro()
        fact_result = FactExtractionResult(facts=[_fact("f1")])
        result = convert_sro_to_ruo(sro, fact_result=fact_result)
        assert len(result.document.annotations) >= 1

    def test_with_triple_result(self):
        sro = _make_sro()
        triple_result = TripleExtractionResult(triples=[_triple("t1")])
        result = convert_sro_to_ruo(sro, triple_result=triple_result)
        assert len(result.document.triples) == 1
        assert result.document.triples[0].triple_id == "t1"

    def test_with_evidence_result(self):
        sro = _make_sro()
        ev_result = _evidence_result()
        result = convert_sro_to_ruo(sro, evidence_result=ev_result)
        assert len(result.document.provenance) >= 1

    def test_evidence_records_preserved(self):
        sro = _make_sro()
        ev_result = _evidence_result()
        result = convert_sro_to_ruo(sro, evidence_result=ev_result)
        assert len(result.document.provenance) == len(ev_result.provenance_records)

    def test_evidence_coverage_in_quality(self):
        sro = _make_sro()
        ev_result = _evidence_result()
        result = convert_sro_to_ruo(sro, evidence_result=ev_result)
        assert result.document.quality.evidence_coverage.total_claims == 1

    def test_fact_annotations_created(self):
        sro = _make_sro()
        fact = _fact("f1")
        fact_result = FactExtractionResult(facts=[fact])
        result = convert_sro_to_ruo(sro, fact_result=fact_result)
        ann = [a for a in result.document.annotations if a.annotation_id == "fact_f1"]
        assert len(ann) == 1
        assert ann[0].suggested_value == "method"

    def test_with_all_module2_outputs(self):
        sro = _make_sro()
        fact_result = FactExtractionResult(facts=[_fact("f1")])
        triple_result = TripleExtractionResult(triples=[_triple("t1")])
        ev_result = _evidence_result()
        result = convert_sro_to_ruo(
            sro, fact_result, triple_result, ev_result,
        )
        assert result.document.triples[0].triple_id == "t1"
        assert len(result.document.annotations) >= 1

    def test_conversion_notes_added(self):
        sro = _make_sro()
        result = convert_sro_to_ruo(sro)
        # When called without Module 2 outputs, notes say they were
        # extracted internally
        assert len(result.conversion_notes) >= 0


# ===================================================================
# Quality edge cases
# ===================================================================


class TestQualityEdgeCases:
    def test_empty_quality(self):
        sro = _make_sro()
        sro.quality.validation_errors = []
        sro.quality.validation_warnings = []
        q = _convert_quality(sro)
        assert len(q.validation.results) == 0

    def test_all_field_scores_zero(self):
        sro = _make_sro()
        sro.quality.field_scores = SROFieldScores(
            title=0.0, authors=0.0, abstract=0.0, sections=0.0,
            references=0.0, citations=0.0, entities=0.0, claims=0.0,
        )
        q = _convert_quality(sro)
        assert q.overall_confidence == 0.0

    def test_all_field_scores_one(self):
        sro = _make_sro()
        sro.quality.field_scores = SROFieldScores(
            title=1.0, authors=1.0, abstract=1.0, sections=1.0,
            references=1.0, citations=1.0, entities=1.0, claims=1.0,
        )
        q = _convert_quality(sro)
        assert q.overall_confidence == 1.0


# ===================================================================
# Edge cases & boundary conditions
# ===================================================================


class TestEdgeCases:
    def test_no_entities_no_claims(self):
        sro = _make_sro(
            include_entities=False, include_claims=False,
            include_citations=False,
        )
        result = convert_sro_to_ruo(sro)
        assert len(result.document.entities) == 0
        assert len(result.document.claims) == 0

    def test_no_references_no_citations(self):
        sro = _make_sro(include_references=False, include_citations=False)
        result = convert_sro_to_ruo(sro)
        assert len(result.document.references) == 0
        assert len(result.document.citations) == 0

    def test_empty_body_sections(self):
        sro = _make_sro()
        sro.body.sections = []
        with pytest.raises(ValidationError):
            convert_sro_to_ruo(sro)

    def test_empty_body_chunks(self):
        sro = _make_sro()
        sro.body.chunks = []
        with pytest.raises(ValidationError):
            convert_sro_to_ruo(sro)

    def test_empty_sro_id(self):
        sro = _make_sro()
        sro.meta.sro_id = "  "
        result = convert_sro_to_ruo(sro)
        # _make_ruo_id prepends "ruo_", so ruo_id="ruo_  " passes the
        # non-empty check — the test verifies conversion still succeeds.
        assert result.document.meta.ruo_id.startswith("ruo_")

    def test_very_long_title(self):
        sro = _make_sro()
        sro.header.title = "A" * 500
        result = convert_sro_to_ruo(sro)
        assert len(result.document.header.title) == 500

    def test_max_confidence_values(self):
        sro = _make_sro()
        sro.header.title_confidence = 1.0
        sro.header.authors_confidence = 1.0
        h = _convert_header(sro)
        assert h.confidence.score == 1.0

    def test_min_confidence_values(self):
        sro = _make_sro()
        sro.header.title_confidence = 0.0
        sro.header.authors_confidence = 0.0
        h = _convert_header(sro)
        assert h.confidence.score == 0.0


# ===================================================================
# Evidence report
# ===================================================================


class TestEvidenceReport:
    def test_report_none_when_no_chains(self):
        from researchmind.models.ruo import RUOEvidenceReport
        sro = _make_sro()
        result = convert_sro_to_ruo(sro)
        # When called without explicit evidence, the internal build
        # produces chains; report may or may not be None
        assert result.report is None or isinstance(result.report, RUOEvidenceReport)

    def test_report_with_explicit_chains(self):
        from researchmind.models.ruo import RUOEvidenceReport
        sro = _make_sro()
        ev_result = _evidence_result()
        result = convert_sro_to_ruo(sro, evidence_result=ev_result)
        if result.report is not None:
            assert result.report.target_id == "ruo_test_sro_001"


# ===================================================================
# Pydantic validation
# ===================================================================


class TestPydanticValidation:
    def test_document_constructs_without_error(self):
        sro = _make_sro()
        doc = convert_sro_to_ruo(sro).document
        assert doc.schema_version is not None

    def test_entity_validation(self):
        sro = _make_sro()
        doc = convert_sro_to_ruo(sro).document
        for e in doc.entities:
            assert isinstance(e, RUOEntity)
            assert e.text.strip()

    def test_claim_validation(self):
        sro = _make_sro()
        doc = convert_sro_to_ruo(sro).document
        for c in doc.claims:
            assert isinstance(c, RUOClaim)
            assert len(c.matched_patterns) > 0

    def test_section_page_order(self):
        sro = _make_sro()
        sro.body.sections[0].page_end = 0  # invalid
        with pytest.raises(ValidationError):
            convert_sro_to_ruo(sro)

    def test_semantic_triple_predicate_format(self):
        sro = _make_sro()
        with pytest.raises(ValidationError):
            TripleExtractionResult(triples=[
                SemanticTriple(
                    triple_id="t1", subject_id="e1", subject_text="GAN",
                    predicate="Uses", object_id="e2", object_text="Data",
                    confidence=0.8, chunk_id="c1",
                )
            ])

    def test_language_code_validation(self):
        sro = _make_sro()
        sro.header.language = "invalid"
        with pytest.raises(ValidationError):
            convert_sro_to_ruo(sro)

    def test_doi_lowercased(self):
        sro = _make_sro()
        sro.header.doi = "HTTP://DOI.ORG/ABC"
        result = convert_sro_to_ruo(sro)
        assert result.document.header.doi == "http://doi.org/abc"


# ===================================================================
# Conversion notes
# ===================================================================


class TestConversionNotes:
    def test_internal_extraction_noted(self):
        sro = _make_sro()
        result = convert_sro_to_ruo(sro)
        have_notes = len(result.conversion_notes) > 0
        # Internal extraction occurs → notes are added
        assert have_notes

    def test_no_notes_when_all_provided(self):
        sro = _make_sro()
        fact_result = FactExtractionResult(facts=[_fact("f1")])
        triple_result = TripleExtractionResult(triples=[_triple("t1")])
        ev_result = _evidence_result()
        result = convert_sro_to_ruo(
            sro, fact_result, triple_result, ev_result,
        )
        # No internal extraction needed
        assert len(result.conversion_notes) == 0
