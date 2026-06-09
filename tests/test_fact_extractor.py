"""Tests for the fact extractor (Task M2-2).

Covers five extraction strategies, model validation, deduplication,
priority resolution, edge cases, and integration — ≥40 tests.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from researchmind.models.enums import (
    CanonicalLabel,
    ClaimType,
    EntityLabel,
    ExtractionMethod,
    ExtractionRoute,
    ResolutionStatus,
)
from researchmind.models.sro import (
    SROAbstract,
    SROBody,
    SROCandidateClaim,
    SROChunk,
    SROEntity,
    SROExtractionCompleteness,
    SROFieldScores,
    SROHeader,
    SROMeta,
    SROQuality,
    SROReference,
    SROSection,
    SROSourceFile,
    StructuredResearchObject,
)
from researchmind.understanding.fact_extractor import (
    FactExtractionResult,
    FactType,
    ExtractedFact,
    extract_facts,
    _FACT_PRIORITY_INDEX,
    _MIN_CONFIDENCE,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 9, tzinfo=timezone.utc)
_SHA256 = "a" * 64


def _meta() -> SROMeta:
    return SROMeta(
        sro_id="test_sro",
        created_at=_NOW,
        updated_at=_NOW,
        pipeline_version="1.0.0",
        extraction_route=ExtractionRoute.GROBID_PRIMARY,
        source_file=SROSourceFile(
            filename="test.pdf",
            sha256=_SHA256,
            page_count=1,
            has_text_layer=True,
            is_scanned=False,
        ),
    )


def _header() -> SROHeader:
    return SROHeader(
        title="Test Paper Title",
        title_confidence=0.95,
        authors_confidence=0.90,
    )


def _abstract() -> SROAbstract:
    return SROAbstract(raw_text="Test abstract.", confidence=0.9)


def _quality() -> SROQuality:
    return SROQuality(
        overall_confidence=0.9,
        field_scores=SROFieldScores(),
        extraction_completeness=SROExtractionCompleteness(),
    )


def _make_section(
    section_id: str,
    header: str,
    label: CanonicalLabel,
    confidence: float = 0.9,
    content: str = "Section content with relevant information.",
) -> SROSection:
    return SROSection(
        section_id=section_id,
        level=1,
        position=0,
        original_header=header,
        canonical_label=label,
        label_confidence=confidence,
        page_start=1,
        page_end=1,
        content=content,
    )


def _make_chunk(
    chunk_id: str,
    text: str,
    section_id: str = "sec_001",
    label: CanonicalLabel = CanonicalLabel.METHODOLOGY,
    word_count: int | None = None,
) -> SROChunk:
    return SROChunk(
        chunk_id=chunk_id,
        text=text,
        word_count=word_count or max(len(text.split()), 1),
        section_id=section_id,
        canonical_label=label,
        page_start=1,
        page_end=1,
        paragraph_index=0,
        reading_order=0,
        extraction_method=ExtractionMethod.GROBID,
        extraction_confidence=0.9,
    )


def _make_entity(
    entity_id: str,
    text: str,
    label: EntityLabel,
    confidence: float = 0.6,
    chunk_id: str = "chk_001",
    sentence: str = "Entity in context.",
    source: str = "pattern_match",
) -> SROEntity:
    return SROEntity(
        entity_id=entity_id,
        text=text,
        label=label,
        chunk_id=chunk_id,
        sentence=sentence,
        confidence=confidence,
        source=source,
    )


def _make_claim(
    claim_id: str,
    sentence: str,
    claim_type: ClaimType,
    confidence: float = 0.7,
    section_id: str = "sec_001",
    chunk_id: str = "chk_001",
    canonical_label: CanonicalLabel = CanonicalLabel.RESULTS,
) -> SROCandidateClaim:
    return SROCandidateClaim(
        claim_id=claim_id,
        sentence=sentence,
        chunk_id=chunk_id,
        section_id=section_id,
        canonical_label=canonical_label,
        claim_type=claim_type,
        matched_patterns=["dummy_pattern"],
        confidence=confidence,
        page=1,
    )


def _make_reference(
    ref_id: str,
    title: str | None = None,
    raw_text: str | None = None,
) -> SROReference:
    return SROReference(
        ref_id=ref_id,
        raw_text=raw_text or title or "Some reference.",
        resolution_status=ResolutionStatus.RESOLVED,
        ref_confidence=0.8,
        title=title,
    )


def _make_sro(
    sections: list[SROSection] | None = None,
    chunks: list[SROChunk] | None = None,
    entities: list[SROEntity] | None = None,
    candidate_claims: list[SROCandidateClaim] | None = None,
    references: list[SROReference] | None = None,
) -> StructuredResearchObject:
    if sections is None:
        sections = [_make_section("sec_001", "Methodology", CanonicalLabel.METHODOLOGY)]
    if chunks is None:
        chunks = [_make_chunk("chk_001", "We propose a novel method.")]
    return StructuredResearchObject(
        meta=_meta(),
        header=_header(),
        abstract=_abstract(),
        body=SROBody(sections=sections, chunks=chunks),
        entities=entities or [],
        candidate_claims=candidate_claims or [],
        references=references or [],
        quality=_quality(),
    )


# ===================================================================
# FactType enum
# ===================================================================


class TestFactType:
    def test_all_values_present(self):
        assert len(FactType) == 6

    def test_values_are_correct_strings(self):
        assert FactType.METHOD == "method"
        assert FactType.DATASET == "dataset"
        assert FactType.METRIC == "metric"
        assert FactType.CONTRIBUTION == "contribution"
        assert FactType.LIMITATION == "limitation"
        assert FactType.FUTURE_WORK == "future_work"

    def test_priority_has_all_types(self):
        assert set(_FACT_PRIORITY_INDEX.keys()) == set(FactType)

    def test_priority_order_method_highest(self):
        assert _FACT_PRIORITY_INDEX[FactType.METHOD] < _FACT_PRIORITY_INDEX[FactType.DATASET]
        assert _FACT_PRIORITY_INDEX[FactType.METHOD] < _FACT_PRIORITY_INDEX[FactType.FUTURE_WORK]

    def test_priority_order_future_work_lowest(self):
        assert _FACT_PRIORITY_INDEX[FactType.FUTURE_WORK] > _FACT_PRIORITY_INDEX[FactType.CONTRIBUTION]


# ===================================================================
# ExtractedFact model
# ===================================================================


class TestExtractedFactModel:
    def test_minimal_construction(self):
        fact = ExtractedFact(
            fact_id="fact_001",
            fact_type=FactType.METHOD,
            value="Test method",
            confidence=0.8,
            source_type="entity",
            source_id="ent_001",
        )
        assert fact.fact_id == "fact_001"
        assert fact.section_id is None

    def test_full_construction(self):
        fact = ExtractedFact(
            fact_id="fact_001",
            fact_type=FactType.DATASET,
            value="ImageNet dataset",
            confidence=0.9,
            source_type="pattern",
            source_id="ptn_001",
            section_id="sec_001",
            chunk_id="chk_001",
            context_sentence="We evaluate on ImageNet dataset.",
            evidence_text="ImageNet dataset",
            matched_pattern="dataset_keyword",
        )
        assert fact.context_sentence == "We evaluate on ImageNet dataset."

    def test_rejects_invalid_source_type(self):
        with pytest.raises(ValidationError):
            ExtractedFact(
                fact_id="fact_001",
                fact_type=FactType.METHOD,
                value="Test",
                confidence=0.8,
                source_type="invalid",
                source_id="s1",
            )

    def test_rejects_empty_value(self):
        with pytest.raises(ValidationError):
            ExtractedFact(
                fact_id="fact_001",
                fact_type=FactType.METHOD,
                value="",
                confidence=0.8,
                source_type="entity",
                source_id="s1",
            )

    def test_rejects_confidence_too_high(self):
        with pytest.raises(ValidationError):
            ExtractedFact(
                fact_id="fact_001",
                fact_type=FactType.METHOD,
                value="Test",
                confidence=1.5,
                source_type="entity",
                source_id="s1",
            )

    def test_rejects_confidence_too_low(self):
        with pytest.raises(ValidationError):
            ExtractedFact(
                fact_id="fact_001",
                fact_type=FactType.METHOD,
                value="Test",
                confidence=-0.1,
                source_type="entity",
                source_id="s1",
            )

    def test_all_optional_fields_none(self):
        fact = ExtractedFact(
            fact_id="fact_001",
            fact_type=FactType.LIMITATION,
            value="Some limitation",
            confidence=0.5,
            source_type="claim",
            source_id="clm_001",
        )
        assert fact.section_id is None
        assert fact.chunk_id is None
        assert fact.context_sentence is None
        assert fact.evidence_text is None
        assert fact.matched_pattern is None


# ===================================================================
# FactExtractionResult model
# ===================================================================


class TestFactExtractionResult:
    def test_empty_facts(self):
        result = FactExtractionResult(facts=[])
        assert result.summary == {}
        assert result.by_type(FactType.METHOD) == []
        assert result.deduplicated() == []

    def test_summary_computed_automatically(self):
        facts = [
            ExtractedFact(
                fact_id="f1", fact_type=FactType.METHOD, value="M1",
                confidence=0.8, source_type="entity", source_id="e1",
            ),
            ExtractedFact(
                fact_id="f2", fact_type=FactType.DATASET, value="D1",
                confidence=0.8, source_type="entity", source_id="e2",
            ),
            ExtractedFact(
                fact_id="f3", fact_type=FactType.METHOD, value="M2",
                confidence=0.8, source_type="claim", source_id="c1",
            ),
        ]
        result = FactExtractionResult(facts=facts)
        assert result.summary == {"method": 2, "dataset": 1}

    def test_by_type_filters_correctly(self):
        facts = [
            ExtractedFact(
                fact_id="f1", fact_type=FactType.METHOD, value="M1",
                confidence=0.8, source_type="entity", source_id="e1",
            ),
            ExtractedFact(
                fact_id="f2", fact_type=FactType.DATASET, value="D1",
                confidence=0.8, source_type="entity", source_id="e2",
            ),
        ]
        result = FactExtractionResult(facts=facts)
        methods = result.by_type(FactType.METHOD)
        assert len(methods) == 1
        assert methods[0].fact_id == "f1"

    def test_by_type_no_matches(self):
        facts = [
            ExtractedFact(
                fact_id="f1", fact_type=FactType.METHOD, value="M1",
                confidence=0.8, source_type="entity", source_id="e1",
            ),
        ]
        result = FactExtractionResult(facts=facts)
        assert result.by_type(FactType.DATASET) == []


# ===================================================================
# extract_facts — empty / edge cases
# ===================================================================


class TestExtractFactsEmpty:
    def test_no_mapped_content_returns_empty(self):
        section = _make_section("s1", "Intro", CanonicalLabel.INTRODUCTION)
        neutral = _make_chunk("c1", "This is completely neutral text with no triggers.")
        sro = _make_sro(sections=[section], chunks=[neutral])
        result = extract_facts(sro)
        assert result.facts == []


# ===================================================================
# Strategy 1 — Section-aware extraction
# ===================================================================


class TestSectionExtraction:
    def test_methodology_section(self):
        section = _make_section("s1", "Methodology", CanonicalLabel.METHODOLOGY)
        sro = _make_sro(sections=[section])
        result = extract_facts(sro)
        methods = result.by_type(FactType.METHOD)
        assert len(methods) >= 1
        assert methods[0].source_type == "section"

    def test_limitations_section(self):
        section = _make_section("s1", "Limitations", CanonicalLabel.LIMITATIONS)
        sro = _make_sro(sections=[section])
        result = extract_facts(sro)
        lims = result.by_type(FactType.LIMITATION)
        assert len(lims) >= 1
        assert lims[0].source_type == "section"

    def test_future_work_section(self):
        section = _make_section("s1", "Future Work", CanonicalLabel.FUTURE_WORK)
        sro = _make_sro(sections=[section])
        result = extract_facts(sro)
        fws = result.by_type(FactType.FUTURE_WORK)
        assert len(fws) >= 1
        assert fws[0].source_type == "section"

    def test_conclusion_section(self):
        section = _make_section("s1", "Conclusion", CanonicalLabel.CONCLUSION)
        sro = _make_sro(sections=[section])
        result = extract_facts(sro)
        contribs = result.by_type(FactType.CONTRIBUTION)
        assert len(contribs) >= 1
        assert contribs[0].source_type == "section"

    def test_unmapped_section_skipped(self):
        section = _make_section("s1", "Related Work", CanonicalLabel.RELATED_WORK)
        sro = _make_sro(sections=[section])
        result = extract_facts(sro)
        # No section fact expected for RELATED_WORK
        section_facts = [f for f in result.facts if f.source_type == "section"]
        assert section_facts == []

    def test_confidence_below_threshold_filtered(self):
        section = _make_section(
            "s1", "Methodology", CanonicalLabel.METHODOLOGY,
            confidence=0.4,  # 0.4 * 0.6 = 0.24 < 0.3
        )
        sro = _make_sro(sections=[section])
        result = extract_facts(sro)
        section_facts = [f for f in result.facts if f.source_type == "section"]
        assert section_facts == []

    def test_empty_content_skipped(self):
        section = SROSection(
            section_id="s1",
            level=1,
            position=0,
            original_header="Methodology",
            canonical_label=CanonicalLabel.METHODOLOGY,
            label_confidence=0.9,
            page_start=1,
            page_end=1,
            content="",
        )
        sro = _make_sro(sections=[section])
        result = extract_facts(sro)
        section_facts = [f for f in result.facts if f.source_type == "section"]
        assert section_facts == []

    def test_confidence_computation(self):
        section = _make_section(
            "s1", "Methodology", CanonicalLabel.METHODOLOGY, confidence=0.85,
        )
        sro = _make_sro(sections=[section])
        result = extract_facts(sro)
        section_facts = [f for f in result.facts if f.source_type == "section"]
        assert len(section_facts) == 1
        assert section_facts[0].confidence == pytest.approx(0.85 * 0.6)


# ===================================================================
# Strategy 2 — Entity-aware extraction
# ===================================================================


class TestEntityExtraction:
    def test_method_entity(self):
        sro = _make_sro(entities=[
            _make_entity("e1", "Adam Optimizer", EntityLabel.METHOD),
        ])
        result = extract_facts(sro)
        entity_facts = [f for f in result.facts
                        if f.source_type == "entity"]
        assert len(entity_facts) >= 1
        assert entity_facts[0].value == "Adam Optimizer"

    def test_dataset_entity(self):
        sro = _make_sro(entities=[
            _make_entity("e1", "ImageNet", EntityLabel.DATASET),
        ])
        result = extract_facts(sro)
        datasets = result.by_type(FactType.DATASET)
        assert len(datasets) >= 1

    def test_metric_entity(self):
        sro = _make_sro(entities=[
            _make_entity("e1", "F1-score", EntityLabel.METRIC),
        ])
        result = extract_facts(sro)
        metrics = result.by_type(FactType.METRIC)
        assert len(metrics) >= 1

    def test_tool_entity_maps_to_method(self):
        sro = _make_sro(entities=[
            _make_entity("e1", "PyTorch", EntityLabel.TOOL),
        ])
        result = extract_facts(sro)
        entity_facts = [f for f in result.facts
                        if f.source_type == "entity"]
        assert len(entity_facts) >= 1
        assert entity_facts[0].value == "PyTorch"

    def test_non_relevant_entity_skipped(self):
        sro = _make_sro(entities=[
            _make_entity("e1", "London", EntityLabel.LOCATION),
            _make_entity("e2", "John", EntityLabel.PERSON),
        ])
        result = extract_facts(sro)
        # These entity types don't map to any FactType
        entity_facts = [f for f in result.facts if f.source_type == "entity"]
        assert entity_facts == []

    def test_empty_text_skipped(self):
        sro = _make_sro(entities=[
            _make_entity("e1", "", EntityLabel.METHOD, confidence=0.6),
        ])
        result = extract_facts(sro)
        entity_facts = [f for f in result.facts if f.source_type == "entity"]
        assert entity_facts == []

    def test_entity_confidence_used_directly(self):
        sro = _make_sro(entities=[
            _make_entity("e1", "BERT", EntityLabel.METHOD, confidence=0.75),
        ])
        result = extract_facts(sro)
        entity_facts = [f for f in result.facts if f.source_type == "entity"]
        assert entity_facts[0].confidence == 0.75

    def test_entity_propagates_sentence(self):
        sro = _make_sro(entities=[
            _make_entity(
                "e1", "COCO", EntityLabel.DATASET,
                sentence="We evaluate on the COCO dataset.",
            ),
        ])
        result = extract_facts(sro)
        entity_facts = [f for f in result.facts if f.source_type == "entity"]
        assert entity_facts[0].context_sentence == "We evaluate on the COCO dataset."


# ===================================================================
# Strategy 3 — Claim-aware extraction
# ===================================================================


class TestClaimExtraction:
    def test_methodological_claim(self):
        sro = _make_sro(candidate_claims=[
            _make_claim("c1", "We propose a new method.", ClaimType.METHODOLOGICAL),
        ])
        result = extract_facts(sro)
        methods = result.by_type(FactType.METHOD)
        assert len(methods) >= 1

    def test_comparative_claim_to_contribution(self):
        sro = _make_sro(candidate_claims=[
            _make_claim("c1", "Our model outperforms SOTA.", ClaimType.COMPARATIVE),
        ])
        result = extract_facts(sro)
        contribs = result.by_type(FactType.CONTRIBUTION)
        assert len(contribs) >= 1

    def test_existence_claim_to_contribution(self):
        sro = _make_sro(candidate_claims=[
            _make_claim("c1", "We show that attention works.", ClaimType.EXISTENCE),
        ])
        result = extract_facts(sro)
        contribs = result.by_type(FactType.CONTRIBUTION)
        assert len(contribs) >= 1

    def test_negation_claim_to_limitation(self):
        sro = _make_sro(candidate_claims=[
            _make_claim("c1", "Our method fails on noisy data.", ClaimType.NEGATION),
        ])
        result = extract_facts(sro)
        lims = result.by_type(FactType.LIMITATION)
        assert len(lims) >= 1

    def test_statistical_claim_to_metric(self):
        sro = _make_sro(candidate_claims=[
            _make_claim("c1", "p < 0.05 with effect size.", ClaimType.STATISTICAL),
        ])
        result = extract_facts(sro)
        metrics = result.by_type(FactType.METRIC)
        assert len(metrics) >= 1

    def test_causal_claim_skipped(self):
        sro = _make_sro(candidate_claims=[
            _make_claim("c1", "A causes B.", ClaimType.CAUSAL),
        ])
        result = extract_facts(sro)
        # CAUSAL is not in _CLAIM_TO_FACT
        claim_facts = [f for f in result.facts if f.source_type == "claim"]
        assert claim_facts == []

    def test_confidence_computation(self):
        sro = _make_sro(candidate_claims=[
            _make_claim("c1", "We propose a method.", ClaimType.METHODOLOGICAL,
                        confidence=0.8),
        ])
        result = extract_facts(sro)
        claim_facts = [f for f in result.facts if f.source_type == "claim"]
        assert len(claim_facts) == 1
        assert claim_facts[0].confidence == pytest.approx(0.8 * 0.8)


# ===================================================================
# Strategy 4 — Pattern-based extraction
# ===================================================================


class TestPatternExtraction:
    def test_contribution_pattern_state_of_art(self):
        chunk = _make_chunk("c1", "Our model achieves state-of-the-art results.")
        sro = _make_sro(chunks=[chunk])
        result = extract_facts(sro)
        contribs = result.by_type(FactType.CONTRIBUTION)
        assert len(contribs) >= 1
        pattern_facts = [f for f in contribs if f.source_type == "pattern"]
        assert len(pattern_facts) >= 1

    def test_limitation_pattern(self):
        chunk = _make_chunk("c1", "A key limitation is the computational cost.")
        sro = _make_sro(chunks=[chunk])
        result = extract_facts(sro)
        lims = result.by_type(FactType.LIMITATION)
        pattern_facts = [f for f in lims if f.source_type == "pattern"]
        assert len(pattern_facts) >= 1

    def test_future_work_pattern(self):
        chunk = _make_chunk("c1", "Future work should explore this direction.")
        sro = _make_sro(chunks=[chunk])
        result = extract_facts(sro)
        fws = result.by_type(FactType.FUTURE_WORK)
        pattern_facts = [f for f in fws if f.source_type == "pattern"]
        assert len(pattern_facts) >= 1

    def test_no_pattern_match(self):
        chunk = _make_chunk("c1", "This is completely neutral text with no special patterns visible.")
        sro = _make_sro(chunks=[chunk])
        result = extract_facts(sro)
        pattern_facts = [f for f in result.facts if f.source_type == "pattern"]
        assert pattern_facts == []

    def test_confidence_is_always_0_65(self):
        chunk = _make_chunk("c1", "We outperform the previous state-of-the-art method.")
        sro = _make_sro(chunks=[chunk])
        result = extract_facts(sro)
        pattern_facts = [f for f in result.facts if f.source_type == "pattern"]
        assert all(f.confidence == 0.65 for f in pattern_facts)


# ===================================================================
# Strategy 5 — Reference-aware extraction
# ===================================================================


class TestReferenceExtraction:
    def test_dataset_keyword(self):
        sro = _make_sro(references=[
            _make_reference("r1", title="ImageNet: A Large-Scale Dataset"),
        ])
        result = extract_facts(sro)
        datasets = result.by_type(FactType.DATASET)
        assert len(datasets) >= 1

    def test_method_keyword(self):
        sro = _make_sro(references=[
            _make_reference("r1", title="A Novel Approach to ML"),
        ])
        result = extract_facts(sro)
        methods = result.by_type(FactType.METHOD)
        assert len(methods) >= 1

    def test_survey_keyword_to_contribution(self):
        sro = _make_sro(references=[
            _make_reference("r1", title="A Survey of Deep Learning"),
        ])
        result = extract_facts(sro)
        contribs = result.by_type(FactType.CONTRIBUTION)
        assert len(contribs) >= 1

    def test_metric_keyword(self):
        sro = _make_sro(references=[
            _make_reference("r1", title="Evaluation Metrics for NLP"),
        ])
        result = extract_facts(sro)
        metrics = result.by_type(FactType.METRIC)
        assert len(metrics) >= 1

    def test_limitation_keyword(self):
        sro = _make_sro(references=[
            _make_reference("r1", title="Challenges and Limitations of GANs"),
        ])
        result = extract_facts(sro)
        lims = result.by_type(FactType.LIMITATION)
        assert len(lims) >= 1

    def test_no_matching_keyword_skipped(self):
        sro = _make_sro(references=[
            _make_reference("r1", title="Nothing about datasets or methods here"),
        ])
        result = extract_facts(sro)
        ref_facts = [f for f in result.facts if f.source_type == "reference"]
        assert ref_facts == []

    def test_falls_back_to_raw_text_when_no_title(self):
        sro = _make_sro(references=[
            _make_reference("r1", title=None, raw_text="A novel dataset for vision"),
        ])
        result = extract_facts(sro)
        datasets = result.by_type(FactType.DATASET)
        assert len(datasets) >= 1

    def test_confidence_is_always_0_5(self):
        sro = _make_sro(references=[
            _make_reference("r1", title="A Novel Algorithm for ML"),
        ])
        result = extract_facts(sro)
        ref_facts = [f for f in result.facts if f.source_type == "reference"]
        assert all(f.confidence == 0.5 for f in ref_facts)


# ===================================================================
# Deduplication & priority resolution
# ===================================================================


class TestDeduplication:
    def test_same_value_type_keeps_highest_confidence(self):
        facts = [
            ExtractedFact(
                fact_id="f1", fact_type=FactType.METHOD, value="Adam",
                confidence=0.6, source_type="entity", source_id="e1",
            ),
            ExtractedFact(
                fact_id="f2", fact_type=FactType.METHOD, value="Adam",
                confidence=0.8, source_type="claim", source_id="c1",
            ),
        ]
        result = FactExtractionResult(facts=facts)
        deduped = result.deduplicated()
        assert len(deduped) == 1
        assert deduped[0].confidence == 0.8

    def test_different_values_not_deduplicated(self):
        facts = [
            ExtractedFact(
                fact_id="f1", fact_type=FactType.METHOD, value="Adam",
                confidence=0.8, source_type="entity", source_id="e1",
            ),
            ExtractedFact(
                fact_id="f2", fact_type=FactType.METHOD, value="SGD",
                confidence=0.8, source_type="entity", source_id="e2",
            ),
        ]
        result = FactExtractionResult(facts=facts)
        deduped = result.deduplicated()
        assert len(deduped) == 2

    def test_priority_same_confidence_picks_highest_priority(self):
        facts = [
            ExtractedFact(
                fact_id="f1", fact_type=FactType.METRIC, value="Adam",
                confidence=0.7, source_type="entity", source_id="e1",
            ),
            ExtractedFact(
                fact_id="f2", fact_type=FactType.METHOD, value="Adam",
                confidence=0.7, source_type="entity", source_id="e2",
            ),
        ]
        result = FactExtractionResult(facts=facts)
        deduped = result.deduplicated()
        # Same value "Adam", same confidence 0.7, different types.
        # METHOD has higher priority than METRIC.
        assert len(deduped) == 1
        assert deduped[0].fact_type == FactType.METHOD

    def test_different_confidences_keeps_both(self):
        facts = [
            ExtractedFact(
                fact_id="f1", fact_type=FactType.METHOD, value="Transformer",
                confidence=0.9, source_type="entity", source_id="e1",
            ),
            ExtractedFact(
                fact_id="f2", fact_type=FactType.METRIC, value="Transformer",
                confidence=0.6, source_type="entity", source_id="e2",
            ),
        ]
        result = FactExtractionResult(facts=facts)
        deduped = result.deduplicated()
        assert len(deduped) == 2

    def test_deduplicated_renumbers_ids(self):
        facts = [
            ExtractedFact(
                fact_id="old1", fact_type=FactType.METHOD, value="M1",
                confidence=0.8, source_type="entity", source_id="e1",
            ),
            ExtractedFact(
                fact_id="old2", fact_type=FactType.DATASET, value="D1",
                confidence=0.8, source_type="entity", source_id="e2",
            ),
        ]
        deduped = FactExtractionResult(facts=facts).deduplicated()
        assert all(f.fact_id.startswith("fact_") for f in deduped)
        # Sorted by (fact_type.value, fact_id); "dataset" < "method"
        assert deduped[0].fact_type == FactType.DATASET


# ===================================================================
# Integration — all strategies together
# ===================================================================


class TestIntegration:
    def test_all_strategies_produce_facts(self):
        section = _make_section("s1", "Methodology", CanonicalLabel.METHODOLOGY)
        chunk = _make_chunk("c1", "Our model achieves state-of-the-art performance.")
        entity = _make_entity("e1", "ImageNet", EntityLabel.DATASET)
        claim = _make_claim("cl1", "We propose a new method.", ClaimType.METHODOLOGICAL)
        ref = _make_reference("r1", title="A Survey of Deep Learning Methods")

        sro = _make_sro(
            sections=[section],
            chunks=[chunk],
            entities=[entity],
            candidate_claims=[claim],
            references=[ref],
        )
        result = extract_facts(sro)

        # Should have facts from all five strategies
        source_types = {f.source_type for f in result.facts}
        assert "section" in source_types
        assert "entity" in source_types
        assert "claim" in source_types
        assert "pattern" in source_types
        assert "reference" in source_types

    def test_summary_counts_aggregate_correctly(self):
        section = _make_section("s1", "Methodology", CanonicalLabel.METHODOLOGY)
        chunk = _make_chunk("c1", "We outperform existing methods.")
        entity = _make_entity("e1", "SGD", EntityLabel.METHOD)
        claim = _make_claim("c1", "We propose a novel framework.", ClaimType.METHODOLOGICAL)

        sro = _make_sro(
            sections=[section],
            chunks=[chunk],
            entities=[entity],
            candidate_claims=[claim],
        )
        result = extract_facts(sro)
        # METHOD facts from section, entity, claim (and possibly pattern from "outperform")
        assert result.summary.get("method", 0) >= 2


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    def test_long_section_content_truncated(self):
        long_text = "A" * 1000
        section = _make_section(
            "s1", "Methodology", CanonicalLabel.METHODOLOGY,
            content=long_text,
        )
        sro = _make_sro(sections=[section])
        result = extract_facts(sro)
        section_facts = [f for f in result.facts if f.source_type == "section"]
        assert len(section_facts) == 1
        assert len(section_facts[0].value) == 300

    def test_sentence_finding_valid(self):
        text = "First sentence. Our method is novel. Third sentence."
        chunk = _make_chunk("c1", text)
        sro = _make_sro(chunks=[chunk])
        result = extract_facts(sro)
        # "novel" should trigger CONTRIBUTION pattern
        pattern_facts = [f for f in result.facts if f.source_type == "pattern"]
        if pattern_facts:
            assert "Our method is novel" in pattern_facts[0].value

    def test_multiple_sections_same_type(self):
        sections = [
            _make_section("s1", "Method 1", CanonicalLabel.METHODOLOGY,
                          content="First method."),
            _make_section("s2", "Method 2", CanonicalLabel.METHODOLOGY,
                          content="Second method."),
        ]
        sro = _make_sro(sections=sections)
        result = extract_facts(sro)
        methods = result.by_type(FactType.METHOD)
        assert len(methods) >= 2
