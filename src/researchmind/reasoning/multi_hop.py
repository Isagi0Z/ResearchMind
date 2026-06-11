"""M4-3 MultiHopReasoner — path finding and confidence propagation.

Supports exploration mode (neighbors at depth) and path-finding mode
(shortest/all paths between two nodes) with cycle handling and
confidence aggregation.
"""

from __future__ import annotations

from typing import Any

from researchmind.corpus.graph import (
    CorpusGraphEdge,
    CorpusGraphPath,
    CorpusGraphResult,
)
from researchmind.models.ruo_enums import EvidenceType, RelationType

from researchmind.reasoning.models import (
    AnswerEvidence,
    ReasoningQuery,
    ReasoningResult,
    ReasoningStep,
)

# ---------------------------------------------------------------------------
# Confidence helpers
# ---------------------------------------------------------------------------


def _product_confidence(confidences: list[float]) -> float:
    if not confidences:
        return 0.0
    prod = 1.0
    for c in confidences:
        prod *= c
    return prod


def _min_confidence(confidences: list[float]) -> float:
    return min(confidences) if confidences else 0.0


def _max_path_confidence(paths: list[CorpusGraphPath]) -> float:
    return max((p.confidence for p in paths), default=0.0)


def _noisy_or_unique_edges(paths: list[CorpusGraphPath]) -> float:
    seen: set[str] = set()
    prob = 1.0
    for p in paths:
        for e in p.edges:
            if e.edge_id not in seen:
                seen.add(e.edge_id)
                prob *= 1.0 - e.confidence
    return 1.0 - prob


# ---------------------------------------------------------------------------
# MultiHopReasoner
# ---------------------------------------------------------------------------


