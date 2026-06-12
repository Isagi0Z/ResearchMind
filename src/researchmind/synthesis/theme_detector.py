"""Theme Detector — discover research themes from graph structure.

Deterministic connected-component clustering on entity co-occurrence edges.
No ML, no embeddings, no LLMs.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from researchmind.models.enums import EntityLabel
from researchmind.models.ruo_enums import RelationType
from researchmind.synthesis.models import ThemeCluster, ThemeType, _generate_id

_THEME_EDGE_TYPES: frozenset[str] = frozenset({
    RelationType.COMPARES_WITH.value,
    RelationType.USES_METHOD.value,
})

_TIEBREAK_ORDER: list[ThemeType] = [
    ThemeType.METHOD,
    ThemeType.DATASET,
    ThemeType.METRIC,
    ThemeType.CONCEPT,
]

_LABEL_TO_THEME: dict[str, ThemeType] = {
    EntityLabel.METHOD.value: ThemeType.METHOD,
    EntityLabel.DATASET.value: ThemeType.DATASET,
    EntityLabel.METRIC.value: ThemeType.METRIC,
}


def _extract_entity_metadata(node) -> dict[str, Any]:
    label_raw = node.metadata.get("label", "")
    entity_label = label_raw.lower().strip() if isinstance(label_raw, str) else ""
    confidence = float(node.metadata.get("confidence", 0.0))
    return {"entity_label": entity_label, "confidence": max(0.0, min(1.0, confidence))}


def _classify_theme(entity_labels: list[str]) -> ThemeType:
    counts: dict[ThemeType, int] = {t: 0 for t in _TIEBREAK_ORDER}
    for el in entity_labels:
        theme = _LABEL_TO_THEME.get(el, ThemeType.CONCEPT)
        counts[theme] = counts.get(theme, 0) + 1
    best = max(counts, key=lambda t: (counts[t], -_TIEBREAK_ORDER.index(t)))
    return best


def _pick_label(
    node_labels: list[str],
    confidences: list[float],
) -> str:
    if not node_labels:
        return ""
    best_idx = 0
    best_conf = confidences[0]
    for i in range(1, len(node_labels)):
        if confidences[i] > best_conf:
            best_conf = confidences[i]
            best_idx = i
        elif confidences[i] == best_conf:
            if len(node_labels[i]) > len(node_labels[best_idx]):
                best_idx = i
            elif len(node_labels[i]) == len(node_labels[best_idx]) and node_labels[i] < node_labels[best_idx]:
                best_idx = i
    return node_labels[best_idx]


def _compute_confidence(confidences: list[float]) -> float:
    if not confidences:
        return 0.0
    mean = sum(confidences) / len(confidences)
    return max(0.0, min(1.0, mean))


class ThemeDetector:
    """Discovers research themes from entity cluster co-occurrence patterns."""

    def __init__(self) -> None:
        pass

    def detect_themes(
        self,
        graph: Any,
        max_themes: int = 20,
        min_cluster_size: int = 2,
    ) -> list[ThemeCluster]:
        """Deterministic theme detection using graph structure.

        Parameters
        ----------
        graph : CorpusGraphResult
            Graph result from M3 corpus intelligence.
        max_themes : int
            Maximum number of themes to return (default 20).
        min_cluster_size : int
            Minimum number of entity clusters per theme (default 2).

        Returns
        -------
        list[ThemeCluster]
            Detected themes sorted by size desc, confidence desc, label asc.
        """
        if max_themes < 1:
            return []
        if min_cluster_size < 1:
            min_cluster_size = 1

        nodes = list(getattr(graph, "nodes", []) or [])
        edges = list(getattr(graph, "edges", []) or [])

        if not nodes or not edges:
            return []

        entity_nodes = {}
        for n in nodes:
            if getattr(n, "node_type", None) == "entity_cluster":
                entity_nodes[n.node_id] = n

        if not entity_nodes:
            return []

        entity_ids: set[str] = set(entity_nodes.keys())
        adj: dict[str, set[str]] = defaultdict(set)
        theme_edge_types: set[str] = set()
        for e in edges:
            etype = getattr(e, "relation_type", None)
            if etype is None:
                continue
            etype_str = etype.value if hasattr(etype, "value") else str(etype)
            if etype_str not in _THEME_EDGE_TYPES:
                continue
            src = getattr(e, "source_id", "")
            tgt = getattr(e, "target_id", "")
            if src in entity_ids and tgt in entity_ids:
                adj[src].add(tgt)
                adj[tgt].add(src)
                theme_edge_types.add(etype_str)
            elif src in entity_ids or tgt in entity_ids:
                theme_edge_types.add(etype_str)

        visited: set[str] = set()
        components: list[list[str]] = []

        sorted_entity_ids = sorted(entity_ids)
        for eid in sorted_entity_ids:
            if eid in visited:
                continue
            component: list[str] = []
            queue: deque[str] = deque()
            queue.append(eid)
            visited.add(eid)
            while queue:
                current = queue.popleft()
                component.append(current)
                neighbors = sorted(adj.get(current, set()))
                for nb in neighbors:
                    if nb not in visited:
                        visited.add(nb)
                        queue.append(nb)
            component.sort()
            components.append(component)

        themes: list[ThemeCluster] = []
        for comp in components:
            if len(comp) < min_cluster_size:
                continue

            comp_nodes = [entity_nodes[cid] for cid in comp if cid in entity_nodes]
            if not comp_nodes:
                continue

            labels: list[str] = []
            confidences: list[float] = []
            entity_labels: list[str] = []
            for cn in comp_nodes:
                meta = _extract_entity_metadata(cn)
                labels.append(cn.label)
                confidences.append(meta["confidence"])
                entity_labels.append(meta["entity_label"])

            theme_type = _classify_theme(entity_labels)
            label = _pick_label(labels, confidences)
            confidence = _compute_confidence(confidences)

            doc_ids: set[str] = set()
            for e in edges:
                src = getattr(e, "source_id", "")
                tgt = getattr(e, "target_id", "")
                etype = getattr(e, "relation_type", None)
                if etype is None:
                    continue
                etype_str = etype.value if hasattr(etype, "value") else str(etype)
                if etype_str != RelationType.EXTENDS.value:
                    continue

                other = None
                if src in comp and tgt not in entity_ids:
                    other = tgt
                elif tgt in comp and src not in entity_ids:
                    other = src

                if other is not None:
                    other_node = None
                    for n in nodes:
                        if n.node_id == other:
                            other_node = n
                            break
                    if other_node is not None and getattr(other_node, "node_type", None) == "document":
                        doc_ids.add(other)

            sorted_doc_ids = sorted(doc_ids)
            component_relation_types = sorted(theme_edge_types)

            cid = _generate_id("theme", *sorted(entity_labels + list(comp)))

            metadata: dict[str, Any] = {
                "entity_count": len(comp),
                "document_count": len(sorted_doc_ids),
                "edge_count": sum(1 for e in edges if (
                    getattr(e, "source_id", "") in comp and
                    getattr(e, "target_id", "") in comp
                )),
            }

            theme = ThemeCluster(
                cluster_id=cid,
                theme_type=theme_type.value,
                label=label,
                entities=comp,
                documents=sorted_doc_ids,
                entity_cluster_ids=comp,
                entity_labels=labels,
                document_ids=sorted_doc_ids,
                relation_types=component_relation_types,
                evidence_count=0,
                confidence=confidence,
                metadata=metadata,
            )
            themes.append(theme)

        themes.sort(key=lambda t: (-(t.metadata.get("entity_count", 0) if t.metadata else 0), -t.confidence, t.label))

        return themes[:max_themes]


def detect_themes(
    graph: Any,
    max_themes: int = 20,
    min_cluster_size: int = 2,
) -> list[ThemeCluster]:
    """Convenience helper for theme detection.

    See :meth:`ThemeDetector.detect_themes`.
    """
    return ThemeDetector().detect_themes(
        graph=graph,
        max_themes=max_themes,
        min_cluster_size=min_cluster_size,
    )
