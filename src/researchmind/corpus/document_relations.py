"""Deterministic document relation detection for RUOCorpus.

Detection stages:
    1. Citation Relations — DOI, target_ruo_id, title match
    2. Shared Canonical Entities — cross-document entity cluster overlap
    3. Shared Methods — METHOD-typed entity overlap
    4. Triple Comparison — subject/predicate/object matching
    5. Claim Comparison — claim type and statement similarity
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from researchmind.corpus.entity_resolution import (
    CanonicalEntity,
    EntityCluster,
    ResolutionResult,
    normalize_entity_text,
)
from researchmind.models.enums import EntityLabel
from researchmind.models.ruo import (
    DocumentRelation,
    RUOClaim,
    RUODocument,
    RUOEntity,
    RUOReference,
    SemanticTriple,
)
from researchmind.models.ruo_enums import RelationType
from researchmind.storage.corpus import CorpusManager

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    fuzz = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_ENTITY_THRESHOLD: float = 0.2
"""Minimum entity overlap ratio for a COMPARES_WITH relation."""

DEFAULT_METHOD_THRESHOLD: float = 0.2
"""Minimum method overlap ratio for a USES_METHOD relation."""

DEFAULT_FUZZY_THRESHOLD: float = 85.0
"""Minimum title similarity for citation detection via title match."""

_STAGE_WEIGHTS: dict[str, float] = {
    "citation": 0.40,
    "entity": 0.20,
    "method": 0.15,
    "triple": 0.15,
    "claim": 0.10,
}

# Negation markers for claim comparison
_NEGATION_WORDS: set[str] = {
    "not", "no", "never", "doesn't", "don't", "didn't",
    "isn't", "aren't", "wasn't", "weren't", "cannot", "can't",
    "without", "lack", "absence", "fails", "failure",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class RelationEvidence(BaseModel):
    """A single piece of evidence supporting a document relation."""

    evidence_id: str
    evidence_type: str = Field(
        pattern=r"^(citation|entity|method|triple|claim)$"
    )
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_ids: list[str] = Field(default_factory=list)
    target_ids: list[str] = Field(default_factory=list)


class RelationDetectionStats(BaseModel):
    """Summary statistics for a relation detection run."""

    total_pairs: int = Field(default=0, ge=0)
    relations_detected: int = Field(default=0, ge=0)
    relations_by_type: dict[str, int] = Field(default_factory=dict)
    stages_summary: dict[str, int] = Field(default_factory=dict)


class DocumentRelationResult(BaseModel):
    """Full output of a relation detection pass."""

    relations: list[DocumentRelation] = Field(default_factory=list)
    evidence: list[RelationEvidence] = Field(default_factory=list)
    stats: RelationDetectionStats = Field(default_factory=lambda: RelationDetectionStats())


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class DocumentRelationEngine:
    """Deterministic document relation detector.

    Detects CITES, CITED_BY, COMPARES_WITH, USES_METHOD, EXTENDS,
    SUPPORTS, and CONTRADICTS relations between document pairs using
    five evidence stages.
    """

    def __init__(
        self,
        resolution_result: ResolutionResult | None = None,
        entity_threshold: float = DEFAULT_ENTITY_THRESHOLD,
        method_threshold: float = DEFAULT_METHOD_THRESHOLD,
        fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
    ) -> None:
        self._resolution = resolution_result
        self.entity_threshold = entity_threshold
        self.method_threshold = method_threshold
        self.fuzzy_threshold = fuzzy_threshold

        # Precompute entity-cluster → doc mapping from resolution result
        # cluster_text -> set of ruo_ids containing that entity
        self._cluster_doc_map: dict[str, set[str]] = {}
        # entity_id -> canonical_text
        self._entity_to_canonical: dict[str, str] = {}
        # canonical_text -> EntityCluster
        self._canonical_clusters: dict[str, EntityCluster] = {}
        # canonical_text -> set of entity_ids
        self._canonical_entity_ids: dict[str, set[str]] = {}

        if resolution_result:
            self._build_cluster_index()

    # ------------------------------------------------------------------
    # Index building
    # ------------------------------------------------------------------

    def _build_cluster_index(self) -> None:
        """Build lookup indexes from resolution clusters."""
        for cluster in self._resolution.clusters:
            ce = cluster.canonical_entity
            canonical = ce.canonical_text.lower()
            self._canonical_clusters[canonical] = cluster
            eids = set(ce.entity_ids)
            self._canonical_entity_ids[canonical] = eids

            # Extract doc IDs from entity IDs
            doc_ids: set[str] = set()
            for eid in eids:
                # Entity IDs may be prefixed with doc ID (e.g., "d1_e0")
                parts = eid.split("_")
                if len(parts) >= 2:
                    doc_ids.add(parts[0])
            self._cluster_doc_map[canonical] = doc_ids

            # Track entity_id -> canonical mapping
            for eid in eids:
                self._entity_to_canonical[eid] = canonical

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_relations(
        self,
        documents: list[RUODocument],
        corpus_manager: CorpusManager | None = None,
    ) -> DocumentRelationResult:
        """Run all detection stages on a set of documents."""
        if len(documents) < 2:
            return DocumentRelationResult(
                stats=RelationDetectionStats(
                    total_pairs=0, relations_detected=0,
                ),
            )

        by_id: dict[str, RUODocument] = {d.meta.ruo_id: d for d in documents}
        doc_ids = list(by_id.keys())

        # Build a doc_id -> set[str] of canonical entity texts for overlap checks
        doc_canonicals: dict[str, set[str]] = {}
        if self._resolution:
            for doc_id in doc_ids:
                doc = by_id[doc_id]
                ents = set(e.entity_id for e in doc.entities)
                canonicals: set[str] = set()
                for eid in ents:
                    canon = self._entity_to_canonical.get(eid)
                    if canon:
                        canonicals.add(canon)
                doc_canonicals[doc_id] = canonicals

        # Gather candidate pairs
        candidates = self._find_candidate_pairs(doc_ids, by_id, corpus_manager)

        all_relations: list[DocumentRelation] = []
        all_evidence: list[RelationEvidence] = []
        stages_summary: dict[str, int] = {"citation": 0, "entity": 0, "method": 0, "triple": 0, "claim": 0}

        for src_id, tgt_id in candidates:
            if src_id == tgt_id:
                continue
            doc_a = by_id[src_id]
            doc_b = by_id[tgt_id]

            pair_relations, pair_evidence = self._detect_pair(
                doc_a, doc_b, doc_canonicals,
            )
            all_relations.extend(pair_relations)
            for ev in pair_evidence:
                stages_summary[ev.evidence_type] = (
                    stages_summary.get(ev.evidence_type, 0) + 1
                )
            all_evidence.extend(pair_evidence)

        # Also add CITED_BY for every CITES
        cited_by_relations: list[DocumentRelation] = []
        for rel in all_relations:
            if rel.relation_type == RelationType.CITES:
                # Create inverse
                inv = DocumentRelation(
                    relation_id=f"rel_{uuid.uuid4().hex[:12]}",
                    source_ruo_id=rel.target_ruo_id,
                    target_ruo_id=rel.source_ruo_id,
                    relation_type=RelationType.CITED_BY,
                    confidence=rel.confidence,
                    evidence_ids=list(rel.evidence_ids),
                    is_directed=True,
                    detected_at=rel.detected_at,
                )
                cited_by_relations.append(inv)
        all_relations.extend(cited_by_relations)

        # Stats
        rel_by_type: dict[str, int] = {}
        for rel in all_relations:
            rt = rel.relation_type.value
            rel_by_type[rt] = rel_by_type.get(rt, 0) + 1

        stats = RelationDetectionStats(
            total_pairs=len(candidates),
            relations_detected=len(all_relations),
            relations_by_type=rel_by_type,
            stages_summary=stages_summary,
        )

        return DocumentRelationResult(
            relations=all_relations,
            evidence=all_evidence,
            stats=stats,
        )

    # ------------------------------------------------------------------
    # Candidate pair generation
    # ------------------------------------------------------------------

    def _find_candidate_pairs(
        self,
        doc_ids: list[str],
        by_id: dict[str, RUODocument],
        corpus_manager: CorpusManager | None,
    ) -> list[tuple[str, str]]:
        """Find document pairs that are worth evaluating.

        Uses citation indexes, entity cluster co-occurrence, and
        fallback all-pairs for small corpora.
        """
        candidates: set[tuple[str, str]] = set()

        # 1. Citation candidates from corpus indexes
        if corpus_manager:
            idx = corpus_manager.indexes
            for target, sources in idx.citations_to.items():
                if target in by_id:
                    for src in sources:
                        if src in by_id and src != target:
                            candidates.add((src, target))

        # 2. Entity cluster co-occurrence
        if self._resolution:
            for canonical, doc_set in self._cluster_doc_map.items():
                doc_list = [d for d in doc_set if d in by_id]
                for i in range(len(doc_list)):
                    for j in range(i + 1, len(doc_list)):
                        candidates.add((doc_list[i], doc_list[j]))
                        candidates.add((doc_list[j], doc_list[i]))

        # 3. Fallback: all pairs for small corpora (<= 20 docs)
        if len(doc_ids) <= 20 and len(candidates) == 0:
            for i in range(len(doc_ids)):
                for j in range(i + 1, len(doc_ids)):
                    candidates.add((doc_ids[i], doc_ids[j]))
                    candidates.add((doc_ids[j], doc_ids[i]))

        return list(candidates)

    # ------------------------------------------------------------------
    # Per-pair detection
    # ------------------------------------------------------------------

    def _detect_pair(
        self,
        doc_a: RUODocument,
        doc_b: RUODocument,
        doc_canonicals: dict[str, set[str]],
    ) -> tuple[list[DocumentRelation], list[RelationEvidence]]:
        """Run all 5 stages on a single document pair."""
        now = datetime.now(timezone.utc)
        all_relations: list[DocumentRelation] = []
        all_evidence: list[RelationEvidence] = []

        # Stage 1: Citation
        cit_evidence = self._detect_citation(doc_a, doc_b)
        all_evidence.extend(cit_evidence)

        # Stage 2: Shared entities
        ent_evidence = self._detect_entity_overlap(
            doc_a, doc_b, doc_canonicals,
        )
        all_evidence.extend(ent_evidence)

        # Stage 3: Shared methods
        meth_evidence = self._detect_method_overlap(
            doc_a, doc_b, doc_canonicals,
        )
        all_evidence.extend(meth_evidence)

        # Stage 4: Triple comparison
        triple_evidence = self._detect_triple_overlap(doc_a, doc_b)
        all_evidence.extend(triple_evidence)

        # Stage 5: Claim comparison
        claim_evidence = self._detect_claim_overlap(doc_a, doc_b)
        all_evidence.extend(claim_evidence)

        # Build relations from evidence
        relation_map: dict[str, list[RelationEvidence]] = {}

        # CITES
        if cit_evidence:
            relation_map.setdefault("cites", []).extend(cit_evidence)

        # COMPARES_WITH from entity+mix
        comp_evidence = ent_evidence + meth_evidence
        # Use entity/method evidence to produce COMPARES_WITH and SUPPORTS/etc
        # Actually, we produce relations per evidence type below.

        # Build relations by evidence type
        # CITES citation
        cites_weighted, _, cites_ev = self._aggregate_evidence(
            cit_evidence, "citation",
        )
        if cites_weighted > 0:
            ev_ids = [e.evidence_id for e in cites_ev]
            rel = DocumentRelation(
                relation_id=f"rel_{uuid.uuid4().hex[:12]}",
                source_ruo_id=doc_a.meta.ruo_id,
                target_ruo_id=doc_b.meta.ruo_id,
                relation_type=RelationType.CITES,
                confidence=cites_weighted,
                evidence_ids=ev_ids,
                is_directed=True,
                detected_at=now,
            )
            all_relations.append(rel)

        # COMPARES_WITH from entity overlap
        ent_weighted, ent_raw, ent_ev = self._aggregate_evidence(
            ent_evidence, "entity",
        )
        if ent_raw >= self.entity_threshold:
            ev_ids = [e.evidence_id for e in ent_ev]
            rel = DocumentRelation(
                relation_id=f"rel_{uuid.uuid4().hex[:12]}",
                source_ruo_id=doc_a.meta.ruo_id,
                target_ruo_id=doc_b.meta.ruo_id,
                relation_type=RelationType.COMPARES_WITH,
                confidence=ent_weighted,
                evidence_ids=ev_ids,
                is_directed=True,
                detected_at=now,
            )
            all_relations.append(rel)
            # Also add inverse
            inv = DocumentRelation(
                relation_id=f"rel_{uuid.uuid4().hex[:12]}",
                source_ruo_id=doc_b.meta.ruo_id,
                target_ruo_id=doc_a.meta.ruo_id,
                relation_type=RelationType.COMPARES_WITH,
                confidence=ent_weighted,
                evidence_ids=ev_ids,
                is_directed=True,
                detected_at=now,
            )
            all_relations.append(inv)

        # USES_METHOD from method overlap
        meth_weighted, meth_raw, meth_ev = self._aggregate_evidence(
            meth_evidence, "method",
        )
        if meth_raw >= self.method_threshold:
            rt = RelationType.USES_METHOD if meth_raw >= 0.4 else RelationType.EXTENDS
            ev_ids = [e.evidence_id for e in meth_ev]
            rel = DocumentRelation(
                relation_id=f"rel_{uuid.uuid4().hex[:12]}",
                source_ruo_id=doc_a.meta.ruo_id,
                target_ruo_id=doc_b.meta.ruo_id,
                relation_type=rt,
                confidence=meth_weighted,
                evidence_ids=ev_ids,
                is_directed=True,
                detected_at=now,
            )
            all_relations.append(rel)

        # SUPPORTS / CONTRADICTS from triple overlap
        triple_weighted, _, _ = self._aggregate_evidence(
            triple_evidence, "triple",
        )
        for ev in triple_evidence:
            if ev.confidence > 0:
                if "contradict" in ev.description.lower() or "negates" in ev.description.lower():
                    rt = RelationType.CONTRADICTS
                else:
                    rt = RelationType.SUPPORTS
                rel = DocumentRelation(
                    relation_id=f"rel_{uuid.uuid4().hex[:12]}",
                    source_ruo_id=doc_a.meta.ruo_id,
                    target_ruo_id=doc_b.meta.ruo_id,
                    relation_type=rt,
                    confidence=triple_weighted,
                    evidence_ids=[ev.evidence_id],
                    is_directed=True,
                    detected_at=now,
                )
                all_relations.append(rel)

        # SUPPORTS / CONTRADICTS from claim overlap
        claim_weighted, _, _ = self._aggregate_evidence(
            claim_evidence, "claim",
        )
        for ev in claim_evidence:
            if ev.confidence > 0:
                if "contradict" in ev.description.lower() or "negates" in ev.description.lower():
                    rt = RelationType.CONTRADICTS
                else:
                    rt = RelationType.SUPPORTS
                rel = DocumentRelation(
                    relation_id=f"rel_{uuid.uuid4().hex[:12]}",
                    source_ruo_id=doc_a.meta.ruo_id,
                    target_ruo_id=doc_b.meta.ruo_id,
                    relation_type=rt,
                    confidence=claim_weighted,
                    evidence_ids=[ev.evidence_id],
                    is_directed=True,
                    detected_at=now,
                )
                all_relations.append(rel)

        return all_relations, all_evidence

    # ------------------------------------------------------------------
    # Stage 1: Citation detection
    # ------------------------------------------------------------------

    def _detect_citation(
        self,
        doc_a: RUODocument,
        doc_b: RUODocument,
    ) -> list[RelationEvidence]:
        """Detect citation relations from doc_a to doc_b."""
        evidence: list[RelationEvidence] = []
        b_id = doc_b.meta.ruo_id
        b_doi = (doc_b.header.doi or "").lower().strip()
        b_title = (doc_b.header.title or "").strip()

        for ref in doc_a.references:
            ref_doi = (ref.doi or "").lower().strip()
            ref_target = ref.target_ruo_id
            ref_title = (ref.title or "").strip()

            # Check target_ruo_id match
            if ref_target and ref_target == b_id:
                ev = RelationEvidence(
                    evidence_id=f"ev_{uuid.uuid4().hex[:12]}",
                    evidence_type="citation",
                    description=f"Reference {ref.ref_id} target_ruo_id matches {b_id}",
                    confidence=1.0,
                    source_ids=[ref.ref_id],
                    target_ids=[b_id],
                )
                evidence.append(ev)
                continue

            # Check DOI match
            if ref_doi and b_doi and ref_doi == b_doi:
                ev = RelationEvidence(
                    evidence_id=f"ev_{uuid.uuid4().hex[:12]}",
                    evidence_type="citation",
                    description=f"DOI match: {ref_doi}",
                    confidence=1.0,
                    source_ids=[ref.ref_id],
                    target_ids=[b_id],
                )
                evidence.append(ev)
                continue

            # Check fuzzy title match
            if ref_title and b_title and len(ref_title) > 5 and len(b_title) > 5:
                sim = _fuzz_ratio(ref_title, b_title)
                if sim >= self.fuzzy_threshold:
                    ev = RelationEvidence(
                        evidence_id=f"ev_{uuid.uuid4().hex[:12]}",
                        evidence_type="citation",
                        description=f"Title fuzzy match: {sim:.1f}%",
                        confidence=1.0,
                        source_ids=[ref.ref_id],
                        target_ids=[b_id],
                    )
                    evidence.append(ev)

        return evidence

    # ------------------------------------------------------------------
    # Stage 2: Shared entity overlap
    # ------------------------------------------------------------------

    def _detect_entity_overlap(
        self,
        doc_a: RUODocument,
        doc_b: RUODocument,
        doc_canonicals: dict[str, set[str]],
    ) -> list[RelationEvidence]:
        """Detect relations via shared canonical entities."""
        a_id = doc_a.meta.ruo_id
        b_id = doc_b.meta.ruo_id

        a_canon = doc_canonicals.get(a_id, set())
        b_canon = doc_canonicals.get(b_id, set())

        if not a_canon or not b_canon:
            return []

        shared = a_canon & b_canon
        if not shared:
            return []

        overlap = len(shared) / min(len(a_canon), len(b_canon))
        conf = min(overlap, 1.0)

        shared_texts = sorted(shared)
        ev = RelationEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:12]}",
            evidence_type="entity",
            description=f"Shared canonical entities ({len(shared)}: {', '.join(shared_texts[:5])}{'...' if len(shared) > 5 else ''})",
            confidence=conf,
            source_ids=[f"{a_id}"],
            target_ids=[f"{b_id}"],
        )

        return [ev]

    # ------------------------------------------------------------------
    # Stage 3: Method overlap
    # ------------------------------------------------------------------

    def _detect_method_overlap(
        self,
        doc_a: RUODocument,
        doc_b: RUODocument,
        doc_canonicals: dict[str, set[str]],
    ) -> list[RelationEvidence]:
        """Detect relations via shared METHOD canonical entities."""
        a_id = doc_a.meta.ruo_id
        b_id = doc_b.meta.ruo_id

        # Get METHOD entity IDs for each doc
        a_method_canon = self._get_method_canonicals(doc_a)
        b_method_canon = self._get_method_canonicals(doc_b)

        if not a_method_canon or not b_method_canon:
            return []

        shared = a_method_canon & b_method_canon
        if not shared:
            return []

        overlap = len(shared) / min(len(a_method_canon), len(b_method_canon))
        conf = min(overlap, 1.0)

        shared_texts = sorted(shared)
        ev = RelationEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:12]}",
            evidence_type="method",
            description=f"Shared methods ({len(shared)}: {', '.join(shared_texts[:5])}{'...' if len(shared) > 5 else ''})",
            confidence=conf,
            source_ids=[f"{a_id}"],
            target_ids=[f"{b_id}"],
        )
        return [ev]

    def _get_method_canonicals(self, doc: RUODocument) -> set[str]:
        """Get set of canonical texts for METHOD entities in a document."""
        result: set[str] = set()
        for ent in doc.entities:
            if ent.label == EntityLabel.METHOD:
                canon = self._entity_to_canonical.get(ent.entity_id)
                if canon:
                    result.add(canon)
                else:
                    result.add(normalize_entity_text(ent.text))
        return result

    # ------------------------------------------------------------------
    # Stage 4: Triple comparison
    # ------------------------------------------------------------------

    def _detect_triple_overlap(
        self,
        doc_a: RUODocument,
        doc_b: RUODocument,
    ) -> list[RelationEvidence]:
        """Detect support or contradiction from triple comparison."""
        evidence: list[RelationEvidence] = []
        triples_a = doc_a.triples
        triples_b = doc_b.triples

        if not triples_a or not triples_b:
            return evidence

        # Build lookup for B's triples by (subject_id, predicate)
        b_lookup: dict[tuple[str, str], list[SemanticTriple]] = {}
        for t in triples_b:
            key = (t.subject_id, t.predicate)
            b_lookup.setdefault(key, []).append(t)

        for ta in triples_a:
            key = (ta.subject_id, ta.predicate)
            matches = b_lookup.get(key)
            if not matches:
                continue

            for tb in matches:
                if ta.object_id == tb.object_id and ta.is_negated == tb.is_negated:
                    # Support
                    conf = (ta.confidence + tb.confidence) / 2
                    ev = RelationEvidence(
                        evidence_id=f"ev_{uuid.uuid4().hex[:12]}",
                        evidence_type="triple",
                        description=f"Triple supports: {ta.subject_text} {ta.predicate} {ta.object_text}",
                        confidence=conf,
                        source_ids=[ta.triple_id],
                        target_ids=[tb.triple_id],
                    )
                    evidence.append(ev)
                elif ta.object_id != tb.object_id:
                    # Contradiction (conflicting object)
                    conf = (ta.confidence + tb.confidence) / 2 * 0.8
                    ev = RelationEvidence(
                        evidence_id=f"ev_{uuid.uuid4().hex[:12]}",
                        evidence_type="triple",
                        description=f"Triple contradicts: {ta.subject_text} {ta.predicate} differs",
                        confidence=conf,
                        source_ids=[ta.triple_id],
                        target_ids=[tb.triple_id],
                    )
                    evidence.append(ev)
                elif ta.is_negated != tb.is_negated:
                    # Contradiction (negation conflict)
                    conf = (ta.confidence + tb.confidence) / 2 * 0.9
                    ev = RelationEvidence(
                        evidence_id=f"ev_{uuid.uuid4().hex[:12]}",
                        evidence_type="triple",
                        description=f"Triple negates: {ta.subject_text} {ta.predicate} {ta.object_text}",
                        confidence=conf,
                        source_ids=[ta.triple_id],
                        target_ids=[tb.triple_id],
                    )
                    evidence.append(ev)

        return evidence

    # ------------------------------------------------------------------
    # Stage 5: Claim comparison
    # ------------------------------------------------------------------

    def _detect_claim_overlap(
        self,
        doc_a: RUODocument,
        doc_b: RUODocument,
    ) -> list[RelationEvidence]:
        """Detect support or contradiction from claim comparison."""
        evidence: list[RelationEvidence] = []

        claims_a = doc_a.claims
        claims_b = doc_b.claims

        if not claims_a or not claims_b:
            return evidence

        for ca in claims_a:
            for cb in claims_b:
                if ca.claim_type != cb.claim_type:
                    continue

                # Check for negation mismatch
                a_neg = _has_negation(ca.sentence)
                b_neg = _has_negation(cb.sentence)

                # Compare normalized statements if available
                match = self._claims_similar(ca, cb)

                if match and a_neg != b_neg:
                    # Contradiction
                    conf = (ca.confidence + cb.confidence) / 2 * 0.85
                    ev = RelationEvidence(
                        evidence_id=f"ev_{uuid.uuid4().hex[:12]}",
                        evidence_type="claim",
                        description=f"Claim contradicts: '{ca.sentence[:60]}...' vs '{cb.sentence[:60]}...'",
                        confidence=conf,
                        source_ids=[ca.claim_id],
                        target_ids=[cb.claim_id],
                    )
                    evidence.append(ev)
                elif match and not a_neg and not b_neg:
                    # Support
                    conf = (ca.confidence + cb.confidence) / 2 * 0.8
                    ev = RelationEvidence(
                        evidence_id=f"ev_{uuid.uuid4().hex[:12]}",
                        evidence_type="claim",
                        description=f"Claim supports: '{ca.sentence[:60]}...'",
                        confidence=conf,
                        source_ids=[ca.claim_id],
                        target_ids=[cb.claim_id],
                    )
                    evidence.append(ev)

        return evidence

    def _claims_similar(self, ca: RUOClaim, cb: RUOClaim) -> bool:
        """Check if two claims are semantically similar.

        Uses normalized_statement if available, otherwise falls back
        to matched_patterns intersection.
        """
        # Check normalized statements
        if ca.normalized_statement and cb.normalized_statement:
            sim = _fuzz_ratio(ca.normalized_statement, cb.normalized_statement)
            if sim >= 80.0:
                return True

        # Fallback: check pattern intersection
        a_patterns = {p.lower().strip() for p in ca.matched_patterns}
        b_patterns = {p.lower().strip() for p in cb.matched_patterns}
        if a_patterns & b_patterns:
            return True

        # Fallback: fuzzy sentence match
        sim = _fuzz_ratio(ca.sentence, cb.sentence)
        return sim >= 70.0

    # ------------------------------------------------------------------
    # Confidence aggregation
    # ------------------------------------------------------------------

    def _aggregate_evidence(
        self,
        evidence_list: list[RelationEvidence],
        stage_type: str,
    ) -> tuple[float, float, list[RelationEvidence]]:
        """Aggregate evidence from a single stage.

        Returns (weighted_confidence, raw_max_confidence, contributing_evidence).
        """
        if not evidence_list:
            return 0.0, 0.0, []

        weight = _STAGE_WEIGHTS.get(stage_type, 0.1)
        max_conf = max(e.confidence for e in evidence_list)
        return weight * max_conf, max_conf, evidence_list


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_negation(sentence: str) -> bool:
    """Check if a sentence contains negation markers."""
    lower = sentence.lower()
    words = set(lower.split())
    return bool(words & _NEGATION_WORDS)


def _fuzz_ratio(a: str, b: str) -> float:
    """Fuzzy string similarity in [0, 100] using RapidFuzz.

    Normalizes both inputs (lowercase, strip) before comparing.
    """
    if fuzz is None:
        return 0.0  # pragma: no cover
    if not a or not b:
        return 0.0
    na = normalize_entity_text(a)
    nb = normalize_entity_text(b)
    return float(fuzz.token_sort_ratio(na, nb))