class MultiHopReasoner:
    """Multi-hop path reasoning over a CorpusGraph."""

    def __init__(
        self,
        graph: CorpusGraphResult,
        evidence_provider: Any | None = None,
    ):
        self._graph = graph
        self._evidence_provider = evidence_provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reason(
        self,
        source_id: str | None,
        target_id: str | None,
        query: ReasoningQuery,
    ) -> ReasoningResult:
        """Entry point. Routes to exploration or path-finding mode."""
        if target_id is None:
            return self._explore(source_id=source_id, query=query)
        if source_id is None:
            return ReasoningResult(
                query=query,
                answer="source_id is required for path reasoning.",
                confidence=0.0,
                warnings=["source_id is None"],
            )
        return self._path_find(source_id=source_id, target_id=target_id, query=query)

    # ------------------------------------------------------------------
    # Exploration mode
    # ------------------------------------------------------------------

    def _explore(
        self, source_id: str | None, query: ReasoningQuery
    ) -> ReasoningResult:
        if source_id is None and not query.node_ids:
            return ReasoningResult(
                query=query,
                answer="No source or node_ids provided for exploration.",
                confidence=0.0,
                warnings=["source_id and node_ids are both None"],
            )

        node_ids: list[str] = []
        if source_id is not None:
            node_ids.append(source_id)
        if query.node_ids:
            node_ids.extend(query.node_ids)

        all_nodes: list = []
        all_edges: list = []
        seen_nodes: set[str] = set()

        for nid in node_ids:
            neighbors = self._graph.get_neighbors(
                nid, depth=query.max_depth
            )
            for node in neighbors.nodes:
                if node.node_id not in seen_nodes:
                    seen_nodes.add(node.node_id)
                    all_nodes.append(node)
            for edge in neighbors.edges:
                all_edges.append(edge)

        evidence_list = self._make_evidence(all_edges)
        trace = self._build_trace(all_edges)

        graph_paths = []
        for e in all_edges:
            p = CorpusGraphPath(edges=[e])
            p.confidence = e.confidence
            graph_paths.append(p)

        return ReasoningResult(
            query=query,
            answer=(
                f"Exploration from {len(node_ids)} source(s): "
                f"found {len(all_nodes)} node(s), {len(all_edges)} edge(s)."
            ),
            confidence=_max_path_confidence(graph_paths),
            supporting_evidence=evidence_list,
            supporting_documents=list(
                {e.document_id for e in evidence_list if e.document_id}
            ),
            graph_paths=graph_paths,
            reasoning_trace=trace,
            metadata={
                "node_count": len(all_nodes),
                "edge_count": len(all_edges),
            },
        )

    # ------------------------------------------------------------------
    # Path-finding mode
    # ------------------------------------------------------------------

    def _path_find(
        self, source_id: str, target_id: str, query: ReasoningQuery
    ) -> ReasoningResult:
        paths = self._find_paths(
            source=source_id,
            target=target_id,
            max_depth=query.max_depth,
        )

        paths = self._filter_paths(
            paths,
            min_conf=query.min_confidence,
            rel_types=query.relation_types,
        )

        paths = self._detect_cycles(paths, strategy="per_path")

        for p in paths:
            p.confidence = self._propagate_confidence(
                p, method="product"
            )

        primary = _max_path_confidence(paths)
        upper = _noisy_or_unique_edges(paths)
        paths.sort(key=lambda p: (p.length, -p.confidence))
        paths = paths[: query.max_results]

        all_edges = []
        for p in paths:
            all_edges.extend(p.edges)
        unique_edges = list({e.edge_id: e for e in all_edges}.values())
        evidence_list = self._make_evidence(unique_edges)
        trace = self._build_trace(all_edges)

        answer_parts = [
            f"Found {len(paths)} path(s) from '{source_id}' to '{target_id}'.",
            f"Best path confidence: {primary:.3f}",
            f"Upper bound (unique-edge Noisy-OR): {upper:.3f}",
        ]

        return ReasoningResult(
            query=query,
            answer=" ".join(answer_parts),
            confidence=primary,
            supporting_evidence=evidence_list,
            supporting_documents=list(
                {e.document_id for e in evidence_list if e.document_id}
            ),
            graph_paths=paths,
            reasoning_trace=trace,
            metadata={
                "path_count": len(paths),
                "primary_confidence": primary,
                "upper_bound_confidence": upper,
            },
        )

    # ------------------------------------------------------------------
    # Pipeline methods
    # ------------------------------------------------------------------

    def _find_paths(
        self, source: str, target: str, max_depth: int = 5
    ) -> list[CorpusGraphPath]:
        if not source or not target:
            return []
        try:
            return self._graph.find_paths(
                source_id=source, target_id=target, max_depth=max_depth
            )
        except Exception:
            return []

    def _filter_paths(
        self,
        paths: list[CorpusGraphPath],
        min_conf: float = 0.0,
        rel_types: list[RelationType] | None = None,
    ) -> list[CorpusGraphPath]:
        result = []
        for p in paths:
            if rel_types is not None:
                if not any(
                    e.relation_type in rel_types for e in p.edges
                ):
                    continue
            edge_confs = [e.confidence for e in p.edges]
            if edge_confs and min(edge_confs) < min_conf:
                continue
            result.append(p)
        return result

    def _propagate_confidence(
        self, path: CorpusGraphPath, method: str = "product"
    ) -> float:
        confs = [e.confidence for e in path.edges]
        if method == "product":
            return _product_confidence(confs)
        elif method == "min":
            return _min_confidence(confs)
        return _product_confidence(confs)

    def _detect_cycles(
        self,
        paths: list[CorpusGraphPath],
        strategy: str = "per_path",
    ) -> list[CorpusGraphPath]:
        seen_sequences: set[tuple[str, ...]] = set()
        result = []
        for p in paths:
            nids = tuple(p.node_ids())
            if nids in seen_sequences:
                continue
            seen_sequences.add(nids)
            if strategy == "per_path":
                if len(nids) != len(set(nids)):
                    continue
            result.append(p)
        return result

    def _resolve_evidence_for_path(
        self, path: CorpusGraphPath
    ) -> list[AnswerEvidence]:
        eids = []
        for e in path.edges:
            eids.extend(e.evidence_ids)
        return self._resolve_evidence(eids)

    def _build_trace(
        self, edges: list[CorpusGraphEdge]
    ) -> list[ReasoningStep]:
        steps = []
        for i, e in enumerate(edges):
            steps.append(
                ReasoningStep(
                    step_number=i + 1,
                    description=f"Traverse {e.relation_type.value} edge",
                    source_node_id=e.source_id,
                    target_node_id=e.target_id,
                    relation_type=e.relation_type,
                    confidence=e.confidence,
                    evidence_ids=e.evidence_ids,
                )
            )
        return steps

    def _make_evidence(
        self, edges: list[CorpusGraphEdge]
    ) -> list[AnswerEvidence]:
        evidence = []
        for e in edges:
            for eid in e.evidence_ids:
                evidence.append(
                    AnswerEvidence(
                        evidence_id=eid,
                        source_text="",
                        confidence=e.confidence,
                        document_id=e.source_id,
                        evidence_type=self._determine_evidence_type(e.relation_type),
                        relation_type=e.relation_type,
                    )
                )
        return evidence

    def _resolve_evidence(
        self, evidence_ids: list[str]
    ) -> list[AnswerEvidence]:
        if self._evidence_provider is None or not evidence_ids:
            return []
        records = self._evidence_provider(evidence_ids)
        result = []
        for r in records:
            result.append(
                AnswerEvidence(
                    evidence_id=getattr(r, "evidence_id", ""),
                    source_text=getattr(r, "source_text", ""),
                    confidence=getattr(r, "confidence", 0.0),
                    document_id=getattr(r, "document_id", ""),
                    evidence_type=getattr(r, "evidence_type", EvidenceType.DIRECT_QUOTE),
                    location=getattr(r, "location", None),
                )
            )
        return result

    @staticmethod
    def _determine_evidence_type(rt: RelationType) -> EvidenceType:
        mapping = {
            RelationType.CONTRADICTS: EvidenceType.DERIVED,
            RelationType.SUPPORTS: EvidenceType.DERIVED,
            RelationType.EXTENDS: EvidenceType.DERIVED,
            RelationType.USES_METHOD: EvidenceType.DERIVED,
            RelationType.USES_DATASET: EvidenceType.DERIVED,
            RelationType.COMPARES_WITH: EvidenceType.DERIVED,
            RelationType.CITES: EvidenceType.DIRECT_QUOTE,
            RelationType.CITED_BY: EvidenceType.DIRECT_QUOTE,
        }
        return mapping.get(rt, EvidenceType.DERIVED)
