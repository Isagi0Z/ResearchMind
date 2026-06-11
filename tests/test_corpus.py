"""Tests for the corpus management layer — DocumentStore implementations,
CorpusManager, indexes, statistics, lazy-loading, and persistence."""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from researchmind.models.enums import (
    CanonicalLabel,
    ClaimType,
    DocumentType,
    EntityLabel,
    ExtractionMethod,
    ExtractionRoute,
    ResolutionSource,
    ResolutionStatus,
    VenueType,
)
from researchmind.models.ruo import (
    Annotation,
    ComponentConfidence,
    ComponentSubscore,
    ConfidenceBreakdown,
    DocumentRelation,
    DocumentStore,
    EvidenceCoverage,
    ProvenanceRecord,
    RUOAbstract,
    RUOAuthor,
    RUOBody,
    RUOChunk,
    RUOCitation,
    RUOClaim,
    RUODocument,
    RUOEntity,
    RUOFigure,
    RUOHeader,
    RUOMeta,
    RUOQuality,
    RUOReference,
    RUOSection,
    RUOSourceFile,
    RUOTable,
    SemanticTriple,
    SROPipelineLogEntry,
)
from researchmind.models.ruo_enums import (
    CitationIntent,
    ProvenanceAction,
    ProvenanceAgentType,
    RelationType,
    ResolutionSource,
    ResolutionStatus,
    StageStatus,
)
from researchmind.storage.corpus import (
    ConfidenceStats,
    CorpusIndexes,
    CorpusManager,
    CorpusStatistics,
)
from researchmind.storage.document_store import (
    FilesystemDocumentStore,
    InMemoryDocumentStore,
)

_NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

# ===================================================================
# Helpers — minimal RUODocument factory
# ===================================================================


def _source_file(filename: str = "paper.pdf") -> RUOSourceFile:
    return RUOSourceFile(
        filename=filename,
        sha256="a" * 64,
        page_count=5,
        has_text_layer=True,
        is_scanned=False,
    )


def _meta(
    ruo_id: str = "doc_001",
) -> RUOMeta:
    return RUOMeta(
        ruo_id=ruo_id,
        created_at=_NOW,
        updated_at=_NOW,
        pipeline_version="2.1.0",
        source_file=_source_file(),
        extraction_route=ExtractionRoute.GROBID_PRIMARY,
        document_type=DocumentType.RESEARCH_ARTICLE,
    )


def _header(
    title: str = "Test Document",
    authors: list[str] | None = None,
    publication_date: str | None = None,
) -> RUOHeader:
    author_models: list[RUOAuthor] = []
    if authors:
        for i, name in enumerate(authors):
            author_models.append(RUOAuthor(full_name=name))
    conf = ComponentConfidence(
        component="header",
        score=0.85,
        subscores=[ComponentSubscore(name="header", value=0.85, weight=1.0)],
    )
    return RUOHeader(
        title=title,
        authors=author_models,
        document_type=DocumentType.RESEARCH_ARTICLE,
        confidence=conf,
        publication_date=publication_date,
    )


def _section(sid: str = "s1") -> RUOSection:
    return RUOSection(
        section_id=sid,
        level=1,
        position=0,
        original_header="Introduction",
        canonical_label=CanonicalLabel.INTRODUCTION,
        label_confidence=0.9,
        page_start=0,
        page_end=2,
        content="Section content.",
        extraction_method=ExtractionMethod.GROBID,
    )


def _chunk(cid: str = "c1") -> RUOChunk:
    return RUOChunk(
        chunk_id=cid,
        text="Chunk text.",
        word_count=2,
        section_id="s1",
        canonical_label=CanonicalLabel.INTRODUCTION,
        page_start=0,
        page_end=1,
        paragraph_index=0,
        reading_order=0,
        extraction_method=ExtractionMethod.GROBID,
        extraction_confidence=0.9,
    )


def _body() -> RUOBody:
    return RUOBody(
        sections=[_section()],
        chunks=[_chunk()],
    )


def _entity(
    eid: str = "e1",
    text: str = "BERT",
    label: EntityLabel = EntityLabel.METHOD,
) -> RUOEntity:
    return RUOEntity(
        entity_id=eid,
        text=text,
        label=label,
        chunk_id="c1",
        sentence="BERT is a model.",
        confidence=0.9,
        source="ner",
    )


def _claim(
    cid: str = "cl1",
    sentence: str = "BERT achieves SOTA.",
    claim_type: ClaimType = ClaimType.STATISTICAL,
) -> RUOClaim:
    return RUOClaim(
        claim_id=cid,
        sentence=sentence,
        chunk_id="c1",
        section_id="s1",
        canonical_label=CanonicalLabel.INTRODUCTION,
        claim_type=claim_type,
        matched_patterns=["statistical"],
        confidence=0.85,
        page=1,
        evidence_chain_id=f"ech_{cid}",
    )


def _triple(
    tid: str = "t1",
    predicate: str = "uses",
    subject_text: str = "BERT",
    object_text: str = "ImageNet",
) -> SemanticTriple:
    return SemanticTriple(
        triple_id=tid,
        subject_id="e1",
        subject_text=subject_text,
        predicate=predicate,
        object_id="e2",
        object_text=object_text,
        confidence=0.8,
        chunk_id="c1",
    )


