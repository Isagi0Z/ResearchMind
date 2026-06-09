"""Tests for RUO v2.1.0 schema models.

Covers all models, validators, enums, and edge cases defined in
architecture/ruo_schema_v2_1.md.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from researchmind.models.ruo import (
    Annotation,
    ConfidenceBreakdown,
    ComponentConfidence,
    ComponentSubscore,
    DocumentRelation,
    DocumentStore,
    EvidenceChain,
    EvidenceCoverage,
    EvidenceRecord,
    EvidenceSpan,
    ProvenanceRecord,
    RUOAbstract,
    RUOAuthor,
    RUOBody,
    RUOChunk,
    RUOCitation,
    RUOClaim,
    RUOCorpus,
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
    Uncertainty,
    ValidationReport,
    ValidationResult,
    ValidationRule,
)
from researchmind.models.ruo_enums import (
    AggregationMethod,
    AnnotationStatus,
    AnnotationType,
    CanonicalLabel,
    CitationIntent,
    ClaimType,
    ConsensusStatus,
    DataSource,
    DocumentType,
    EntityLabel,
    EvidenceTargetType,
    EvidenceType,
    ExtractionMethod,
    ExtractionRoute,
    ProvenanceAction,
    ProvenanceAgentType,
    RelationType,
    ResolutionSource,
    ResolutionStatus,
    StageStatus,
    UncertaintyType,
    ValidationSeverity,
    VenueType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc)


def valid_source_file(**kw):
    defaults = dict(
        filename="paper.pdf",
        sha256="abcd" * 16,
        page_count=10,
        has_text_layer=True,
        is_scanned=False,
    )
    defaults.update(kw)
    return RUOSourceFile(**defaults)


def valid_confidence(component="title", score=0.9, subscores=None, **kw):
    if subscores is None:
        subscores = [ComponentSubscore(name="length", value=0.9, weight=1.0)]
    defaults = dict(component=component, score=score, subscores=subscores)
    defaults.update(kw)
    return ComponentConfidence(**defaults)


def valid_breakdown(components=None, overall=0.9, weights=None):
    if components is None:
        components = [valid_confidence()]
    if weights is None:
        weights = {c.component: 1.0 for c in components}
    return ConfidenceBreakdown(
        components=components,
        overall=overall,
        component_weights=weights,
    )


def valid_evidence_record(**kw):
    defaults = dict(
        evidence_id="ev1",
        evidence_type=EvidenceType.DIRECT_QUOTE,
        source_text="Some evidence text",
        data_source=DataSource.GROBID,
        extraction_method=ExtractionMethod.GROBID,
        confidence=0.95,
        timestamp=NOW,
    )
    defaults.update(kw)
    return EvidenceRecord(**defaults)


def valid_meta(**kw):
    defaults = dict(
        ruo_id="ruo-001",
        created_at=NOW,
        updated_at=NOW,
        pipeline_version="1.0",
        source_file=valid_source_file(),
        extraction_route=ExtractionRoute.GROBID_PRIMARY,
    )
    defaults.update(kw)
    return RUOMeta(**defaults)


def valid_quality(**kw):
    bd = kw.pop("breakdown", None) or valid_breakdown()
    defaults = dict(
        confidence=bd,
        evidence_coverage=EvidenceCoverage(),
        overall_confidence=bd.overall,
    )
    defaults.update(kw)
    return RUOQuality(**defaults)


def valid_header(**kw):
    defaults = dict(
        title="A Valid Paper Title Here",
        confidence=valid_confidence(),
    )
    defaults.update(kw)
    return RUOHeader(**defaults)


def valid_section(**kw):
    defaults = dict(
        section_id="s1",
        level=1,
        position=0,
        original_header="Introduction",
        canonical_label=CanonicalLabel.INTRODUCTION,
        label_confidence=0.95,
        page_start=1,
        page_end=3,
        content="Some section content.",
        extraction_method=ExtractionMethod.GROBID,
    )
    defaults.update(kw)
    return RUOSection(**defaults)


def valid_chunk(**kw):
    defaults = dict(
        chunk_id="c1",
        text="This is a valid chunk of text for testing purposes.",
        word_count=12,
        section_id="s1",
        canonical_label=CanonicalLabel.INTRODUCTION,
        page_start=1,
        page_end=1,
        paragraph_index=0,
        reading_order=0,
        extraction_method=ExtractionMethod.GROBID,
        extraction_confidence=0.9,
    )
    defaults.update(kw)
    return RUOChunk(**defaults)


# ===================================================================
# Enum Tests
# ===================================================================


class TestEnums:
    def test_evidence_type_values(self):
        assert EvidenceType.DIRECT_QUOTE.value == "direct_quote"
        assert EvidenceType.PARAPHRASE.value == "paraphrase"
        assert EvidenceType.HUMAN_ANNOTATED.value == "human_annotated"

    def test_evidence_target_type_values(self):
        assert EvidenceTargetType.CLAIM.value == "claim"
        assert EvidenceTargetType.CONFIDENCE.value == "confidence"

    def test_aggregation_method_values(self):
        assert AggregationMethod.WEIGHTED_AVERAGE.value == "weighted_average"
        assert AggregationMethod.MINIMUM.value == "minimum"
        assert AggregationMethod.PRODUCT.value == "product"

    def test_consensus_status_values(self):
        assert ConsensusStatus.CONSISTENT.value == "consistent"
        assert ConsensusStatus.CONTRADICTORY.value == "contradictory"
        assert ConsensusStatus.INSUFFICIENT_EVIDENCE.value == "insufficient_evidence"

    def test_annotation_status_values(self):
        assert AnnotationStatus.OPEN.value == "open"
        assert AnnotationStatus.ACCEPTED.value == "accepted"
        assert AnnotationStatus.REJECTED.value == "rejected"
        assert AnnotationStatus.SUPERSEDED.value == "superseded"

    def test_relation_type_values(self):
        assert RelationType.CITES.value == "cites"
        assert RelationType.CONTRADICTS.value == "contradicts"
        assert RelationType.SUPPORTS.value == "supports"

    def test_data_source_values(self):
        assert DataSource.GROBID.value == "grobid"
        assert DataSource.CROSSREF.value == "crossref"

    def test_provenance_action_values(self):
        assert ProvenanceAction.CREATED.value == "created"
        assert ProvenanceAction.CORRECTED.value == "corrected"

    def test_validation_severity_values(self):
        assert ValidationSeverity.ERROR.value == "error"
        assert ValidationSeverity.WARNING.value == "warning"

    def test_uncertainty_type_values(self):
        assert UncertaintyType.MODEL_UNCERTAINTY.value == "model_uncertainty"


# ===================================================================
# RUOSourceFile
# ===================================================================


class TestRUOSourceFile:
    def test_valid(self):
        sf = valid_source_file()
        assert sf.filename == "paper.pdf"
        assert sf.page_count == 10

    def test_invalid_sha256(self):
        with pytest.raises(ValidationError, match="sha256"):
            RUOSourceFile(
                filename="p.pdf",
                sha256="not-a-valid-hex",
                page_count=1,
                has_text_layer=True,
                is_scanned=False,
            )

    def test_sha256_too_short(self):
        with pytest.raises(ValidationError):
            RUOSourceFile(
                filename="p.pdf",
                sha256="abc123",
                page_count=1,
                has_text_layer=True,
                is_scanned=False,
            )


# ===================================================================
# EvidenceSpan
# ===================================================================


class TestEvidenceSpan:
    def test_valid_with_chunk_id(self):
        span = EvidenceSpan(chunk_id="c1")
        assert span.chunk_id == "c1"

    def test_valid_with_page(self):
        span = EvidenceSpan(page=5)
        assert span.page == 5

    def test_no_location_raises(self):
        with pytest.raises(ValidationError, match="At least one location"):
            EvidenceSpan()


# ===================================================================
# EvidenceRecord
# ===================================================================


class TestEvidenceRecord:
    def test_valid(self):
        er = valid_evidence_record()
        assert er.evidence_id == "ev1"

    def test_empty_source_text_raises(self):
        with pytest.raises(ValidationError, match="source_text"):
            valid_evidence_record(source_text="   ")

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            valid_evidence_record(confidence=1.5)


# ===================================================================
# EvidenceChain
# ===================================================================


class TestEvidenceChain:
    def test_valid(self):
        chain = EvidenceChain(
            target_id="claim1",
            target_type=EvidenceTargetType.CLAIM,
            chain=[valid_evidence_record()],
            aggregate_confidence=0.9,
        )
        assert chain.aggregation_method == AggregationMethod.WEIGHTED_AVERAGE

    def test_out_of_order_timestamps_raises(self):
        early = valid_evidence_record(
            evidence_id="e1",
            timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
        late = valid_evidence_record(
            evidence_id="e2",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        with pytest.raises(ValidationError, match="chronological"):
            EvidenceChain(
                target_id="c1",
                target_type=EvidenceTargetType.CLAIM,
                chain=[early, late],
                aggregate_confidence=0.9,
            )

    def test_aggregate_exceeds_max_confidence_raises(self):
        rec = valid_evidence_record(confidence=0.8)
        with pytest.raises(ValidationError, match="aggregate_confidence"):
            EvidenceChain(
                target_id="c1",
                target_type=EvidenceTargetType.CLAIM,
                chain=[rec],
                aggregate_confidence=0.9,
            )

    def test_equal_timestamps_allowed(self):
        t = datetime(2024, 6, 1, tzinfo=timezone.utc)
        chain = EvidenceChain(
            target_id="c1",
            target_type=EvidenceTargetType.ENTITY,
            chain=[
                valid_evidence_record(evidence_id="e1", timestamp=t),
                valid_evidence_record(evidence_id="e2", timestamp=t),
            ],
            aggregate_confidence=0.8,
        )
        assert len(chain.chain) == 2

    def test_empty_chain_raises(self):
        with pytest.raises(ValidationError):
            EvidenceChain(
                target_id="c1",
                target_type=EvidenceTargetType.CLAIM,
                chain=[],
                aggregate_confidence=0.9,
            )


# ===================================================================
# ProvenanceRecord
# ===================================================================


class TestProvenanceRecord:
    def test_valid(self):
        pr = ProvenanceRecord(
            provenance_id="p1",
            action=ProvenanceAction.CREATED,
            agent_type=ProvenanceAgentType.PIPELINE_STAGE,
            agent_name="grobid_client",
            timestamp=NOW,
        )
        assert pr.provenance_id == "p1"


# ===================================================================
# Uncertainty
# ===================================================================


class TestUncertainty:
    def test_valid(self):
        u = Uncertainty(
            uncertainty_type=UncertaintyType.MODEL_UNCERTAINTY,
            magnitude=0.3,
        )
        assert u.magnitude == 0.3

    def test_magnitude_bounds(self):
        with pytest.raises(ValidationError):
            Uncertainty(
                uncertainty_type=UncertaintyType.MODEL_UNCERTAINTY,
                magnitude=1.5,
            )


# ===================================================================
# ComponentConfidence
# ===================================================================


class TestComponentConfidence:
    def test_valid(self):
        cc = valid_confidence()
        assert cc.score == 0.9

    def test_weight_sum_not_one_raises(self):
        with pytest.raises(ValidationError, match="must sum to 1.0"):
            ComponentConfidence(
                component="title",
                score=0.8,
                subscores=[
                    ComponentSubscore(name="a", value=0.8, weight=0.5),
                    ComponentSubscore(name="b", value=0.8, weight=0.3),
                ],
            )

    def test_score_mismatch_raises(self):
        with pytest.raises(ValidationError, match="must equal weighted sum"):
            ComponentConfidence(
                component="title",
                score=0.5,
                subscores=[
                    ComponentSubscore(name="len", value=0.9, weight=1.0),
                ],
            )

    def test_no_subscores_ok(self):
        cc = ComponentConfidence(component="title", score=0.8)
        assert cc.score == 0.8

    def test_evidence_chain_id(self):
        cc = ComponentConfidence(
            component="title",
            score=0.8,
            evidence_chain_id="ec1",
        )
        assert cc.evidence_chain_id == "ec1"


# ===================================================================
# ConfidenceBreakdown
# ===================================================================


class TestConfidenceBreakdown:
    def test_valid(self):
        bd = valid_breakdown()
        assert bd.overall == 0.9

    def test_missing_weight_raises(self):
        with pytest.raises(ValidationError, match="weight/component mismatch"):
            ConfidenceBreakdown(
                components=[valid_confidence(component="title")],
                overall=0.9,
                component_weights={"other": 1.0},
            )

    def test_extra_weight_raises(self):
        with pytest.raises(ValidationError, match="weight/component mismatch"):
            ConfidenceBreakdown(
                components=[valid_confidence(component="title")],
                overall=0.9,
                component_weights={"title": 0.5, "extra": 0.5},
            )

    def test_overall_mismatch_raises(self):
        cc = valid_confidence(component="title", score=0.9)
        with pytest.raises(ValidationError, match="does not match"):
            ConfidenceBreakdown(
                components=[cc],
                overall=0.5,
                component_weights={"title": 1.0},
            )


# ===================================================================
# EvidenceCoverage
# ===================================================================


class TestEvidenceCoverage:
    def test_defaults(self):
        ec = EvidenceCoverage()
        assert ec.total_claims == 0
        assert ec.claims_evidence_rate == 0.0

    def test_rate_bounds(self):
        with pytest.raises(ValidationError):
            EvidenceCoverage(claims_evidence_rate=1.5)


# ===================================================================
# Validation Framework
# ===================================================================


class TestValidation:
    def test_validation_rule_valid(self):
        vr = ValidationRule(
            rule_id="R01",
            description="Test rule",
            severity=ValidationSeverity.ERROR,
            category="completeness",
            message_template="{field} is missing",
        )
        assert vr.rule_id == "R01"

    def test_validation_result_valid(self):
        vr = ValidationResult(
            rule_id="R01",
            passed=True,
            severity=ValidationSeverity.WARNING,
            message="All good",
        )
        assert vr.passed

    def test_validation_report_computes_summary(self):
        r1 = ValidationResult(
            rule_id="R1",
            passed=False,
            severity=ValidationSeverity.ERROR,
            message="fail",
        )
        r2 = ValidationResult(
            rule_id="R2",
            passed=True,
            severity=ValidationSeverity.WARNING,
            message="ok",
        )
        report = ValidationReport(results=[r1, r2])
        assert report.is_valid is False
        assert len(report.summary) == 2

    def test_validation_report_all_pass(self):
        r = ValidationResult(
            rule_id="R1",
            passed=True,
            severity=ValidationSeverity.ERROR,
            message="ok",
        )
        report = ValidationReport(results=[r])
        assert report.is_valid is True


# ===================================================================
# RUOAuthor
# ===================================================================


class TestRUOAuthor:
    def test_valid(self):
        a = RUOAuthor(full_name="Alice Smith")
        assert a.full_name == "Alice Smith"

    def test_invalid_orcid(self):
        with pytest.raises(ValidationError, match="orcid"):
            RUOAuthor(full_name="Alice", orcid="not-an-orcid")


# ===================================================================
# RUOHeader
# ===================================================================


class TestRUOHeader:
    def test_valid(self):
        h = valid_header()
        assert h.title == "A Valid Paper Title Here"

    def test_doi_lowercased(self):
        h = valid_header(doi="10.1234/ABC-DEF")
        assert h.doi == "10.1234/abc-def"

    def test_title_too_short(self):
        with pytest.raises(ValidationError):
            valid_header(title="AB")


# ===================================================================
# RUOAbstract
# ===================================================================


class TestRUOAbstract:
    def test_valid_plain(self):
        a = RUOAbstract(
            raw_text="Abstract text here.",
            confidence=valid_confidence(),
        )
        assert a.is_structured is False

    def test_structured_without_data_raises(self):
        with pytest.raises(ValidationError, match="structured must be provided"):
            RUOAbstract(
                raw_text="Abstract",
                is_structured=True,
                confidence=valid_confidence(),
            )

    def test_structured_valid(self):
        a = RUOAbstract(
            raw_text="Structured abstract.",
            is_structured=True,
            structured=RUOStructuredAbstract(methods="Method A"),
            confidence=valid_confidence(),
        )
        assert a.structured.methods == "Method A"


# ===================================================================
# RUOSection
# ===================================================================


class TestRUOSection:
    def test_valid(self):
        s = valid_section()
        assert s.section_id == "s1"

    def test_page_end_before_start_raises(self):
        with pytest.raises(ValidationError, match="page_end"):
            valid_section(page_start=5, page_end=3)

    def test_other_label_high_confidence_raises(self):
        with pytest.raises(ValidationError, match="label_confidence"):
            valid_section(
                canonical_label=CanonicalLabel.OTHER,
                label_confidence=1.0,
            )


# ===================================================================
# RUOChunk
# ===================================================================


class TestRUOChunk:
    def test_valid(self):
        c = valid_chunk()
        assert c.chunk_id == "c1"

    def test_empty_text_raises(self):
        with pytest.raises(ValidationError, match="chunk text"):
            valid_chunk(text="   ")

    def test_with_embedding(self):
        c = valid_chunk(embedding=[0.1, 0.2, 0.3], embedding_model="text-embedding-3")
        assert len(c.embedding) == 3
        assert c.embedding_model == "text-embedding-3"


# ===================================================================
# RUOReference
# ===================================================================


class TestRUOReference:
    def test_valid_unresolved(self):
        r = RUOReference(
            ref_id="r1",
            raw_text="Some reference",
            resolution_status=ResolutionStatus.UNRESOLVED,
            ref_confidence=0.0,
        )
        assert r.ref_id == "r1"

    def test_resolved_requires_source(self):
        with pytest.raises(ValidationError, match="resolution_source"):
            RUOReference(
                ref_id="r1",
                raw_text="Ref",
                resolution_status=ResolutionStatus.RESOLVED,
                resolution_source=ResolutionSource.NONE,
                ref_confidence=0.9,
            )

    def test_target_ruo_requires_resolved(self):
        with pytest.raises(ValidationError, match="target_ruo_id"):
            RUOReference(
                ref_id="r1",
                raw_text="Ref",
                resolution_status=ResolutionStatus.UNRESOLVED,
                ref_confidence=0.0,
                target_ruo_id="doc-2",
            )

    def test_doi_normalized(self):
        r = RUOReference(
            ref_id="r1",
            raw_text="Ref",
            resolution_status=ResolutionStatus.UNRESOLVED,
            ref_confidence=0.0,
            doi="10.1234/UPPER-CASE",
        )
        assert r.doi == "10.1234/upper-case"


# ===================================================================
# RUOCitation
# ===================================================================


class TestRUOCitation:
    def test_valid(self):
        c = RUOCitation(
            citation_id="cit1",
            chunk_id="c1",
            section_id="s1",
            context_sentence="As shown in [1]",
            page=3,
        )
        assert c.citation_id == "cit1"

    def test_intent_requires_confidence(self):
        with pytest.raises(ValidationError, match="intent_confidence"):
            RUOCitation(
                citation_id="cit1",
                chunk_id="c1",
                section_id="s1",
                context_sentence="text",
                page=1,
                citation_intent=CitationIntent.SUPPORTS,
            )

    def test_intent_requires_evidence(self):
        with pytest.raises(ValidationError, match="evidence record"):
            RUOCitation(
                citation_id="cit1",
                chunk_id="c1",
                section_id="s1",
                context_sentence="text",
                page=1,
                citation_intent=CitationIntent.SUPPORTS,
                intent_confidence=0.9,
                intent_evidence_ids=[],
            )

    def test_intent_with_evidence_ok(self):
        c = RUOCitation(
            citation_id="cit1",
            chunk_id="c1",
            section_id="s1",
            context_sentence="text",
            page=1,
            citation_intent=CitationIntent.BACKGROUND,
            intent_confidence=0.8,
            intent_evidence_ids=["ev1"],
        )
        assert c.citation_intent == CitationIntent.BACKGROUND


# ===================================================================
# RUOEntity
# ===================================================================


class TestRUOEntity:
    def test_valid(self):
        e = RUOEntity(
            entity_id="e1",
            text="CNN",
            label=EntityLabel.METHOD,
            chunk_id="c1",
            sentence="We used CNN.",
            confidence=0.95,
            source="spacy",
        )
        assert e.entity_id == "e1"

    def test_empty_text_raises(self):
        with pytest.raises(ValidationError, match="entity text"):
            RUOEntity(
                entity_id="e1",
                text="",
                label=EntityLabel.METHOD,
                chunk_id="c1",
                sentence="text",
                confidence=0.9,
                source="spacy",
            )

    def test_with_embedding(self):
        e = RUOEntity(
            entity_id="e1",
            text="CNN",
            label=EntityLabel.METHOD,
            chunk_id="c1",
            sentence="We used CNN.",
            confidence=0.95,
            source="spacy",
            embedding=[0.5, 0.5],
            embedding_model="test-model",
        )
        assert len(e.embedding) == 2


# ===================================================================
# RUOClaim
# ===================================================================


class TestRUOClaim:
    def test_valid(self):
        c = RUOClaim(
            claim_id="cl1",
            sentence="Our method achieves 95% accuracy.",
            chunk_id="c1",
            section_id="s1",
            canonical_label=CanonicalLabel.RESULTS,
            claim_type=ClaimType.STATISTICAL,
            matched_patterns=["achieves"],
            confidence=0.9,
            page=5,
            evidence_chain_id="ec1",
        )
        assert c.claim_id == "cl1"

    def test_empty_patterns_raises(self):
        with pytest.raises(ValidationError, match="matched_patterns"):
            RUOClaim(
                claim_id="cl1",
                sentence="text",
                chunk_id="c1",
                section_id="s1",
                canonical_label=CanonicalLabel.RESULTS,
                claim_type=ClaimType.STATISTICAL,
                matched_patterns=[],
                confidence=0.9,
                page=1,
                evidence_chain_id="ec1",
            )

    def test_with_embedding(self):
        c = RUOClaim(
            claim_id="cl1",
            sentence="text",
            chunk_id="c1",
            section_id="s1",
            canonical_label=CanonicalLabel.RESULTS,
            claim_type=ClaimType.EXISTENCE,
            matched_patterns=["shows"],
            confidence=0.8,
            page=1,
            evidence_chain_id="ec1",
            embedding=[0.1, 0.2],
            embedding_model="m",
        )
        assert c.embedding_model == "m"

    def test_contradiction_timestamp(self):
        c = RUOClaim(
            claim_id="cl1",
            sentence="text",
            chunk_id="c1",
            section_id="s1",
            canonical_label=CanonicalLabel.RESULTS,
            claim_type=ClaimType.EXISTENCE,
            matched_patterns=["shows"],
            confidence=0.8,
            page=1,
            evidence_chain_id="ec1",
            is_contradicted=True,
            contradiction_detected_at=NOW,
        )
        assert c.is_contradicted is True
        assert c.contradiction_detected_at is not None


# ===================================================================
# SemanticTriple
# ===================================================================


class TestSemanticTriple:
    def test_valid(self):
        t = SemanticTriple(
            triple_id="t1",
            subject_id="e1",
            subject_text="CNN",
            predicate="achieves",
            object_id="e2",
            object_text="95% accuracy",
            confidence=0.9,
            chunk_id="c1",
        )
        assert t.triple_id == "t1"

    def test_invalid_predicate_format(self):
        with pytest.raises(ValidationError, match="snake_case"):
            SemanticTriple(
                triple_id="t1",
                subject_id="e1",
                subject_text="X",
                predicate="achieves-something",
                object_id="e2",
                object_text="Y",
                confidence=0.9,
                chunk_id="c1",
            )

    def test_negated(self):
        t = SemanticTriple(
            triple_id="t1",
            subject_id="e1",
            subject_text="X",
            predicate="improves",
            object_id="e2",
            object_text="Y",
            is_negated=True,
            confidence=0.9,
            chunk_id="c1",
        )
        assert t.is_negated is True


# ===================================================================
# DocumentRelation
# ===================================================================


class TestDocumentRelation:
    def test_valid(self):
        r = DocumentRelation(
            relation_id="r1",
            source_ruo_id="doc-a",
            target_ruo_id="doc-b",
            relation_type=RelationType.CITES,
            confidence=0.95,
            detected_at=NOW,
        )
        assert r.relation_id == "r1"

    def test_self_relation_raises(self):
        with pytest.raises(ValidationError, match="must differ"):
            DocumentRelation(
                relation_id="r1",
                source_ruo_id="doc-a",
                target_ruo_id="doc-a",
                relation_type=RelationType.CITES,
                confidence=0.95,
                detected_at=NOW,
            )


# ===================================================================
# Annotation
# ===================================================================


class TestAnnotation:
    def test_valid(self):
        a = Annotation(
            annotation_id="a1",
            annotation_type=AnnotationType.HUMAN_REVIEW,
            target_id="c1",
            target_type="chunk",
            field="canonical_label",
            author="human:user@example.com",
            timestamp=NOW,
        )
        assert a.status == AnnotationStatus.OPEN

    def test_invalid_target_type(self):
        with pytest.raises(ValidationError, match="target_type"):
            Annotation(
                annotation_id="a1",
                annotation_type=AnnotationType.HUMAN_REVIEW,
                target_id="c1",
                target_type="invalid_type",
                field="label",
                author="test",
                timestamp=NOW,
            )

    def test_accepted_status(self):
        a = Annotation(
            annotation_id="a2",
            annotation_type=AnnotationType.HUMAN_CORRECTION,
            target_id="e1",
            target_type="entity",
            field="text",
            previous_value="CNN",
            suggested_value="Convolutional Neural Network",
            author="human:reviewer",
            timestamp=NOW,
            status=AnnotationStatus.ACCEPTED,
        )
        assert a.status == AnnotationStatus.ACCEPTED


# ===================================================================
# RUOCorpus
# ===================================================================


class TestRUOCorpus:
    def test_valid_empty(self):
        c = RUOCorpus(
            corpus_id="corp-1",
            name="test-corpus",
            created_at=NOW,
            updated_at=NOW,
            quality=valid_quality(),
        )
        assert c.corpus_id == "corp-1"

    def test_relation_refers_to_unknown_doc_raises(self):
        rel = DocumentRelation(
            relation_id="r1",
            source_ruo_id="doc-unknown",
            target_ruo_id="doc-other",
            relation_type=RelationType.CITES,
            confidence=0.9,
            detected_at=NOW,
        )
        with pytest.raises(ValidationError, match="not found in corpus"):
            RUOCorpus(
                corpus_id="c1",
                name="test",
                created_at=NOW,
                updated_at=NOW,
                relations=[rel],
                quality=valid_quality(),
            )


# ===================================================================
# RUOQuality
# ===================================================================


class TestRUOQuality:
    def test_valid(self):
        q = valid_quality()
        assert q.overall_confidence == 0.9

    def test_overall_mismatch_raises(self):
        bd = valid_breakdown(overall=0.9)
        with pytest.raises(ValidationError, match="must match"):
            RUOQuality(
                confidence=bd,
                evidence_coverage=EvidenceCoverage(),
                overall_confidence=0.5,
            )


# ===================================================================
# RUOEvidenceReport
# ===================================================================


class TestRUOEvidenceReport:
    def test_valid(self):
        r = RUOEvidenceReport(
            report_id="rep1",
            target_id="claim1",
            target_type="claim",
            target_text="Test claim",
            aggregate_confidence=0.85,
            consensus=ConsensusStatus.CONSISTENT,
            generated_at=NOW,
            generator="test_synthesizer",
        )
        assert r.consensus == ConsensusStatus.CONSISTENT

    def test_no_consensus(self):
        r = RUOEvidenceReport(
            report_id="rep2",
            target_id="e1",
            target_type="entity",
            target_text="CNN",
            aggregate_confidence=0.5,
            generated_at=NOW,
            generator="test",
        )
        assert r.consensus is None


# ===================================================================
# RUODocument
# ===================================================================


class TestRUODocument:
    def test_valid_minimal(self):
        doc = RUODocument(
            meta=valid_meta(),
            header=valid_header(),
            body=RUOBody(
                sections=[valid_section()],
                chunks=[valid_chunk()],
            ),
            quality=valid_quality(),
        )
        assert doc.schema_version == "2.1.0"
        assert doc.meta.ruo_id == "ruo-001"

    def test_invalid_schema_version(self):
        with pytest.raises(ValidationError, match="semver"):
            RUODocument(
                meta=valid_meta(schema_version="bad-version"),
                header=valid_header(),
                body=RUOBody(
                    sections=[valid_section()],
                    chunks=[valid_chunk()],
                ),
                quality=valid_quality(),
                schema_version="not-semver",
            )

    def test_get_provenance_by_action(self):
        pr = ProvenanceRecord(
            provenance_id="p1",
            action=ProvenanceAction.CREATED,
            agent_type=ProvenanceAgentType.PIPELINE_STAGE,
            agent_name="test",
            timestamp=NOW,
        )
        doc = RUODocument(
            meta=valid_meta(),
            header=valid_header(),
            body=RUOBody(
                sections=[valid_section()],
                chunks=[valid_chunk()],
            ),
            quality=valid_quality(),
            provenance=[pr],
        )
        result = doc.get_provenance_by_action(ProvenanceAction.CREATED)
        assert len(result) == 1
        assert result[0].provenance_id == "p1"


# ===================================================================
# RUOBody (cross-reference validators)
# ===================================================================


class TestRUOBody:
    def test_duplicate_section_id_raises(self):
        s1 = valid_section(section_id="s1")
        s2 = valid_section(section_id="s1", position=1)
        with pytest.raises(ValidationError, match="section_id"):
            RUOBody(sections=[s1, s2], chunks=[valid_chunk()])

    def test_duplicate_chunk_id_raises(self):
        c1 = valid_chunk(chunk_id="c1")
        c2 = valid_chunk(chunk_id="c1", paragraph_index=1)
        with pytest.raises(ValidationError, match="chunk_id"):
            RUOBody(
                sections=[valid_section()],
                chunks=[c1, c2],
            )


# ===================================================================
# RUOBody helpers
# ===================================================================


class TestRUOTable:
    def test_valid(self):
        t = RUOTable(
            table_id="t1",
            caption="Results table",
            section_id="s1",
            page=5,
            confidence=0.9,
        )
        assert t.table_id == "t1"


class TestRUOFigure:
    def test_valid(self):
        f = RUOFigure(
            figure_id="f1",
            caption="Architecture diagram",
            section_id="s1",
            page=3,
        )
        assert f.figure_id == "f1"


# ===================================================================
# DocumentStore ABC
# ===================================================================


class TestDocumentStore:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            DocumentStore()  # type: ignore


# ===================================================================
# RUOStructuredAbstract
# ===================================================================


class TestRUOStructuredAbstract:
    def test_valid(self):
        sa = RUOStructuredAbstract(
            background="Background",
            methods="Methods",
            results="Results",
        )
        assert sa.background == "Background"
        assert sa.results == "Results"
        assert sa.objective is None
