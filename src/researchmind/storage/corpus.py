"""Corpus management layer — indexes, statistics, and lazy-loading
for collections of :class:`RUODocument` objects.

Builds on the existing :class:`RUOCorpus` model and :class:`DocumentStore`
abstraction.  Documents are always loaded lazily through the store.
"""

from __future__ import annotations

import json
import logging
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from statistics import stdev, StatisticsError

from pydantic import BaseModel, Field

from researchmind.models.enums import CanonicalLabel, ClaimType, EntityLabel
from researchmind.models.ruo import (
    DocumentRelation,
    DocumentStore,
    EvidenceCoverage,
    ProvenanceRecord,
    RUOCorpus,
    RUODocument,
    RUOQuality,
    SROPipelineLogEntry,
)
from researchmind.models.ruo_enums import (
    ProvenanceAction,
    ProvenanceAgentType,
    RelationType,
)
from researchmind.storage.document_store import InMemoryDocumentStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CorpusIndexes — pre-computed lookup tables
# ---------------------------------------------------------------------------


class CorpusIndexes(BaseModel):
    """Pre-computed lookup tables for corpus-level queries.

    Each ``by_*`` field maps a key (label, name, year, …) to a list of
    document IDs.  ``by_entity_text`` and ``by_predicate`` also store the
    specific entity/triple ID for drill-down.
    """

    by_entity_label: dict[str, list[str]] = Field(default_factory=dict)
    by_entity_text: dict[str, list[tuple[str, str]]] = Field(default_factory=dict)
    by_claim_type: dict[str, list[str]] = Field(default_factory=dict)
    by_author_name: dict[str, list[str]] = Field(default_factory=dict)
    by_year: dict[str, list[str]] = Field(default_factory=dict)
    by_research_field: dict[str, list[str]] = Field(default_factory=dict)
    by_predicate: dict[str, list[tuple[str, str]]] = Field(default_factory=dict)
    citations_to: dict[str, list[str]] = Field(default_factory=dict)
    citations_from: dict[str, list[str]] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# CorpusStatistics — aggregate metrics
# ---------------------------------------------------------------------------


class ConfidenceStats(BaseModel):
    """Summary statistics for a set of confidence scores."""

    mean: float = 0.0
    min: float = 0.0
    max: float = 0.0
    std: float = 0.0


class CorpusStatistics(BaseModel):
    """Aggregate metrics computed across all documents in a corpus."""

    document_count: int = 0
    total_entities: int = 0
    distinct_entity_labels: int = 0
    entities_by_label: dict[str, int] = Field(default_factory=dict)
    total_claims: int = 0
    claims_by_type: dict[str, int] = Field(default_factory=dict)
    total_triples: int = 0
    triples_by_predicate: dict[str, int] = Field(default_factory=dict)
    total_authors: int = 0
    distinct_author_names: int = 0
    year_distribution: dict[str, int] = Field(default_factory=dict)
    overall_confidence: ConfidenceStats = Field(default_factory=ConfidenceStats)
    citation_network_edges: int = 0
    citation_network_density: float = 0.0
    coverage: EvidenceCoverage | None = None


# ---------------------------------------------------------------------------
# CorpusManager
# ---------------------------------------------------------------------------


