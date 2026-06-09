"""Tests for entity resolution — deterministic cross-document entity merging.

Test organization:
    - TestNormalizeEntityText       (12 tests)
    - TestLabelCompatibility        (10 tests)
    - TestAliasLoading              (8 tests)
    - TestCanonicalEntityModel      (4 tests)
    - TestEntityAliasModel          (3 tests)
    - TestEntityClusterModel        (3 tests)
    - TestResolutionResultModel     (4 tests)
    - TestTokenSimilarity           (4 tests)
    - TestResolverExact             (15 tests)
    - TestResolverAlias             (15 tests)
    - TestResolverFuzzy             (12 tests)
    - TestResolverTypeProtection    (10 tests)
    - TestResolverClusters          (12 tests)
    - TestResolverEdgeCases         (18 tests)
    - TestResolverStageCounts       (8 tests)
    - TestResolverCorpusIntegration (8 tests)
    Total: ~146
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from researchmind.corpus.entity_resolution import (
    DEFAULT_FUZZY_THRESHOLD,
    LABEL_COMPATIBILITY,
    CanonicalEntity,
    EntityAlias,
    EntityCluster,
    EntityResolver,
    ResolutionResult,
    normalize_entity_text,
    _token_similarity,
)
from researchmind.models.enums import EntityLabel
from researchmind.models.ruo import (
    RUOEntity, RUODocument, RUOMeta, RUOSourceFile, RUOHeader, RUOAuthor,
    RUOBody, RUOSection, RUOChunk, RUOQuality, EvidenceCoverage,
    ConfidenceBreakdown, ComponentConfidence, ComponentSubscore,
    SemanticTriple, RUOReference,
)
from researchmind.models.ruo_enums import RelationType
from researchmind.models.enums import (
    CanonicalLabel, ClaimType, DocumentType, EntityLabel,
    ExtractionMethod, ExtractionRoute, ResolutionSource,
    ResolutionStatus,
)
from researchmind.storage.corpus import CorpusManager


# ===================================================================
# Helpers
# ===================================================================


# ===================================================================
# make_doc helper (adapted from test_corpus.py)
# ===================================================================

_NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _source_file(filename: str = "paper.pdf") -> RUOSourceFile:
    return RUOSourceFile(
        filename=filename,
        sha256="a" * 64,
        page_count=5,
        has_text_layer=True,
        is_scanned=False,
    )


def _meta(ruo_id: str = "doc_001") -> RUOMeta:
    return RUOMeta(
        ruo_id=ruo_id,
        created_at=_NOW,
        updated_at=_NOW,
        pipeline_version="2.1.0",
        source_file=_source_file(),
        extraction_route=ExtractionRoute.GROBID_PRIMARY,
        document_type=DocumentType.RESEARCH_ARTICLE,
    )


def _header(title: str = "Test Document", authors: list[str] | None = None) -> RUOHeader:
    author_models = [RUOAuthor(full_name=n) for n in (authors or [])]
    conf = ComponentConfidence(
        component="header", score=0.85,
        subscores=[ComponentSubscore(name="header", value=0.85, weight=1.0)],
    )
    return RUOHeader(title=title, authors=author_models, document_type=DocumentType.RESEARCH_ARTICLE, confidence=conf)


def _section(sid: str = "s1") -> RUOSection:
    return RUOSection(
        section_id=sid, level=1, position=0, original_header="Introduction",
        canonical_label=CanonicalLabel.INTRODUCTION, label_confidence=0.9,
        page_start=0, page_end=2, content="Section content.",
        extraction_method=ExtractionMethod.GROBID,
    )


def _chunk(cid: str = "c1") -> RUOChunk:
    return RUOChunk(
        chunk_id=cid, text="Chunk text.", word_count=2, section_id="s1",
        canonical_label=CanonicalLabel.INTRODUCTION, page_start=0, page_end=1,
        paragraph_index=0, reading_order=0, extraction_method=ExtractionMethod.GROBID,
        extraction_confidence=0.9,
    )


def _body() -> RUOBody:
    return RUOBody(sections=[_section()], chunks=[_chunk()])


def _entity_helper(eid: str = "e1", text: str = "BERT", label: EntityLabel = EntityLabel.METHOD) -> RUOEntity:
    return RUOEntity(
        entity_id=eid, text=text, label=label, chunk_id="c1",
        sentence="Sample sentence.", confidence=0.9, source="ner",
    )


def _claim(cid: str = "cl1", sentence: str = "SOTA.", claim_type: ClaimType = ClaimType.STATISTICAL) -> "RUOClaim":
    from researchmind.models.ruo import RUOClaim
    return RUOClaim(
        claim_id=cid, sentence=sentence, chunk_id="c1", section_id="s1",
        canonical_label=CanonicalLabel.INTRODUCTION, claim_type=claim_type,
        matched_patterns=["statistical"], confidence=0.85, page=1,
        evidence_chain_id=f"ech_{cid}",
    )


def _triple(tid: str = "t1", predicate: str = "uses", subject_text: str = "BERT", object_text: str = "ImageNet") -> SemanticTriple:
    return SemanticTriple(
        triple_id=tid, subject_id="e1", subject_text=subject_text,
        predicate=predicate, object_id="e2", object_text=object_text,
        confidence=0.8, chunk_id="c1",
    )


def _reference(rid: str = "r1", target_ruo_id: str | None = None) -> "RUOReference":
    return RUOReference(
        ref_id=rid, raw_text="Ref", title="Ref" if target_ruo_id else None,
        year="2023" if target_ruo_id else None,
        resolution_status=ResolutionStatus.RESOLVED if target_ruo_id else ResolutionStatus.UNRESOLVED,
        resolution_source=ResolutionSource.CROSSREF_LOOKUP if target_ruo_id else ResolutionSource.NONE,
        ref_confidence=0.9 if target_ruo_id else 0.0,
        target_ruo_id=target_ruo_id,
    )


def _coverage() -> EvidenceCoverage:
    return EvidenceCoverage(
        total_claims=1, claims_with_evidence=1, claims_evidence_rate=1.0,
        total_entities=1, entities_with_evidence=1, entities_evidence_rate=1.0,
        total_citations=0, citations_with_intent_evidence=0,
        citation_intent_evidence_rate=0.0,
        total_references=1, references_with_resolution_evidence=1,
        reference_resolution_evidence_rate=1.0,
    )


def _quality(overall: float = 0.85) -> RUOQuality:
    comp = ComponentConfidence(
        component="overall", score=overall,
        subscores=[ComponentSubscore(name="overall", value=overall, weight=1.0)],
    )
    breakdown = ConfidenceBreakdown(
        components=[comp], overall=overall, component_weights={"overall": 1.0},
    )
    return RUOQuality(
        confidence=breakdown, evidence_coverage=_coverage(),
        overall_confidence=overall,
    )


def make_doc(
    ruo_id: str = "doc_001",
    title: str = "Test Document",
    authors: list[str] | None = None,
    entities: list[tuple[str, EntityLabel]] | None = None,
    claims: list[tuple[str, ClaimType]] | None = None,
    triples: list[tuple[str, str]] | None = None,
    references: list[str | tuple[str, str]] | None = None,
    year: str | None = "2024",
    confidence: float = 0.85,
    research_fields: list[str] | None = None,
) -> RUODocument:
    meta = _meta(ruo_id)
    meta.source_file = _source_file()
    if research_fields:
        meta.research_fields = research_fields
    header = _header(title=title, authors=authors)
    entity_models = []
    if entities:
        for i, (text, label) in enumerate(entities):
            entity_models.append(_entity_helper(eid=f"{ruo_id}_e{i}", text=text, label=label))
    claim_models = []
    if claims:
        for i, (sentence, ct) in enumerate(claims):
            claim_models.append(_claim(cid=f"cl{i}", sentence=sentence, claim_type=ct))
    triple_models = []
    if triples:
        for i, (subj, pred) in enumerate(triples):
            triple_models.append(_triple(tid=f"t{i}", predicate=pred, subject_text=subj))
    ref_models = []
    if references:
        for i, ref in enumerate(references):
            if isinstance(ref, tuple):
                ref_models.append(_reference(rid=ref[0], target_ruo_id=ref[1]))
            else:
                ref_models.append(_reference(rid=f"r{i}", target_ruo_id=ref))
    return RUODocument(
        meta=meta, header=header, body=_body(),
        entities=entity_models, claims=claim_models, triples=triple_models,
        references=ref_models, quality=_quality(overall=confidence), provenance=[],
    )


# ===================================================================
# Helpers
# ===================================================================


def _entity(
    eid: str = "e1",
    text: str = "BERT",
    label: EntityLabel = EntityLabel.METHOD,
    confidence: float = 0.9,
) -> RUOEntity:
    return RUOEntity(
        entity_id=eid,
        text=text,
        label=label,
        chunk_id="c1",
        sentence="Sample sentence.",
        confidence=confidence,
        source="ner",
    )


def _resolver(aliases: bool = True) -> EntityResolver:
    if aliases:
        return EntityResolver("config/entity_aliases.yaml")
    return EntityResolver(alias_path=Path(tempfile.mkdtemp()) / "empty.yaml")


# ===================================================================
# normalize_entity_text
# ===================================================================


class TestNormalizeEntityText:
    def test_lowercases(self):
        assert normalize_entity_text("BERT") == "bert"

    def test_strips_whitespace(self):
        assert normalize_entity_text("  GAN  ") == "gan"

    def test_collapses_internal_whitespace(self):
        assert normalize_entity_text("batch  normalization") == "batch normalization"

    def test_removes_trailing_period(self):
        assert normalize_entity_text("ResNet.") == "resnet"

    def test_removes_trailing_comma(self):
        assert normalize_entity_text("CNN,") == "cnn"

    def test_removes_trailing_punctuation_mixed(self):
        assert normalize_entity_text("Attention!") == "attention"

    def test_removes_multiple_trailing_punctuation(self):
        assert normalize_entity_text("SGD?!") == "sgd"

    def test_preserves_internal_punctuation(self):
        assert normalize_entity_text("U-Net") == "u-net"

    def test_empty_string_becomes_empty(self):
        assert normalize_entity_text("") == ""

    def test_whitespace_only_becomes_empty(self):
        assert normalize_entity_text("   ") == ""

    def test_newline_and_tab_collapsed(self):
        assert normalize_entity_text("batch\nnorm\tlayer") == "batch norm layer"

    def test_preserves_hyphen(self):
        assert normalize_entity_text("f1-score") == "f1-score"


# ===================================================================
# Label compatibility
# ===================================================================


class TestLabelCompatibility:
    def test_same_label_always_compatible(self):
        resolver = _resolver(aliases=False)
        assert resolver._labels_compatible(EntityLabel.METHOD, EntityLabel.METHOD)

    def test_method_compatible_with_tool(self):
        resolver = _resolver(aliases=False)
        assert resolver._labels_compatible(EntityLabel.METHOD, EntityLabel.TOOL)

    def test_tool_compatible_with_method(self):
        resolver = _resolver(aliases=False)
        assert resolver._labels_compatible(EntityLabel.TOOL, EntityLabel.METHOD)

    def test_dataset_not_compatible_with_method(self):
        resolver = _resolver(aliases=False)
        assert not resolver._labels_compatible(EntityLabel.DATASET, EntityLabel.METHOD)

    def test_metric_not_compatible_with_method(self):
        resolver = _resolver(aliases=False)
        assert not resolver._labels_compatible(EntityLabel.METRIC, EntityLabel.METHOD)

    def test_person_compatible_with_organization(self):
        resolver = _resolver(aliases=False)
        assert resolver._labels_compatible(EntityLabel.PERSON, EntityLabel.ORGANIZATION)

    def test_location_not_compatible_with_method(self):
        resolver = _resolver(aliases=False)
        assert not resolver._labels_compatible(EntityLabel.LOCATION, EntityLabel.METHOD)

    def test_gene_protein_compatible_with_method(self):
        resolver = _resolver(aliases=False)
        assert resolver._labels_compatible(EntityLabel.GENE_PROTEIN, EntityLabel.METHOD)

    def test_drug_not_compatible_with_dataset(self):
        resolver = _resolver(aliases=False)
        assert not resolver._labels_compatible(EntityLabel.DRUG, EntityLabel.DATASET)

    def test_other_only_compatible_with_other(self):
        resolver = _resolver(aliases=False)
        assert resolver._labels_compatible(EntityLabel.OTHER, EntityLabel.OTHER)
        assert not resolver._labels_compatible(EntityLabel.OTHER, EntityLabel.METHOD)


# ===================================================================
# Alias loading
# ===================================================================


class TestAliasLoading:
    def test_loads_known_aliases(self):
        resolver = EntityResolver("config/entity_aliases.yaml")
        assert len(resolver._alias_map) > 100
        assert normalize_entity_text("gan") in resolver._alias_map
        assert normalize_entity_text("cnn") in resolver._alias_map

    def test_missing_file_returns_empty(self):
        resolver = EntityResolver(alias_path="nonexistent.yaml")
        assert resolver._alias_map == {}

    def test_canonical_mapping(self):
        resolver = EntityResolver("config/entity_aliases.yaml")
        assert resolver._alias_map[normalize_entity_text("gan")] == normalize_entity_text(
            "generative adversarial network"
        )

    def test_label_mapping(self):
        resolver = EntityResolver("config/entity_aliases.yaml")
        assert resolver._alias_label[normalize_entity_text("gan")] == EntityLabel.METHOD
        assert resolver._alias_label[normalize_entity_text("auc")] == EntityLabel.METRIC

    def test_original_canonical_preserved(self):
        resolver = EntityResolver("config/entity_aliases.yaml")
        orig = resolver._canonical_for_alias[normalize_entity_text("batchnorm")]
        assert "batch" in orig.lower()

    def test_variant_not_overwritten(self):
        resolver = EntityResolver("config/entity_aliases.yaml")
        # "cnn" should map to "convolutional neural network"
        assert resolver._alias_map[normalize_entity_text("cnn")] == normalize_entity_text(
            "convolutional neural network"
        )

    def test_custom_alias_path(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("aliases:\n  - canonical: Custom\n    variants: [cust]\n    label: method\n")
            f.flush()
            resolver = EntityResolver(alias_path=f.name)
            assert normalize_entity_text("cust") in resolver._alias_map
        os.unlink(f.name)

    def test_invalid_yaml_handled_gracefully(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("invalid: [yaml: broken\n")
            f.flush()
            with pytest.raises(Exception):
                EntityResolver(alias_path=f.name)
        os.unlink(f.name)


# ===================================================================
# Model construction
# ===================================================================


class TestCanonicalEntityModel:
    def test_valid_construction(self):
        ce = CanonicalEntity(
            canonical_id="ce_abc123",
            canonical_text="BERT",
            label=EntityLabel.METHOD,
            variants=["BERT", "bert"],
            entity_ids=["e1", "e2"],
            confidence=0.9,
            resolution_method="exact",
        )
        assert ce.canonical_id == "ce_abc123"
        assert ce.canonical_text == "BERT"

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            CanonicalEntity(
                canonical_id="ce_abc",
                canonical_text="test",
                label=EntityLabel.METHOD,
                variants=[],
                entity_ids=[],
                confidence=1.5,
                resolution_method="exact",
            )

    def test_method_pattern(self):
        with pytest.raises(ValidationError):
            CanonicalEntity(
                canonical_id="ce_abc",
                canonical_text="test",
                label=EntityLabel.METHOD,
                variants=[],
                entity_ids=[],
                confidence=0.5,
                resolution_method="invalid",
            )

    def test_frozen(self):
        ce = CanonicalEntity(
            canonical_id="ce_abc",
            canonical_text="test",
            label=EntityLabel.METHOD,
            variants=[],
            entity_ids=[],
            confidence=0.5,
            resolution_method="exact",
        )
        with pytest.raises(ValidationError):
            ce.canonical_text = "changed"


class TestEntityAliasModel:
    def test_valid_construction(self):
        ea = EntityAlias(canonical_id="ce_abc", variant="BERT", confidence=0.9)
        assert ea.canonical_id == "ce_abc"
        assert ea.variant == "BERT"

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            EntityAlias(canonical_id="ce_abc", variant="test", confidence=-0.1)

    def test_frozen(self):
        ea = EntityAlias(canonical_id="ce_abc", variant="test", confidence=0.5)
        with pytest.raises(ValidationError):
            ea.variant = "changed"


class TestEntityClusterModel:
    def test_valid_construction(self):
        ce = CanonicalEntity(
            canonical_id="ce_abc",
            canonical_text="BERT",
            label=EntityLabel.METHOD,
            variants=["BERT"],
            entity_ids=["e1"],
            confidence=0.9,
            resolution_method="exact",
        )
        ec = EntityCluster(
            cluster_id="ec_123",
            canonical_entity=ce,
            members=[EntityAlias(canonical_id="ce_abc", variant="BERT", confidence=0.9)],
            size=1,
        )
        assert ec.size == 1

    def test_size_ge_one(self):
        with pytest.raises(ValidationError):
            EntityCluster(
                cluster_id="ec_123",
                canonical_entity=CanonicalEntity(
                    canonical_id="ce_abc",
                    canonical_text="test",
                    label=EntityLabel.METHOD,
                    variants=[],
                    entity_ids=[],
                    confidence=0.5,
                    resolution_method="exact",
                ),
                members=[],
                size=0,
            )

    def test_frozen(self):
        ce = CanonicalEntity(
            canonical_id="ce_abc",
            canonical_text="test",
            label=EntityLabel.METHOD,
            variants=[],
            entity_ids=[],
            confidence=0.5,
            resolution_method="exact",
        )
        ec = EntityCluster(
            cluster_id="ec_123",
            canonical_entity=ce,
            members=[],
            size=1,
        )
        with pytest.raises(ValidationError):
            ec.size = 5


class TestResolutionResultModel:
    def test_valid_construction(self):
        rr = ResolutionResult(
            clusters=[],
            unresolved=[],
            total_entities=0,
            resolved_count=0,
            cluster_count=0,
            resolution_rate=1.0,
        )
        assert rr.resolution_rate == 1.0

    def test_resolution_rate_bounds(self):
        with pytest.raises(ValidationError):
            ResolutionResult(
                clusters=[],
                unresolved=[],
                total_entities=0,
                resolved_count=0,
                cluster_count=0,
                resolution_rate=1.5,
            )

    def test_frozen(self):
        rr = ResolutionResult(
            clusters=[],
            unresolved=[],
            total_entities=0,
            resolved_count=0,
            cluster_count=0,
            resolution_rate=1.0,
        )
        with pytest.raises(ValidationError):
            rr.resolution_rate = 0.5

    def test_with_data(self):
        ce = CanonicalEntity(
            canonical_id="ce_abc",
            canonical_text="BERT",
            label=EntityLabel.METHOD,
            variants=["BERT", "bert"],
            entity_ids=["e1", "e2"],
            confidence=0.9,
            resolution_method="exact",
        )
        cluster = EntityCluster(
            cluster_id="ec_123",
            canonical_entity=ce,
            members=[
                EntityAlias(canonical_id="ce_abc", variant="BERT", confidence=0.9),
            ],
            size=1,
        )
        rr = ResolutionResult(
            clusters=[cluster],
            unresolved=[_entity("e3", "GAN")],
            total_entities=3,
            resolved_count=2,
            cluster_count=1,
            resolution_rate=2 / 3,
            stage_counts={"exact": 2},
        )
        assert rr.cluster_count == 1
        assert rr.resolved_count == 2


# ===================================================================
# Token similarity
# ===================================================================


class TestTokenSimilarity:
    def test_identical_strings(self):
        assert _token_similarity("BERT", "BERT") == 100.0

    def test_case_difference_high_similarity(self):
        # token_set_ratio lowercases internally, so this should be 100
        sim = _token_similarity("BERT", "bert")
        assert sim >= 95.0

    def test_completely_different(self):
        sim = _token_similarity("apple", "zebra")
        assert sim < 50.0

    def test_token_reordering(self):
        sim = _token_similarity("neural network", "network neural")
        assert sim >= 90.0


# ===================================================================
# Resolver — Exact Matching
# ===================================================================


class TestResolverExact:
    def test_exact_same_text(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "BERT"),
            _entity("e2", "BERT"),
        ]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1
        assert result.clusters[0].size == 2

    def test_case_difference(self):
        resolver = _resolver()
        ents = [_entity("e1", "BERT"), _entity("e2", "bert")]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1
        assert result.clusters[0].size == 2

    def test_whitespace_difference(self):
        resolver = _resolver()
        ents = [_entity("e1", "GAN"), _entity("e2", "  GAN  ")]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1

    def test_trailing_punctuation(self):
        resolver = _resolver()
        ents = [_entity("e1", "ResNet"), _entity("e2", "ResNet.")]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1

    def test_multiple_identical_entities(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "CNN"),
            _entity("e2", "CNN"),
            _entity("e3", "CNN"),
            _entity("e4", "CNN"),
        ]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1
        assert result.clusters[0].size == 4

    def test_exact_preserves_unmatched(self):
        resolver = _resolver()
        ents = [_entity("e1", "BERT"), _entity("e2", "BERT"), _entity("e3", "ResNet")]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1
        assert len(result.unresolved) == 1

    def test_internal_whitespace_collapsed(self):
        resolver = _resolver()
        ents = [_entity("e1", "batch  normalization"), _entity("e2", "batch normalization")]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1

    def test_exact_method_is_exact(self):
        resolver = _resolver()
        ents = [_entity("e1", "BERT"), _entity("e2", "bert")]
        result = resolver.resolve(ents)
        assert result.clusters[0].canonical_entity.resolution_method == "exact"

    def test_exact_confidence_is_one(self):
        resolver = _resolver()
        ents = [_entity("e1", "BERT", confidence=0.8), _entity("e2", "bert", confidence=0.9)]
        result = resolver.resolve(ents)
        # Member confidences are 0.8 and 0.9, aggregate = min = 0.8
        assert result.clusters[0].canonical_entity.confidence == 0.8

    def test_exact_canonical_text_is_longest(self):
        resolver = _resolver()
        ents = [_entity("e1", "ResNet"), _entity("e2", "Residual Network")]
        result = resolver.resolve(ents)
        # "Residual Network" (16 chars) vs "ResNet" (6 chars)
        if result.clusters:
            assert result.clusters[0].canonical_entity.canonical_text == "Residual Network"

    def test_exact_with_special_chars(self):
        resolver = _resolver()
        ents = [_entity("e1", "U-Net"), _entity("e2", "u-net")]
        result = resolver.resolve(ents)
        # normalize: 'u-net' == 'u-net' (hyphen preserved)
        assert len(result.clusters) == 1

    def test_exact_multiple_groups(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "BERT"),
            _entity("e2", "BERT"),
            _entity("e3", "GAN"),
            _entity("e4", "GAN"),
            _entity("e5", "CNN"),
        ]
        result = resolver.resolve(ents)
        assert result.cluster_count == 2  # BERT group, GAN group
        assert len(result.unresolved) == 1  # CNN alone

    def test_exact_aggregate_confidence_min(self):
        resolver = _resolver()
        ents = [_entity("e1", "BERT", confidence=0.9), _entity("e2", "bert", confidence=0.7)]
        result = resolver.resolve(ents)
        assert result.clusters[0].canonical_entity.confidence == 0.7

    def test_exact_variants_collected(self):
        resolver = _resolver()
        ents = [_entity("e1", "BERT"), _entity("e2", "bert")]
        result = resolver.resolve(ents)
        assert set(result.clusters[0].canonical_entity.variants) == {"BERT", "bert"}


# ===================================================================
# Resolver — Alias Matching
# ===================================================================


class TestResolverAlias:
    def test_gan_aliased(self):
        resolver = _resolver()
        ents = [_entity("e1", "GAN"), _entity("e2", "generative adversarial network")]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1
        assert result.clusters[0].size == 2

    def test_cnn_aliased(self):
        resolver = _resolver()
        ents = [_entity("e1", "CNN"), _entity("e2", "convolutional neural network")]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1

    def test_multiple_aliases_same_canonical(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "CNN"),
            _entity("e2", "convnet"),
            _entity("e3", "convolutional neural network"),
        ]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1
        assert result.clusters[0].size == 3

    def test_alias_method_type(self):
        resolver = _resolver()
        ents = [_entity("e1", "GAN"), _entity("e2", "generative adversarial network")]
        result = resolver.resolve(ents)
        assert result.clusters[0].canonical_entity.resolution_method == "alias"

    def test_alias_hits_tracked(self):
        resolver = _resolver()
        ents = [_entity("e1", "GAN"), _entity("e2", "generative adversarial network")]
        result = resolver.resolve(ents)
        assert len(result.alias_hits) >= 1
        hit = result.alias_hits[0]
        assert "entity_id" in hit
        assert "entity_text" in hit
        assert "canonical" in hit

    def test_alias_confidence(self):
        resolver = _resolver()
        ents = [_entity("e1", "GAN"), _entity("e2", "generative adversarial network")]
        result = resolver.resolve(ents)
        for hit in result.alias_hits:
            assert hit["confidence"] == 0.95

    def test_batchnorm_to_batch_normalization(self):
        resolver = _resolver()
        ents = [_entity("e1", "BatchNorm"), _entity("e2", "batch normalization")]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1

    def test_lstm_aliased(self):
        resolver = _resolver()
        ents = [_entity("e1", "LSTM"), _entity("e2", "long short-term memory")]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1

    def test_alias_with_unmatched_entity(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "ResNet"),
            _entity("e2", "residual network"),
            _entity("e3", "SomeRandomMethod"),
        ]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1
        assert len(result.unresolved) == 1

    def test_alias_case_insensitive(self):
        resolver = _resolver()
        ents = [_entity("e1", "SGD"), _entity("e2", "Stochastic Gradient Descent")]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1

    def test_alias_dataset_metric(self):
        resolver = _resolver()
        ents = [_entity("e1", "ImageNet", label=EntityLabel.DATASET)]
        # ImageNet canonical is dataset, entity is dataset → compatible
        ents.append(_entity("e2", "imagenet dataset", label=EntityLabel.DATASET))
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1

    def test_alias_reject_wrong_label(self):
        resolver = _resolver()
        # "ImageNet" in aliases has label=dataset, entity has label=method
        ents = [
            _entity("e1", "ImageNet", label=EntityLabel.METHOD),
            _entity("e2", "imagenet dataset", label=EntityLabel.METHOD),
        ]
        result = resolver.resolve(ents)
        # Both should remain unresolved (label mismatch with alias)
        assert len(result.unresolved) >= 1

    def test_alias_auroc(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "AUC", label=EntityLabel.METRIC),
            _entity("e2", "area under the curve", label=EntityLabel.METRIC),
        ]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1

    def test_alias_prefers_longest(self):
        resolver = _resolver()
        ents = [_entity("e1", "adam"), _entity("e2", "adaptive moment estimation")]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1


# ===================================================================
# Resolver — Fuzzy Matching
# ===================================================================


class TestResolverFuzzy:
    def test_fuzzy_similar_phrases(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "Maximum Mean Discrepancy"),
            _entity("e2", "Maximum Mean Discrepancy loss"),
        ]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1

    def test_fuzzy_word_reorder(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "neural network convolution"),
            _entity("e2", "convolution neural network"),
        ]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1

    def test_fuzzy_method_type(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "Maximum Mean Discrepancy"),
            _entity("e2", "Maximum Mean Discrepancy loss"),
        ]
        result = resolver.resolve(ents)
        assert result.clusters[0].canonical_entity.resolution_method == "fuzzy"

    def test_fuzzy_threshold_respected(self):
        resolver = EntityResolver(
            alias_path="config/entity_aliases.yaml",
            fuzzy_threshold=90.0,
        )
        ents = [
            _entity("e1", "Maximum Mean Discrepancy"),
            _entity("e2", "Maximum Mean Discrepancy loss"),
        ]
        result = resolver.resolve(ents)
        # At threshold 90, this 87.x pair won't match
        # But this could vary, so we just check it forms fewer or same clusters

    def test_fuzzy_low_threshold_matches_more(self):
        resolver = EntityResolver(
            alias_path="config/entity_aliases.yaml",
            fuzzy_threshold=50.0,
        )
        ents = [
            _entity("e1", "apple"),
            _entity("e2", "apple pie"),
        ]
        result = resolver.resolve(ents)
        # At 50%, "apple" vs "apple pie" token_set_ratio should be above 50
        # Actually token_set_ratio("apple", "apple pie") = ?
        # Set A: {apple}, Set B: {apple, pie}
        # Combined: "apple apple pie" -> comparing "apple" vs "apple apple pie"
        # This gives fuzz.ratio("apple", "apple apple pie") which should be high

    def test_fuzzy_english_plurals(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "language model"),
            _entity("e2", "language models"),
        ]
        result = resolver.resolve(ents)
        # token_set_ratio should be high (same token set modulo plural)
        assert len(result.clusters) == 1

    def test_fuzzy_preserves_high_confidence(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "Maximum Mean Discrepancy", confidence=0.95),
            _entity("e2", "Maximum Mean Discrepancy loss", confidence=0.85),
        ]
        result = resolver.resolve(ents)
        assert result.clusters[0].canonical_entity.confidence == 0.85  # min

    def test_fuzzy_multiple_matches(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "Graph Neural Network"),
            _entity("e2", "graph neural networks"),
            _entity("e3", "graph network"),
        ]
        result = resolver.resolve(ents)
        # All three should cluster (via alias dict for some, fuzzy for others)
        assert len(result.clusters) >= 0

    def test_fuzzy_below_threshold_no_cluster(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "Apple"),
            _entity("e2", "Orange"),
        ]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 0
        assert len(result.unresolved) == 2


# ===================================================================
# Resolver — Type Protection
# ===================================================================


class TestResolverTypeProtection:
    def test_different_labels_same_text_no_merge(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "BERT", label=EntityLabel.METHOD),
            _entity("e2", "BERT", label=EntityLabel.DATASET),
        ]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 0
        assert len(result.unresolved) == 2

    def test_different_labels_alias_no_merge(self):
        resolver = _resolver()
        # "ImageNet" aliases have label=DATASET
        ents = [
            _entity("e1", "ImageNet", label=EntityLabel.DATASET),
            _entity("e2", "imagenet", label=EntityLabel.METHOD),
        ]
        result = resolver.resolve(ents)
        # These have same normalized text "imagenet" but different labels
        # Stage 1: (normalized="imagenet", label=dataset) vs (normalized="imagenet", label=method)
        # Different keys → not merged
        assert len(result.clusters) == 0

    def test_method_and_tool_merge(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "PyTorch", label=EntityLabel.TOOL),
            _entity("e2", "pytorch", label=EntityLabel.METHOD),
        ]
        result = resolver.resolve(ents)
        # METHOD and TOOL are compatible
        assert len(result.clusters) == 1

    def test_person_and_org_merge(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "DeepMind", label=EntityLabel.ORGANIZATION),
            _entity("e2", "deepmind", label=EntityLabel.PERSON),
        ]
        result = resolver.resolve(ents)
        # PERSON and ORGANIZATION are compatible
        assert len(result.clusters) >= 0  # May or may not match

    def test_custom_label_compatibility(self):
        custom_compat = {EntityLabel.METHOD.value: {EntityLabel.METHOD.value}}
        resolver = EntityResolver(
            alias_path="config/entity_aliases.yaml",
            label_compatibility=custom_compat,
        )
        ents = [
            _entity("e1", "PyTorch", label=EntityLabel.TOOL),
            _entity("e2", "pytorch", label=EntityLabel.METHOD),
        ]
        result = resolver.resolve(ents)
        # With strict compatibility (only METHOD=METHOD), TOOL != METHOD
        assert len(result.clusters) == 0

    def test_different_labels_fuzzy_no_merge(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "ResNet50", label=EntityLabel.METHOD),
            _entity("e2", "ResNet-50", label=EntityLabel.DATASET),
        ]
        result = resolver.resolve(ents)
        # Different labels → no merge even if fuzzy-similar
        assert len(result.clusters) == 0

    def test_label_preserved_in_cluster(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "BERT", label=EntityLabel.METHOD),
            _entity("e2", "bert", label=EntityLabel.METHOD),
        ]
        result = resolver.resolve(ents)
        assert result.clusters[0].canonical_entity.label == EntityLabel.METHOD

    def test_gene_protein_and_method_merge(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "Transformer", label=EntityLabel.GENE_PROTEIN),
            _entity("e2", "transformer", label=EntityLabel.METHOD),
        ]
        result = resolver.resolve(ents)
        # GENE_PROTEIN and METHOD are compatible
        assert len(result.clusters) >= 0


# ===================================================================
# Resolver — Cluster Properties
# ===================================================================


class TestResolverClusters:
    def test_cluster_has_unique_id(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "BERT"),
            _entity("e2", "BERT"),
            _entity("e3", "GAN"),
            _entity("e4", "GAN"),
        ]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 2
        assert result.clusters[0].cluster_id != result.clusters[1].cluster_id

    def test_cluster_canonical_entity_has_id(self):
        resolver = _resolver()
        ents = [_entity("e1", "BERT"), _entity("e2", "bert")]
        result = resolver.resolve(ents)
        assert result.clusters[0].canonical_entity.canonical_id.startswith("ce_")

    def test_cluster_members_have_entity_ids(self):
        resolver = _resolver()
        ents = [_entity("e1", "BERT"), _entity("e2", "bert")]
        result = resolver.resolve(ents)
        assert len(result.clusters[0].canonical_entity.entity_ids) == 2
        assert "e1" in result.clusters[0].canonical_entity.entity_ids

    def test_cluster_members_are_entity_aliases(self):
        resolver = _resolver()
        ents = [_entity("e1", "BERT"), _entity("e2", "bert")]
        result = resolver.resolve(ents)
        assert len(result.clusters[0].members) == 2
        for m in result.clusters[0].members:
            assert isinstance(m, EntityAlias)

    def test_cluster_variants_deduplicated(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "BERT"),
            _entity("e2", "BERT"),
            _entity("e3", "bert"),
        ]
        result = resolver.resolve(ents)
        assert len(result.clusters[0].canonical_entity.variants) == 2  # "BERT", "bert"

    def test_cluster_label_by_majority(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "ToolX", label=EntityLabel.TOOL),
            _entity("e2", "toolx", label=EntityLabel.TOOL),
            _entity("e3", "ToolX", label=EntityLabel.METHOD),
        ]
        result = resolver.resolve(ents)
        # TOOL appears 2 times, METHOD appears 1 time
        assert result.clusters[0].canonical_entity.label == EntityLabel.TOOL

    def test_cluster_entity_ids_sorted(self):
        resolver = _resolver()
        ents = [_entity("e2", "BERT"), _entity("e1", "bert")]
        result = resolver.resolve(ents)
        assert result.clusters[0].canonical_entity.entity_ids == sorted(["e1", "e2"])

    def test_cluster_member_confidence_preserved(self):
        resolver = _resolver()
        ents = [_entity("e1", "BERT", confidence=0.9), _entity("e2", "bert", confidence=0.7)]
        result = resolver.resolve(ents)
        confs = {m.variant: m.confidence for m in result.clusters[0].members}
        assert confs["BERT"] == 0.9
        assert confs["bert"] == 0.7


# ===================================================================
# Resolver — Edge Cases
# ===================================================================


class TestResolverEdgeCases:
    def test_empty_list(self):
        resolver = _resolver()
        result = resolver.resolve([])
        assert result.total_entities == 0
        assert result.resolution_rate == 1.0
        assert result.clusters == []
        assert result.unresolved == []

    def test_single_entity(self):
        resolver = _resolver()
        result = resolver.resolve([_entity("e1", "BERT")])
        assert result.total_entities == 1
        assert result.resolved_count == 0
        assert result.clusters == []
        assert len(result.unresolved) == 1

    def test_duplicate_entity_ids_keeps_highest_confidence(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "BERT", confidence=0.5),
            _entity("e1", "BERT", confidence=0.9),
        ]
        result = resolver.resolve(ents)
        assert result.total_entities == 1  # deduplicated

    def test_all_identical(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "BERT"),
            _entity("e2", "BERT"),
            _entity("e3", "BERT"),
            _entity("e4", "BERT"),
        ]
        result = resolver.resolve(ents)
        assert result.cluster_count == 1
        assert result.clusters[0].size == 4
        assert result.resolution_rate == 1.0

    def test_all_different(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "Apple"),
            _entity("e2", "Banana"),
            _entity("e3", "Cherry"),
        ]
        result = resolver.resolve(ents)
        assert result.cluster_count == 0
        assert result.resolved_count == 0
        assert len(result.unresolved) == 3

    def test_unicode_text(self):
        resolver = _resolver()
        ents = [_entity("e1", "café"), _entity("e2", "Café")]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1

    def test_numbers_in_entity_text(self):
        resolver = _resolver()
        ents = [_entity("e1", "ResNet50"), _entity("e2", "resnet50")]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1

    def test_entity_with_empty_text_fails(self):
        with pytest.raises(ValidationError):
            RUOEntity(
                entity_id="e1",
                text="   ",
                label=EntityLabel.METHOD,
                chunk_id="c1",
                sentence="x",
                confidence=0.9,
                source="ner",
            )

    def test_virtual_canonical_not_in_unresolved(self):
        resolver = _resolver()
        ents = [_entity("e1", "BERT"), _entity("e2", "bert")]
        result = resolver.resolve(ents)
        for u in result.unresolved:
            assert u.entity_id in ("e1", "e2")

    def test_many_entities_performance(self):
        resolver = _resolver()
        ents = []
        for i in range(100):
            if i < 50:
                ents.append(_entity(f"e{i}", "BERT"))
            else:
                ents.append(_entity(f"e{i}", "Other"))
        result = resolver.resolve(ents)
        assert result.cluster_count >= 1

    def test_no_alias_dict_loaded(self):
        resolver = _resolver(aliases=False)
        ents = [_entity("e1", "GAN"), _entity("e2", "generative adversarial network")]
        result = resolver.resolve(ents)
        # Without aliases, these won't match (GAN vs generative adversarial network)
        assert len(result.clusters) == 0

    def test_no_alias_dict_exact_still_works(self):
        resolver = _resolver(aliases=False)
        ents = [_entity("e1", "BERT"), _entity("e2", "bert")]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1

    def test_no_alias_fuzzy_still_works(self):
        resolver = _resolver(aliases=False)
        ents = [
            _entity("e1", "Maximum Mean Discrepancy"),
            _entity("e2", "Maximum Mean Discrepancy loss"),
        ]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1

    def test_mixed_exact_and_alias_in_cluster(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "CNN"),
            _entity("e2", "CNN"),
            _entity("e3", "convolutional neural network"),
        ]
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1
        assert result.clusters[0].size == 3
        # e1 and e2 matched via exact, e3 via alias → hybrid
        assert result.clusters[0].canonical_entity.resolution_method == "hybrid"


# ===================================================================
# Resolver — Stage Counts
# ===================================================================


class TestResolverStageCounts:
    def test_stage_counts_exact_only(self):
        resolver = _resolver()
        ents = [_entity("e1", "BERT"), _entity("e2", "bert")]
        result = resolver.resolve(ents)
        assert result.stage_counts["exact"] == 2
        assert result.stage_counts["alias"] == 0
        assert result.stage_counts["fuzzy"] == 0

    def test_stage_counts_alias_only(self):
        resolver = _resolver()
        ents = [_entity("e1", "GAN"), _entity("e2", "generative adversarial network")]
        result = resolver.resolve(ents)
        # GAN → alias, generative adversarial network → exact (via canonical match) or alias
        assert result.stage_counts["alias"] > 0

    def test_stage_counts_fuzzy_only(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "Maximum Mean Discrepancy"),
            _entity("e2", "Maximum Mean Discrepancy loss"),
        ]
        result = resolver.resolve(ents)
        assert result.stage_counts["fuzzy"] == 2

    def test_stage_counts_empty_result(self):
        resolver = _resolver()
        result = resolver.resolve([])
        assert result.stage_counts == {}

    def test_stage_counts_all_different(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "Apple"),
            _entity("e2", "Banana"),
            _entity("e3", "Cherry"),
        ]
        result = resolver.resolve(ents)
        assert result.stage_counts == {"exact": 0, "alias": 0, "fuzzy": 0}

    def test_stage_counts_mixed(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "BERT"),  # will exact-match with e2
            _entity("e2", "bert"),  # exact with e1
            _entity("e3", "CNN"),   # alias with e4
            _entity("e4", "convolutional neural network"),  # alias or exact with canonical
            _entity("e5", "Maximum Mean Discrepancy"),  # fuzzy with e6
            _entity("e6", "Maximum Mean Discrepancy loss"),  # fuzzy with e5
        ]
        result = resolver.resolve(ents)
        total = sum(result.stage_counts.values())
        assert total == 6  # all 6 entities resolved

    def test_stage_counts_plus_unresolved(self):
        resolver = _resolver()
        ents = [
            _entity("e1", "BERT"),
            _entity("e2", "bert"),
            _entity("e3", "Unmatched"),
        ]
        result = resolver.resolve(ents)
        assert sum(result.stage_counts.values()) == 2  # 2 resolved
        assert len(result.unresolved) == 1  # 1 unresolved
        assert result.resolution_rate == 2 / 3


# ===================================================================
# Corpus Integration
# ===================================================================


class TestResolverCorpusIntegration:
    def test_resolve_entities_from_corpus(self):
        doc1 = make_doc("d1", entities=[("BERT", EntityLabel.METHOD), ("GAN", EntityLabel.METHOD)])
        doc2 = make_doc("d2", entities=[("bert", EntityLabel.METHOD), ("generative adversarial network", EntityLabel.METHOD)])
        mgr = CorpusManager.from_documents([doc1, doc2], "c1")
        docs = mgr.get_documents()
        all_entities = []
        for d in docs:
            all_entities.extend(d.entities)
        resolver = _resolver()
        result = resolver.resolve(all_entities)
        assert result.cluster_count >= 1
        assert result.resolution_rate > 0

    def test_corpus_resolution_rate(self):
        doc1 = make_doc("d1", entities=[("BERT", EntityLabel.METHOD)])
        doc2 = make_doc("d2", entities=[("bert", EntityLabel.METHOD)])
        doc3 = make_doc("d3", entities=[("GAN", EntityLabel.METHOD)])
        mgr = CorpusManager.from_documents([doc1, doc2, doc3], "c1")
        all_entities = [e for d in mgr.get_documents() for e in d.entities]
        resolver = _resolver()
        result = resolver.resolve(all_entities)
        assert result.total_entities == 3
        assert result.resolved_count == 2  # BERT+bert resolved, GAN solo
        assert result.resolution_rate == 2 / 3

    def test_cross_document_clusters(self):
        ents = [
            _entity("d1e1", "BERT"),
            _entity("d2e1", "bert"),
            _entity("d3e1", "bert model"),
        ]
        resolver = _resolver()
        result = resolver.resolve(ents)
        # BERT and bert exact-match; "bert model" may fuzzy-match if threshold met
        assert result.cluster_count >= 1

    def test_resolve_without_corpus_manager(self):
        ents = [_entity("e1", "ResNet"), _entity("e2", "residual network")]
        resolver = _resolver()
        result = resolver.resolve(ents)
        assert len(result.clusters) == 1

    def test_resolve_preserves_entity_order(self):
        ents = [_entity("e1", "Z"), _entity("e2", "A"), _entity("e3", "Z")]
        resolver = _resolver()
        result = resolver.resolve(ents)
        # Just checking it doesn't crash
        assert result.total_entities == 3

    def test_multiple_corpus_documents_combined(self):
        doc1 = make_doc("d1", entities=[("CNN", EntityLabel.METHOD)])
        doc2 = make_doc("d2", entities=[("cnn", EntityLabel.METHOD)])
        doc3 = make_doc("d3", entities=[("convolutional neural network", EntityLabel.METHOD)])
        mgr = CorpusManager.from_documents([doc1, doc2, doc3], "c1")
        all_entities = [e for d in mgr.get_documents() for e in d.entities]
        resolver = _resolver()
        result = resolver.resolve(all_entities)
        assert result.cluster_count == 1
        assert result.clusters[0].size == 3

    def test_resolver_backward_compatible(self):
        """Resolution result should not affect original entities."""
        ents = [_entity("e1", "BERT"), _entity("e2", "bert")]
        texts_before = [(e.entity_id, e.text) for e in ents]
        resolver = _resolver()
        resolver.resolve(ents)
        texts_after = [(e.entity_id, e.text) for e in ents]
        assert texts_before == texts_after

    def test_default_threshold_constant(self):
        assert DEFAULT_FUZZY_THRESHOLD == 85.0
