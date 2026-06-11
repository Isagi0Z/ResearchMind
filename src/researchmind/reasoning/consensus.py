"""M4-4 ConsensusEngine — cross-document agreement analysis.

Measures agreement/disagreement about claims or entities across the corpus
using deterministic stance detection from graph edges and document signals.
"""

from __future__ import annotations

from typing import Any

from researchmind.corpus.graph import CorpusGraphNode, CorpusGraphResult
from researchmind.models.enums import ClaimType
from researchmind.models.ruo_enums import RelationType

from researchmind.reasoning.models import (
    ConsensusResult,
    DocumentConsensusEntry,
    ReasoningQuery,
)

# Edges that signal supporting stance
_SUPPORT_EDGES: set[RelationType] = {
    RelationType.SUPPORTS,
    RelationType.EXTENDS,
    RelationType.USES_METHOD,
    RelationType.USES_DATASET,
    RelationType.REPRODUCES,
}

# Edges that signal contradicting stance
_CONTRADICT_EDGES: set[RelationType] = {
    RelationType.CONTRADICTS,
}


class ConsensusEngine:
    """Deterministic cross-document consensus analysis."""

    def __init__(
        self,
        graph: CorpusGraphResult,
        corpus_id: str | None = None,
    ):
        self._graph = graph
        self._corpus_id = corpus_id
        self._min_docs_warn: int = 2
        self._min_docs_recommended: int = 5
        self._contradiction_threshold: float = 0.2
        self._strong_threshold: float = 0.8
        self._moderate_threshold: float = 0.6
        self._weak_threshold: float = 0.4

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self, target_id: str, query: ReasoningQuery
    ) -> ConsensusResult:
        target_label = self._resolve_label(target_id)
        entries: list[DocumentConsensusEntry] = []
        document_ids = self._get_document_ids_for_target(target_id)

        for doc_id in document_ids:
            entry = self._determine_stance(doc_id, target_id)
            entries.append(entry)

        stance_counts = {"supports": 0, "contradicts": 0, "neutral": 0}
        for e in entries:
            stance_counts[e.stance] += 1

        total = len(entries) if entries else 0
        sr = stance_counts["supports"] / total if total else 0.0
        cr = stance_counts["contradicts"] / total if total else 0.0
        nr = stance_counts["neutral"] / total if total else 0.0

        confidence = self._compute_consensus_confidence(
            entries, sr, cr, nr
        )
        classification = self._classify_consensus(cr, sr)

        warnings = self._check_min_docs(total)

        return ConsensusResult(
            target_id=target_id,
            target_label=target_label,
            total_documents=total,
            supporting_documents=stance_counts["supports"],
            contradicting_documents=stance_counts["contradicts"],
            neutral_documents=stance_counts["neutral"],
            support_ratio=round(sr, 4),
            contradiction_ratio=round(cr, 4),
            neutral_ratio=round(nr, 4),
            consensus_confidence=round(confidence, 4),
            classification=classification,
            warnings=warnings,
            per_document=entries,
        )

    # ------------------------------------------------------------------
    # Stance determination
    # ------------------------------------------------------------------

    def _determine_stance(
        self, doc_id: str, target_id: str
    ) -> DocumentConsensusEntry:
        edges = self._get_edges_between(doc_id, target_id)
        has_support = False
        has_contradict = False
        evidence_ids: list[str] = []

        for e in edges:
            evidence_ids.extend(e.evidence_ids)
            if e.relation_type in _CONTRADICT_EDGES:
                has_contradict = True
            elif e.relation_type in _SUPPORT_EDGES:
                has_support = True

        has_negation_claim = self._check_negation_claim(doc_id, target_id)
        if has_negation_claim:
            has_contradict = True

        mixed = has_support and has_contradict

        if has_contradict:
            stance = "contradicts"
        elif has_support:
            stance = "supports"
        else:
            stance = "neutral"

        conf = max((e.confidence for e in edges), default=0.5)

        return DocumentConsensusEntry(
            document_id=doc_id,
            document_title=self._resolve_label(doc_id),
            stance=stance,
            confidence=conf,
            evidence_ids=evidence_ids,
            mixed_evidence=mixed,
        )

    def _compute_consensus_confidence(
        self,
        entries: list[DocumentConsensusEntry],
        sr: float,
        cr: float,
        nr: float,
    ) -> float:
        if not entries:
            return 0.0
        support_confs = [
            e.confidence for e in entries if e.stance == "supports"
        ]
        contradict_confs = [
            e.confidence for e in entries if e.stance == "contradicts"
        ]
        avg_support = (
            sum(support_confs) / len(support_confs) if support_confs else 0.0
        )
        avg_contradict = (
            sum(contradict_confs) / len(contradict_confs)
            if contradict_confs
            else 0.0
        )
        return sr * avg_support + cr * avg_contradict + nr * 0.5

    def _classify_consensus(
        self, contradiction_ratio: float, support_ratio: float
    ) -> str:
        if contradiction_ratio >= self._contradiction_threshold:
            return "disputed"
        if support_ratio >= self._strong_threshold:
            return "strong"
        if support_ratio >= self._moderate_threshold:
            return "moderate"
        if support_ratio >= self._weak_threshold:
            return "weak"
        return "insufficient_evidence"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_label(self, node_id: str) -> str:
        nd = self._node_dict()
        node = nd.get(node_id)
        if node is not None:
            return getattr(node, "label", "") or ""
        return ""

    def _node_dict(self) -> dict[str, Any]:
        return {n.node_id: n for n in self._graph.nodes}

    def _get_document_ids_for_target(self, target_id: str) -> list[str]:
        result: set[str] = set()
        for edge in self._graph.edges:
            if edge.source_id == target_id:
                result.add(edge.target_id)
            if edge.target_id == target_id:
                result.add(edge.source_id)
        doc_nodes = [
            n.node_id
            for n in self._graph.nodes
            if n.node_id in result or n.node_type == "document"
        ]
        if not doc_nodes:
            return list(result)
        return [d for d in doc_nodes if d in result] or list(result)

    def _get_edges_between(
        self, node_a: str, node_b: str
    ) -> list:
        matches = []
        for e in self._graph.edges:
            if (e.source_id == node_a and e.target_id == node_b) or (
                e.source_id == node_b and e.target_id == node_a
            ):
                matches.append(e)
        return matches

    def _check_negation_claim(
        self, doc_id: str, target_id: str
    ) -> bool:
        return False

    def _check_min_docs(self, total: int) -> list[str]:
        warnings = []
        if total < self._min_docs_warn:
            warnings.append(
                f"Only {total} document(s) — minimum {self._min_docs_warn} required."
            )
        elif total < self._min_docs_recommended:
            warnings.append(
                f"Only {total} document(s) — {self._min_docs_recommended}+ recommended."
            )
        return warnings