class CorpusManager:
    """Manages a collection of :class:`RUODocument` instances.

    Wraps a :class:`RUOCorpus` (the serialisable metadata model) and
    adds lazy document loading, pre-computed indexes, and aggregate
    statistics.

    Usage::

        # Build from existing documents
        manager = CorpusManager.from_documents(docs, corpus_id="my-corpus")

        # Attach a persistent store for lazy access
        store = FilesystemDocumentStore("./ruo_output")
        manager.attach_store(store)

        # Query
        docs = manager.find_by_entity_label("METHOD")
        stats = manager.statistics
    """

    def __init__(
        self,
        corpus: RUOCorpus,
        store: DocumentStore | None = None,
    ) -> None:
        self._corpus = corpus
        self._store = store
        self._indexes: CorpusIndexes | None = None
        self._statistics: CorpusStatistics | None = None

    # -- properties ----------------------------------------------------

    @property
    def corpus(self) -> RUOCorpus:
        """The underlying lightweight metadata model."""
        return self._corpus

    @property
    def store(self) -> DocumentStore | None:
        """The attached document store (may be ``None``)."""
        return self._store

    # -- factory helpers -----------------------------------------------

    @classmethod
    def create(
        cls,
        corpus_id: str,
        name: str = "",
        description: str = "",
        store: DocumentStore | None = None,
    ) -> CorpusManager:
        """Create an empty corpus with a fresh :class:`RUOCorpus`."""
        now = datetime.now(timezone.utc)
        quality = _default_corpus_quality()
        corpus = RUOCorpus(
            corpus_id=corpus_id,
            name=name,
            description=description or None,
            created_at=now,
            updated_at=now,
            quality=quality,
        )
        return cls(corpus, store=store)

    @classmethod
    def from_documents(
        cls,
        documents: list[RUODocument],
        corpus_id: str,
        name: str = "",
        description: str = "",
    ) -> CorpusManager:
        """Build a corpus from an in-memory list of documents.

        An :class:`InMemoryDocumentStore` is created automatically so
        documents can be reloaded lazily.
        """
        store = InMemoryDocumentStore()
        for doc in documents:
            store.put(doc)
        now = datetime.now(timezone.utc)
        quality = _default_corpus_quality()
        corpus = RUOCorpus(
            corpus_id=corpus_id,
            name=name,
            description=description or None,
            created_at=now,
            updated_at=now,
            document_ids=[d.meta.ruo_id for d in documents],
            quality=quality,
            provenance=_make_provenance(corpus_id, "created"),
        )
        return cls(corpus, store=store)

    # -- store management ----------------------------------------------

    def attach_store(self, store: DocumentStore) -> None:
        """Attach (or replace) a :class:`DocumentStore` for lazy loading."""
        self._store = store
        self._corpus.attach_store(store)
        self._indexes = None
        self._statistics = None

    # -- document management -------------------------------------------

    def add_document(self, doc: RUODocument) -> None:
        """Add a document to the corpus.

        The document is also written to the attached :class:`DocumentStore`
        if one is configured.
        """
        ruo_id = doc.meta.ruo_id
        if ruo_id in self._corpus.document_ids:
            logger.warning("Document %s already in corpus — replacing", ruo_id)
        else:
            self._corpus.document_ids.append(ruo_id)
        if self._store is not None:
            self._store.put(doc)
        self._corpus.updated_at = datetime.now(timezone.utc)
        self._indexes = None
        self._statistics = None

    def remove_document(self, ruo_id: str) -> bool:
        """Remove a document from the corpus by ID.

        Also removes it from the attached store.  Returns ``True`` if
        the document was found and removed.
        """
        if ruo_id not in self._corpus.document_ids:
            return False
        self._corpus.document_ids.remove(ruo_id)
        self._corpus.relations = [
            r for r in self._corpus.relations
            if r.source_ruo_id != ruo_id and r.target_ruo_id != ruo_id
        ]
        if self._store is not None:
            self._store.delete(ruo_id)
        self._corpus.updated_at = datetime.now(timezone.utc)
        self._indexes = None
        self._statistics = None
        return True

    def get_document(self, ruo_id: str) -> RUODocument | None:
        """Load a single document (lazy, from the attached store)."""
        if self._store is None:
            raise RuntimeError(
                "No DocumentStore attached — cannot load documents"
            )
        return self._store.get(ruo_id)

    def get_documents(
        self, ruo_ids: list[str] | None = None,
    ) -> list[RUODocument]:
        """Load multiple documents.

        If ``ruo_ids`` is ``None``, all corpus documents are returned.
        """
        if ruo_ids is None:
            ruo_ids = self._corpus.document_ids
        if self._store is None:
            raise RuntimeError(
                "No DocumentStore attached — cannot load documents"
            )
        batch = self._store.get_batch(ruo_ids)
        return [batch[rid] for rid in ruo_ids if rid in batch]

    # -- relation management -------------------------------------------

    def add_relation(self, relation: DocumentRelation) -> None:
        """Register a cross-document relation."""
        self._corpus.relations.append(relation)
        self._corpus.updated_at = datetime.now(timezone.utc)

    def get_relations(
        self,
        relation_type: RelationType | None = None,
    ) -> list[DocumentRelation]:
        """Return relations, optionally filtered by type."""
        if relation_type is None:
            return list(self._corpus.relations)
        return [r for r in self._corpus.relations if r.relation_type == relation_type]

    # -- indexes -------------------------------------------------------

    @property
    def indexes(self) -> CorpusIndexes:
        if self._indexes is None:
            self._indexes = self._build_indexes()
        return self._indexes

    def rebuild_indexes(self) -> CorpusIndexes:
        """Force a full index rebuild and return the result."""
        self._indexes = self._build_indexes()
        return self._indexes

    def _build_indexes(self) -> CorpusIndexes:
        docs = self.get_documents()
        idx = CorpusIndexes()
        _entity_label: dict[str, set[str]] = defaultdict(set)
        _entity_text: dict[str, set[tuple[str, str]]] = defaultdict(set)
        _claim_type: dict[str, set[str]] = defaultdict(set)
        _author_name: dict[str, set[str]] = defaultdict(set)
        _year: dict[str, set[str]] = defaultdict(set)
        _field: dict[str, set[str]] = defaultdict(set)
        _predicate: dict[str, set[tuple[str, str]]] = defaultdict(set)
        _cite_to: dict[str, set[str]] = defaultdict(set)
        _cite_from: dict[str, set[str]] = defaultdict(set)

        for doc in docs:
            rid = doc.meta.ruo_id

            # entities
            for ent in doc.entities:
                _entity_label[ent.label.value].add(rid)
                _entity_text[ent.text.lower()].add((rid, ent.entity_id))

            # claims
            for cl in doc.claims:
                _claim_type[cl.claim_type.value].add(rid)

            # authors
            for au in doc.header.authors:
                name = (au.full_name or "").strip().lower()
                if name:
                    _author_name[name].add(rid)

            # year
            pub = doc.meta.source_file.filename  # fallback: not ideal
            if doc.header.publication_date:
                y = doc.header.publication_date[:4]
                if y.isdigit():
                    _year[y].add(rid)

            # research fields
            for rf in doc.meta.research_fields:
                _field[rf].add(rid)

            # triples (predicates)
            for tr in doc.triples:
                _predicate[tr.predicate].add((rid, tr.triple_id))

            # citation network via DocumentRelation
            for rel in self._corpus.relations:
                if rel.relation_type in (RelationType.CITES,):
                    _cite_to[rel.target_ruo_id].add(rel.source_ruo_id)
                    _cite_from[rel.source_ruo_id].add(rel.target_ruo_id)

            # citation network via references with target_ruo_id
            for ref in doc.references:
                if ref.target_ruo_id:
                    _cite_to[ref.target_ruo_id].add(rid)
                    _cite_from[rid].add(ref.target_ruo_id)

        idx.by_entity_label = {k: sorted(v) for k, v in _entity_label.items()}
        idx.by_entity_text = {k: sorted(v) for k, v in _entity_text.items()}
        idx.by_claim_type = {k: sorted(v) for k, v in _claim_type.items()}
        idx.by_author_name = {k: sorted(v) for k, v in _author_name.items()}
        idx.by_year = {k: sorted(v) for k, v in _year.items()}
        idx.by_research_field = {k: sorted(v) for k, v in _field.items()}
        idx.by_predicate = {k: sorted(v) for k, v in _predicate.items()}
        idx.citations_to = {k: sorted(v) for k, v in _cite_to.items()}
        idx.citations_from = {k: sorted(v) for k, v in _cite_from.items()}
        return idx

    # -- query helpers -------------------------------------------------

    def find_by_entity_label(self, label: str) -> list[RUODocument]:
        """Return documents containing entities with the given label."""
        ruo_ids = self.indexes.by_entity_label.get(label, [])
        return self.get_documents(ruo_ids)

    def find_by_author_name(self, name: str) -> list[RUODocument]:
        """Return documents by author name (case-insensitive)."""
        key = name.strip().lower()
        ruo_ids = self.indexes.by_author_name.get(key, [])
        return self.get_documents(ruo_ids)

    def find_by_year(self, year: str) -> list[RUODocument]:
        """Return documents published in *year* (four-digit string)."""
        ruo_ids = self.indexes.by_year.get(year, [])
        return self.get_documents(ruo_ids)

    def find_by_claim_type(self, claim_type: str) -> list[RUODocument]:
        """Return documents containing claims of *claim_type*."""
        ruo_ids = self.indexes.by_claim_type.get(claim_type, [])
        return self.get_documents(ruo_ids)

    def find_by_research_field(self, field: str) -> list[RUODocument]:
        """Return documents tagged with *field*."""
        ruo_ids = self.indexes.by_research_field.get(field, [])
        return self.get_documents(ruo_ids)

    # -- statistics ----------------------------------------------------

    @property
    def statistics(self) -> CorpusStatistics:
        if self._statistics is None:
            self._statistics = self._compute_statistics()
        return self._statistics

    def _compute_statistics(self) -> CorpusStatistics:
        docs = self.get_documents()
        if not docs:
            return CorpusStatistics()

        entity_label_counts: Counter[str] = Counter()
        claim_type_counts: Counter[str] = Counter()
        predicate_counts: Counter[str] = Counter()
        year_counts: Counter[str] = Counter()
        all_confidences: list[float] = []
        total_entities = 0
        total_claims = 0
        total_triples = 0
        total_authors = 0
        author_names_set: set[str] = set()
        citation_edges: set[tuple[str, str]] = set()
        combined_coverage: EvidenceCoverage | None = None

        for doc in docs:
            conf = doc.quality.overall_confidence
            all_confidences.append(conf)

            total_entities += len(doc.entities)
            for ent in doc.entities:
                entity_label_counts[ent.label.value] += 1

            total_claims += len(doc.claims)
            for cl in doc.claims:
                claim_type_counts[cl.claim_type.value] += 1

            total_triples += len(doc.triples)
            for tr in doc.triples:
                predicate_counts[tr.predicate] += 1

            for au in doc.header.authors:
                if au.full_name:
                    total_authors += 1
                    author_names_set.add(au.full_name.strip().lower())

            if doc.header.publication_date:
                y = doc.header.publication_date[:4]
                if y.isdigit():
                    year_counts[y] += 1

            # citation edges from references
            for ref in doc.references:
                if ref.target_ruo_id:
                    edge = (doc.meta.ruo_id, ref.target_ruo_id)
                    citation_edges.add(edge)

            # aggregate coverage
            ec = doc.quality.evidence_coverage
            if combined_coverage is None:
                combined_coverage = ec
            else:
                combined_coverage = _merge_coverage(combined_coverage, ec)

        # citation edges from relations
        for rel in self._corpus.relations:
            if rel.relation_type in (RelationType.CITES, RelationType.SUPPORTS,
                                     RelationType.CONTRADICTS, RelationType.EXTENDS,
                                     RelationType.REPRODUCES, RelationType.REVIEWS):
                edge = (rel.source_ruo_id, rel.target_ruo_id)
                citation_edges.add(edge)

        n = len(all_confidences)
        conf_mean = sum(all_confidences) / n if n else 0.0
        conf_min = min(all_confidences) if n else 0.0
        conf_max = max(all_confidences) if n else 0.0
        try:
            conf_std = stdev(all_confidences) if n > 1 else 0.0
        except StatisticsError:
            conf_std = 0.0

        edge_count = len(citation_edges)
        max_edges = n * (n - 1) if n > 1 else 1
        density = edge_count / max_edges if max_edges else 0.0

        return CorpusStatistics(
            document_count=n,
            total_entities=total_entities,
            distinct_entity_labels=len(entity_label_counts),
            entities_by_label=dict(entity_label_counts),
            total_claims=total_claims,
            claims_by_type=dict(claim_type_counts),
            total_triples=total_triples,
            triples_by_predicate=dict(predicate_counts),
            total_authors=total_authors,
            distinct_author_names=len(author_names_set),
            year_distribution=dict(year_counts),
            overall_confidence=ConfidenceStats(
                mean=round(conf_mean, 4),
                min=round(conf_min, 4),
                max=round(conf_max, 4),
                std=round(conf_std, 4),
            ),
            citation_network_edges=edge_count,
            citation_network_density=round(density, 4),
            coverage=combined_coverage,
        )

    # -- persistence ---------------------------------------------------

    def save(self, directory: str | Path) -> None:
        """Save corpus metadata (as JSON) and indexes to *directory*.

        The corpus model, indexes, and statistics are each written to
        separate JSON files for auditability.
        """
        out = Path(directory)
        out.mkdir(parents=True, exist_ok=True)

        # Corpus metadata
        corpus_path = out / "corpus.json"
        corpus_path.write_text(
            self._corpus.model_dump_json(indent=2), encoding="utf-8",
        )

        # Indexes
        idx_path = out / "indexes.json"
        idx_path.write_text(
            self.indexes.model_dump_json(indent=2), encoding="utf-8",
        )

        # Statistics
        stats_path = out / "statistics.json"
        stats_path.write_text(
            self.statistics.model_dump_json(indent=2), encoding="utf-8",
        )

        logger.info(
            "Corpus saved to %s (%d docs, %d relations)",
            out, len(self._corpus.document_ids), len(self._corpus.relations),
        )

    @classmethod
    def load(
        cls,
        directory: str | Path,
        store: DocumentStore | None = None,
    ) -> CorpusManager:
        """Load a previously saved corpus from *directory*.

        Expects ``corpus.json``, ``indexes.json``, and ``statistics.json``
        files written by :meth:`save`.
        """
        base = Path(directory)
        corpus_path = base / "corpus.json"
        if not corpus_path.exists():
            raise FileNotFoundError(
                f"Corpus metadata not found at {corpus_path}"
            )

        raw = json.loads(corpus_path.read_text(encoding="utf-8"))
        corpus = RUOCorpus(**raw)
        manager = cls(corpus, store=store)

        # Reload cached indexes and statistics from disk
        idx_path = base / "indexes.json"
        if idx_path.exists():
            idx_raw = json.loads(idx_path.read_text(encoding="utf-8"))
            manager._indexes = CorpusIndexes(**idx_raw)

        stats_path = base / "statistics.json"
        if stats_path.exists():
            stats_raw = json.loads(stats_path.read_text(encoding="utf-8"))
            manager._statistics = CorpusStatistics(**stats_raw)

        return manager


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _default_corpus_quality() -> RUOQuality:
    """Create a minimal RUOQuality for a corpus."""
    from researchmind.models.ruo import (
        ComponentConfidence,
        ComponentSubscore,
        ConfidenceBreakdown,
        EvidenceCoverage,
    )

    comp = ComponentConfidence(
        component="corpus",
        score=0.0,
        subscores=[ComponentSubscore(name="corpus", value=0.0, weight=1.0)],
    )
    breakdown = ConfidenceBreakdown(
        components=[comp],
        overall=0.0,
        component_weights={"corpus": 1.0},
    )
    coverage = EvidenceCoverage(
        total_claims=0, claims_with_evidence=0, claims_evidence_rate=0.0,
        total_entities=0, entities_with_evidence=0, entities_evidence_rate=0.0,
        total_citations=0, citations_with_intent_evidence=0,
        citation_intent_evidence_rate=0.0,
        total_references=0, references_with_resolution_evidence=0,
        reference_resolution_evidence_rate=0.0,
    )
    return RUOQuality(
        confidence=breakdown,
        evidence_coverage=coverage,
        overall_confidence=0.0,
    )


