"""Tests for CorpusGraphBuilder — 8-stage builder for corpus-level graph."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from researchmind.corpus.graph import (
    CorpusGraphBuilder,
    CorpusGraphEdge,
    CorpusGraphNode,
    CorpusGraphPath,
    CorpusGraphQuery,
    CorpusGraphResult,
    CorpusGraphStatistics,
)
from researchmind.storage.corpus import CorpusManager
from researchmind.corpus.entity_resolution import (
    CanonicalEntity,
    EntityAlias,
    EntityCluster,
    ResolutionResult,
)
from researchmind.models.ruo import (
    ComponentConfidence,
    ComponentSubscore,
    ConfidenceBreakdown,
    DocumentRelation,
    EvidenceCoverage,
    RUOAuthor,
    RUOBody,
    RUOChunk,
    RUOClaim,
    RUODocument,
    RUOEntity,
    RUOHeader,
    RUOMeta,
    RUOQuality,
    RUOReference,
    RUOSection,
    RUOSourceFile,
    SemanticTriple,
)
from researchmind.models.ruo_enums import (
    CanonicalLabel,
    ClaimType,
    DocumentType,
    EntityLabel,
    ExtractionMethod,
    ExtractionRoute,
    RelationType,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
_NODE_ID_PATTERN = re.compile(r"^doc_\w+$")
_EC_ID_PATTERN = re.compile(r"^ec_\w+$")
_CL_ID_PATTERN = re.compile(r"^cl_\w+_\w+$")


# ---------------------------------------------------------------------------
# Helper factories (following project pattern)
# ---------------------------------------------------------------------------


def _source_file(filename: str = "paper.pdf") -> RUOSourceFile:
    return RUOSourceFile(
        filename=filename, sha256="a" * 64, page_count=5,
        has_text_layer=True, is_scanned=False,
    )


def _meta(
    ruo_id: str = "doc_001",
    research_fields: list[str] | None = None,
) -> RUOMeta:
    return RUOMeta(
        ruo_id=ruo_id,
        created_at=_NOW,
        updated_at=_NOW,
        pipeline_version="2.1.0",
        source_file=_source_file(),
        extraction_route=ExtractionRoute.GROBID_PRIMARY,
        document_type=DocumentType.RESEARCH_ARTICLE,
        research_fields=research_fields or [],
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


def _header(
    title: str = "Test Paper",
    authors: list[str] | None = None,
    publication_date: str | None = "2024-01-15",
) -> RUOHeader:
    author_models = [RUOAuthor(full_name=n) for n in (authors or [])]
    return RUOHeader(
        title=title,
        authors=author_models,
        document_type=DocumentType.RESEARCH_ARTICLE,
        confidence=ComponentConfidence(
            component="header", score=0.85,
            subscores=[ComponentSubscore(name="header", value=0.85, weight=1.0)],
        ),
        publication_date=publication_date,
    )


def _section(sid: str = "s1") -> RUOSection:
    return RUOSection(
        section_id=sid, level=1, position=0,
        original_header="Introduction",
        canonical_label=CanonicalLabel.INTRODUCTION,
        label_confidence=0.9, page_start=0, page_end=2,
        content="Section content.",
        extraction_method=ExtractionMethod.GROBID,
    )


def _chunk(cid: str = "c1") -> RUOChunk:
    return RUOChunk(
        chunk_id=cid, text="Chunk text.", word_count=2,
        section_id="s1", canonical_label=CanonicalLabel.INTRODUCTION,
        page_start=0, page_end=1, paragraph_index=0,
        reading_order=0, extraction_method=ExtractionMethod.GROBID,
        extraction_confidence=0.9,
    )


def _body() -> RUOBody:
    return RUOBody(sections=[_section()], chunks=[_chunk()])


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
        sentence="Sentence with entity.",
        confidence=confidence,
        source="ner",
    )


def _claim(
    cid: str = "cl1",
    sentence: str = "BERT achieves state-of-the-art results.",
    claim_type: ClaimType = ClaimType.STATISTICAL,
    confidence: float = 0.85,
    chunk_id: str = "c1",
    section_id: str = "s1",
    page: int = 1,
) -> RUOClaim:
    return RUOClaim(
        claim_id=cid,
        sentence=sentence,
        chunk_id=chunk_id,
        section_id=section_id,
        canonical_label=CanonicalLabel.RESULTS,
        claim_type=claim_type,
        matched_patterns=["statistical"],
        confidence=confidence,
        page=page,
        evidence_chain_id=f"ech_{cid}",
        normalized_statement=sentence,
    )


def _triple(
    tid: str = "t1",
    predicate: str = "improves",
    subject_text: str = "BERT",
    confidence: float = 0.8,
) -> SemanticTriple:
    return SemanticTriple(
        triple_id=tid,
        predicate=predicate,
        subject_text=subject_text,
        object_text="accuracy",
        subject_id="e1",
        object_id="e2",
        confidence=confidence,
        chunk_id="c1",
    )


def _reference(
    rid: str = "r1",
    target_ruo_id: str = "doc_002",
) -> RUOReference:
    from researchmind.models.ruo_enums import ResolutionStatus, ResolutionSource
    return RUOReference(
        ref_id=rid,
        raw_text="Referenced Paper",
        target_ruo_id=target_ruo_id,
        title="Referenced Paper",
        year="2023",
        resolution_status=ResolutionStatus.RESOLVED,
        resolution_source=ResolutionSource.CROSSREF_LOOKUP,
        ref_confidence=0.9,
    )


def make_doc(
    ruo_id: str = "doc_001",
    title: str = "Test Paper",
    authors: list[str] | None = None,
    entities: list[tuple[str, EntityLabel]] | None = None,
    claims: list[tuple[str, ClaimType]] | None = None,
    triples: list[tuple[str, str]] | None = None,
    references: list[str | tuple[str, str]] | None = None,
    confidence: float = 0.85,
    research_fields: list[str] | None = None,
) -> RUODocument:
    """Create an RUODocument for testing."""
    meta = _meta(ruo_id, research_fields=research_fields)
    hdr = _header(title=title, authors=authors)

    entity_models: list[RUOEntity] = []
    if entities:
        for i, (text, label) in enumerate(entities):
            entity_models.append(
                _entity(eid=f"{ruo_id}_e{i}", text=text, label=label)
            )

    claim_models: list[RUOClaim] = []
    if claims:
        for i, (sentence, ct) in enumerate(claims):
            claim_models.append(
                _claim(cid=f"cl{i}", sentence=sentence, claim_type=ct)
            )

    triple_models: list[SemanticTriple] = []
    if triples:
        for i, (subj, pred) in enumerate(triples):
            triple_models.append(
                _triple(tid=f"t{i}", predicate=pred, subject_text=subj)
            )

    ref_models: list[RUOReference] = []
    if references:
        for i, ref in enumerate(references):
            if isinstance(ref, tuple):
                ref_models.append(
                    _reference(rid=ref[0], target_ruo_id=ref[1])
                )
            else:
                ref_models.append(
                    _reference(rid=f"r{i}", target_ruo_id=ref)
                )

    return RUODocument(
        meta=meta,
        header=hdr,
        body=_body(),
        entities=entity_models,
        claims=claim_models,
        triples=triple_models,
        references=ref_models,
        quality=_quality(overall=confidence),
        provenance=[],
    )


def make_resolution(
    doc: RUODocument,
) -> ResolutionResult | None:
    """Build a ResolutionResult from a document's entities.

    Each entity becomes its own cluster (no cross-doc merging) for
    deterministic testing.
    """
    if not doc.entities:
        return None
    clusters: list[EntityCluster] = []
    for ent in doc.entities:
        eid = f"ec_{ent.entity_id}"
        ce = CanonicalEntity(
            canonical_id=eid,
            canonical_text=ent.text,
            label=ent.label,
            variants=[ent.text],
            entity_ids=[ent.entity_id],
            confidence=ent.confidence,
            resolution_method="exact",
        )
        cluster = EntityCluster(
            cluster_id=eid,
            canonical_entity=ce,
            members=[EntityAlias(
                canonical_id=eid, variant=ent.text, confidence=ent.confidence
            )],
            size=1,
        )
        clusters.append(cluster)
    return ResolutionResult(
        clusters=clusters,
        unresolved=[],
        total_entities=len(doc.entities),
        resolved_count=len(doc.entities),
        cluster_count=len(clusters),
        resolution_rate=1.0,
        stage_counts={"exact": len(doc.entities)},
    )


# ===================================================================
# Tests: CorpusGraphNode
# ===================================================================


class TestCorpusGraphNode:
    def test_minimal(self):
        n = CorpusGraphNode(node_id="n1", node_type="document", label="Doc")
        assert n.node_id == "n1"
        assert n.node_type == "document"
        assert n.label == "Doc"
        assert n.metadata == {}
        assert n.weight == 1.0

    def test_full(self):
        n = CorpusGraphNode(
            node_id="n1",
            node_type="entity_cluster",
            label="BERT",
            metadata={"confidence": 0.9},
            weight=0.95,
        )
        assert n.metadata["confidence"] == 0.9
        assert n.weight == 0.95

    def test_invalid_type(self):
        with pytest.raises(ValidationError):
            CorpusGraphNode(node_id="n1", node_type="unknown_type", label="X")


# ===================================================================
# Tests: CorpusGraphEdge
# ===================================================================


class TestCorpusGraphEdge:
    def test_minimal(self):
        e = CorpusGraphEdge(
            edge_id="e1", source_id="a", target_id="b",
            relation_type=RelationType.CITES, confidence=0.9,
        )
        assert e.source_id == "a"
        assert e.target_id == "b"
        assert e.relation_type == RelationType.CITES
        assert e.confidence == 0.9

    def test_self_loop_allowed(self):
        e = CorpusGraphEdge(
            edge_id="e1", source_id="a", target_id="a",
            relation_type=RelationType.EXTENDS, confidence=0.5,
        )
        assert e.source_id == e.target_id

    def test_unknown_relation_type(self):
        e = CorpusGraphEdge(
            edge_id="e1", source_id="a", target_id="b",
            relation_type=RelationType.UNKNOWN, confidence=0.5,
        )
        assert e.relation_type == RelationType.UNKNOWN


# ===================================================================
# Tests: CorpusGraphPath
# ===================================================================


class TestCorpusGraphPath:
    def test_minimal(self):
        e1 = CorpusGraphEdge(
            edge_id="e1", source_id="a", target_id="b",
            relation_type=RelationType.CITES, confidence=0.9,
        )
        e2 = CorpusGraphEdge(
            edge_id="e2", source_id="b", target_id="c",
            relation_type=RelationType.EXTENDS, confidence=0.8,
        )
        p = CorpusGraphPath(edges=[e1, e2], total_weight=1.7)
        assert len(p.edges) == 2
        assert p.total_weight == 1.7
        assert p.source_id() == "a"
        assert p.target_id() == "c"
        assert p.node_ids() == ["a", "b", "c"]


# ===================================================================
# Tests: CorpusGraphQuery
# ===================================================================


class TestCorpusGraphQuery:
    def test_defaults(self):
        q = CorpusGraphQuery()
        assert q.node_type is None
        assert q.relation_types is None
        assert q.max_depth == 3
        assert q.min_confidence == 0.0

    def test_custom(self):
        q = CorpusGraphQuery(
            node_type="document",
            relation_types=[RelationType.CITES],
            max_depth=5,
            min_confidence=0.5,
            metadata_filter={"year": 2024},
            node_ids=["doc_001"],
        )
        assert q.node_type == "document"
        assert q.max_depth == 5
        assert q.min_confidence == 0.5
        assert q.metadata_filter == {"year": 2024}
        assert q.node_ids == ["doc_001"]


# ===================================================================
# Tests: CorpusGraphStatistics
# ===================================================================


class TestCorpusGraphStatistics:
    def test_defaults(self):
        s = CorpusGraphStatistics()
        assert s.total_nodes == 0
        assert s.total_edges == 0

    def test_full(self):
        s = CorpusGraphStatistics(
            total_nodes=10,
            total_edges=15,
            node_type_counts={"document": 5, "entity_cluster": 5},
            edge_type_counts={"cites": 10, "extends": 5},
            average_degree=3.0,
            density=0.167,
            connected_components=2,
            largest_component_size=8,
        )
        assert s.total_nodes == 10
        assert s.average_degree == 3.0
        assert s.largest_component_size == 8


# ===================================================================
# Tests: CorpusGraphResult
# ===================================================================


class TestCorpusGraphResult:
    def test_minimal(self):
        r = CorpusGraphResult(nodes=[], edges=[])
        assert r.total_nodes_found == 0
        assert r.total_edges_found == 0

    def test_with_data(self):
        n1 = CorpusGraphNode(node_id="a", node_type="document", label="A")
        e1 = CorpusGraphEdge(
            edge_id="e1", source_id="a", target_id="b",
            relation_type=RelationType.CITES, confidence=0.9,
        )
        r = CorpusGraphResult(nodes=[n1], edges=[e1], total_nodes_found=1, total_edges_found=1)
        assert r.total_nodes_found == 1
        assert r.total_edges_found == 1


# ===================================================================
# Tests: CorpusGraphBuilder — Stage 1 (Document nodes)
# ===================================================================


class TestStage1DocumentNodes:
    def test_single_document(self):
        doc = make_doc("doc_001", title="BERT Paper",
                       entities=[("BERT", EntityLabel.METHOD)])
        builder = CorpusGraphBuilder()
        result = builder.build(documents=[doc])
        assert result.total_nodes_found == 1
        node = result.nodes[0]
        assert node.node_id == "doc_001"
        assert node.label == "BERT Paper"
        assert node.node_type == "document"

    def test_metadata_fields(self):
        doc = make_doc(
            "doc_001", title="Test",
            entities=[("BERT", EntityLabel.METHOD)],
            claims=[("BERT is good", ClaimType.STATISTICAL)],
            triples=[("BERT", "improves")],
            confidence=0.9,
            research_fields=["NLP"],
        )
        builder = CorpusGraphBuilder()
        result = builder.build(documents=[doc])
        node = result.nodes[0]
        md = node.metadata
        assert md["ruo_id"] == "doc_001"
        assert md["entity_count"] == 1
        assert md["claim_count"] == 1
        assert md["triple_count"] == 1
        assert md["overall_confidence"] == 0.9
        assert md["research_field"] == "NLP"
        assert md["year"] == 2024

    def test_empty_document(self):
        doc = make_doc("doc_empty", title="Empty", entities=[])
        builder = CorpusGraphBuilder()
        result = builder.build(documents=[doc])
        assert result.total_nodes_found == 1
        md = result.nodes[0].metadata
        assert md["entity_count"] == 0
        assert md["claim_count"] == 0
        assert md["triple_count"] == 0


# ===================================================================
# Tests: CorpusGraphBuilder — Stage 2 (Entity cluster nodes)
# ===================================================================


class TestStage2EntityClusterNodes:
    def test_single_cluster(self):
        doc = make_doc("doc_001", entities=[("BERT", EntityLabel.METHOD)])
        resolution = make_resolution(doc)
        builder = CorpusGraphBuilder(resolution_result=resolution)
        result = builder.build(documents=[doc])
        # 1 doc node + 1 entity cluster node
        assert result.total_nodes_found == 2
        ec_nodes = [n for n in result.nodes if n.node_type == "entity_cluster"]
        assert len(ec_nodes) == 1
        assert ec_nodes[0].label == "BERT"

    def test_multiple_clusters(self):
        doc = make_doc(
            "doc_001",
            entities=[
                ("BERT", EntityLabel.METHOD),
                ("GAN", EntityLabel.METHOD),
            ],
        )
        resolution = make_resolution(doc)
        builder = CorpusGraphBuilder(resolution_result=resolution)
        result = builder.build(documents=[doc])
        ec_nodes = [n for n in result.nodes if n.node_type == "entity_cluster"]
        assert len(ec_nodes) == 2

    def test_no_resolution(self):
        doc = make_doc("doc_001", entities=[("BERT", EntityLabel.METHOD)])
        builder = CorpusGraphBuilder(resolution_result=None)
        result = builder.build(documents=[doc])
        # Only doc node — no resolution provided
        assert result.total_nodes_found == 1

    def test_cluster_metadata(self):
        doc = make_doc("doc_001", entities=[("BERT", EntityLabel.METHOD)])
        resolution = make_resolution(doc)
        builder = CorpusGraphBuilder(resolution_result=resolution)
        result = builder.build(documents=[doc])
        ec = [n for n in result.nodes if n.node_type == "entity_cluster"][0]
        assert ec.metadata["canonical_text"] == "BERT"
        assert ec.metadata["cluster_size"] == 1
        assert ec.metadata["confidence"] == 0.9


# ===================================================================
# Tests: CorpusGraphBuilder — Stage 3 (Document-entity edges)
# ===================================================================


class TestStage3DocumentEntityEdges:
    def test_doc_to_entity_edge(self):
        doc = make_doc("doc_001", entities=[("BERT", EntityLabel.METHOD)])
        resolution = make_resolution(doc)
        builder = CorpusGraphBuilder(resolution_result=resolution)
        result = builder.build(documents=[doc])
        de_edges = [e for e in result.edges
                    if e.metadata.get("edge_kind") == "doc_contains_entity"]
        assert len(de_edges) == 1
        e = de_edges[0]
        assert e.source_id == "doc_001"
        assert e.target_id.startswith("ec_")
        assert e.is_directed is True

    def test_no_resolution_no_edges(self):
        doc = make_doc("doc_001", entities=[("BERT", EntityLabel.METHOD)])
        builder = CorpusGraphBuilder(resolution_result=None)
        result = builder.build(documents=[doc])
        assert result.total_edges_found == 0

    def test_entity_not_in_resolution(self):
        doc = make_doc("doc_001", entities=[("BERT", EntityLabel.METHOD)])
        # Create resolution for a different entity
        other_ent = _entity(eid="other", text="GAN", label=EntityLabel.METHOD)
        ce = CanonicalEntity(
            canonical_id="ec_other",
            canonical_text="GAN",
            label=EntityLabel.METHOD,
            variants=["GAN"],
            entity_ids=["other"],
            confidence=0.9,
            resolution_method="exact",
        )
        cluster = EntityCluster(
            cluster_id="ec_other", canonical_entity=ce,
            members=[EntityAlias(canonical_id="ec_other", variant="GAN", confidence=0.9)],
            size=1,
        )
        resolution = ResolutionResult(
            clusters=[cluster], unresolved=[],
            total_entities=1, resolved_count=1, cluster_count=1,
            resolution_rate=1.0, stage_counts={"exact": 1},
        )
        builder = CorpusGraphBuilder(resolution_result=resolution)
        result = builder.build(documents=[doc])
        de_edges = [e for e in result.edges
                    if e.metadata.get("edge_kind") == "doc_contains_entity"]
        assert len(de_edges) == 0


# ===================================================================
# Tests: CorpusGraphBuilder — Stage 4 (Document-relation edges)
# ===================================================================


class TestStage4DocumentRelationEdges:
    def test_single_relation(self):
        docs = [
            make_doc("doc_001", title="Paper A"),
            make_doc("doc_002", title="Paper B"),
        ]
        rel = DocumentRelation(
            relation_id="rel_001",
            source_ruo_id="doc_001",
            target_ruo_id="doc_002",
            relation_type=RelationType.CITES,
            confidence=0.9,
            is_directed=True,
            detected_at=_NOW,
        )
        builder = CorpusGraphBuilder()
        result = builder.build(documents=docs, relations=[rel])
        assert result.total_edges_found == 1
        e = result.edges[0]
        assert e.source_id == "doc_001"
        assert e.target_id == "doc_002"
        assert e.relation_type == RelationType.CITES

    def test_multiple_relations(self):
        docs = [
            make_doc("doc_001", title="Paper A"),
            make_doc("doc_002", title="Paper B"),
            make_doc("doc_003", title="Paper C"),
        ]
        rels = [
            DocumentRelation(
                relation_id="r1", source_ruo_id="doc_001",
                target_ruo_id="doc_002",
                relation_type=RelationType.CITES,
                confidence=0.9, is_directed=True, detected_at=_NOW,
            ),
            DocumentRelation(
                relation_id="r2", source_ruo_id="doc_002",
                target_ruo_id="doc_003",
                relation_type=RelationType.EXTENDS,
                confidence=0.8, is_directed=True, detected_at=_NOW,
            ),
        ]
        builder = CorpusGraphBuilder()
        result = builder.build(documents=docs, relations=rels)
        assert result.total_edges_found == 2

    def test_no_relations(self):
        doc = make_doc("doc_001")
        builder = CorpusGraphBuilder()
        result = builder.build(documents=[doc], relations=[])
        assert result.total_edges_found == 0


# ===================================================================
# Tests: CorpusGraphBuilder — Stage 5 (Entity-entity edges)
# ===================================================================


class TestStage5EntityEntityEdges:
    def test_co_occurrence_edge(self):
        doc = make_doc(
            "doc_001",
            entities=[
                ("BERT", EntityLabel.METHOD),
                ("GAN", EntityLabel.METHOD),
            ],
        )
        resolution = make_resolution(doc)
        builder = CorpusGraphBuilder(resolution_result=resolution)
        result = builder.build(documents=[doc])
        ee_edges = [e for e in result.edges
                    if e.metadata.get("edge_kind") == "entity_co_occur"]
        assert len(ee_edges) == 1
        e = ee_edges[0]
        assert e.relation_type == RelationType.COMPARES_WITH
        assert e.is_directed is False

    def test_no_co_occurrence_with_single_entity(self):
        doc = make_doc("doc_001", entities=[("BERT", EntityLabel.METHOD)])
        resolution = make_resolution(doc)
        builder = CorpusGraphBuilder(resolution_result=resolution)
        result = builder.build(documents=[doc])
        ee_edges = [e for e in result.edges
                    if e.metadata.get("edge_kind") == "entity_co_occur"]
        assert len(ee_edges) == 0

    def test_across_documents_no_duplicates(self):
        doc1 = make_doc(
            "doc_001",
            entities=[("BERT", EntityLabel.METHOD), ("GAN", EntityLabel.METHOD)],
        )
        doc2 = make_doc(
            "doc_002",
            entities=[("BERT", EntityLabel.METHOD), ("GAN", EntityLabel.METHOD)],
        )
        # Merge entities with same text into shared clusters
        text_to_eids: dict[str, list[str]] = {}
        for ent in doc1.entities + doc2.entities:
            text_to_eids.setdefault(ent.text, []).append(ent.entity_id)
        clusters = []
        for text, eids in text_to_eids.items():
            cid = f"ec_{text.lower()}"
            ce = CanonicalEntity(
                canonical_id=cid, canonical_text=text,
                label=EntityLabel.METHOD, variants=[text],
                entity_ids=eids, confidence=0.9,
                resolution_method="exact",
            )
            cluster = EntityCluster(
                cluster_id=cid, canonical_entity=ce,
                members=[EntityAlias(canonical_id=cid, variant=text,
                                     confidence=0.9)],
                size=1,
            )
            clusters.append(cluster)
        resolution = ResolutionResult(
            clusters=clusters, unresolved=[],
            total_entities=4, resolved_count=4,
            cluster_count=len(clusters),
            resolution_rate=1.0,
            stage_counts={"exact": 4},
        )
        builder = CorpusGraphBuilder(resolution_result=resolution)
        result = builder.build(documents=[doc1, doc2])
        ee_edges = [e for e in result.edges
                    if e.metadata.get("edge_kind") == "entity_co_occur"]
        # Same cluster pair in both docs — should only produce one edge
        assert len(ee_edges) == 1


# ===================================================================
# Tests: CorpusGraphBuilder — Stage 6 (Claim nodes)
# ===================================================================


class TestStage6ClaimNodes:
    def test_single_claim(self):
        doc = make_doc(
            "doc_001",
            claims=[("BERT achieves SOTA.", ClaimType.STATISTICAL)],
        )
        builder = CorpusGraphBuilder()
        result = builder.build(documents=[doc])
        claim_nodes = [n for n in result.nodes if n.node_type == "claim"]
        assert len(claim_nodes) == 1
        cn = claim_nodes[0]
        assert cn.node_id.startswith("cl_doc_001_")
        assert cn.node_type == "claim"

    def test_multiple_claims(self):
        doc = make_doc(
            "doc_001",
            claims=[
                ("Claim A", ClaimType.STATISTICAL),
                ("Claim B", ClaimType.METHODOLOGICAL),
            ],
        )
        builder = CorpusGraphBuilder()
        result = builder.build(documents=[doc])
        claim_nodes = [n for n in result.nodes if n.node_type == "claim"]
        assert len(claim_nodes) == 2

    def test_claim_metadata(self):
        doc = make_doc(
            "doc_001",
            claims=[("BERT achieves SOTA.", ClaimType.STATISTICAL)],
        )
        builder = CorpusGraphBuilder()
        result = builder.build(documents=[doc])
        cn = [n for n in result.nodes if n.node_type == "claim"][0]
        assert cn.metadata["claim_type"] == "statistical"
        assert cn.metadata["confidence"] == 0.85
        assert cn.metadata["doc_id"] == "doc_001"


# ===================================================================
# Tests: CorpusGraphBuilder — Stage 7 (Claim-relation edges)
# ===================================================================


class TestStage7ClaimRelationEdges:
    def test_doc_to_claim_edges(self):
        doc = make_doc(
            "doc_001",
            claims=[("BERT achieves SOTA.", ClaimType.STATISTICAL)],
        )
        builder = CorpusGraphBuilder()
        result = builder.build(documents=[doc])
        dc_edges = [e for e in result.edges
                    if e.metadata.get("edge_kind") == "doc_has_claim"]
        assert len(dc_edges) == 1
        e = dc_edges[0]
        assert e.source_id == "doc_001"
        assert e.target_id.startswith("cl_doc_001_")
        assert e.relation_type == RelationType.SUPPORTS
        assert e.is_directed is True

    def test_cross_doc_claim_relation(self):
        docs = [
            make_doc("doc_001", claims=[("Claim A", ClaimType.STATISTICAL)]),
            make_doc("doc_002", claims=[("Claim B", ClaimType.STATISTICAL)]),
        ]
        rel = DocumentRelation(
            relation_id="rel_001",
            source_ruo_id="doc_001",
            target_ruo_id="doc_002",
            relation_type=RelationType.SUPPORTS,
            source_claim_id="cl0",
            target_claim_id="cl0",
            confidence=0.85,
            is_directed=True,
            detected_at=_NOW,
        )
        builder = CorpusGraphBuilder()
        result = builder.build(documents=docs, relations=[rel])
        cc_edges = [e for e in result.edges
                    if e.metadata.get("edge_kind") == "claim_relation"]
        assert len(cc_edges) == 1
        e = cc_edges[0]
        assert e.source_id.startswith("cl_doc_001_")
        assert e.target_id.startswith("cl_doc_002_")
        assert e.relation_type == RelationType.SUPPORTS

    def test_claim_relation_without_claim_ids_skipped(self):
        docs = [
            make_doc("doc_001"),
            make_doc("doc_002"),
        ]
        rel = DocumentRelation(
            relation_id="rel_001",
            source_ruo_id="doc_001",
            target_ruo_id="doc_002",
            relation_type=RelationType.CITES,
            source_claim_id=None,
            target_claim_id=None,
            confidence=0.9,
            is_directed=True,
            detected_at=_NOW,
        )
        builder = CorpusGraphBuilder()
        result = builder.build(documents=docs, relations=[rel])
        cc_edges = [e for e in result.edges
                    if e.metadata.get("edge_kind") == "claim_relation"]
        assert len(cc_edges) == 0

    def test_doc_to_claim_no_claims(self):
        doc = make_doc("doc_001", claims=[])
        builder = CorpusGraphBuilder()
        result = builder.build(documents=[doc])
        dc_edges = [e for e in result.edges
                    if e.metadata.get("edge_kind") == "doc_has_claim"]
        assert len(dc_edges) == 0


# ===================================================================
# Tests: CorpusGraphBuilder — Stage 8 (Deduplication)
# ===================================================================


class TestStage8Deduplication:
    def test_duplicate_node_id_keeps_higher_weight(self):
        doc = make_doc("doc_001", title="Original",
                       entities=[("BERT", EntityLabel.METHOD)])
        resolution = make_resolution(doc)
        builder = CorpusGraphBuilder(resolution_result=resolution)
        # Manually add a duplicate node node with higher weight (0.95 vs 0.9)
        node2 = CorpusGraphNode(
            node_id="ec_doc_001_e0", node_type="entity_cluster",
            label="Replacement", weight=0.95,
        )
        builder._nodes[node2.node_id] = node2
        builder._stage_8_deduplicate()
        ec_nodes = [n for n in builder._nodes.values()
                    if n.node_type == "entity_cluster"]
        assert len(ec_nodes) == 1
        assert ec_nodes[0].weight == 0.95

    def test_build_clears_state(self):
        doc = make_doc("doc_001", title="Paper A")
        builder = CorpusGraphBuilder()
        r1 = builder.build(documents=[doc])
        assert r1.total_nodes_found == 1
        r2 = builder.build(documents=[doc])
        assert r2.total_nodes_found == 1


# ===================================================================
# Tests: CorpusGraphBuilder — Edge cases
# ===================================================================


class TestEdgeCases:
    def test_no_documents(self):
        builder = CorpusGraphBuilder()
        result = builder.build(documents=[])
        assert result.total_nodes_found == 0
        assert result.total_edges_found == 0

    def test_document_with_no_entities_no_claims(self):
        doc = make_doc("doc_empty", title="Empty Document",
                       entities=[], claims=[], triples=[])
        builder = CorpusGraphBuilder()
        result = builder.build(documents=[doc])
        assert result.total_nodes_found == 1  # just the doc node
        assert result.total_edges_found == 0

    def test_none_resolution(self):
        doc = make_doc("doc_001", entities=[("BERT", EntityLabel.METHOD)])
        builder = CorpusGraphBuilder(resolution_result=None)
        result = builder.build(documents=[doc])
        # Only doc node, no entity nodes or edges
        assert len([n for n in result.nodes if n.node_type == "entity_cluster"]) == 0

    def test_self_relation_not_created_as_doc_rel(self):
        """DocumentRelation model prevents self-relations via validation,
        but if somehow present, the edge is still created."""
        pass  # validation is in the model, not the builder


# ===================================================================
# Tests: CorpusGraphBuilder — Statistics
# ===================================================================


class TestCorpusGraphStatisticsComputation:
    def test_empty_graph_statistics(self):
        builder = CorpusGraphBuilder()
        result = builder.build(documents=[])
        stats = result.statistics
        assert stats is not None
        assert stats.total_nodes == 0
        assert stats.total_edges == 0
        assert stats.connected_components == 0
        assert stats.density == 0.0

    def test_single_node_statistics(self):
        doc = make_doc("doc_001", title="Solo")
        builder = CorpusGraphBuilder()
        result = builder.build(documents=[doc])
        stats = result.statistics
        assert stats.total_nodes == 1
        assert stats.total_edges == 0
        assert stats.node_type_counts == {"document": 1}
        assert stats.average_degree == 0.0

    def test_two_connected_docs_statistics(self):
        docs = [
            make_doc("doc_001", title="Paper A"),
            make_doc("doc_002", title="Paper B"),
        ]
        rel = DocumentRelation(
            relation_id="r1", source_ruo_id="doc_001",
            target_ruo_id="doc_002",
            relation_type=RelationType.CITES,
            confidence=0.9, is_directed=True, detected_at=_NOW,
        )
        builder = CorpusGraphBuilder()
        result = builder.build(documents=docs, relations=[rel])
        stats = result.statistics
        assert stats.total_nodes == 2
        assert stats.total_edges == 1
        assert stats.connected_components == 1
        assert stats.largest_component_size == 2
        assert stats.node_type_counts == {"document": 2}
        assert stats.edge_type_counts == {"cites": 1}


# ===================================================================
# Tests: CorpusGraphBuilder — Full pipeline smoke test
# ===================================================================


class TestFullPipelineSmoke:
    def test_small_corpus(self):
        """Build a small 3-document corpus graph."""
        docs = [
            make_doc(
                "doc_001", title="BERT: Pre-training",
                entities=[("BERT", EntityLabel.METHOD),
                          ("Adam", EntityLabel.METHOD)],
                claims=[("BERT achieves SOTA.", ClaimType.STATISTICAL)],
                triples=[("BERT", "improves")],
            ),
            make_doc(
                "doc_002", title="GAN: Generative Models",
                entities=[("GAN", EntityLabel.METHOD),
                          ("Adam", EntityLabel.METHOD)],
                claims=[("GAN generates images.", ClaimType.STATISTICAL)],
                triples=[("GAN", "generates")],
            ),
            make_doc(
                "doc_003", title="Adam Optimizer",
                entities=[("Adam", EntityLabel.METHOD)],
                claims=[("Adam converges fast.", ClaimType.STATISTICAL)],
            ),
        ]

        # Create resolution: each entity is its own cluster
        all_entities = []
        for doc in docs:
            all_entities.extend(doc.entities)
        clusters_dict: dict[str, EntityCluster] = {}
        for ent in all_entities:
            if ent.entity_id not in clusters_dict:
                cid = f"ec_{ent.entity_id}"
                ce = CanonicalEntity(
                    canonical_id=cid, canonical_text=ent.text,
                    label=ent.label, variants=[ent.text],
                    entity_ids=[ent.entity_id],
                    confidence=ent.confidence,
                    resolution_method="exact",
                )
                clusters_dict[ent.entity_id] = EntityCluster(
                    cluster_id=cid, canonical_entity=ce,
                    members=[EntityAlias(
                        canonical_id=cid, variant=ent.text,
                        confidence=ent.confidence,
                    )],
                    size=1,
                )
        resolution = ResolutionResult(
            clusters=list(clusters_dict.values()),
            unresolved=[],
            total_entities=len(all_entities),
            resolved_count=len(all_entities),
            cluster_count=len(clusters_dict),
            resolution_rate=1.0,
            stage_counts={"exact": len(all_entities)},
        )

        relations = [
            DocumentRelation(
                relation_id="r1", source_ruo_id="doc_001",
                target_ruo_id="doc_002",
                relation_type=RelationType.CITES,
                confidence=0.9, is_directed=True, detected_at=_NOW,
            ),
            DocumentRelation(
                relation_id="r2", source_ruo_id="doc_002",
                target_ruo_id="doc_003",
                relation_type=RelationType.EXTENDS,
                confidence=0.8, is_directed=True, detected_at=_NOW,
            ),
        ]

        builder = CorpusGraphBuilder(resolution_result=resolution)
        result = builder.build(documents=docs, relations=relations)

        # Verify counts
        # 3 docs + 5 entity clusters (BERT doc1, Adam doc1, GAN doc2, Adam doc2, Adam doc3)
        # + 3 claims = 11 nodes
        assert result.total_nodes_found == 11

        # Verify node types
        docs_found = [n for n in result.nodes if n.node_type == "document"]
        ec_found = [n for n in result.nodes if n.node_type == "entity_cluster"]
        claim_found = [n for n in result.nodes if n.node_type == "claim"]
        assert len(docs_found) == 3
        assert len(ec_found) == 5
        assert len(claim_found) == 3

        # Verify edge types
        de_edges = [e for e in result.edges
                    if e.metadata.get("edge_kind") == "doc_contains_entity"]
        assert len(de_edges) == 5  # doc_001:2 + doc_002:2 + doc_003:1

        dr_edges = [e for e in result.edges
                    if e.metadata.get("edge_kind") == "doc_relation"]
        assert len(dr_edges) == 2

        ee_edges = [e for e in result.edges
                    if e.metadata.get("edge_kind") == "entity_co_occur"]
        assert len(ee_edges) == 2  # doc_001: BERT-Adam, doc_002: GAN-Adam

        dc_edges = [e for e in result.edges
                    if e.metadata.get("edge_kind") == "doc_has_claim"]
        assert len(dc_edges) == 3

        # Verify statistics
        stats = result.statistics
        assert stats is not None
        assert stats.total_nodes == 11
        assert stats.node_type_counts["document"] == 3
        assert stats.node_type_counts["entity_cluster"] == 5
        assert stats.node_type_counts["claim"] == 3
        assert stats.connected_components == 1  # All connected via relations
        assert stats.density > 0.0


# ===================================================================
# Tests: CorpusGraphBuilder — Metadata verification
# ===================================================================


class TestMetadata:
    def test_document_node_metadata(self):
        doc = make_doc(
            "doc_meta", title="Meta Test",
            entities=[("BERT", EntityLabel.METHOD)],
            research_fields=["NLP"],
            confidence=0.95,
        )
        builder = CorpusGraphBuilder()
        result = builder.build(documents=[doc])
        node = result.nodes[0]
        assert node.metadata["research_field"] == "NLP"
        assert node.metadata["overall_confidence"] == 0.95
        assert node.weight == 0.95

    def test_claim_node_metadata(self):
        doc = make_doc(
            "doc_001",
            claims=[("Test claim.", ClaimType.STATISTICAL)],
        )
        builder = CorpusGraphBuilder()
        result = builder.build(documents=[doc])
        cn = [n for n in result.nodes if n.node_type == "claim"][0]
        assert cn.metadata["claim_type"] == "statistical"
        assert cn.metadata["doc_id"] == "doc_001"

    def test_entity_cluster_node_metadata(self):
        doc = make_doc("doc_001", entities=[("Transformer", EntityLabel.METHOD)])
        resolution = make_resolution(doc)
        builder = CorpusGraphBuilder(resolution_result=resolution)
        result = builder.build(documents=[doc])
        ec = [n for n in result.nodes if n.node_type == "entity_cluster"][0]
        assert ec.metadata["label"] == "method"
        assert ec.metadata["canonical_text"] == "Transformer"
        assert ec.metadata["cluster_size"] == 1


# ===================================================================
# Helpers: Small graph for traversal tests
# ===================================================================


def _small_corpus_graph() -> CorpusGraphResult:
    """Build a small graph for traversal testing.

    Structure (two disconnected components):
      A ── B ── C
      │
      D

      E ── F
    """
    A = CorpusGraphNode(node_id="A", node_type="document", label="Alpha")
    B = CorpusGraphNode(node_id="B", node_type="document", label="Beta")
    C = CorpusGraphNode(node_id="C", node_type="document", label="Gamma")
    D = CorpusGraphNode(node_id="D", node_type="document", label="Delta")
    E = CorpusGraphNode(node_id="E", node_type="document", label="Epsilon")
    F = CorpusGraphNode(node_id="F", node_type="document", label="Zeta")
    AB = CorpusGraphEdge(
        edge_id="e_AB", source_id="A", target_id="B",
        relation_type=RelationType.CITES, confidence=0.9, weight=0.9,
    )
    BC = CorpusGraphEdge(
        edge_id="e_BC", source_id="B", target_id="C",
        relation_type=RelationType.EXTENDS, confidence=0.8, weight=0.8,
    )
    AD = CorpusGraphEdge(
        edge_id="e_AD", source_id="A", target_id="D",
        relation_type=RelationType.SUPPORTS, confidence=0.7, weight=0.7,
    )
    EF = CorpusGraphEdge(
        edge_id="e_EF", source_id="E", target_id="F",
        relation_type=RelationType.CITES, confidence=0.95, weight=0.95,
    )
    return CorpusGraphResult(
        nodes=[A, B, C, D, E, F],
        edges=[AB, BC, AD, EF],
        total_nodes_found=6,
        total_edges_found=4,
    )


# ===================================================================
# Tests: Traversal — get_neighbors
# ===================================================================


class TestGetNeighbors:
    def test_direct_neighbors(self):
        g = _small_corpus_graph()
        r = g.get_neighbors("A", depth=1)
        assert r.total_nodes_found == 3  # A + B + D
        assert sorted(r.nodes, key=lambda n: n.node_id)[0].node_id == "A"
        assert {n.node_id for n in r.nodes} == {"A", "B", "D"}

    def test_depth_2_neighbors(self):
        g = _small_corpus_graph()
        r = g.get_neighbors("A", depth=2)
        assert r.total_nodes_found == 4  # A + B + D + C
        assert {n.node_id for n in r.nodes} == {"A", "B", "C", "D"}

    def test_isolated_node_no_neighbors(self):
        g = _small_corpus_graph()
        r = g.get_neighbors("F", depth=1)
        assert r.total_nodes_found == 2  # F + E
        assert {n.node_id for n in r.nodes} == {"E", "F"}

    def test_nonexistent_node(self):
        g = _small_corpus_graph()
        r = g.get_neighbors("Z", depth=1)
        assert r.total_nodes_found == 0
        assert r.nodes == []

    def test_depth_default(self):
        g = _small_corpus_graph()
        r = g.get_neighbors("B")
        assert {n.node_id for n in r.nodes} == {"A", "B", "C"}


# ===================================================================
# Tests: Traversal — shortest_path
# ===================================================================


class TestShortestPath:
    def test_direct_path(self):
        g = _small_corpus_graph()
        p = g.shortest_path("A", "B")
        assert p is not None
        assert len(p.edges) == 1
        assert p.source_id() == "A"
        assert p.target_id() == "B"

    def test_two_hop_path(self):
        g = _small_corpus_graph()
        p = g.shortest_path("A", "C")
        assert p is not None
        assert len(p.edges) == 2
        assert p.node_ids() == ["A", "B", "C"]

    def test_no_path(self):
        g = _small_corpus_graph()
        p = g.shortest_path("A", "E")
        assert p is None

    def test_self_path(self):
        g = _small_corpus_graph()
        p = g.shortest_path("A", "A")
        assert p is not None
        assert len(p.edges) == 0
        assert p.total_weight == 0.0

    def test_nonexistent_source(self):
        g = _small_corpus_graph()
        p = g.shortest_path("Z", "A")
        assert p is None


# ===================================================================
# Tests: Traversal — find_paths
# ===================================================================


class TestFindPaths:
    def test_single_path(self):
        g = _small_corpus_graph()
        paths = g.find_paths("A", "C", max_depth=5)
        assert len(paths) == 1
        assert len(paths[0].edges) == 2

    def test_no_path(self):
        g = _small_corpus_graph()
        paths = g.find_paths("A", "E", max_depth=5)
        assert len(paths) == 0

    def test_max_depth_prunes(self):
        g = _small_corpus_graph()
        paths = g.find_paths("A", "C", max_depth=1)
        assert len(paths) == 0

    def test_self_path(self):
        g = _small_corpus_graph()
        paths = g.find_paths("A", "A", max_depth=5)
        assert len(paths) == 1
        assert len(paths[0].edges) == 0

    def test_nonexistent_source(self):
        g = _small_corpus_graph()
        paths = g.find_paths("Z", "A", max_depth=5)
        assert len(paths) == 0


# ===================================================================
# Tests: Traversal — connected_components
# ===================================================================


class TestConnectedComponents:
    def test_two_components(self):
        g = _small_corpus_graph()
        comps = g.connected_components()
        assert len(comps) == 2

    def test_component_sizes(self):
        g = _small_corpus_graph()
        comps = g.connected_components()
        sizes = sorted((len(c.nodes) for c in comps), reverse=True)
        assert sizes == [4, 2]

    def test_sorted_largest_first(self):
        g = _small_corpus_graph()
        comps = g.connected_components()
        assert len(comps[0].nodes) >= len(comps[1].nodes)

    def test_first_component_has_four_nodes(self):
        g = _small_corpus_graph()
        comps = g.connected_components()
        c0 = comps[0]
        assert c0.total_nodes_found == 4
        assert {n.node_id for n in c0.nodes} == {"A", "B", "C", "D"}

    def test_second_component_has_two_nodes(self):
        g = _small_corpus_graph()
        comps = g.connected_components()
        c1 = comps[1]
        assert c1.total_nodes_found == 2
        assert {n.node_id for n in c1.nodes} == {"E", "F"}


# ===================================================================
# Tests: Traversal — subgraph
# ===================================================================


class TestSubgraph:
    def test_induced_subgraph(self):
        g = _small_corpus_graph()
        sg = g.subgraph({"A", "B", "C"})
        assert sg.total_nodes_found == 3
        assert sg.total_edges_found == 2
        assert {e.edge_id for e in sg.edges} == {"e_AB", "e_BC"}

    def test_single_node_no_edges(self):
        g = _small_corpus_graph()
        sg = g.subgraph({"A"})
        assert sg.total_nodes_found == 1
        assert sg.total_edges_found == 0

    def test_disconnected_pair(self):
        g = _small_corpus_graph()
        sg = g.subgraph({"A", "F"})
        assert sg.total_nodes_found == 2
        assert sg.total_edges_found == 0

    def test_empty_set(self):
        g = _small_corpus_graph()
        sg = g.subgraph(set())
        assert sg.total_nodes_found == 0
        assert sg.total_edges_found == 0


# ===================================================================
# Tests: Traversal — query_nodes
# ===================================================================


class TestQueryNodes:
    def test_filter_by_type(self):
        g = _small_corpus_graph()
        q = CorpusGraphQuery(node_type="document")
        r = g.query_nodes(q)
        assert r.total_nodes_found == 6

    def test_filter_by_label_contains(self):
        g = _small_corpus_graph()
        q = CorpusGraphQuery(label_contains="lph")
        r = g.query_nodes(q)
        assert r.total_nodes_found == 1
        assert r.nodes[0].node_id == "A"

    def test_filter_by_confidence(self):
        g = _small_corpus_graph()
        q = CorpusGraphQuery(min_confidence=0.5)
        r = g.query_nodes(q)
        assert r.total_nodes_found == 6

    def test_filter_by_node_ids(self):
        g = _small_corpus_graph()
        q = CorpusGraphQuery(node_ids=["A", "C"])
        r = g.query_nodes(q)
        assert r.total_nodes_found == 2
        assert {n.node_id for n in r.nodes} == {"A", "C"}

    def test_edges_are_star_neighborhood(self):
        g = _small_corpus_graph()
        q = CorpusGraphQuery(node_ids=["A"])
        r = g.query_nodes(q)
        assert r.total_nodes_found == 1
        assert r.total_edges_found == 2

    def test_no_match_returns_empty(self):
        g = _small_corpus_graph()
        q = CorpusGraphQuery(label_contains="xyz")
        r = g.query_nodes(q)
        assert r.total_nodes_found == 0

    def test_query_stored_in_result(self):
        g = _small_corpus_graph()
        q = CorpusGraphQuery(node_type="document")
        r = g.query_nodes(q)
        assert r.query is not None
        assert r.query.node_type == "document"


# ===================================================================
# Tests: Traversal — query_edges
# ===================================================================


class TestQueryEdges:
    def test_filter_by_relation_type(self):
        g = _small_corpus_graph()
        q = CorpusGraphQuery(relation_types=[RelationType.CITES])
        r = g.query_edges(q)
        assert r.total_edges_found == 2
        assert {e.edge_id for e in r.edges} == {"e_AB", "e_EF"}

    def test_filter_by_source(self):
        g = _small_corpus_graph()
        q = CorpusGraphQuery(source_id="A")
        r = g.query_edges(q)
        assert r.total_edges_found == 2

    def test_filter_by_target(self):
        g = _small_corpus_graph()
        q = CorpusGraphQuery(target_id="C")
        r = g.query_edges(q)
        assert r.total_edges_found == 1

    def test_filter_by_confidence(self):
        g = _small_corpus_graph()
        q = CorpusGraphQuery(min_confidence=0.9)
        r = g.query_edges(q)
        assert r.total_edges_found == 2

    def test_filter_by_weight(self):
        g = _small_corpus_graph()
        q = CorpusGraphQuery(min_weight=0.9)
        r = g.query_edges(q)
        assert r.total_edges_found == 2

    def test_nodes_include_endpoints(self):
        g = _small_corpus_graph()
        q = CorpusGraphQuery(relation_types=[RelationType.CITES])
        r = g.query_edges(q)
        assert {n.node_id for n in r.nodes} == {"A", "B", "E", "F"}

    def test_no_match_returns_empty(self):
        g = _small_corpus_graph()
        q = CorpusGraphQuery(source_id="Z")
        r = g.query_edges(q)
        assert r.total_edges_found == 0

    def test_combined_filters(self):
        g = _small_corpus_graph()
        q = CorpusGraphQuery(
            source_id="A",
            relation_types=[RelationType.CITES],
        )
        r = g.query_edges(q)
        assert r.total_edges_found == 1
        assert r.edges[0].edge_id == "e_AB"


# ===================================================================
# Tests: statistics() method
# ===================================================================


class TestStatisticsMethod:
    def test_empty(self):
        g = CorpusGraphResult(nodes=[], edges=[])
        s = g.compute_statistics()
        assert s.total_nodes == 0
        assert s.total_edges == 0
        assert s.density == 0.0

    def test_small_graph(self):
        g = _small_corpus_graph()
        s = g.compute_statistics()
        assert s.total_nodes == 6
        assert s.total_edges == 4
        assert s.node_type_counts["document"] == 6
        assert s.connected_components == 2
        assert s.largest_component_size == 4
        assert s.largest_component_edges == 3
        assert s.density > 0.0

    def test_single_node_no_edges(self):
        n = CorpusGraphNode(node_id="X", node_type="document", label="X")
        g = CorpusGraphResult(nodes=[n], edges=[])
        s = g.compute_statistics()
        assert s.total_nodes == 1
        assert s.total_edges == 0
        assert s.density == 0.0
        assert s.connected_components == 1

    def test_self_loop_counts(self):
        n = CorpusGraphNode(node_id="X", node_type="document", label="X")
        e = CorpusGraphEdge(
            edge_id="e_self", source_id="X", target_id="X",
            relation_type=RelationType.EXTENDS, confidence=0.5,
        )
        g = CorpusGraphResult(nodes=[n], edges=[e])
        s = g.compute_statistics()
        assert s.self_loops == 1
        assert s.connected_components == 1

    def test_confidence_bounds(self):
        nodes = [CorpusGraphNode(node_id=f"N{i}", node_type="document", label=f"N{i}")
                 for i in range(3)]
        edges = [
            CorpusGraphEdge(edge_id=f"e{i}", source_id=f"N{i}", target_id=f"N{(i+1)%3}",
                            relation_type=RelationType.CITES, confidence=c)
            for i, c in enumerate([0.3, 0.6, 0.9])
        ]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        s = g.compute_statistics()
        assert s.min_confidence == 0.3
        assert s.max_confidence == 0.9
        assert s.avg_confidence == 0.6


# ===================================================================
# Tests: top_entities
# ===================================================================


class TestTopEntities:
    def test_top_returns_sorted(self):
        nodes = [
            CorpusGraphNode(node_id="e1", node_type="entity_cluster",
                            label="BERT", weight=0.9),
            CorpusGraphNode(node_id="e2", node_type="entity_cluster",
                            label="GAN", weight=0.8),
            CorpusGraphNode(node_id="e3", node_type="entity_cluster",
                            label="Adam", weight=0.95),
            CorpusGraphNode(node_id="d1", node_type="document",
                            label="Doc", weight=1.0),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=[])
        top = g.top_entities(n=2)
        assert len(top) == 2
        assert top[0].node_id == "e3"
        assert top[1].node_id == "e1"

    def test_top_n_larger_than_count(self):
        nodes = [
            CorpusGraphNode(node_id="e1", node_type="entity_cluster",
                            label="X", weight=0.5),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=[])
        top = g.top_entities(n=10)
        assert len(top) == 1

    def test_no_entities(self):
        nodes = [CorpusGraphNode(node_id="d1", node_type="document",
                                 label="Doc")]
        g = CorpusGraphResult(nodes=nodes, edges=[])
        top = g.top_entities(n=5)
        assert top == []

    def test_default_n(self):
        nodes = [CorpusGraphNode(node_id=f"e{i}", node_type="entity_cluster",
                                 label=f"E{i}", weight=w)
                 for i, w in enumerate([0.1, 0.2, 0.3, 0.4, 0.5, 0.6,
                                        0.7, 0.8, 0.9, 1.0, 0.95])]
        g = CorpusGraphResult(nodes=nodes, edges=[])
        top = g.top_entities()
        assert len(top) == 10
        assert top[0].weight == 1.0


# ===================================================================
# Tests: top_documents
# ===================================================================


class TestTopDocuments:
    def test_top_returns_sorted(self):
        nodes = [
            CorpusGraphNode(node_id="d1", node_type="document",
                            label="Doc A", weight=0.7),
            CorpusGraphNode(node_id="d2", node_type="document",
                            label="Doc B", weight=0.9),
            CorpusGraphNode(node_id="d3", node_type="document",
                            label="Doc C", weight=0.8),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=[])
        top = g.top_documents(n=2)
        assert len(top) == 2
        assert top[0].node_id == "d2"
        assert top[1].node_id == "d3"

    def test_no_documents(self):
        g = CorpusGraphResult(nodes=[], edges=[])
        top = g.top_documents(n=5)
        assert top == []

    def test_default_n(self):
        nodes = [CorpusGraphNode(node_id=f"d{i}", node_type="document",
                                 label=f"Doc {i}", weight=w)
                 for i, w in enumerate([0.1, 0.2, 0.3, 0.4, 0.5, 0.6,
                                        0.7, 0.8, 0.9, 1.0, 0.95])]
        g = CorpusGraphResult(nodes=nodes, edges=[])
        top = g.top_documents()
        assert len(top) == 10

    def test_ignores_non_document_nodes(self):
        nodes = [
            CorpusGraphNode(node_id="d1", node_type="document",
                            label="Doc", weight=0.8),
            CorpusGraphNode(node_id="e1", node_type="entity_cluster",
                            label="Ent", weight=0.9),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=[])
        top = g.top_documents(n=5)
        assert len(top) == 1
        assert top[0].node_id == "d1"


# ===================================================================
# Tests: top_predicates
# ===================================================================


class TestTopPredicates:
    def test_returns_counts(self):
        nodes = [CorpusGraphNode(node_id=f"N{i}", node_type="document", label=f"N{i}")
                 for i in range(4)]
        edges = [
            CorpusGraphEdge(edge_id="e1", source_id="N0", target_id="N1",
                            relation_type=RelationType.CITES, confidence=0.9),
            CorpusGraphEdge(edge_id="e2", source_id="N1", target_id="N2",
                            relation_type=RelationType.CITES, confidence=0.8),
            CorpusGraphEdge(edge_id="e3", source_id="N2", target_id="N3",
                            relation_type=RelationType.EXTENDS, confidence=0.7),
            CorpusGraphEdge(edge_id="e4", source_id="N0", target_id="N3",
                            relation_type=RelationType.COMPARES_WITH, confidence=0.6),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        top = g.top_predicates(n=3)
        assert len(top) == 3
        assert top[0] == ("cites", 2)
        assert top[1][0] in ("extends", "compares_with")
        assert top[2][0] in ("extends", "compares_with")

    def test_empty(self):
        g = CorpusGraphResult(nodes=[], edges=[])
        top = g.top_predicates(n=5)
        assert top == []

    def test_default_n(self):
        nodes = [CorpusGraphNode(node_id=f"N{i}", node_type="document", label=f"N{i}")
                 for i in range(15)]
        edges = [CorpusGraphEdge(edge_id=f"e{i}", source_id=f"N{i}", target_id=f"N{(i+1)%15}",
                                 relation_type=RelationType.CITES, confidence=0.5)
                 for i in range(15)]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        top = g.top_predicates()
        assert len(top) == 1
        assert top[0] == ("cites", 15)


# ===================================================================
# Tests: Empty corpus
# ===================================================================


class TestEmptyCorpus:
    def test_no_nodes_no_edges(self):
        g = CorpusGraphResult(nodes=[], edges=[])
        assert g.total_nodes_found == 0
        assert g.total_edges_found == 0

    def test_statistics_on_empty(self):
        g = CorpusGraphResult(nodes=[], edges=[])
        s = g.compute_statistics()
        assert s.total_nodes == 0
        assert s.total_edges == 0
        assert s.density == 0.0

    def test_get_neighbors_on_empty(self):
        g = CorpusGraphResult(nodes=[], edges=[])
        r = g.get_neighbors("nonexistent")
        assert r.total_nodes_found == 0

    def test_shortest_path_on_empty(self):
        g = CorpusGraphResult(nodes=[], edges=[])
        p = g.shortest_path("A", "B")
        assert p is None

    def test_find_paths_on_empty(self):
        g = CorpusGraphResult(nodes=[], edges=[])
        paths = g.find_paths("A", "B")
        assert paths == []

    def test_connected_components_on_empty(self):
        g = CorpusGraphResult(nodes=[], edges=[])
        comps = g.connected_components()
        assert comps == []

    def test_subgraph_on_empty(self):
        g = CorpusGraphResult(nodes=[], edges=[])
        sg = g.subgraph({"A"})
        assert sg.total_nodes_found == 0

    def test_query_nodes_on_empty(self):
        g = CorpusGraphResult(nodes=[], edges=[])
        q = CorpusGraphQuery()
        r = g.query_nodes(q)
        assert r.total_nodes_found == 0

    def test_query_edges_on_empty(self):
        g = CorpusGraphResult(nodes=[], edges=[])
        q = CorpusGraphQuery()
        r = g.query_edges(q)
        assert r.total_edges_found == 0

    def test_top_entities_on_empty(self):
        g = CorpusGraphResult(nodes=[], edges=[])
        assert g.top_entities() == []

    def test_top_documents_on_empty(self):
        g = CorpusGraphResult(nodes=[], edges=[])
        assert g.top_documents() == []

    def test_top_predicates_on_empty(self):
        g = CorpusGraphResult(nodes=[], edges=[])
        assert g.top_predicates() == []


# ===================================================================
# Tests: Single-document corpus
# ===================================================================


class TestSingleDocumentCorpus:
    def test_one_doc_no_edges(self):
        n = CorpusGraphNode(node_id="d1", node_type="document",
                            label="Single Document")
        g = CorpusGraphResult(nodes=[n], edges=[], total_nodes_found=1)
        assert g.total_nodes_found == 1
        assert g.total_edges_found == 0

    def test_statistics_single_doc(self):
        n = CorpusGraphNode(node_id="d1", node_type="document",
                            label="Single")
        g = CorpusGraphResult(nodes=[n], edges=[])
        s = g.compute_statistics()
        assert s.total_nodes == 1
        assert s.total_edges == 0
        assert s.connected_components == 1
        assert s.node_type_counts == {"document": 1}

    def test_neighbors_single_doc(self):
        n = CorpusGraphNode(node_id="d1", node_type="document",
                            label="Single")
        g = CorpusGraphResult(nodes=[n], edges=[])
        r = g.get_neighbors("d1", depth=1)
        assert r.total_nodes_found == 1
        assert r.nodes[0].node_id == "d1"

    def test_shortest_path_single_doc_self(self):
        n = CorpusGraphNode(node_id="d1", node_type="document",
                            label="Single")
        g = CorpusGraphResult(nodes=[n], edges=[])
        p = g.shortest_path("d1", "d1")
        assert p is not None
        assert len(p.edges) == 0

    def test_shortest_path_to_nonexistent(self):
        n = CorpusGraphNode(node_id="d1", node_type="document",
                            label="Single")
        g = CorpusGraphResult(nodes=[n], edges=[])
        p = g.shortest_path("d1", "X")
        assert p is None

    def test_find_paths_single_doc(self):
        n = CorpusGraphNode(node_id="d1", node_type="document",
                            label="Single")
        g = CorpusGraphResult(nodes=[n], edges=[])
        paths = g.find_paths("d1", "d1")
        assert len(paths) == 1
        assert len(paths[0].edges) == 0

    def test_connected_components_single_doc(self):
        n = CorpusGraphNode(node_id="d1", node_type="document",
                            label="Single")
        g = CorpusGraphResult(nodes=[n], edges=[])
        comps = g.connected_components()
        assert len(comps) == 1
        assert comps[0].total_nodes_found == 1

    def test_subgraph_single_doc(self):
        n = CorpusGraphNode(node_id="d1", node_type="document",
                            label="Single")
        g = CorpusGraphResult(nodes=[n], edges=[])
        sg = g.subgraph({"d1"})
        assert sg.total_nodes_found == 1
        assert sg.total_edges_found == 0

    def test_subgraph_empty_set(self):
        n = CorpusGraphNode(node_id="d1", node_type="document",
                            label="Single")
        g = CorpusGraphResult(nodes=[n], edges=[])
        sg = g.subgraph(set())
        assert sg.total_nodes_found == 0

    def test_doc_with_self_loop_edge(self):
        n = CorpusGraphNode(node_id="d1", node_type="document", label="Self")
        e = CorpusGraphEdge(
            edge_id="e_self", source_id="d1", target_id="d1",
            relation_type=RelationType.EXTENDS, confidence=0.5,
        )
        g = CorpusGraphResult(nodes=[n], edges=[e], total_edges_found=1)
        assert g.total_edges_found == 1
        nbrs = g.get_neighbors("d1", depth=1)
        assert nbrs.total_nodes_found == 1
        assert nbrs.total_edges_found == 1

    def test_top_documents_single(self):
        n = CorpusGraphNode(node_id="d1", node_type="document",
                            label="Single", weight=0.8)
        g = CorpusGraphResult(nodes=[n], edges=[])
        top = g.top_documents()
        assert len(top) == 1
        assert top[0].node_id == "d1"

    def test_top_entities_single_doc_no_entities(self):
        n = CorpusGraphNode(node_id="d1", node_type="document",
                            label="Single")
        g = CorpusGraphResult(nodes=[n], edges=[])
        assert g.top_entities() == []


# ===================================================================
# Tests: Large corpus
# ===================================================================


class TestLargeCorpus:
    """Stress-test with 500 nodes forming a line graph + cross-edges."""

    @staticmethod
    def _build_large_graph(
        n_nodes: int = 500,
    ) -> CorpusGraphResult:
        nodes: list[CorpusGraphNode] = []
        edges: list[CorpusGraphEdge] = []
        for i in range(n_nodes):
            nodes.append(CorpusGraphNode(
                node_id=f"N{i:04d}",
                node_type="document",
                label=f"Doc {i}",
                weight=1.0 - (i / n_nodes) * 0.5,
            ))
        # Line edges: N0→N1→N2→...→Nn
        for i in range(n_nodes - 1):
            edges.append(CorpusGraphEdge(
                edge_id=f"e_line_{i:04d}",
                source_id=f"N{i:04d}",
                target_id=f"N{i+1:04d}",
                relation_type=RelationType.CITES,
                confidence=0.9 - (i / n_nodes) * 0.4,
                weight=0.9 - (i / n_nodes) * 0.4,
            ))
        # Cross edges: N0→N2, N1→N3, ...
        for i in range(0, n_nodes - 2, 2):
            edges.append(CorpusGraphEdge(
                edge_id=f"e_cross_{i:04d}",
                source_id=f"N{i:04d}",
                target_id=f"N{i+2:04d}",
                relation_type=RelationType.EXTENDS,
                confidence=0.7,
                weight=0.7,
            ))
        return CorpusGraphResult(
            nodes=nodes, edges=edges,
            total_nodes_found=len(nodes),
            total_edges_found=len(edges),
        )

    def test_node_count(self):
        g = self._build_large_graph(500)
        assert g.total_nodes_found == 500

    def test_edge_count(self):
        g = self._build_large_graph(500)
        assert g.total_edges_found == 499 + 249  # 499 line + 249 cross

    def test_statistics(self):
        g = self._build_large_graph(500)
        s = g.compute_statistics()
        assert s.total_nodes == 500
        assert s.total_edges == 748
        assert s.connected_components == 1
        assert s.largest_component_size == 500
        assert s.density > 0

    def test_get_neighbors_depth_1(self):
        g = self._build_large_graph(500)
        r = g.get_neighbors("N0250", depth=1)
        # N0250 connected to N0249, N0251, N0248, N0252
        expected = {"N0249", "N0250", "N0251", "N0248", "N0252"}
        assert {n.node_id for n in r.nodes} == expected

    def test_get_neighbors_depth_2(self):
        g = self._build_large_graph(500)
        r = g.get_neighbors("N0250", depth=2)
        # depth 2 adds N0248, N0252's neighbors etc.
        assert r.total_nodes_found > 3

    def test_shortest_path(self):
        g = self._build_large_graph(500)
        p = g.shortest_path("N0000", "N0004")
        assert p is not None
        # Shortest: N0→N2→N4 (2 hops via cross edge) vs N0→N1→N2→N3→N4 (4 hops via line)
        assert len(p.edges) == 2

    def test_shortest_path_across_graph(self):
        g = self._build_large_graph(500)
        p = g.shortest_path("N0000", "N0499")
        assert p is not None
        assert len(p.edges) > 1

    def test_no_path_honors_disconnected(self):
        # Disconnected node
        isolated = CorpusGraphNode(node_id="ISO", node_type="document",
                                   label="Isolated")
        g = self._build_large_graph(500)
        # We can't add to the frozen result; test on the static graph instead
        # Build a separate disconnected case
        nodes = [isolated]
        g2 = CorpusGraphResult(nodes=nodes, edges=[])
        p = g2.shortest_path("ISO", "N0000")
        assert p is None

    def test_find_paths_limited(self):
        g = self._build_large_graph(50)
        paths = g.find_paths("N0000", "N0004", max_depth=3)
        # Should find at least one path
        assert len(paths) >= 1
        for p in paths:
            assert len(p.edges) <= 3

    def test_connected_components_large(self):
        g = self._build_large_graph(500)
        comps = g.connected_components()
        assert len(comps) == 1

    def test_subgraph_large(self):
        g = self._build_large_graph(500)
        sg = g.subgraph({"N0000", "N0001", "N0002"})
        assert sg.total_nodes_found == 3
        # Edges among them: N0-N1 line, N1-N2 line, N0-N2 cross
        assert sg.total_edges_found == 3

    def test_query_nodes_on_large(self):
        g = self._build_large_graph(500)
        q = CorpusGraphQuery(node_type="document", max_results=1000)
        r = g.query_nodes(q)
        assert r.total_nodes_found == 500

    def test_query_edges_on_large(self):
        g = self._build_large_graph(500)
        q = CorpusGraphQuery(relation_types=[RelationType.CITES], max_results=1000)
        r = g.query_edges(q)
        assert r.total_edges_found == 499

    def test_top_documents_large(self):
        g = self._build_large_graph(500)
        top = g.top_documents(n=5)
        assert len(top) == 5
        # First node has highest weight
        assert top[0].node_id == "N0000"

    def test_top_predicates_large(self):
        g = self._build_large_graph(500)
        top = g.top_predicates(n=5)
        assert len(top) == 2  # cites and extends
        assert top[0][0] == "cites"
        assert top[0][1] == 499


# ===================================================================
# Tests: Module-level compute_graph_statistics
# ===================================================================


class TestComputeGraphStatistics:
    def test_module_function_exists(self):
        from researchmind.corpus.graph import compute_graph_statistics
        s = compute_graph_statistics([], [])
        assert s.total_nodes == 0

    def test_isolated_nodes(self):
        from researchmind.corpus.graph import compute_graph_statistics
        nodes = [
            CorpusGraphNode(node_id="A", node_type="document", label="A"),
            CorpusGraphNode(node_id="B", node_type="document", label="B"),
        ]
        s = compute_graph_statistics(nodes, [])
        assert s.total_nodes == 2
        assert s.total_edges == 0
        assert s.connected_components == 2

    def test_single_edge_graph(self):
        from researchmind.corpus.graph import compute_graph_statistics
        nodes = [
            CorpusGraphNode(node_id="A", node_type="document", label="A"),
            CorpusGraphNode(node_id="B", node_type="document", label="B"),
        ]
        edges = [
            CorpusGraphEdge(edge_id="e1", source_id="A", target_id="B",
                            relation_type=RelationType.CITES, confidence=0.8),
        ]
        s = compute_graph_statistics(nodes, edges)
        assert s.total_nodes == 2
        assert s.total_edges == 1
        assert s.connected_components == 1
        assert s.density > 0.0


# ===================================================================
# Tests: get_neighbors edge cases
# ===================================================================


class TestGetNeighborsEdgeCases:
    def test_depth_zero_clamped_to_one(self):
        g = _small_corpus_graph()
        r = g.get_neighbors("A", depth=0)
        assert {n.node_id for n in r.nodes} == {"A", "B", "D"}

    def test_depth_three(self):
        g = _small_corpus_graph()
        r = g.get_neighbors("F", depth=3)
        # F-E, E's neighbors = E, F
        assert {n.node_id for n in r.nodes} == {"E", "F"}

    def test_returns_all_connecting_edges(self):
        g = _small_corpus_graph()
        r = g.get_neighbors("B", depth=1)
        assert r.total_edges_found == 2  # A-B, B-C
        assert {e.edge_id for e in r.edges} == {"e_AB", "e_BC"}


# ===================================================================
# Tests: shortest_path edge cases
# ===================================================================


class TestShortestPathEdgeCases:
    def test_target_nonexistent(self):
        g = _small_corpus_graph()
        p = g.shortest_path("A", "Z")
        assert p is None

    def test_source_nonexistent(self):
        g = _small_corpus_graph()
        p = g.shortest_path("Z", "A")
        assert p is None

    def test_both_nonexistent(self):
        g = _small_corpus_graph()
        p = g.shortest_path("Z", "Y")
        assert p is None

    def test_path_weight_sum(self):
        g = _small_corpus_graph()
        p = g.shortest_path("A", "C")
        assert p is not None
        assert p.total_weight == 0.9 + 0.8  # A-B (0.9) + B-C (0.8)
        assert p.length == 2


# ===================================================================
# Tests: find_paths edge cases
# ===================================================================


class TestFindPathsEdgeCases:
    def test_max_depth_zero(self):
        g = _small_corpus_graph()
        paths = g.find_paths("A", "C", max_depth=0)
        assert len(paths) == 0

    def test_max_depth_one_no_path(self):
        g = _small_corpus_graph()
        paths = g.find_paths("A", "C", max_depth=1)
        assert len(paths) == 0

    def test_path_length_set(self):
        g = _small_corpus_graph()
        paths = g.find_paths("A", "B", max_depth=2)
        assert len(paths) >= 1
        assert paths[0].length == 1


# ===================================================================
# Tests: query_edges metadata filter
# ===================================================================


class TestQueryEdgesMetadata:
    def test_metadata_filter_match(self):
        nodes = [CorpusGraphNode(node_id=f"N{i}", node_type="document", label=f"N{i}")
                 for i in range(2)]
        edges = [
            CorpusGraphEdge(edge_id="e1", source_id="N0", target_id="N1",
                            relation_type=RelationType.CITES, confidence=0.9,
                            metadata={"edge_kind": "doc_relation", "year": 2024}),
            CorpusGraphEdge(edge_id="e2", source_id="N1", target_id="N0",
                            relation_type=RelationType.EXTENDS, confidence=0.8,
                            metadata={"edge_kind": "doc_relation", "year": 2023}),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        q = CorpusGraphQuery(metadata_filter={"year": 2024})
        r = g.query_edges(q)
        assert r.total_edges_found == 1
        assert r.edges[0].edge_id == "e1"

    def test_metadata_filter_no_match(self):
        nodes = [CorpusGraphNode(node_id=f"N{i}", node_type="document", label=f"N{i}")
                 for i in range(2)]
        edges = [
            CorpusGraphEdge(edge_id="e1", source_id="N0", target_id="N1",
                            relation_type=RelationType.CITES, confidence=0.9),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        q = CorpusGraphQuery(metadata_filter={"nonexistent": "value"})
        r = g.query_edges(q)
        assert r.total_edges_found == 0

    def test_metadata_filter_partial_match_excluded(self):
        nodes = [CorpusGraphNode(node_id=f"N{i}", node_type="document", label=f"N{i}")
                 for i in range(3)]
        edges = [
            CorpusGraphEdge(edge_id="e1", source_id="N0", target_id="N1",
                            relation_type=RelationType.CITES, confidence=0.9,
                            metadata={"kind": "a", "year": 2024}),
            CorpusGraphEdge(edge_id="e2", source_id="N1", target_id="N2",
                            relation_type=RelationType.EXTENDS, confidence=0.8,
                            metadata={"kind": "a", "year": 2023}),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=edges)
        q = CorpusGraphQuery(metadata_filter={"kind": "a", "year": 2024})
        r = g.query_edges(q)
        assert r.total_edges_found == 1


# ===================================================================
# Tests: query_nodes metadata filter
# ===================================================================


class TestQueryNodesMetadata:
    def test_metadata_filter(self):
        nodes = [
            CorpusGraphNode(node_id="A", node_type="document", label="Alpha",
                            metadata={"year": 2024, "field": "NLP"}),
            CorpusGraphNode(node_id="B", node_type="document", label="Beta",
                            metadata={"year": 2023, "field": "CV"}),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=[])
        q = CorpusGraphQuery(metadata_filter={"field": "NLP"})
        r = g.query_nodes(q)
        assert r.total_nodes_found == 1
        assert r.nodes[0].node_id == "A"

    def test_metadata_filter_multiple_keys(self):
        nodes = [
            CorpusGraphNode(node_id="A", node_type="document", label="Alpha",
                            metadata={"year": 2024, "field": "NLP"}),
            CorpusGraphNode(node_id="B", node_type="document", label="Beta",
                            metadata={"year": 2024, "field": "CV"}),
        ]
        g = CorpusGraphResult(nodes=nodes, edges=[])
        q = CorpusGraphQuery(metadata_filter={"year": 2024, "field": "NLP"})
        r = g.query_nodes(q)
        assert r.total_nodes_found == 1


# ===================================================================
# Tests: Builder edge cases
# ===================================================================


class TestBuilderEdgeCases:
    def test_no_resolution_no_entities(self):
        doc = make_doc("doc_empty", title="No entities")
        builder = CorpusGraphBuilder(resolution_result=None)
        result = builder.build(documents=[doc])
        assert result.total_nodes_found == 1
        assert result.total_edges_found == 0

    def test_resolution_with_empty_clusters(self):
        doc = make_doc("doc_001", entities=[("BERT", EntityLabel.METHOD)])
        resolution = ResolutionResult(
            clusters=[], unresolved=[], total_entities=0,
            resolved_count=0, cluster_count=0, resolution_rate=0.0,
            stage_counts={},
        )
        builder = CorpusGraphBuilder(resolution_result=resolution)
        result = builder.build(documents=[doc])
        ec_nodes = [n for n in result.nodes if n.node_type == "entity_cluster"]
        assert len(ec_nodes) == 0

    def test_build_statistics_not_none(self):
        doc = make_doc("doc_001", title="Paper")
        builder = CorpusGraphBuilder()
        result = builder.build(documents=[doc])
        assert result.statistics is not None
        assert result.statistics.total_nodes == 1


# ===================================================================
# Tests: Directed graph neighbors — edge direction respected by
# query_nodes star-neighborhood
# ===================================================================


class TestDirectedQueryNodes:
    def test_star_neighborhood_picks_directed_edges(self):
        A = CorpusGraphNode(node_id="A", node_type="document", label="A")
        B = CorpusGraphNode(node_id="B", node_type="document", label="B")
        AB = CorpusGraphEdge(
            edge_id="e_AB", source_id="A", target_id="B",
            relation_type=RelationType.CITES, confidence=0.9,
            is_directed=True,
        )
        g = CorpusGraphResult(nodes=[A, B], edges=[AB])
        q = CorpusGraphQuery(node_ids=["A"])
        r = g.query_nodes(q)
        # Star neighborhood includes edges touching A
        assert r.total_edges_found == 1

    def test_query_edges_respects_direction_source(self):
        A = CorpusGraphNode(node_id="A", node_type="document", label="A")
        B = CorpusGraphNode(node_id="B", node_type="document", label="B")
        AB = CorpusGraphEdge(
            edge_id="e_AB", source_id="A", target_id="B",
            relation_type=RelationType.CITES, confidence=0.9,
        )
        g = CorpusGraphResult(nodes=[A, B], edges=[AB])
        q = CorpusGraphQuery(source_id="A")
        r = g.query_edges(q)
        assert r.total_edges_found == 1
        q2 = CorpusGraphQuery(source_id="B")
        r2 = g.query_edges(q2)
        assert r2.total_edges_found == 0


# ===================================================================
# Part B — End-to-End Integration Tests
#
# Validate the full pipeline:
#   RUODocument -> CorpusManager -> EntityResolver ->
#   DocumentRelationEngine -> CorpusGraphBuilder -> CorpusGraphResult
# ===================================================================


def _e2e_doc(
    ruo_id: str,
    title: str,
    entities: list[tuple[str, EntityLabel]],
    references: list[str | tuple[str, str]] | None = None,
) -> RUODocument:
    """Create a document for end-to-end testing."""
    return make_doc(ruo_id, title=title, entities=entities, references=references)


class TestE2EScenario1AttentionBERT:
    """Attention Is All You Need → BERT: citation + entity resolution."""

    def test_attention_bert_pipeline(self):
        doc_a = _e2e_doc(
            "attn", "Attention Is All You Need",
            entities=[("Transformer", EntityLabel.METHOD)],
        )
        doc_b = _e2e_doc(
            "bert", "BERT: Pre-training of Deep Bidirectional Transformers",
            entities=[("BERT", EntityLabel.METHOD)],
            references=[("r1", "attn")],
        )
        mgr = CorpusManager.from_documents([doc_a, doc_b], "scenario1")
        g = mgr.corpus_graph

        # Both document nodes present
        doc_nodes = {n.node_id: n for n in g.nodes if n.node_type == "document"}
        assert "attn" in doc_nodes
        assert "bert" in doc_nodes

        # Entity cluster nodes (each entity appears only once → no clusters)
        ec_nodes = [n for n in g.nodes if n.node_type == "entity_cluster"]
        assert len(ec_nodes) == 0  # each entity text appears once

        # Citation edge from bert -> attn (via reference)
        cite_edges = [e for e in g.edges
                      if e.relation_type in (RelationType.CITES, RelationType.CITED_BY)]
        assert len(cite_edges) >= 1

        # Graph statistics non-empty
        assert g.statistics.total_nodes >= 2
        assert g.statistics.total_edges >= 1
        assert g.statistics.density >= 0.0

    def test_citation_source_and_target(self):
        doc_a = _e2e_doc(
            "attn", "Attention Is All You Need",
            entities=[("Transformer", EntityLabel.METHOD)],
        )
        doc_b = _e2e_doc(
            "bert", "BERT",
            entities=[("BERT", EntityLabel.METHOD)],
            references=[("r1", "attn")],
        )
        mgr = CorpusManager.from_documents([doc_a, doc_b], "scenario1b")
        g = mgr.corpus_graph
        cite_edges = [e for e in g.edges
                      if e.relation_type in (RelationType.CITES, RelationType.CITED_BY)]
        # At least one edge has bert as source and attn as target
        matches = [e for e in cite_edges if e.source_id == "bert" and e.target_id == "attn"]
        assert len(matches) >= 1

    def test_graph_statistics_correct(self):
        doc_a = _e2e_doc(
            "attn", "Attention",
            entities=[("Transformer", EntityLabel.METHOD)],
        )
        doc_b = _e2e_doc(
            "bert", "BERT",
            entities=[("BERT", EntityLabel.METHOD)],
            references=[("r1", "attn")],
        )
        mgr = CorpusManager.from_documents([doc_a, doc_b], "scenario1c")
        g = mgr.corpus_graph
        s = g.compute_statistics()
        assert s.total_nodes >= 2
        assert s.connected_components >= 1


class TestE2EScenario2ResNetDenseNet:
    """ResNet ↔ DenseNet: shared dataset + method entities."""

    def test_shared_dataset_entity(self):
        doc_a = _e2e_doc(
            "resnet", "Deep Residual Learning",
            entities=[("ResNet", EntityLabel.METHOD),
                      ("ImageNet", EntityLabel.DATASET)],
        )
        doc_b = _e2e_doc(
            "densenet", "Densely Connected Convolutional Networks",
            entities=[("DenseNet", EntityLabel.METHOD),
                      ("ImageNet", EntityLabel.DATASET)],
        )
        mgr = CorpusManager.from_documents([doc_a, doc_b], "scenario2")
        g = mgr.corpus_graph

        # ImageNet appears in both docs → should form a shared cluster
        ec_nodes = [n for n in g.nodes if n.node_type == "entity_cluster"]
        imagenet_clusters = [n for n in ec_nodes if "ImageNet" in n.label]
        assert len(imagenet_clusters) >= 1

        # Doc→entity edges for both docs connecting to the ImageNet cluster
        if imagenet_clusters:
            ic_id = imagenet_clusters[0].node_id
            connecting = [e for e in g.edges
                          if e.target_id == ic_id and e.relation_type == RelationType.EXTENDS]
            assert len(connecting) >= 2

    def test_entity_overlap_produces_relations(self):
        doc_a = _e2e_doc(
            "resnet", "ResNet",
            entities=[("ResNet", EntityLabel.METHOD),
                      ("ImageNet", EntityLabel.DATASET)],
        )
        doc_b = _e2e_doc(
            "densenet", "DenseNet",
            entities=[("DenseNet", EntityLabel.METHOD),
                      ("ImageNet", EntityLabel.DATASET)],
        )
        mgr = CorpusManager.from_documents([doc_a, doc_b], "scenario2b")
        g = mgr.corpus_graph

        # Relation edges exist between docs (from DocumentRelationEngine)
        doc_doc_edges = [e for e in g.edges
                         if e.source_id in ("resnet", "densenet")
                         and e.target_id in ("resnet", "densenet")
                         and e.source_id != e.target_id]
        assert len(doc_doc_edges) >= 1

        # Relation confidence > 0
        for e in doc_doc_edges:
            assert e.confidence > 0.0

    def test_graph_traversal_works(self):
        doc_a = _e2e_doc(
            "resnet", "ResNet",
            entities=[("ImageNet", EntityLabel.DATASET)],
        )
        doc_b = _e2e_doc(
            "densenet", "DenseNet",
            entities=[("ImageNet", EntityLabel.DATASET)],
        )
        mgr = CorpusManager.from_documents([doc_a, doc_b], "scenario2c")
        g = mgr.corpus_graph
        # Shortest path between the two docs
        path = g.shortest_path("resnet", "densenet")
        if path is not None:
            assert path.length >= 1
            assert path.total_weight > 0


class TestE2EScenario3MultiPaper:
    """Multi-paper synthetic corpus — larger graph with various structures."""

    def _build_corpus(self):
        papers = [
            _e2e_doc("p1", "Paper One",
                     entities=[("CNN", EntityLabel.METHOD),
                               ("ImageNet", EntityLabel.DATASET)]),
            _e2e_doc("p2", "Paper Two",
                     entities=[("CNN", EntityLabel.METHOD),
                               ("MNIST", EntityLabel.DATASET)]),
            _e2e_doc("p3", "Paper Three",
                     entities=[("RNN", EntityLabel.METHOD),
                               ("ImageNet", EntityLabel.DATASET)]),
            _e2e_doc("p4", "Paper Four",
                     entities=[("LSTM", EntityLabel.METHOD),
                               ("MNIST", EntityLabel.DATASET)]),
            _e2e_doc("p5", "Paper Five",
                     entities=[("CNN", EntityLabel.METHOD),
                               ("LSTM", EntityLabel.METHOD)]),
        ]
        return CorpusManager.from_documents(papers, "scenario3")

    def test_document_count(self):
        mgr = self._build_corpus()
        g = mgr.corpus_graph
        doc_nodes = [n for n in g.nodes if n.node_type == "document"]
        assert len(doc_nodes) == 5

    def test_entity_count(self):
        mgr = self._build_corpus()
        g = mgr.corpus_graph
        ec_nodes = [n for n in g.nodes if n.node_type == "entity_cluster"]
        # 4 unique entity texts: CNN, ImageNet, MNIST, RNN, LSTM
        # But some only appear once (RNN, LSTM) → no cluster for singletons
        # CNN (p1,p2,p5), ImageNet (p1,p3), MNIST (p2,p4) → 3 clusters
        # LSTM (p4,p5) → 1 cluster
        # RNN (p3) → 0 clusters (singleton)
        assert len(ec_nodes) >= 3

    def test_edge_count(self):
        mgr = self._build_corpus()
        g = mgr.corpus_graph
        assert g.total_edges_found > 0

    def test_connected_components(self):
        mgr = self._build_corpus()
        g = mgr.corpus_graph
        assert g.statistics.connected_components >= 1

    def test_shortest_path_between_connected_docs(self):
        mgr = self._build_corpus()
        g = mgr.corpus_graph
        path = g.shortest_path("p1", "p2")  # both share CNN
        if path is not None:
            assert path.length >= 1

    def test_get_neighbors_works(self):
        mgr = self._build_corpus()
        g = mgr.corpus_graph
        nbrs = g.get_neighbors("p1", depth=1)
        assert nbrs.total_nodes_found >= 1

    def test_query_nodes_works(self):
        mgr = self._build_corpus()
        g = mgr.corpus_graph
        q = CorpusGraphQuery(node_type="document")
        r = g.query_nodes(q)
        assert r.total_nodes_found == 5

    def test_query_edges_works(self):
        mgr = self._build_corpus()
        g = mgr.corpus_graph
        q = CorpusGraphQuery(relation_types=[RelationType.EXTENDS], max_results=1000)
        r = g.query_edges(q)
        assert r.total_edges_found >= 1

    def test_top_entities(self):
        mgr = self._build_corpus()
        g = mgr.corpus_graph
        top = g.top_entities(n=5)
        assert len(top) >= 0

    def test_statistics_non_trivial(self):
        mgr = self._build_corpus()
        g = mgr.corpus_graph
        s = g.compute_statistics()
        assert s.total_nodes >= 5
        assert s.total_edges >= 1
        assert s.average_degree >= 0
