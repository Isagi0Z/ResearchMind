"""M4-5 ContradictionEngine — contradiction detection.

Detects direct contradictions (via CONTRADICTS edges) and indirect
contradictions (via polarity mismatches and negated triple conflicts).
"""

from __future__ import annotations

from typing import Any

from researchmind.corpus.graph import CorpusGraphResult
from researchmind.models.ruo_enums import RelationType

from researchmind.reasoning.models import (
    ContradictionResult,
    DirectContradiction,
    IndirectContradiction,
    ReasoningQuery,
)


class ContradictionEngine:
    """Deterministic contradiction detection across the corpus."""

    def __init__(self, graph: CorpusGraphResult):
        self._graph = graph
        self._contradict_relation = RelationType.CONTRADICTS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self, target_id: str, query: ReasoningQuery
    ) -> ContradictionResult:
        target_label = self._resolve_label(target_id)

        direct = self._detect_direct(target_id, query)
        indirect = self._detect_indirect(target_id, query)

        all_contradictions = direct + indirect
        count = len(all_contradictions)

        agg_conf = self._compute_contradiction_confidence(all_contradictions)

        return ContradictionResult(
            target_id=target_id,
            target_label=target_label,
            direct_contradictions=direct,
            indirect_contradictions=indirect,
            contradiction_count=count,
            aggregate_confidence=round(agg_conf, 4),
        )

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def _detect_direct(
        self, target_id: str, query: ReasoningQuery
    ) -> list[DirectContradiction]:
        results: list[DirectContradiction] = []
        seen_pairs: set[tuple[str, str]] = set()

        for edge in self._graph.edges:
            if edge.relation_type != self._contradict_relation:
                continue
            if edge.source_id == target_id:
                other = edge.target_id
            elif edge.target_id == target_id:
                other = edge.source_id
            else:
                continue

            pair = tuple(sorted([target_id, other]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            if edge.confidence < query.min_confidence:
                continue

            source_doc = target_id
            target_doc = other
            source_title = self._resolve_label(target_id)
            target_title = self._resolve_label(other)

            results.append(
                DirectContradiction(
                    source_document_id=source_doc,
                    source_document_title=source_title,
                    target_document_id=target_doc,
                    target_document_title=target_title,
                    edge_id=edge.edge_id,
                    confidence=edge.confidence,
                    evidence_ids=list(edge.evidence_ids),
                    source_text="",
                )
            )
        return results

    def _detect_indirect(
        self, target_id: str, query: ReasoningQuery
    ) -> list[IndirectContradiction]:
        results: list[IndirectContradiction] = []

        edges = self._graph.edges
        target_edges = [
            e
            for e in edges
            if e.source_id == target_id or e.target_id == target_id
        ]

        documents: set[str] = set()
        for e in target_edges:
            if e.source_id != target_id:
                documents.add(e.source_id)
            if e.target_id != target_id:
                documents.add(e.target_id)

        doc_list = list(documents)
        for i in range(len(doc_list)):
            for j in range(i + 1, len(doc_list)):
                a_edges = [
                    e
                    for e in edges
                    if e.source_id == doc_list[i]
                    or e.target_id == doc_list[i]
                ]
                b_edges = [
                    e
                    for e in edges
                    if e.source_id == doc_list[j]
                    or e.target_id == doc_list[j]
                ]
                for ea in a_edges:
                    for eb in b_edges:
                        if (
                            ea.relation_type == RelationType.CONTRADICTS
                            and eb.relation_type == RelationType.CONTRADICTS
                            and (
                                ea.target_id == target_id
                                or ea.source_id == target_id
                            )
                            and (
                                eb.target_id == target_id
                                or eb.source_id == target_id
                            )
                        ):
                            results.append(
                                IndirectContradiction(
                                    description=(
                                        f"Inferred contradiction via "
                                        f"{self._resolve_label(doc_list[i])} "
                                        f"and {self._resolve_label(doc_list[j])}"
                                    ),
                                    subject_id=target_id,
                                    subject_label=self._resolve_label(target_id),
                                    claim_a=self._resolve_label(doc_list[i]),
                                    claim_a_document=doc_list[i],
                                    claim_b=self._resolve_label(doc_list[j]),
                                    claim_b_document=doc_list[j],
                                    confidence=min(ea.confidence, eb.confidence),
                                )
                            )
        return results

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    def _compute_contradiction_confidence(
        self, contradictions: list
    ) -> float:
        if not contradictions:
            return 0.0
        confs = [c.confidence for c in contradictions]
        return max(confs)

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

    def _deduplicate_contradictions(
        self, contradictions: list
    ) -> list[Any]:
        seen: set[tuple[str, str]] = set()
        result = []
        for c in contradictions:
            key: tuple[str, str] | None = None
            if isinstance(c, DirectContradiction):
                key = tuple(sorted([c.source_document_id, c.target_document_id]))
            elif isinstance(c, IndirectContradiction):
                key = tuple(sorted([c.claim_a_document, c.claim_b_document]))
            if key is not None and key not in seen:
                seen.add(key)
                result.append(c)
        return result