def _make_provenance(
    corpus_id: str,
    action: str = "created",
) -> list[ProvenanceRecord]:
    now = datetime.now(timezone.utc)
    pa = ProvenanceAction.CREATED if action == "created" else ProvenanceAction.UPDATED
    return [
        ProvenanceRecord(
            provenance_id=f"prov_{corpus_id}_001",
            action=pa,
            agent_type=ProvenanceAgentType.PIPELINE_STAGE,
            agent_name="researchmind_corpus",
            pipeline_stage="corpus",
            pipeline_version="2.1.0",
            timestamp=now,
        ),
    ]


def _merge_coverage(
    a: EvidenceCoverage, b: EvidenceCoverage,
) -> EvidenceCoverage:
    """Combine two :class:`EvidenceCoverage` instances by summing counts."""
    tc = a.total_claims + b.total_claims
    te = a.total_entities + b.total_entities
    tci = a.total_citations + b.total_citations
    tr = a.total_references + b.total_references
    return EvidenceCoverage(
        total_claims=tc,
        claims_with_evidence=a.claims_with_evidence + b.claims_with_evidence,
        claims_evidence_rate=round(
            (a.claims_with_evidence + b.claims_with_evidence) / max(tc, 1), 4
        ),
        total_entities=te,
        entities_with_evidence=a.entities_with_evidence + b.entities_with_evidence,
        entities_evidence_rate=round(
            (a.entities_with_evidence + b.entities_with_evidence) / max(te, 1), 4
        ),
        total_citations=tci,
        citations_with_intent_evidence=(
            a.citations_with_intent_evidence + b.citations_with_intent_evidence
        ),
        citation_intent_evidence_rate=round(
            (a.citations_with_intent_evidence + b.citations_with_intent_evidence)
            / max(tci, 1), 4
        ),
        total_references=tr,
        references_with_resolution_evidence=(
            a.references_with_resolution_evidence
            + b.references_with_resolution_evidence
        ),
        reference_resolution_evidence_rate=round(
            (a.references_with_resolution_evidence
             + b.references_with_resolution_evidence)
            / max(tr, 1), 4
        ),
    )
