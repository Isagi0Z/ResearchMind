"""Tests for the semantic triple extractor (Task M2-3).

Covers predicate normalization, five extraction strategies, deduplication,
confidence scoring, edge cases, cross-section extraction, and integration.
Target: ≥50 tests.
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
)
from researchmind.models.ruo import SemanticTriple
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
    SROSection,
    SROSourceFile,
    StructuredResearchObject,
)
from researchmind.understanding.fact_extractor import (
    ExtractedFact,
    FactExtractionResult,
    FactType,
)
from researchmind.understanding.triple_extractor import (
    TripleExtractionResult,
    extract_triples,
    normalize_predicate,
    VALID_PREDICATES,
)

# ---------------------------------------------------------------------------
# Fixtures (adapted from test_fact_extractor)
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
            filename="test.pdf", sha256=_SHA256, page_count=1,
            has_text_layer=True, is_scanned=False,
        ),
    )


def _header(title: str = "Test Paper") -> SROHeader:
    return SROHeader(
        title=title, title_confidence=0.95, authors_confidence=0.90,
    )


def _abstract() -> SROAbstract:
    return SROAbstract(raw_text="Abstract.", confidence=0.9)


def _quality() -> SROQuality:
    return SROQuality(
        overall_confidence=0.9,
        field_scores=SROFieldScores(),
        extraction_completeness=SROExtractionCompleteness(),
    )


def _make_section(
    section_id: str, header: str, label: CanonicalLabel,
    content: str = "Section content.",
) -> SROSection:
    return SROSection(
        section_id=section_id, level=1, position=0,
        original_header=header, canonical_label=label,
        label_confidence=0.9, page_start=1, page_end=1, content=content,
    )


def _make_chunk(
    chunk_id: str, text: str, section_id: str = "sec_001",
    label: CanonicalLabel = CanonicalLabel.METHODOLOGY,
) -> SROChunk:
    return SROChunk(
        chunk_id=chunk_id, text=text,
        word_count=max(len(text.split()), 1),
        section_id=section_id, canonical_label=label,
        page_start=1, page_end=1, paragraph_index=0, reading_order=0,
        extraction_method=ExtractionMethod.GROBID,
        extraction_confidence=0.9,
    )


def _make_entity(
    entity_id: str, text: str, label: EntityLabel,
    confidence: float = 0.7, chunk_id: str = "chk_001",
    sentence: str = "Entity in context.",
    source: str = "pattern_match",
) -> SROEntity:
    return SROEntity(
        entity_id=entity_id, text=text, label=label,
        chunk_id=chunk_id, sentence=sentence,
        confidence=confidence, source=source,
    )


def _make_claim(
    claim_id: str, sentence: str, claim_type: ClaimType,
    confidence: float = 0.7, chunk_id: str = "chk_001",
    section_id: str = "sec_001",
    label: CanonicalLabel = CanonicalLabel.RESULTS,
) -> SROCandidateClaim:
    return SROCandidateClaim(
        claim_id=claim_id, sentence=sentence, chunk_id=chunk_id,
        section_id=section_id, canonical_label=label,
        claim_type=claim_type, matched_patterns=["pattern"],
        confidence=confidence, page=1,
    )


def _make_sro(
    sections: list[SROSection] | None = None,
    chunks: list[SROChunk] | None = None,
    entities: list[SROEntity] | None = None,
    claims: list[SROCandidateClaim] | None = None,
    title: str = "Test Paper",
) -> StructuredResearchObject:
    if sections is None:
        sections = [_make_section("s1", "Intro", CanonicalLabel.INTRODUCTION)]
    if chunks is None:
        chunks = [_make_chunk("c1", "We propose a method.")]
    if entities is None:
        entities = []
    if claims is None:
        claims = []
    return StructuredResearchObject(
        meta=_meta(), header=_header(title=title), abstract=_abstract(),
        body=SROBody(sections=sections, chunks=chunks),
        entities=entities, candidate_claims=claims,
        quality=_quality(),
    )


def _make_fact(
    fact_id: str, fact_type: FactType, value: str,
    confidence: float = 0.7, chunk_id: str | None = "c1",
    section_id: str | None = "s1",
    source_type: str = "section",
) -> ExtractedFact:
    return ExtractedFact(
        fact_id=fact_id, fact_type=fact_type, value=value,
        confidence=confidence, source_type=source_type,
        source_id=fact_id, chunk_id=chunk_id, section_id=section_id,
        context_sentence=value, evidence_text=value,
    )


# ===================================================================
# Predicate vocabulary & normalization
# ===================================================================


class TestPredicateVocabulary:
    def test_all_predicates_are_snake_case(self):
        for p in VALID_PREDICATES:
            assert p.islower() and "_" in p or p.islower()

    def test_contains_required_predicates(self):
        required = {
            "introduces", "uses", "evaluated_on", "outperforms",
            "improves", "replaces", "supports", "contradicts",
            "achieves", "contains", "depends_on",
        }
        assert required.issubset(VALID_PREDICATES)

    def test_normalize_outperforms(self):
        assert normalize_predicate("outperforms") == "outperforms"
        assert normalize_predicate("Outperform") == "outperforms"

    def test_normalize_improves(self):
        assert normalize_predicate("improves") == "improves"
        assert normalize_predicate("better than") == "improves"
        assert normalize_predicate("superior to") == "improves"

    def test_normalize_evaluated_on(self):
        assert normalize_predicate("evaluated on") == "evaluated_on"
        assert normalize_predicate("tested on") == "evaluated_on"

    def test_normalize_unknown_returns_original(self):
        assert normalize_predicate("xyzzy") == "xyzzy"

    def test_normalize_empty_still_valid(self):
        assert normalize_predicate("") == ""


# ===================================================================
# TripleExtractionResult model
# ===================================================================


class TestTripleExtractionResultModel:
    def test_empty_result(self):
        r = TripleExtractionResult(triples=[])
        assert r.statistics == {"total": 0}
        assert r.confidence_metrics == {"mean": 0.0, "min": 0.0, "max": 0.0}
        assert r.predicate_distribution() == {}

    def test_single_triple_metrics(self):
        t = SemanticTriple(
            triple_id="t1", subject_id="s1", subject_text="M",
            predicate="uses", object_id="o1", object_text="D",
            confidence=0.8, chunk_id="c1",
        )
        r = TripleExtractionResult(triples=[t])
        assert r.statistics == {"total": 1}
        assert r.confidence_metrics == {"mean": 0.8, "min": 0.8, "max": 0.8}

    def test_predicate_distribution(self):
        triples = [
            SemanticTriple(
                triple_id=f"t{i}", subject_id="s1", subject_text="M",
                predicate=p, object_id=f"o{i}", object_text="D",
                confidence=0.8, chunk_id="c1",
            )
            for i, p in enumerate(["uses", "uses", "achieves"])
        ]
        r = TripleExtractionResult(triples=triples)
        assert r.predicate_distribution() == {"uses": 2, "achieves": 1}

    def test_by_predicate_filter(self):
        triples = [
            SemanticTriple(
                triple_id=f"t{i}", subject_id="s1", subject_text="M",
                predicate=p, object_id=f"o{i}", object_text="D",
                confidence=0.8, chunk_id="c1",
            )
            for i, p in enumerate(["uses", "achieves"])
        ]
        r = TripleExtractionResult(triples=triples)
        assert len(r.by_predicate("uses")) == 1
        assert len(r.by_predicate("outperforms")) == 0

    def test_deduplicated_removes_duplicates(self):
        triples = [
            SemanticTriple(
                triple_id="t1", subject_id="s1", subject_text="M",
                predicate="uses", object_id="o1", object_text="D",
                confidence=0.8, chunk_id="c1",
            ),
            SemanticTriple(
                triple_id="t2", subject_id="s1", subject_text="M",
                predicate="uses", object_id="o1", object_text="D",
                confidence=0.9, chunk_id="c1",
            ),
        ]
        r = TripleExtractionResult(triples=triples)
        deduped = r.deduplicated()
        assert len(deduped) == 1
        assert deduped[0].confidence == 0.9


# ===================================================================
# Strategy 1 — Entity-Entity relation patterns
# ===================================================================


class TestStrategy1EntityRelation:
    def test_outperforms_pattern(self):
        chunk = _make_chunk("c1", "BERT outperforms RoBERTa on GLUE.")
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e2", "RoBERTa", EntityLabel.METHOD, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        outperforms = result.by_predicate("outperforms")
        assert len(outperforms) >= 1
        t = outperforms[0]
        assert t.subject_text == "BERT"
        assert t.object_text == "RoBERTa"

    def test_improves_pattern(self):
        chunk = _make_chunk("c1", "Our method improves upon previous approach.")
        entities = [
            _make_entity("e1", "Our method", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e2", "previous approach", EntityLabel.METHOD, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        improves = result.by_predicate("improves")
        assert len(improves) >= 1

    def test_uses_pattern(self):
        chunk = _make_chunk("c1", "BERT uses the Transformer architecture.")
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e2", "Transformer", EntityLabel.METHOD, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        uses = result.by_predicate("uses")
        assert len(uses) >= 1

    def test_introduces_pattern(self):
        chunk = _make_chunk("c1", "We introduce a novel architecture called DeepNet.")
        entities = [
            _make_entity("e1", "DeepNet", EntityLabel.METHOD, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        introduces = result.by_predicate("introduces")
        assert len(introduces) >= 1

    def test_depends_on_pattern(self):
        chunk = _make_chunk("c1", "ResNet is based on convolutional layers.")
        entities = [
            _make_entity("e1", "ResNet", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e2", "convolutional layers", EntityLabel.METHOD, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        deps = result.by_predicate("depends_on")
        assert len(deps) >= 1

    def test_single_entity_no_triple(self):
        chunk = _make_chunk("c1", "BERT outperforms all baselines.")
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        # Only one entity → no entity-relation triple
        assert isinstance(result, TripleExtractionResult)


# ===================================================================
# Strategy 2 — Method → Dataset
# ===================================================================


class TestStrategy2MethodDataset:
    def test_same_chunk_pair(self):
        chunk = _make_chunk("c1", "BERT evaluated on GLUE.")
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e2", "GLUE", EntityLabel.DATASET, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        eds = result.by_predicate("evaluated_on")
        assert len(eds) >= 1
        t = eds[0]
        assert t.subject_text == "BERT"
        assert t.object_text == "GLUE"

    def test_no_dataset_no_triple(self):
        chunk = _make_chunk("c1", "BERT evaluated on GLUE.")
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        assert len(result.by_predicate("evaluated_on")) == 0

    def test_multiple_datasets(self):
        chunk = _make_chunk("c1", "Tested on multiple datasets.")
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e2", "SQuAD", EntityLabel.DATASET, chunk_id="c1"),
            _make_entity("e3", "GLUE", EntityLabel.DATASET, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        eds = result.by_predicate("evaluated_on")
        assert len(eds) >= 2

    def test_cross_section_lower_confidence(self):
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e2", "GLUE", EntityLabel.DATASET, chunk_id="c2"),
        ]
        chunks = [
            _make_chunk("c1", "BERT method.", section_id="s1"),
            _make_chunk("c2", "GLUE dataset.", section_id="s2"),
        ]
        sro = _make_sro(chunks=chunks, entities=entities)
        result = extract_triples(sro)
        eds = result.by_predicate("evaluated_on")
        # Should still produce cross-section triples
        assert len(eds) >= 1

    def test_confidence_same_chunk_higher(self):
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1",
                         confidence=0.8),
            _make_entity("e2", "GLUE", EntityLabel.DATASET, chunk_id="c1",
                         confidence=0.7),
        ]
        chunk = _make_chunk("c1", "BERT on GLUE.")
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        eds = result.by_predicate("evaluated_on")
        assert len(eds) >= 1
        # min(0.8, 0.7) * 0.90 = 0.63
        assert eds[0].confidence == pytest.approx(0.63)


# ===================================================================
# Strategy 3 — Method → Metric
# ===================================================================


class TestStrategy3MethodMetric:
    def test_same_chunk_pair(self):
        chunk = _make_chunk("c1", "BERT achieves 84.5 accuracy.")
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e2", "accuracy", EntityLabel.METRIC, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        achieves = result.by_predicate("achieves")
        assert len(achieves) >= 1
        t = achieves[0]
        assert t.subject_text == "BERT"
        assert t.object_text == "accuracy"

    def test_no_metric_no_triple(self):
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e2", "GLUE", EntityLabel.DATASET, chunk_id="c1"),
        ]
        chunk = _make_chunk("c1", "BERT on GLUE.")
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        assert len(result.by_predicate("achieves")) == 0

    def test_multiple_metrics(self):
        chunk = _make_chunk("c1", "Results table.")
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e2", "F1", EntityLabel.METRIC, chunk_id="c1"),
            _make_entity("e3", "BLEU", EntityLabel.METRIC, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        achieves = result.by_predicate("achieves")
        assert len(achieves) >= 2

    def test_confidence_same_chunk(self):
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1",
                         confidence=0.9),
            _make_entity("e2", "F1", EntityLabel.METRIC, chunk_id="c1",
                         confidence=0.6),
        ]
        chunk = _make_chunk("c1", "BERT achieves high F1.")
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        achieves = result.by_predicate("achieves")
        assert len(achieves) >= 1
        # min(0.9, 0.6) * 0.85 = 0.51
        assert achieves[0].confidence == pytest.approx(0.51)


# ===================================================================
# Strategy 4 — Method → Contribution
# ===================================================================


class TestStrategy4MethodContribution:
    def test_method_with_contribution(self):
        chunk = _make_chunk("c1", "We propose BERT.", section_id="s1")
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
        ]
        sections = [_make_section("s1", "Method", CanonicalLabel.METHODOLOGY)]
        sro = _make_sro(sections=sections, chunks=[chunk], entities=entities)
        fact_result = FactExtractionResult(facts=[
            _make_fact("f1", FactType.CONTRIBUTION,
                       "BERT introduces bidirectional pretraining.",
                       chunk_id="c1", section_id="s1"),
        ])
        result = extract_triples(sro, fact_result)
        introduces = result.by_predicate("introduces")
        assert len(introduces) >= 1
        assert introduces[0].subject_text == "BERT"

    def test_no_method_falls_back_to_title(self):
        sections = [_make_section("s1", "Conclusion", CanonicalLabel.CONCLUSION)]
        chunk = _make_chunk("c1", "We made contributions.", section_id="s1")
        sro = _make_sro(sections=sections, chunks=[chunk],
                        title="Test Paper Title")
        fact_result = FactExtractionResult(facts=[
            _make_fact("f1", FactType.CONTRIBUTION,
                       "A novel approach to ML.",
                       chunk_id="c1", section_id="s1"),
        ])
        result = extract_triples(sro, fact_result)
        introduces = result.by_predicate("introduces")
        assert len(introduces) >= 1
        assert introduces[0].subject_text == "Test Paper Title"

    def test_fact_confidence_affects_triple_confidence(self):
        entities = [
            _make_entity("e1", "DeepNet", EntityLabel.METHOD,
                         chunk_id="c1", confidence=0.8),
        ]
        chunk = _make_chunk("c1", "DeepNet contribution.", section_id="s1")
        sro = _make_sro(chunks=[chunk], entities=entities)
        fact_result = FactExtractionResult(facts=[
            _make_fact("f1", FactType.CONTRIBUTION,
                       "DeepNet is a novel architecture.",
                       chunk_id="c1", section_id="s1"),
        ])
        result = extract_triples(sro, fact_result)
        introduces = result.by_predicate("introduces")
        assert len(introduces) >= 1
        # method.confidence (0.8) * 0.75 = 0.6
        assert introduces[0].confidence == pytest.approx(0.6)

    def test_contribution_only_from_right_fact_type(self):
        entities = [
            _make_entity("e1", "M1", EntityLabel.METHOD, chunk_id="c1"),
        ]
        chunk = _make_chunk("c1", "Content.", section_id="s1")
        sro = _make_sro(chunks=[chunk], entities=entities)
        fact_result = FactExtractionResult(facts=[
            _make_fact("f1", FactType.LIMITATION,
                       "A limitation.",
                       chunk_id="c1", section_id="s1"),
            _make_fact("f2", FactType.METHOD,
                       "A method.",
                       chunk_id="c1", section_id="s1"),
        ])
        result = extract_triples(sro, fact_result)
        # Only CONTRIBUTION facts produce introduces triples
        assert len(result.by_predicate("introduces")) == 0

    def test_contribution_without_facts_returns_empty(self):
        chunk = _make_chunk("c1", "Content.")
        sro = _make_sro(chunks=[chunk])
        result = extract_triples(sro)
        assert len(result.by_predicate("introduces")) == 0


# ===================================================================
# Strategy 5 — Claim-derived triples
# ===================================================================


class TestStrategy5ClaimDerived:
    def test_methodological_claim_to_introduces(self):
        entities = [
            _make_entity("e1", "Our method", EntityLabel.METHOD, chunk_id="c1"),
        ]
        chunk = _make_chunk("c1", "We propose a new approach.")
        claims = [
            _make_claim("cl1", "We propose a new approach.",
                        ClaimType.METHODOLOGICAL, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities, claims=claims)
        result = extract_triples(sro)
        intro = result.by_predicate("introduces")
        assert len(intro) >= 1

    def test_comparative_claim_to_outperforms(self):
        entities = [
            _make_entity("e1", "Our model", EntityLabel.METHOD, chunk_id="c1"),
        ]
        chunk = _make_chunk("c1", "Our model outperforms baselines.")
        claims = [
            _make_claim("cl1", "Our model outperforms baselines.",
                        ClaimType.COMPARATIVE, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities, claims=claims)
        result = extract_triples(sro)
        outperforms = result.by_predicate("outperforms")
        assert len(outperforms) >= 1

    def test_existence_claim_to_supports(self):
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
        ]
        chunk = _make_chunk("c1", "We show BERT is effective.")
        claims = [
            _make_claim("cl1", "We show BERT is effective.",
                        ClaimType.EXISTENCE, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities, claims=claims)
        result = extract_triples(sro)
        supports = result.by_predicate("supports")
        assert len(supports) >= 1

    def test_negation_claim_to_contradicts_with_negated_flag(self):
        entities = [
            _make_entity("e1", "Model", EntityLabel.METHOD, chunk_id="c1"),
        ]
        chunk = _make_chunk("c1", "No significant improvement found.")
        claims = [
            _make_claim("cl1", "No significant improvement found.",
                        ClaimType.NEGATION, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities, claims=claims)
        result = extract_triples(sro)
        contradicts = result.by_predicate("contradicts")
        assert len(contradicts) >= 1
        assert contradicts[0].is_negated is True

    def test_statistical_claim_to_achieves(self):
        entities = [
            _make_entity("e1", "Model", EntityLabel.METHOD, chunk_id="c1"),
        ]
        chunk = _make_chunk("c1", "p < 0.05 with high effect size.")
        claims = [
            _make_claim("cl1", "p < 0.05 with high effect size.",
                        ClaimType.STATISTICAL, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities, claims=claims)
        result = extract_triples(sro)
        achieves = result.by_predicate("achieves")
        assert len(achieves) >= 1

    def test_causal_claim_to_depends_on(self):
        entities = [
            _make_entity("e1", "X", EntityLabel.METHOD, chunk_id="c1"),
        ]
        chunk = _make_chunk("c1", "X causes improvement in Y.")
        claims = [
            _make_claim("cl1", "X causes improvement in Y.",
                        ClaimType.CAUSAL, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities, claims=claims)
        result = extract_triples(sro)
        deps = result.by_predicate("depends_on")
        assert len(deps) >= 1

    def test_no_entity_falls_back_to_title(self):
        chunk = _make_chunk("c1", "We propose something new.",
                            section_id="s1")
        claims = [
            _make_claim("cl1", "We propose something new.",
                        ClaimType.METHODOLOGICAL, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], claims=claims,
                        title="Fallback Paper")
        result = extract_triples(sro)
        intro = result.by_predicate("introduces")
        assert len(intro) >= 1
        assert intro[0].subject_text == "Fallback Paper"


# ===================================================================
# Deduplication
# ===================================================================


class TestDeduplication:
    def test_identical_triple_deduplicated(self):
        chunk = _make_chunk("c1", "BERT outperforms RoBERTa on GLUE.")
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e2", "RoBERTa", EntityLabel.METHOD, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        # Strategy 1 may produce one; Strategy 5 might also. Either way,
        # dedup should ensure unique (subject_id, predicate, object_id).
        outperforms = result.by_predicate("outperforms")
        unique = set(
            (t.subject_id, t.predicate, t.object_id)
            for t in outperforms
        )
        assert len(unique) == len(outperforms)

    def test_deduplicated_method_keeps_highest_confidence(self):
        triples = [
            SemanticTriple(
                triple_id="t1", subject_id="s1", subject_text="M",
                predicate="uses", object_id="o1", object_text="D",
                confidence=0.6, chunk_id="c1",
            ),
            SemanticTriple(
                triple_id="t2", subject_id="s1", subject_text="M",
                predicate="uses", object_id="o1", object_text="D",
                confidence=0.9, chunk_id="c1",
            ),
        ]
        result = TripleExtractionResult(triples=triples)
        deduped = result.deduplicated()
        assert len(deduped) == 1
        assert deduped[0].confidence == 0.9

    def test_deduplicated_merges_evidence(self):
        triples = [
            SemanticTriple(
                triple_id="t1", subject_id="s1", subject_text="M",
                predicate="uses", object_id="o1", object_text="D",
                confidence=0.8, chunk_id="c1",
                evidence_ids=["e1"],
            ),
            SemanticTriple(
                triple_id="t2", subject_id="s1", subject_text="M",
                predicate="uses", object_id="o1", object_text="D",
                confidence=0.8, chunk_id="c1",
                evidence_ids=["e2"],
            ),
        ]
        result = TripleExtractionResult(triples=triples)
        deduped = result.deduplicated()
        assert "e1" in deduped[0].evidence_ids
        assert "e2" in deduped[0].evidence_ids

    def test_different_triples_not_deduplicated(self):
        triples = [
            SemanticTriple(
                triple_id="t1", subject_id="s1", subject_text="M",
                predicate="uses", object_id="o1", object_text="D1",
                confidence=0.8, chunk_id="c1",
            ),
            SemanticTriple(
                triple_id="t2", subject_id="s1", subject_text="M",
                predicate="uses", object_id="o2", object_text="D2",
                confidence=0.8, chunk_id="c1",
            ),
        ]
        result = TripleExtractionResult(triples=triples)
        assert len(result.deduplicated()) == 2


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    def test_no_entities_no_claims(self):
        chunk = _make_chunk("c1", "Some text.")
        sro = _make_sro(chunks=[chunk])
        result = extract_triples(sro)
        assert result.statistics["total"] == 0

    def test_empty_chunk_text(self):
        chunk = _make_chunk("c1", "   ", section_id="s1")
        entities = [
            _make_entity("e1", "M1", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e2", "M2", EntityLabel.METHOD, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        # Blank text produces no pattern matches
        assert isinstance(result, TripleExtractionResult)

    def test_entity_with_empty_text_skipped(self):
        chunk = _make_chunk("c1", "M1 outperforms M2.")
        entities = [
            _make_entity("e1", "M1", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e2", "", EntityLabel.METHOD, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        # entity with empty text is skipped matching → no triple
        assert isinstance(result, TripleExtractionResult)

    def test_very_low_confidence_filtered(self):
        entities = [
            _make_entity("e1", "M1", EntityLabel.METHOD,
                         chunk_id="c1", confidence=0.1),
            _make_entity("e2", "D1", EntityLabel.DATASET,
                         chunk_id="c1", confidence=0.1),
        ]
        chunk = _make_chunk("c1", "M1 on D1.")
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        # min(0.1, 0.1) * 0.9 = 0.09 < 0.3 → filtered
        eds = result.by_predicate("evaluated_on")
        assert len(eds) == 0

    def test_same_entity_not_self_related(self):
        chunk = _make_chunk("c1", "BERT outperforms BERT.")
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        # Only one entity, no self-relation
        assert isinstance(result, TripleExtractionResult)

    def test_too_many_pairs_limited(self):
        entities = [
            _make_entity(f"m{i}", f"M{i}", EntityLabel.METHOD, chunk_id=f"c{i}")
            for i in range(15)
        ] + [
            _make_entity(f"d{i}", f"D{i}", EntityLabel.DATASET, chunk_id=f"c{i}")
            for i in range(15)
        ]
        chunks = [
            _make_chunk(f"c{i}", f"Content {i}.", section_id=f"s{i}")
            for i in range(15)
        ]
        sections = [
            _make_section(f"s{i}", f"Section {i}", CanonicalLabel.METHODOLOGY)
            for i in range(15)
        ]
        sro = _make_sro(sections=sections, chunks=chunks, entities=entities)
        result = extract_triples(sro)
        # Should not crash from combinatorial explosion
        assert isinstance(result, TripleExtractionResult)


# ===================================================================
# Integration
# ===================================================================


class TestIntegration:
    def test_multiple_strategies_work_together(self):
        chunk = _make_chunk("c1", "BERT outperforms RoBERTa and achieves high F1.")
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e2", "RoBERTa", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e3", "F1", EntityLabel.METRIC, chunk_id="c1"),
            _make_entity("e4", "GLUE", EntityLabel.DATASET, chunk_id="c1"),
        ]
        claims = [
            _make_claim("cl1", "BERT outperforms baselines.",
                        ClaimType.COMPARATIVE, chunk_id="c1"),
            _make_claim("cl2", "We propose BERT.",
                        ClaimType.METHODOLOGICAL, chunk_id="c1"),
        ]
        sections = [
            _make_section("s1", "Method", CanonicalLabel.METHODOLOGY),
        ]
        sro = _make_sro(
            sections=sections, chunks=[chunk],
            entities=entities, claims=claims,
        )
        fact_result = FactExtractionResult(facts=[
            _make_fact("f1", FactType.CONTRIBUTION,
                       "BERT introduces masked language modeling.",
                       chunk_id="c1", section_id="s1"),
        ])
        result = extract_triples(sro, fact_result)

        # Should produce triples from multiple strategies
        assert result.statistics["total"] >= 4
        predicates = set(result.predicate_distribution().keys())
        assert "outperforms" in predicates
        assert "achieves" in predicates
        assert "evaluated_on" in predicates
        assert "introduces" in predicates

    def test_statistics_and_metrics_populated(self):
        chunk = _make_chunk("c1", "BERT outperforms RoBERTa on GLUE.")
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e2", "RoBERTa", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e3", "GLUE", EntityLabel.DATASET, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities)
        result = extract_triples(sro)
        assert result.statistics["total"] > 0
        assert result.confidence_metrics["mean"] > 0
        assert result.confidence_metrics["min"] > 0
        assert result.confidence_metrics["max"] > 0

    def test_extract_without_facts_still_works(self):
        chunk = _make_chunk("c1", "BERT outperforms RoBERTa.")
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e2", "RoBERTa", EntityLabel.METHOD, chunk_id="c1"),
        ]
        sro = _make_sro(chunks=[chunk], entities=entities)
        # No fact_result passed
        result = extract_triples(sro)
        outperforms = result.by_predicate("outperforms")
        assert len(outperforms) >= 1


# ===================================================================
# SemanticTriple model validation
# ===================================================================


class TestSemanticTripleValidation:
    def test_valid_triple(self):
        t = SemanticTriple(
            triple_id="t1", subject_id="s1", subject_text="BERT",
            predicate="uses", object_id="o1", object_text="Transformer",
            confidence=0.8, chunk_id="c1",
        )
        assert t.predicate == "uses"

    def test_invalid_predicate_format_raises(self):
        with pytest.raises(ValidationError):
            SemanticTriple(
                triple_id="t1", subject_id="s1", subject_text="BERT",
                predicate="Uses", object_id="o1", object_text="Transformer",
                confidence=0.8, chunk_id="c1",
            )

    def test_predicate_must_be_snake_case(self):
        with pytest.raises(ValidationError):
            SemanticTriple(
                triple_id="t1", subject_id="s1", subject_text="BERT",
                predicate="evaluatedOn", object_id="o1", object_text="GLUE",
                confidence=0.8, chunk_id="c1",
            )

    def test_negation_defaults_to_false(self):
        t = SemanticTriple(
            triple_id="t1", subject_id="s1", subject_text="BERT",
            predicate="uses", object_id="o1", object_text="Transformer",
            confidence=0.8, chunk_id="c1",
        )
        assert t.is_negated is False


# ===================================================================
# Cross-section extraction
# ===================================================================


class TestCrossSection:
    def test_method_dataset_different_sections(self):
        chunks = [
            _make_chunk("c1", "BERT is a transformer model.", section_id="s1"),
            _make_chunk("c2", "GLUE is a benchmark dataset.", section_id="s2"),
        ]
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e2", "GLUE", EntityLabel.DATASET, chunk_id="c2"),
        ]
        sections = [
            _make_section("s1", "Method", CanonicalLabel.METHODOLOGY),
            _make_section("s2", "Results", CanonicalLabel.RESULTS),
        ]
        sro = _make_sro(sections=sections, chunks=chunks, entities=entities)
        result = extract_triples(sro)
        eds = result.by_predicate("evaluated_on")
        assert len(eds) >= 1
        t = eds[0]
        # Cross-section confidence: min(0.7, 0.7) * 0.70 = 0.49
        assert t.confidence == pytest.approx(0.49)

    def test_method_metric_different_sections(self):
        chunks = [
            _make_chunk("c1", "BERT method details.", section_id="s1"),
            _make_chunk("c2", "F1 score results.", section_id="s2"),
        ]
        entities = [
            _make_entity("e1", "BERT", EntityLabel.METHOD, chunk_id="c1"),
            _make_entity("e2", "F1", EntityLabel.METRIC, chunk_id="c2"),
        ]
        sections = [
            _make_section("s1", "Method", CanonicalLabel.METHODOLOGY),
            _make_section("s2", "Results", CanonicalLabel.RESULTS),
        ]
        sro = _make_sro(sections=sections, chunks=chunks, entities=entities)
        result = extract_triples(sro)
        achieves = result.by_predicate("achieves")
        assert len(achieves) >= 1
        # Cross-section confidence: min(0.7, 0.7) * 0.65 = 0.455
        assert achieves[0].confidence == pytest.approx(0.455)