def _reference(
    rid: str = "r1",
    target_ruo_id: str | None = None,
    title: str = "A Reference Paper",
    resolved: bool = False,
) -> RUOReference:
    return RUOReference(
        ref_id=rid,
        raw_text=title,
        title=title if resolved else None,
        year="2023" if resolved else None,
        resolution_status=ResolutionStatus.RESOLVED if resolved else ResolutionStatus.UNRESOLVED,
        resolution_source=ResolutionSource.CROSSREF_LOOKUP if resolved else ResolutionSource.NONE,
        ref_confidence=0.9 if resolved else 0.0,
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
        component="overall",
        score=overall,
        subscores=[ComponentSubscore(name="overall", value=overall, weight=1.0)],
    )
    breakdown = ConfidenceBreakdown(
        components=[comp],
        overall=overall,
        component_weights={"overall": 1.0},
    )
    return RUOQuality(
        confidence=breakdown,
        evidence_coverage=_coverage(),
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

    header = _header(title=title, authors=authors, publication_date=year)

    entity_models = []
    if entities:
        for i, (text, label) in enumerate(entities):
            entity_models.append(_entity(eid=f"e{i}", text=text, label=label))

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
                ref_id, target = ref
                ref_models.append(_reference(rid=ref_id, target_ruo_id=target, resolved=True))
            else:
                ref_models.append(_reference(rid=f"r{i}", title=ref))

    return RUODocument(
        meta=meta,
        header=header,
        body=_body(),
        entities=entity_models,
        claims=claim_models,
        triples=triple_models,
        references=ref_models,
        quality=_quality(overall=confidence),
        provenance=[],
    )


# ===================================================================
# InMemoryDocumentStore tests
# ===================================================================


class TestInMemoryDocumentStore:
    def test_put_and_get(self):
        store = InMemoryDocumentStore()
        doc = make_doc("d1")
        store.put(doc)
        assert store.get("d1") is doc

    def test_get_nonexistent(self):
        store = InMemoryDocumentStore()
        assert store.get("nonexistent") is None

    def test_get_batch(self):
        store = InMemoryDocumentStore()
        d1, d2 = make_doc("d1"), make_doc("d2")
        store.put(d1)
        store.put(d2)
        result = store.get_batch(["d1", "d2", "d3"])
        assert result == {"d1": d1, "d2": d2}

    def test_put_overwrites(self):
        store = InMemoryDocumentStore()
        d1 = make_doc("d1", title="First")
        d2 = make_doc("d1", title="Second")
        store.put(d1)
        store.put(d2)
        assert store.get("d1").header.title == "Second"

    def test_delete_existing(self):
        store = InMemoryDocumentStore()
        store.put(make_doc("d1"))
        assert store.delete("d1") is True
        assert store.get("d1") is None

    def test_delete_nonexistent(self):
        store = InMemoryDocumentStore()
        assert store.delete("nonexistent") is False

    def test_contains(self):
        store = InMemoryDocumentStore()
        store.put(make_doc("d1"))
        assert store.contains("d1") is True
        assert store.contains("d2") is False

    def test_list_ids(self):
        store = InMemoryDocumentStore()
        store.put(make_doc("b"))
        store.put(make_doc("a"))
        assert set(store.list_ids()) == {"a", "b"}

    def test_count(self):
        store = InMemoryDocumentStore()
        assert store.count() == 0
        store.put(make_doc("d1"))
        store.put(make_doc("d2"))
        assert store.count() == 2

    def test_constructor_with_docs(self):
        d1 = make_doc("d1")
        d2 = make_doc("d2")
        store = InMemoryDocumentStore({"d1": d1, "d2": d2})
        assert store.count() == 2
        assert store.get("d1") is d1

    def test_constructor_key_mismatch_raises(self):
        d1 = make_doc("d1")
        with pytest.raises(ValueError, match="does not match"):
            InMemoryDocumentStore({"wrong_key": d1})

    def test_put_key_mismatch_not_checked(self):
        store = InMemoryDocumentStore()
        d = make_doc("actual_id")
        store.put(d)
        assert store.get("actual_id") is d


# ===================================================================
# FilesystemDocumentStore tests
# ===================================================================


class TestFilesystemDocumentStore:
    @pytest.fixture
    def tmpdir(self):
        d = tempfile.mkdtemp()
        yield Path(d)
        shutil.rmtree(d)

    def test_put_and_get(self, tmpdir):
        store = FilesystemDocumentStore(tmpdir)
        doc = make_doc("d1")
        store.put(doc)
        loaded = store.get("d1")
        assert loaded is not None
        assert loaded.meta.ruo_id == "d1"
        assert loaded.header.title == "Test Document"

    def test_get_nonexistent(self, tmpdir):
        store = FilesystemDocumentStore(tmpdir)
        assert store.get("nonexistent") is None

    def test_get_batch(self, tmpdir):
        store = FilesystemDocumentStore(tmpdir)
        d1, d2 = make_doc("d1"), make_doc("d2")
        store.put(d1)
        store.put(d2)
        result = store.get_batch(["d1", "d2", "d3"])
        assert set(result.keys()) == {"d1", "d2"}

    def test_put_overwrites(self, tmpdir):
        store = FilesystemDocumentStore(tmpdir)
        store.put(make_doc("d1", title="First"))
        store.put(make_doc("d1", title="Second"))
        assert store.get("d1").header.title == "Second"

    def test_delete(self, tmpdir):
        store = FilesystemDocumentStore(tmpdir)
        store.put(make_doc("d1"))
        assert store.delete("d1") is True
        assert store.get("d1") is None

    def test_delete_nonexistent(self, tmpdir):
        store = FilesystemDocumentStore(tmpdir)
        assert store.delete("nonexistent") is False

    def test_contains(self, tmpdir):
        store = FilesystemDocumentStore(tmpdir)
        store.put(make_doc("d1"))
        assert store.contains("d1") is True
        assert store.contains("d2") is False

    def test_list_ids(self, tmpdir):
        store = FilesystemDocumentStore(tmpdir)
        store.put(make_doc("b"))
        store.put(make_doc("a"))
        assert set(store.list_ids()) == {"a", "b"}

    def test_count(self, tmpdir):
        store = FilesystemDocumentStore(tmpdir)
        assert store.count() == 0
        store.put(make_doc("d1"))
        assert store.count() == 1

    def test_persistence_across_instances(self, tmpdir):
        store1 = FilesystemDocumentStore(tmpdir)
        store1.put(make_doc("d1", title="Persistent"))
        del store1
        store2 = FilesystemDocumentStore(tmpdir)
        loaded = store2.get("d1")
        assert loaded is not None
        assert loaded.header.title == "Persistent"
        assert loaded.meta.ruo_id == "d1"

    def test_directory_created_automatically(self, tmpdir):
        nested = tmpdir / "a" / "b" / "c"
        store = FilesystemDocumentStore(nested)
        store.put(make_doc("d1"))
        assert (nested / "d1.json").exists()

    def test_corrupted_json_returns_none(self, tmpdir):
        store = FilesystemDocumentStore(tmpdir)
        (tmpdir / "bad.json").write_text("{invalid", encoding="utf-8")
        assert store.get("bad") is None

    def test_list_ids_empty_dir(self, tmpdir):
        store = FilesystemDocumentStore(tmpdir)
        assert store.list_ids() == []


# ===================================================================
# CorpusManager — construction
# ===================================================================


class TestCorpusManagerConstruction:
    def test_create_empty(self):
        mgr = CorpusManager.create("c1", name="Test", description="A test corpus")
        assert mgr.corpus.corpus_id == "c1"
        assert mgr.corpus.name == "Test"
        assert mgr.corpus.description == "A test corpus"
        assert mgr.corpus.document_ids == []

    def test_create_default_name(self):
        mgr = CorpusManager.create("c1")
        assert mgr.corpus.name == ""

    def test_from_documents(self):
        docs = [make_doc("d1", title="Doc 1"), make_doc("d2", title="Doc 2")]
        mgr = CorpusManager.from_documents(docs, corpus_id="c1")
        assert mgr.corpus.document_ids == ["d1", "d2"]
        assert mgr.store is not None
        assert mgr.store.count() == 2

    def test_from_documents_single(self):
        doc = make_doc("d1")
        mgr = CorpusManager.from_documents([doc], corpus_id="c1")
        assert mgr.corpus.document_ids == ["d1"]

    def test_store_is_inmemory_by_default(self):
        docs = [make_doc("d1")]
        mgr = CorpusManager.from_documents(docs, "c1")
        assert isinstance(mgr.store, InMemoryDocumentStore)

    def test_attach_store(self):
        store = InMemoryDocumentStore()
        store.put(make_doc("d1"))
        mgr = CorpusManager.create("c1")
        mgr.attach_store(store)
        assert mgr.store is store
        assert mgr.get_document("d1") is not None

    def test_get_document_without_store_raises(self):
        mgr = CorpusManager.create("c1")
        with pytest.raises(RuntimeError, match="No DocumentStore"):
            mgr.get_document("d1")

    def test_get_documents_without_store_raises(self):
        mgr = CorpusManager.create("c1")
        with pytest.raises(RuntimeError, match="No DocumentStore"):
            mgr.get_documents()

    def test_create_then_add_document(self):
        mgr = CorpusManager.create("c1")
        mgr.attach_store(InMemoryDocumentStore())
        doc = make_doc("d1")
        mgr.add_document(doc)
        assert "d1" in mgr.corpus.document_ids
        assert mgr.get_document("d1") is doc

    def test_add_document_updates_updated_at(self):
        mgr = CorpusManager.create("c1")
        before = mgr.corpus.updated_at
        mgr.add_document(make_doc("d1"))
        assert mgr.corpus.updated_at >= before

    def test_add_duplicate_document(self):
        mgr = CorpusManager.create("c1")
        mgr.add_document(make_doc("d1"))
        mgr.add_document(make_doc("d1"))  # should not raise
        assert mgr.corpus.document_ids.count("d1") == 1


# ===================================================================
# CorpusManager — document lifecycle
# ===================================================================


class TestCorpusManagerDocumentLifecycle:
    def test_add_and_remove(self):
        mgr = CorpusManager.create("c1", store=InMemoryDocumentStore())
        mgr.add_document(make_doc("d1"))
        assert mgr.remove_document("d1") is True
        assert mgr.corpus.document_ids == []

    def test_remove_nonexistent(self):
        mgr = CorpusManager.create("c1")
        assert mgr.remove_document("nonexistent") is False

    def test_remove_also_deletes_relations(self):
        mgr = CorpusManager.create("c1", store=InMemoryDocumentStore())
        mgr.add_document(make_doc("d1"))
        mgr.add_document(make_doc("d2"))
        rel = DocumentRelation(
            relation_id="r1",
            source_ruo_id="d1",
            target_ruo_id="d2",
            relation_type=RelationType.CITES,
            confidence=1.0,
            detected_at=_NOW,
        )
        mgr.add_relation(rel)
        mgr.remove_document("d1")
        assert mgr.corpus.relations == []

    def test_add_relation(self):
        mgr = CorpusManager.create("c1", store=InMemoryDocumentStore())
        mgr.add_document(make_doc("d1"))
        mgr.add_document(make_doc("d2"))
        rel = DocumentRelation(
            relation_id="r1",
            source_ruo_id="d1",
            target_ruo_id="d2",
            relation_type=RelationType.CITES,
            confidence=1.0,
            detected_at=_NOW,
        )
        mgr.add_relation(rel)
        assert len(mgr.corpus.relations) == 1

    def test_get_relations_filtered(self):
        mgr = CorpusManager.create("c1", store=InMemoryDocumentStore())
        mgr.add_document(make_doc("d1"))
        mgr.add_document(make_doc("d2"))
        r1 = DocumentRelation(
            relation_id="r1", source_ruo_id="d1", target_ruo_id="d2",
            relation_type=RelationType.CITES, confidence=1.0, detected_at=_NOW,
        )
        r2 = DocumentRelation(
            relation_id="r2", source_ruo_id="d2", target_ruo_id="d1",
            relation_type=RelationType.SUPPORTS, confidence=1.0, detected_at=_NOW,
        )
        mgr.add_relation(r1)
        mgr.add_relation(r2)
        cites = mgr.get_relations(RelationType.CITES)
        supports = mgr.get_relations(RelationType.SUPPORTS)
        assert len(cites) == 1
        assert len(supports) == 1
        assert cites[0].relation_id == "r1"


# ===================================================================
# CorpusManager — indexes
# ===================================================================


class TestCorpusManagerIndexes:
    def test_empty_corpus_indexes(self):
        mgr = CorpusManager.create("c1", store=InMemoryDocumentStore())
        idx = mgr.indexes
        assert idx.by_entity_label == {}
        assert idx.by_author_name == {}
        assert idx.by_year == {}
        assert idx.by_claim_type == {}

    def test_entity_label_index(self):
        docs = [
            make_doc("d1", entities=[("BERT", EntityLabel.METHOD)]),
            make_doc("d2", entities=[("CNN", EntityLabel.METHOD)]),
            make_doc("d3", entities=[("ImageNet", EntityLabel.DATASET)]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        idx = mgr.indexes
        assert set(idx.by_entity_label["method"]) == {"d1", "d2"}
        assert idx.by_entity_label["dataset"] == ["d3"]

    def test_entity_text_index(self):
        docs = [
            make_doc("d1", entities=[("BERT", EntityLabel.METHOD)]),
            make_doc("d2", entities=[("bert", EntityLabel.METHOD)]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        idx = mgr.indexes
        assert len(idx.by_entity_text["bert"]) == 2

    def test_claim_type_index(self):
        docs = [
            make_doc("d1", claims=[("SOTA", ClaimType.STATISTICAL)]),
            make_doc("d2", claims=[("Outperforms", ClaimType.COMPARATIVE)]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        idx = mgr.indexes
        assert idx.by_claim_type["statistical"] == ["d1"]
        assert idx.by_claim_type["comparative"] == ["d2"]

    def test_author_name_index(self):
        docs = [
            make_doc("d1", authors=["Alice Smith"]),
            make_doc("d2", authors=["Bob Jones"]),
            make_doc("d3", authors=["Alice Smith"]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        idx = mgr.indexes
        assert set(idx.by_author_name["alice smith"]) == {"d1", "d3"}
        assert idx.by_author_name["bob jones"] == ["d2"]

    def test_year_index(self):
        docs = [
            make_doc("d1", year="2023"),
            make_doc("d2", year="2024"),
            make_doc("d3", year="2024"),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        idx = mgr.indexes
        assert idx.by_year["2023"] == ["d1"]
        assert set(idx.by_year["2024"]) == {"d2", "d3"}

    def test_research_field_index(self):
        docs = [
            make_doc("d1", research_fields=["NLP", "ML"]),
            make_doc("d2", research_fields=["CV"]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        idx = mgr.indexes
        assert idx.by_research_field["NLP"] == ["d1"]
        assert idx.by_research_field["CV"] == ["d2"]

    def test_predicate_index(self):
        docs = [
            make_doc("d1", triples=[("BERT", "uses")]),
            make_doc("d2", triples=[("CNN", "evaluated_on")]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        idx = mgr.indexes
        assert len(idx.by_predicate["uses"]) == 1
        assert len(idx.by_predicate["evaluated_on"]) == 1
        rid, tid = idx.by_predicate["uses"][0]
        assert rid == "d1"

    def test_citation_network_index_from_references(self):
        docs = [
            make_doc("d1", references=[("r1", "d2")]),
            make_doc("d2", references=[]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        idx = mgr.indexes
        assert idx.citations_from.get("d1") == ["d2"]
        assert idx.citations_to.get("d2") == ["d1"]

    def test_citation_network_index_from_relations(self):
        docs = [
            make_doc("d1"),
            make_doc("d2"),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        rel = DocumentRelation(
            relation_id="r1", source_ruo_id="d1", target_ruo_id="d2",
            relation_type=RelationType.CITES, confidence=1.0, detected_at=_NOW,
        )
        mgr.add_relation(rel)
        idx = mgr.indexes
        assert idx.citations_from.get("d1") == ["d2"]
        assert idx.citations_to.get("d2") == ["d1"]

    def test_rebuild_indexes_after_add(self):
        mgr = CorpusManager.create("c1", store=InMemoryDocumentStore())
        idx1 = mgr.indexes
        assert idx1.by_entity_label == {}

        mgr.add_document(make_doc("d1", entities=[("BERT", EntityLabel.METHOD)]))
        idx2 = mgr.indexes
        assert idx2.by_entity_label["method"] == ["d1"]

    def test_rebuild_indexes_after_remove(self):
        mgr = CorpusManager.create("c1", store=InMemoryDocumentStore())
        mgr.add_document(make_doc("d1", entities=[("BERT", EntityLabel.METHOD)]))
        mgr.add_document(make_doc("d2", entities=[("CNN", EntityLabel.METHOD)]))
        idx1 = mgr.indexes
        assert len(idx1.by_entity_label["method"]) == 2

        mgr.remove_document("d1")
        idx2 = mgr.indexes
        assert idx2.by_entity_label["method"] == ["d2"]

    def test_indexes_are_cached(self):
        mgr = CorpusManager.from_documents([make_doc("d1")], "c1")
        i1 = mgr.indexes
        i2 = mgr.indexes
        assert i1 is i2


# ===================================================================
# CorpusManager — find / query
# ===================================================================


class TestCorpusManagerQuery:
    def test_find_by_entity_label(self):
        docs = [
            make_doc("d1", entities=[("BERT", EntityLabel.METHOD)]),
            make_doc("d2", entities=[("CNN", EntityLabel.METHOD)]),
            make_doc("d3", entities=[("ImageNet", EntityLabel.DATASET)]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        results = mgr.find_by_entity_label("method")
        assert {d.meta.ruo_id for d in results} == {"d1", "d2"}

    def test_find_by_entity_label_none(self):
        mgr = CorpusManager.create("c1", store=InMemoryDocumentStore())
        assert mgr.find_by_entity_label("method") == []

    def test_find_by_author_name(self):
        docs = [
            make_doc("d1", authors=["Alice Smith"]),
            make_doc("d2", authors=["Bob Jones"]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        results = mgr.find_by_author_name("Alice Smith")
        assert len(results) == 1
        assert results[0].meta.ruo_id == "d1"

    def test_find_by_author_name_case_insensitive(self):
        docs = [make_doc("d1", authors=["ALICE SMITH"])]
        mgr = CorpusManager.from_documents(docs, "c1")
        assert len(mgr.find_by_author_name("alice smith")) == 1

    def test_find_by_year(self):
        docs = [
            make_doc("d1", year="2023"),
            make_doc("d2", year="2024"),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        assert len(mgr.find_by_year("2024")) == 1
        assert mgr.find_by_year("2020") == []

    def test_find_by_claim_type(self):
        docs = [
            make_doc("d1", claims=[("SOTA", ClaimType.STATISTICAL)]),
            make_doc("d2", claims=[("Outperforms", ClaimType.COMPARATIVE)]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        assert len(mgr.find_by_claim_type("statistical")) == 1
        assert len(mgr.find_by_claim_type("nonexistent")) == 0

    def test_find_by_research_field(self):
        docs = [
            make_doc("d1", research_fields=["NLP"]),
            make_doc("d2", research_fields=["CV"]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        assert len(mgr.find_by_research_field("NLP")) == 1
        assert mgr.find_by_research_field("Nonexistent") == []


# ===================================================================
# CorpusManager — statistics
# ===================================================================


class TestCorpusManagerStatistics:
    def test_empty_statistics(self):
        mgr = CorpusManager.create("c1", store=InMemoryDocumentStore())
        stats = mgr.statistics
        assert stats.document_count == 0
        assert stats.total_entities == 0
        assert stats.total_claims == 0

    def test_document_count(self):
        docs = [make_doc("d1"), make_doc("d2"), make_doc("d3")]
        mgr = CorpusManager.from_documents(docs, "c1")
        assert mgr.statistics.document_count == 3

    def test_total_entities(self):
        docs = [
            make_doc("d1", entities=[("BERT", EntityLabel.METHOD)]),
            make_doc("d2", entities=[("CNN", EntityLabel.METHOD), ("ResNet", EntityLabel.METHOD)]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        assert mgr.statistics.total_entities == 3

    def test_entities_by_label(self):
        docs = [
            make_doc("d1", entities=[("BERT", EntityLabel.METHOD)]),
            make_doc("d2", entities=[("CNN", EntityLabel.METHOD), ("ImageNet", EntityLabel.DATASET)]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        assert mgr.statistics.entities_by_label["method"] == 2
        assert mgr.statistics.entities_by_label["dataset"] == 1

    def test_total_claims(self):
        docs = [
            make_doc("d1", claims=[("SOTA", ClaimType.STATISTICAL)]),
            make_doc("d2", claims=[("Outperforms", ClaimType.COMPARATIVE), ("Better", ClaimType.COMPARATIVE)]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        assert mgr.statistics.total_claims == 3

    def test_claims_by_type(self):
        docs = [
            make_doc("d1", claims=[("SOTA", ClaimType.STATISTICAL)]),
            make_doc("d2", claims=[("Outperforms", ClaimType.COMPARATIVE)]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        assert mgr.statistics.claims_by_type["statistical"] == 1
        assert mgr.statistics.claims_by_type["comparative"] == 1

    def test_total_triples(self):
        docs = [
            make_doc("d1", triples=[("BERT", "uses")]),
            make_doc("d2", triples=[("CNN", "uses"), ("ResNet", "evaluated_on")]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        assert mgr.statistics.total_triples == 3

    def test_triples_by_predicate(self):
        docs = [
            make_doc("d1", triples=[("BERT", "uses")]),
            make_doc("d2", triples=[("CNN", "evaluated_on")]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        assert mgr.statistics.triples_by_predicate["uses"] == 1
        assert mgr.statistics.triples_by_predicate["evaluated_on"] == 1

    def test_total_authors(self):
        docs = [
            make_doc("d1", authors=["Alice Smith", "Bob Jones"]),
            make_doc("d2", authors=["Charlie Brown"]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        assert mgr.statistics.total_authors == 3

    def test_distinct_author_names(self):
        docs = [
            make_doc("d1", authors=["Alice Smith"]),
            make_doc("d2", authors=["Alice Smith", "Bob Jones"]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        assert mgr.statistics.distinct_author_names == 2

    def test_year_distribution(self):
        docs = [
            make_doc("d1", year="2023"),
            make_doc("d2", year="2024"),
            make_doc("d3", year="2024"),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        assert mgr.statistics.year_distribution["2023"] == 1
        assert mgr.statistics.year_distribution["2024"] == 2

    def test_confidence_stats(self):
        docs = [
            make_doc("d1", confidence=0.9),
            make_doc("d2", confidence=0.8),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        cs = mgr.statistics.overall_confidence
        assert cs.mean == 0.85
        assert cs.min == 0.8
        assert cs.max == 0.9
        assert cs.std > 0

    def test_single_document_confidence_std_is_zero(self):
        docs = [make_doc("d1", confidence=0.85)]
        mgr = CorpusManager.from_documents(docs, "c1")
        assert mgr.statistics.overall_confidence.std == 0.0

    def test_citation_network_edges(self):
        docs = [
            make_doc("d1", references=[("r1", "d2")]),
            make_doc("d2", references=[]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        assert mgr.statistics.citation_network_edges == 1

    def test_citation_network_density_two_docs(self):
        docs = [
            make_doc("d1", references=[("r1", "d2")]),
            make_doc("d2", references=[]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        # 2 docs, 1 edge → density = 1/(2*1) = 0.5
        assert mgr.statistics.citation_network_density == 0.5

    def test_citation_network_density_no_edges(self):
        docs = [make_doc("d1"), make_doc("d2")]
        mgr = CorpusManager.from_documents(docs, "c1")
        assert mgr.statistics.citation_network_edges == 0
        assert mgr.statistics.citation_network_density == 0.0

    def test_statistics_are_cached(self):
        mgr = CorpusManager.from_documents([make_doc("d1")], "c1")
        s1 = mgr.statistics
        s2 = mgr.statistics
        assert s1 is s2

    def test_statistics_recomputed_after_add(self):
        mgr = CorpusManager.create("c1", store=InMemoryDocumentStore())
        mgr.add_document(make_doc("d1"))
        assert mgr.statistics.document_count == 1
        mgr.add_document(make_doc("d2"))
        assert mgr.statistics.document_count == 2

    def test_coverage_aggregation(self):
        mgr = CorpusManager.create("c1", store=InMemoryDocumentStore())
        d1 = make_doc("d1")
        mgr.add_document(d1)
        assert mgr.statistics.coverage is not None
        assert mgr.statistics.coverage.total_claims >= 1


# ===================================================================
# CorpusManager — persistence (save / load)
# ===================================================================


class TestCorpusManagerPersistence:
    @pytest.fixture
    def tmpdir(self):
        d = tempfile.mkdtemp()
        yield Path(d)
        shutil.rmtree(d)

    def test_save_creates_files(self, tmpdir):
        docs = [make_doc("d1"), make_doc("d2")]
        mgr = CorpusManager.from_documents(docs, "c1")
        mgr.save(tmpdir)
        assert (tmpdir / "corpus.json").exists()
        assert (tmpdir / "indexes.json").exists()
        assert (tmpdir / "statistics.json").exists()

    def test_save_and_load_roundtrip(self, tmpdir):
        docs = [make_doc("d1", title="Original")]
        mgr1 = CorpusManager.from_documents(docs, "c1")
        mgr1.save(tmpdir)
        mgr2 = CorpusManager.load(tmpdir)
        assert mgr2.corpus.corpus_id == "c1"
        assert mgr2.corpus.document_ids == ["d1"]
        assert mgr2.statistics.document_count == 1

    def test_load_with_store(self, tmpdir):
        doc = make_doc("d1", title="Lazy Load")
        mgr1 = CorpusManager.from_documents([doc], "c1")
        mgr1.save(tmpdir)
        store = FilesystemDocumentStore(tmpdir)
        store.put(doc)
        mgr2 = CorpusManager.load(tmpdir, store=store)
        loaded = mgr2.get_document("d1")
        assert loaded is not None
        assert loaded.header.title == "Lazy Load"

    def test_load_missing_file(self, tmpdir):
        with pytest.raises(FileNotFoundError):
            CorpusManager.load(tmpdir / "nonexistent")

    def test_save_preserves_indexes(self, tmpdir):
        docs = [
            make_doc("d1", entities=[("BERT", EntityLabel.METHOD)]),
            make_doc("d2", entities=[("CNN", EntityLabel.METHOD)]),
        ]
        mgr1 = CorpusManager.from_documents(docs, "c1")
        mgr1.save(tmpdir)
        mgr2 = CorpusManager.load(tmpdir)
        assert mgr2.indexes.by_entity_label["method"] == ["d1", "d2"]

    def test_save_preserves_statistics(self, tmpdir):
        docs = [make_doc("d1"), make_doc("d2")]
        mgr1 = CorpusManager.from_documents(docs, "c1")
        mgr1.save(tmpdir)
        mgr2 = CorpusManager.load(tmpdir)
        assert mgr2.statistics.document_count == 2

    def test_save_then_add_document(self, tmpdir):
        mgr = CorpusManager.create("c1", store=InMemoryDocumentStore())
        mgr.add_document(make_doc("d1"))
        mgr.save(tmpdir)
        mgr.add_document(make_doc("d2"))
        mgr.save(tmpdir)
        mgr2 = CorpusManager.load(tmpdir)
        assert mgr2.corpus.document_ids == ["d1", "d2"]


# ===================================================================
# CorpusManager — lazy loading
# ===================================================================


class TestCorpusManagerLazyLoading:
    def test_get_document_loads_from_store(self):
        store = InMemoryDocumentStore()
        doc = make_doc("d1")
        store.put(doc)
        mgr = CorpusManager.create("c1", store=store)
        loaded = mgr.get_document("d1")
        assert loaded is doc

    def test_get_documents_loads_all(self):
        store = InMemoryDocumentStore()
        d1, d2 = make_doc("d1"), make_doc("d2")
        store.put(d1)
        store.put(d2)
        mgr = CorpusManager.from_documents([d1, d2], "c1")
        mgr.attach_store(store)
        all_docs = mgr.get_documents()
        assert len(all_docs) == 2

    def test_get_documents_subset(self):
        store = InMemoryDocumentStore()
        d1, d2, d3 = make_doc("d1"), make_doc("d2"), make_doc("d3")
        for d in (d1, d2, d3):
            store.put(d)
        mgr = CorpusManager.from_documents([d1, d2, d3], "c1")
        mgr.attach_store(store)
        subset = mgr.get_documents(["d1", "d3"])
        assert len(subset) == 2

    def test_store_not_required_for_create(self):
        mgr = CorpusManager.create("c1")
        assert mgr.store is None

    def test_find_methods_use_lazy_loading(self):
        store = InMemoryDocumentStore()
        d1 = make_doc("d1", entities=[("BERT", EntityLabel.METHOD)])
        d2 = make_doc("d2", entities=[("CNN", EntityLabel.METHOD)])
        store.put(d1)
        store.put(d2)
        mgr = CorpusManager.from_documents([d1, d2], "c1")
        mgr.attach_store(store)
        results = mgr.find_by_entity_label("method")
        assert len(results) == 2


# ===================================================================
# DocumentStore — abstract base
# ===================================================================


class TestDocumentStoreABC:
    def test_abc_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            DocumentStore()  # type: ignore[abstract]


# ===================================================================
# Edge cases
# ===================================================================


class TestCorpusEdgeCases:
    def test_document_with_no_entities(self):
        mgr = CorpusManager.from_documents([make_doc("d1", entities=[])], "c1")
        assert mgr.statistics.total_entities == 0
        assert mgr.indexes.by_entity_label == {}

    def test_document_with_no_claims(self):
        mgr = CorpusManager.from_documents([make_doc("d1", claims=[])], "c1")
        assert mgr.statistics.total_claims == 0

    def test_document_with_no_triples(self):
        mgr = CorpusManager.from_documents([make_doc("d1", triples=[])], "c1")
        assert mgr.statistics.total_triples == 0

    def test_document_with_no_authors(self):
        mgr = CorpusManager.from_documents([make_doc("d1", authors=[])], "c1")
        assert mgr.statistics.total_authors == 0

    def test_document_with_no_year(self):
        doc = make_doc("d1", year=None)
        mgr = CorpusManager.from_documents([doc], "c1")
        assert mgr.statistics.year_distribution == {}

    def test_many_entities_same_label(self):
        ents = [("e", EntityLabel.METHOD) for _ in range(10)]
        mgr = CorpusManager.from_documents([make_doc("d1", entities=ents)], "c1")
        assert mgr.statistics.total_entities == 10
        assert mgr.statistics.distinct_entity_labels == 1

    def test_mixed_entity_labels(self):
        ents = [
            ("BERT", EntityLabel.METHOD),
            ("ImageNet", EntityLabel.DATASET),
            ("F1", EntityLabel.METRIC),
        ]
        mgr = CorpusManager.from_documents([make_doc("d1", entities=ents)], "c1")
        assert mgr.statistics.distinct_entity_labels == 3

    def test_duplicate_entity_text_across_docs(self):
        docs = [
            make_doc("d1", entities=[("BERT", EntityLabel.METHOD)]),
            make_doc("d2", entities=[("BERT", EntityLabel.METHOD)]),
        ]
        mgr = CorpusManager.from_documents(docs, "c1")
        idx = mgr.indexes
        assert len(idx.by_entity_text["bert"]) == 2

    def test_empty_corpus_statistics_defaults(self):
        mgr = CorpusManager.create("c1", store=InMemoryDocumentStore())
        stats = mgr.statistics
        assert stats.document_count == 0
        assert stats.overall_confidence == ConfidenceStats()
        assert stats.citation_network_density == 0.0

    def test_remove_all_documents(self):
        mgr = CorpusManager.create("c1", store=InMemoryDocumentStore())
        mgr.add_document(make_doc("d1"))
        mgr.add_document(make_doc("d2"))
        mgr.remove_document("d1")
        mgr.remove_document("d2")
        stats = mgr.statistics
        assert stats.document_count == 0

    def test_add_document_rebuilds_indexes(self):
        mgr = CorpusManager.create("c1", store=InMemoryDocumentStore())
        mgr.add_document(make_doc("d1", entities=[("BERT", EntityLabel.METHOD)]))
        assert "method" in mgr.indexes.by_entity_label
        mgr.add_document(make_doc("d2", entities=[("CNN", EntityLabel.METHOD)]))
        assert len(mgr.indexes.by_entity_label["method"]) == 2

    def test_attach_store_after_construction(self):
        mgr = CorpusManager.create("c1")
        store = InMemoryDocumentStore()
        store.put(make_doc("d1"))
        mgr.attach_store(store)
        assert mgr.get_document("d1") is not None

    def test_attach_store_invalidates_cache(self):
        mgr = CorpusManager.create("c1", store=InMemoryDocumentStore())
        mgr.add_document(make_doc("d1", entities=[("BERT", EntityLabel.METHOD)]))
        idx_before = mgr.indexes
        mgr.attach_store(InMemoryDocumentStore())
        idx_after = mgr.indexes
        assert idx_before is not idx_after

    def test_filesystem_store_concurrent_access(self, tmpdir):
        # Two stores pointing to the same directory
        s1 = FilesystemDocumentStore(tmpdir)
        s2 = FilesystemDocumentStore(tmpdir)
        s1.put(make_doc("d1"))
        assert s2.get("d1") is not None

    @pytest.fixture
    def tmpdir(self):
        d = tempfile.mkdtemp()
        yield Path(d)
        shutil.rmtree(d)


# ===================================================================
# CorpusGraph integration — cached property on CorpusManager
# ===================================================================


class TestCorpusManagerGraphCache:
    """Part A: corpus_graph cached property — lazy build, cache hit,
    invalidation, empty/single/multi-document scenarios."""

    def _make_mgr(self, docs, corpus_id="test-graph") -> CorpusManager:
        return CorpusManager.from_documents(docs, corpus_id)

    @staticmethod
    def _graph_doc(
        ruo_id: str = "d1",
        entities: list[tuple[str, EntityLabel]] | None = None,
        references: list[str | tuple[str, str]] | None = None,
    ) -> RUODocument:
        """Create a document with unique entity IDs for graph testing."""
        doc = make_doc(ruo_id, entities=entities, references=references)
        # Override entities with unique entity IDs per document
        doc.entities = [
            RUOEntity(
                entity_id=f"{ruo_id}_e{i}",
                text=text, label=label,
                chunk_id=doc.entities[i].chunk_id if i < len(doc.entities) else "c1",
                sentence=f"Sentence about {text}.",
                confidence=0.9,
                source="ner",
            ) for i, (text, label) in enumerate(entities or [])
        ]
        # Override references
        from researchmind.models.ruo_enums import ResolutionStatus, ResolutionSource
        refs = []
        if references:
            for i, ref in enumerate(references):
                if isinstance(ref, tuple):
                    rid, target = ref
                    refs.append(
                        RUOReference(
                            ref_id=rid, target_ruo_id=target,
                            raw_text="Ref: " + target,
                            title="Referenced Paper", year="2023",
                            resolution_status=ResolutionStatus.RESOLVED,
                            resolution_source=ResolutionSource.CROSSREF_LOOKUP,
                            ref_confidence=0.9,
                        )
                    )
                else:
                    refs.append(
                        RUOReference(
                            ref_id=f"r{i}", target_ruo_id=ref,
                            raw_text="Ref: " + ref,
                            title="Referenced Paper", year="2023",
                            resolution_status=ResolutionStatus.RESOLVED,
                            resolution_source=ResolutionSource.CROSSREF_LOOKUP,
                            ref_confidence=0.9,
                        )
                    )
        doc.references = refs
        return doc

    # -- lazy build ---------------------------------------------------

    def test_graph_not_built_on_construction(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        assert mgr._graph_cache is None

    def test_graph_built_on_first_access(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        g = mgr.corpus_graph
        assert g is not None
        assert g.total_nodes_found > 0

    def test_graph_still_not_built_if_unaccessed(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        _ = mgr.indexes  # touch indexes, not graph
        assert mgr._graph_cache is None

    # -- cache hit ----------------------------------------------------

    def test_graph_cache_hit_same_object(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        g1 = mgr.corpus_graph
        g2 = mgr.corpus_graph
        assert g1 is g2

    def test_graph_cache_hit_same_total_nodes(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        g1 = mgr.corpus_graph
        g2 = mgr.corpus_graph
        assert g1.total_nodes_found == g2.total_nodes_found

    # -- cache invalidation on add_document ---------------------------

    def test_graph_cache_invalidation_on_add(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        g1 = mgr.corpus_graph
        mgr.add_document(self._graph_doc("d2", entities=[("GPT", EntityLabel.METHOD)]))
        g2 = mgr.corpus_graph
        assert g1 is not g2
        assert g2.total_nodes_found > g1.total_nodes_found

    # -- cache invalidation on remove_document ------------------------

    def test_graph_cache_invalidation_on_remove(self):
        mgr = self._make_mgr([
            self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)]),
            self._graph_doc("d2", entities=[("GPT", EntityLabel.METHOD)]),
        ])
        g1 = mgr.corpus_graph
        mgr.remove_document("d2")
        g2 = mgr.corpus_graph
        assert g1 is not g2
        nodes_d2_doc = [n for n in g2.nodes if n.node_type == "document"]
        assert len(nodes_d2_doc) == 1

    # -- cache invalidation on clear ----------------------------------

    def test_graph_cache_invalidation_on_clear(self):
        mgr = self._make_mgr([
            self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)]),
            self._graph_doc("d2", entities=[("GPT", EntityLabel.METHOD)]),
        ])
        g1 = mgr.corpus_graph
        mgr.clear()
        g2 = mgr.corpus_graph
        assert g1 is not g2
        assert g2.total_nodes_found == 0
        assert g2.total_edges_found == 0

    # -- rebuild after invalidation -----------------------------------

    def test_graph_rebuild_after_invalidation(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        g1 = mgr.corpus_graph
        mgr.add_document(self._graph_doc("d2", entities=[("GPT", EntityLabel.METHOD)]))
        g2 = mgr.corpus_graph
        assert g2.total_nodes_found > g1.total_nodes_found
        # Cache hit again returns the new cached object
        g3 = mgr.corpus_graph
        assert g3 is g2

    # -- cache independent of indexes / statistics --------------------

    def test_graph_cache_independent_of_indexes(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        g = mgr.corpus_graph
        _ = mgr.indexes  # touch indexes
        assert mgr.corpus_graph is g  # graph should still be cached

    def test_graph_cache_independent_of_statistics(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        g = mgr.corpus_graph
        _ = mgr.statistics  # touch statistics
        assert mgr.corpus_graph is g

    # -- empty corpus -------------------------------------------------

    def test_empty_corpus_graph_returns_empty(self):
        mgr = CorpusManager.create("empty", store=InMemoryDocumentStore())
        g = mgr.corpus_graph
        assert g.total_nodes_found == 0
        assert g.total_edges_found == 0

    def test_empty_corpus_graph_has_statistics(self):
        mgr = CorpusManager.create("empty", store=InMemoryDocumentStore())
        g = mgr.corpus_graph
        assert g.statistics is not None
        assert g.statistics.total_nodes == 0

    # -- single document ----------------------------------------------

    def test_single_document_graph_has_doc_node(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        g = mgr.corpus_graph
        doc_nodes = [n for n in g.nodes if n.node_type == "document"]
        assert len(doc_nodes) == 1
        assert doc_nodes[0].node_id == "d1"

    def test_single_document_no_entity_clusters(self):
        # Single entity with no match -> unresolved -> no cluster node
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        g = mgr.corpus_graph
        ec_nodes = [n for n in g.nodes if n.node_type == "entity_cluster"]
        assert len(ec_nodes) == 0

    def test_single_document_no_edges_without_cluster(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        g = mgr.corpus_graph
        # No cluster means no doc->entity edges
        assert g.total_edges_found == 0

    def test_single_document_without_entities(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[])])
        g = mgr.corpus_graph
        doc_nodes = [n for n in g.nodes if n.node_type == "document"]
        assert len(doc_nodes) == 1

    # -- multi-document -----------------------------------------------

    def test_two_documents_both_have_doc_nodes(self):
        docs = [
            self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)]),
            self._graph_doc("d2", entities=[("GPT", EntityLabel.METHOD)]),
        ]
        mgr = self._make_mgr(docs)
        g = mgr.corpus_graph
        doc_nodes = [n for n in g.nodes if n.node_type == "document"]
        assert len(doc_nodes) == 2

    def test_two_documents_shared_entity_single_cluster(self):
        docs = [
            self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)]),
            self._graph_doc("d2", entities=[("BERT", EntityLabel.METHOD)]),
        ]
        mgr = self._make_mgr(docs)
        g = mgr.corpus_graph
        ec_nodes = [n for n in g.nodes if n.node_type == "entity_cluster"]
        assert len(ec_nodes) == 1

    def test_two_documents_shared_entity_has_edges(self):
        docs = [
            self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)]),
            self._graph_doc("d2", entities=[("BERT", EntityLabel.METHOD)]),
        ]
        mgr = self._make_mgr(docs)
        g = mgr.corpus_graph
        # Each doc connects to the shared cluster via EXTENDS edge
        extends_edges = [e for e in g.edges if e.relation_type == RelationType.EXTENDS]
        assert len(extends_edges) >= 2

    # -- invalidation on attach_store ---------------------------------

    def test_graph_invalidated_on_attach_store(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        g1 = mgr.corpus_graph
        mgr.attach_store(InMemoryDocumentStore())
        mgr.add_document(self._graph_doc("d2", entities=[("GPT", EntityLabel.METHOD)]))
        g2 = mgr.corpus_graph
        assert g1 is not g2

    # -- graph has correct structure ----------------------------------

    def test_graph_node_types_with_multidoc(self):
        docs = [
            self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)]),
            self._graph_doc("d2", entities=[("BERT", EntityLabel.METHOD)]),
        ]
        mgr = self._make_mgr(docs)
        g = mgr.corpus_graph
        types = {n.node_type for n in g.nodes}
        assert "document" in types
        assert "entity_cluster" in types

    def test_graph_edge_types_with_multidoc(self):
        docs = [
            self._graph_doc("d1", entities=[("ImageNet", EntityLabel.DATASET)]),
            self._graph_doc("d2", entities=[("ImageNet", EntityLabel.DATASET),
                                             ("BERT", EntityLabel.METHOD)]),
        ]
        mgr = self._make_mgr(docs)
        g = mgr.corpus_graph
        doc_nodes = [n for n in g.nodes if n.node_type == "document"]
        ec_nodes = [n for n in g.nodes if n.node_type == "entity_cluster"]
        if doc_nodes and ec_nodes:
            doc_id = doc_nodes[0].node_id
            ec_id = ec_nodes[0].node_id
            connecting = [e for e in g.edges
                          if e.source_id == doc_id and e.target_id == ec_id]
            assert len(connecting) >= 1

    # -- rebuild between invalidation cycles --------------------------

    def test_multiple_invalidation_cycles(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        graphs = []
        for _ in range(3):
            graphs.append(mgr.corpus_graph)
            mgr.add_document(self._graph_doc(f"d{_+2}", entities=[("GPT", EntityLabel.METHOD)]))
        assert len({id(g) for g in graphs}) == 3  # each cycle new object

    # -- cache persists without invalidation --------------------------

    def test_cache_persists_across_multiple_accesses(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        g = mgr.corpus_graph
        for _ in range(10):
            assert mgr.corpus_graph is g

    # -- graph with relations -----------------------------------------

    def test_graph_with_citation_edges(self):
        docs = [
            self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)],
                            references=[("r1", "d2")]),
            self._graph_doc("d2", entities=[("GPT", EntityLabel.METHOD)]),
        ]
        mgr = self._make_mgr(docs)
        g = mgr.corpus_graph
        # Should have citation-related edges (d1 -> d2) from references
        doc_doc_edges = [e for e in g.edges
                         if e.source_id == "d1" and e.target_id == "d2"]
        assert len(doc_doc_edges) > 0

    # -- attach_store after graph built --------------------------------

    def test_attach_store_after_graph_creates_new_cache(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        g1 = mgr.corpus_graph
        new_store = InMemoryDocumentStore()
        new_store.put(self._graph_doc("d2", entities=[("GPT", EntityLabel.METHOD)]))
        mgr.attach_store(new_store)
        g2 = mgr.corpus_graph
        assert g1 is not g2

    # -- load invalidates cache ---------------------------------------

    def test_graph_cache_is_none_after_load(self):
        import tempfile, shutil
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        _ = mgr.corpus_graph
        d = tempfile.mkdtemp()
        try:
            mgr.save(d)
            loaded = CorpusManager.load(d, store=InMemoryDocumentStore())
            loaded.add_document(self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)]))
            g = loaded.corpus_graph
            assert g.total_nodes_found >= 1
        finally:
            shutil.rmtree(d)

    # -- graph quality checks -----------------------------------------

    def test_graph_node_weights_positive(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        g = mgr.corpus_graph
        for n in g.nodes:
            assert n.weight >= 0

    def test_graph_edge_confidences_valid(self):
        docs = [
            self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)]),
            self._graph_doc("d2", entities=[("BERT", EntityLabel.METHOD)]),
        ]
        mgr = self._make_mgr(docs)
        g = mgr.corpus_graph
        for e in g.edges:
            assert 0.0 <= e.confidence <= 1.0

    def test_graph_statistics_connected_components(self):
        docs = [
            self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)]),
            self._graph_doc("d2", entities=[("GPT", EntityLabel.METHOD)]),
        ]
        mgr = self._make_mgr(docs)
        g = mgr.corpus_graph
        assert g.statistics.connected_components >= 2  # disconnected docs

    def test_graph_density_non_negative(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        g = mgr.corpus_graph
        assert g.statistics.density >= 0.0

    def test_graph_density_at_most_one(self):
        docs = [
            self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)]),
            self._graph_doc("d2", entities=[("BERT", EntityLabel.METHOD)]),
        ]
        mgr = self._make_mgr(docs)
        g = mgr.corpus_graph
        assert g.statistics.density <= 1.0

    def test_add_duplicate_document_invalidates(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        g1 = mgr.corpus_graph
        mgr.add_document(self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)]))
        g2 = mgr.corpus_graph
        assert g1 is not g2

    def test_remove_nonexistent_does_not_invalidate(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        g1 = mgr.corpus_graph
        mgr.remove_document("nonexistent")
        assert mgr.corpus_graph is g1  # no invalidation

    def test_clear_rebuilds_empty_graph(self):
        mgr = self._make_mgr([self._graph_doc("d1", entities=[("BERT", EntityLabel.METHOD)])])
        _ = mgr.corpus_graph
        mgr.clear()
        g = mgr.corpus_graph
        assert g.total_nodes_found == 0
        assert g.total_edges_found == 0
