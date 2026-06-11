"""M4-6 ResearchGapEngine — deterministic gap detection.

Detects five gap types: isolated entities, missing comparisons,
low-confidence claims, under-studied datasets, and unconnected documents.
"""

from __future__ import annotations

from typing import Any

from researchmind.corpus.graph import CorpusGraphResult
from researchmind.corpus.entity_resolution import (
    CanonicalEntity,
    EntityCluster,
    ResolutionResult,
)
from researchmind.models.enums import EntityLabel

from researchmind.reasoning.models import (
    GapAnalysisResult,
    GapItem,
    GapType,
    ReasoningQuery,
)

# Default thresholds
_ISOLATED_DOC_THRESHOLD = 1
_MISSING_COMPARISON_DOC_MIN = 2
_MISSING_COMPARISON_LABELS: set[EntityLabel] = {
    EntityLabel.METHOD,
    EntityLabel.DATASET,
    EntityLabel.METRIC,
}
_LOW_CONFIDENCE_THRESHOLD = 0.3
_UNDER_STUDIED_DOC_THRESHOLD = 2
_CORPUS_SIZE_MIN = 5


class ResearchGapEngine:
    """Deterministic research gap detection over a corpus graph."""

    def __init__(
        self,
        graph: CorpusGraphResult,
        resolution_result: ResolutionResult | None = None,
        claims_index: dict[str, list] | None = None,
        entity_to_doc: dict[str, list[str]] | None = None,
        corpus_id: str | None = None,
    ):
        self._graph = graph
        self._resolution = resolution_result
        self._claims_index = claims_index or {}
        self._entity_to_doc = entity_to_doc or {}
        self._corpus_id = corpus_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, query: ReasoningQuery) -> GapAnalysisResult:
        gap_types = query.gap_types or [
            GapType.ISOLATED_ENTITY,
            GapType.MISSING_COMPARISON,
            GapType.LOW_CONFIDENCE_CLAIM,
            GapType.UNDER_STUDIED_DATASET,
            GapType.UNCONNECTED_DOCUMENT,
        ]

        isolated: list[GapItem] = []
        missing: list[GapItem] = []
        low_conf: list[GapItem] = []
        understudied: list[GapItem] = []
        unconnected: list[GapItem] = []

        if GapType.ISOLATED_ENTITY in gap_types:
            isolated = self._find_isolated_entities()
        if GapType.MISSING_COMPARISON in gap_types:
            missing = self._find_missing_comparisons()
        if GapType.LOW_CONFIDENCE_CLAIM in gap_types:
            low_conf = self._find_low_confidence_claims()
        if GapType.UNDER_STUDIED_DATASET in gap_types:
            understudied = self._find_under_studied_datasets()
        if GapType.UNCONNECTED_DOCUMENT in gap_types:
            unconnected = self._find_unconnected_documents()

        all_gaps = isolated + missing + low_conf + understudied + unconnected
        all_gaps = self._deduplicate_gaps(all_gaps)
        all_gaps = self._generate_suggestions(all_gaps)

        warnings: list[str] = []
        cw = self._check_corpus_size()
        if cw is not None:
            warnings.append(cw)

        summary_parts = [
            f"Gap analysis identified {len(all_gaps)} gap(s):",
        ]
        if isolated:
            summary_parts.append(f"{len(isolated)} isolated entity(ies)")
        if missing:
            summary_parts.append(f"{len(missing)} missing comparison(s)")
        if low_conf:
            summary_parts.append(f"{len(low_conf)} low-confidence claim(s)")
        if understudied:
            summary_parts.append(f"{len(understudied)} under-studied dataset(s)")
        if unconnected:
            summary_parts.append(f"{len(unconnected)} unconnected document(s)")
        if warnings:
            summary_parts.extend(f"Warning: {w}" for w in warnings)

        return GapAnalysisResult(
            isolated_entities=isolated,
            missing_comparisons=missing,
            low_confidence_claims=low_conf,
            under_studied_datasets=understudied,
            unconnected_documents=unconnected,
            total_gaps=len(all_gaps),
            summary=". ".join(summary_parts) + ".",
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Gap detection methods
    # ------------------------------------------------------------------

    def _find_isolated_entities(self) -> list[GapItem]:
        items: list[GapItem] = []
        entity_doc_map = self._build_entity_doc_map()

        for cluster_id, doc_ids in entity_doc_map.items():
            if len(doc_ids) <= _ISOLATED_DOC_THRESHOLD:
                cluster = self._get_cluster(cluster_id)
                weight = getattr(cluster, "weight", 1.0) if hasattr(cluster, "weight") else 1.0
                if hasattr(cluster, "canonical_entity"):
                    weight = cluster.canonical_entity.confidence if cluster.canonical_entity else weight
                label = ""
                if cluster and hasattr(cluster, "canonical_entity") and cluster.canonical_entity:
                    label = cluster.canonical_entity.canonical_text
                confidence = weight
                if confidence > 0:
                    items.append(
                        GapItem(
                            gap_type=GapType.ISOLATED_ENTITY,
                            node_id=cluster_id,
                            label=label,
                            description=(
                                f"Entity '{label}' appears in only {len(doc_ids)} document(s)"
                            ),
                            confidence=round(confidence, 4),
                            supporting_metrics={
                                "doc_count": len(doc_ids),
                                "cluster_weight": weight,
                            },
                            suggestion="",
                        )
                    )
        return items

    def _find_missing_comparisons(self) -> list[GapItem]:
        items: list[GapItem] = []
        entity_doc_map = self._build_entity_doc_map()
        entity_label_map = self._build_entity_label_map()

        for cluster_id, doc_ids in entity_doc_map.items():
            label = entity_label_map.get(cluster_id)
            if label not in _MISSING_COMPARISON_LABELS:
                continue
            if len(doc_ids) < _MISSING_COMPARISON_DOC_MIN:
                continue
            compare_edges = [
                e
                for e in self._graph.edges
                if e.source_id == cluster_id
                or e.target_id == cluster_id
            ]
            has_comparison = any(
                e.relation_type.value == "compares_with"
                for e in compare_edges
            )
            if not has_comparison:
                doc_count = len(doc_ids)
                confidence = 1.0 - (1.0 / max(doc_count, 2))
                items.append(
                    GapItem(
                        gap_type=GapType.MISSING_COMPARISON,
                        node_id=cluster_id,
                        label=self._resolve_label(cluster_id),
                        description=(
                            f"Entity appears in {doc_count} document(s) "
                            f"with no COMPARES_WITH edges"
                        ),
                        confidence=round(confidence, 4),
                        supporting_metrics={
                            "doc_count": doc_count,
                            "label": label.value if label else "",
                        },
                        suggestion="",
                    )
                )
        return items

    def _find_low_confidence_claims(self) -> list[GapItem]:
        items: list[GapItem] = []
        seen: set[str] = set()

        for (
            cluster_id,
            claims,
        ) in self._claims_index.items():
            for claim in claims:
                claim_conf = getattr(claim, "confidence", 0.0)
                if claim_conf < _LOW_CONFIDENCE_THRESHOLD:
                    claim_id = (
                        getattr(claim, "claim_id", "")
                        or str(id(claim))
                    )
                    if claim_id in seen:
                        continue
                    seen.add(claim_id)
                    confidence = 1.0 - claim_conf
                    items.append(
                        GapItem(
                            gap_type=GapType.LOW_CONFIDENCE_CLAIM,
                            node_id=claim_id,
                            label=getattr(claim, "normalized_statement", "") or "",
                            description=(
                                f"Low-confidence claim (conf={claim_conf:.3f})"
                            ),
                            confidence=round(confidence, 4),
                            supporting_metrics={
                                "claim_confidence": claim_conf,
                            },
                            suggestion="",
                        )
                    )
        return items

    def _find_under_studied_datasets(self) -> list[GapItem]:
        items: list[GapItem] = []
        entity_doc_map = self._build_entity_doc_map()
        entity_label_map = self._build_entity_label_map()

        for cluster_id, doc_ids in entity_doc_map.items():
            label = entity_label_map.get(cluster_id)
            if label != EntityLabel.DATASET:
                continue
            doc_count = len(doc_ids)
            if doc_count < _UNDER_STUDIED_DOC_THRESHOLD:
                confidence = 1.0 - (doc_count / _UNDER_STUDIED_DOC_THRESHOLD)
                items.append(
                    GapItem(
                        gap_type=GapType.UNDER_STUDIED_DATASET,
                        node_id=cluster_id,
                        label=self._resolve_label(cluster_id),
                        description=(
                            f"Dataset appears in only {doc_count} document(s)"
                        ),
                        confidence=round(confidence, 4),
                        supporting_metrics={
                            "doc_count": doc_count,
                            "threshold": _UNDER_STUDIED_DOC_THRESHOLD,
                        },
                        suggestion="",
                    )
                )
        return items

    def _find_unconnected_documents(self) -> list[GapItem]:
        items: list[GapItem] = []
        doc_nodes = [
            n
            for n in self._graph.nodes
            if getattr(n, "node_type", "") == "document"
        ]
        if not doc_nodes:
            doc_nodes = list(self._graph.nodes)

        max_entity_count = 0
        doc_entity_counts: dict[str, int] = {}
        entity_doc_map = self._build_entity_doc_map()

        doc_to_entities: dict[str, set[str]] = {}
        for cluster_id, doc_ids in entity_doc_map.items():
            for did in doc_ids:
                if did not in doc_to_entities:
                    doc_to_entities[did] = set()
                doc_to_entities[did].add(cluster_id)

        for n in doc_nodes:
            nid = n.node_id if hasattr(n, "node_id") else str(n)
            count = len(
                doc_to_entities.get(
                    nid, []
                )
            )
            doc_entity_counts[nid] = count
            if count > max_entity_count:
                max_entity_count = count

        nd = self._node_dict()
        for n in doc_nodes:
            nid = n.node_id if hasattr(n, "node_id") else str(n)
            relevant_edges = [
                e
                for e in self._graph.edges
                if e.source_id == nid or e.target_id == nid
            ]
            doc_doc_edges = [
                e
                for e in relevant_edges
                if (
                    nd.get(e.source_id, nd.get(e.target_id))
                    and getattr(nd.get(e.source_id), "node_type", None) == "document"
                )
                or (
                    nd.get(e.target_id)
                    and getattr(nd.get(e.target_id), "node_type", None) == "document"
                )
            ]
            compare_or_cite = [
                e
                for e in doc_doc_edges
                if e.relation_type.value
                in ("compares_with", "cites", "cited_by")
            ]
            if not compare_or_cite:
                entity_count = doc_entity_counts.get(nid, 0)
                confidence = (
                    min(1.0, entity_count / max_entity_count)
                    if max_entity_count > 0
                    else 0.0
                )
                label = (
                    getattr(n, "label", "") or ""
                )
                items.append(
                    GapItem(
                        gap_type=GapType.UNCONNECTED_DOCUMENT,
                        node_id=nid,
                        label=label,
                        description=(
                            f"Document has no COMPARES_WITH or CITES edges "
                            f"to other documents"
                        ),
                        confidence=round(confidence, 4),
                        supporting_metrics={
                            "entity_count": entity_count,
                            "max_entity_count": max_entity_count,
                        },
                        suggestion="",
                    )
                )
        return items

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    def _generate_suggestions(
        self, gap_items: list[GapItem]
    ) -> list[GapItem]:
        suggestions = {
            GapType.ISOLATED_ENTITY: (
                "Consider expanding the search to cover more documents "
                "that might discuss this entity."
            ),
            GapType.MISSING_COMPARISON: (
                "Consider designing a study that directly compares "
                "this method/dataset/metric with alternatives."
            ),
            GapType.LOW_CONFIDENCE_CLAIM: (
                "Review extraction quality or gather additional evidence "
                "for this claim."
            ),
            GapType.UNDER_STUDIED_DATASET: (
                "This dataset may be underexplored — consider new "
                "experiments or benchmarks."
            ),
            GapType.UNCONNECTED_DOCUMENT: (
                "This document lacks relational context — consider "
                "linking it via comparison or citation analysis."
            ),
        }
        result = []
        for gap in gap_items:
            gap.suggestion = suggestions.get(gap.gap_type, "")
            result.append(gap)
        return result

    def _compute_gap_confidence(
        self, gap_type: str, metrics: dict
    ) -> float:
        return 0.0

    def _deduplicate_gaps(
        self, all_gaps: list[GapItem]
    ) -> list[GapItem]:
        seen: set[tuple[str, str]] = set()
        result = []
        for gap in all_gaps:
            key = (gap.gap_type, gap.node_id)
            if key not in seen:
                seen.add(key)
                result.append(gap)
        return result

    def _check_corpus_size(self) -> str | None:
        doc_count = len(
            [
                n
                for n in self._graph.nodes
                if getattr(n, "node_type", "") == "document"
            ]
        )
        if doc_count == 0:
            doc_count = len(self._graph.nodes)
        if doc_count < _CORPUS_SIZE_MIN:
            return (
                f"Corpus has only {doc_count} document(s); "
                f"gap analysis is more reliable with {_CORPUS_SIZE_MIN}+ documents."
            )
        return None

    # ------------------------------------------------------------------
    # Index builders
    # ------------------------------------------------------------------

    def _build_entity_doc_map(self) -> dict[str, list[str]]:
        if self._entity_to_doc:
            return self._entity_to_doc
        nd = self._node_dict()
        mapping: dict[str, set[str]] = {}
        for edge in self._graph.edges:
            node = nd.get(edge.source_id)
            ntype = node.node_type if node else ("entity_cluster" if edge.source_id.startswith("cluster") else "unknown")
            if ntype == "entity_cluster":
                if edge.source_id not in mapping:
                    mapping[edge.source_id] = set()
                mapping[edge.source_id].add(edge.target_id)
            node = nd.get(edge.target_id)
            ntype = node.node_type if node else ("entity_cluster" if edge.target_id.startswith("cluster") else "unknown")
            if ntype == "entity_cluster":
                if edge.target_id not in mapping:
                    mapping[edge.target_id] = set()
                mapping[edge.target_id].add(edge.source_id)
        return {k: list(v) for k, v in mapping.items()}

    def _build_entity_label_map(self) -> dict[str, EntityLabel | None]:
        mapping: dict[str, EntityLabel | None] = {}
        if self._resolution is not None:
            for cluster in getattr(
                self._resolution, "clusters", []
            ):
                cid = getattr(cluster, "cluster_id", "")
                if (
                    cid
                    and hasattr(cluster, "canonical_entity")
                    and cluster.canonical_entity
                ):
                    mapping[cid] = cluster.canonical_entity.label
        for edge in self._graph.edges:
            if edge.source_id not in mapping:
                mapping[edge.source_id] = None
            if edge.target_id not in mapping:
                mapping[edge.target_id] = None
        return mapping

    def _get_cluster(self, cluster_id: str) -> EntityCluster | None:
        if self._resolution is not None:
            for cluster in getattr(
                self._resolution, "clusters", []
            ):
                if getattr(cluster, "cluster_id", "") == cluster_id:
                    return cluster
        return None

    def _resolve_label(self, node_id: str) -> str:
        nd = self._node_dict()
        node = nd.get(node_id)
        if node is not None:
            return getattr(node, "label", "") or ""
        return ""

    def _node_dict(self) -> dict[str, Any]:
        return {n.node_id: n for n in self._graph.nodes}
