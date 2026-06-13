"""Deterministic query parser using regex pattern cascading and entity index matching.

Classifies raw research questions into the M5 query taxonomy, extracts entities
via corpus index matching, and pulls constraints (year, confidence) from text —
all without NLP models, embeddings, or external APIs.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any

from researchmind.query.models import (
    ParsedQuery,
    QueryConstraint,
    QueryEntity,
    QueryType,
)

# ---------------------------------------------------------------------------
# Detection rules — priority-ordered cascade (highest priority first)
# ---------------------------------------------------------------------------
# Each entry: (type_name, {patterns: list[str], min_entities: int})
# A rule matches when at least one pattern matches AND entity_count >= min_entities.

_DETECTION_RULES: list[tuple[str, dict]] = [
    ("CONTRADICTION", {
        "patterns": [
            r"contradict",
            r"disagree",
            r"conflict",
            r"inconsistent",
            r"opposing",
            r"different (?:results|findings|conclusions)",
            r"which papers (?:contradict|disagree with|refute)",
        ],
        "min_entities": 0,
    }),
    ("COMPARISON", {
        "patterns": [
            r"compare",
            r"difference between",
            r"better (?:than|worse)",
            r"vs\.?",
            r"versus",
            r"similarities",
            r"trade.?off",
            r"how does .* compare",
        ],
        "min_entities": 2,
    }),
    ("CONSENSUS", {
        "patterns": [
            r"consensus",
            r"agreement",
            r"do .* agree",
            r"what is the (?:general|prevailing|common) (?:view|opinion|wisdom)",
            r"broadly (?:accepted|supported)",
        ],
        "min_entities": 1,
    }),
    ("RESEARCH_GAP", {
        "patterns": [
            r"research gap",
            r"under.?explored",
            r"missing",
            r"what (?:is|are) (?:the )?(?:open|remaining|unsolved) (?:questions|problems|challenges)",
            r"lack of (?:research|studies|work)",
            r"what (?:has|have) not been (?:studied|explored|investigated)",
        ],
        "min_entities": 0,
    }),
    ("EXPLANATION", {
        "patterns": [
            r"explain",
            r"how does .* work",
            r"describe",
            r"what (?:is|are) the (?:mechanism|principle|idea|concept)",
            r"how (?:is|are|does|do)",
        ],
        "min_entities": 1,
    }),
    ("MULTI_HOP", {
        "patterns": [
            r"(?:path|chain|sequence|route|connection)(?: .*)? (?:between|from|to)\b",
            r"how (?:is|are) .* (?:connected|related|linked) (?:to|with)\b",
            r"find.*paths?",
            r"relationship between.*and",
        ],
        "min_entities": 2,
    }),
    ("FACTUAL", {
        "patterns": [
            r"what (?:is|are|was|were|does|do|did)",
            r"who (?:proposed|introduced|created|developed|invented)",
            r"which (?:dataset|method|model|metric|technique)",
            r"how many",
            r"list",
        ],
        "min_entities": 1,
    }),
    ("EXPLORATION", {
        "patterns": [
            r"(?:what|show|find|list|tell|display).*(?:connected|related|associated|linked|neighbor)",
            r"explore",
            r"neighbors? of",
            r"relationships? (?:involving|with|for)",
            r"everything (?:about|related|connected|associated)",
        ],
        "min_entities": 1,
    }),
]

_DETECTION_COMPILED: list[tuple[str, list[re.Pattern], int]] = [
    (name, [re.compile(p, re.IGNORECASE) for p in rule["patterns"]], rule["min_entities"])
    for name, rule in _DETECTION_RULES
]

# ---------------------------------------------------------------------------
# Constraint extraction patterns
# ---------------------------------------------------------------------------
# Each entry: (compiled_pattern, field, operator, value_callable)

_REFERENCE_YEAR = 2025
_RECENT_WINDOW_YEARS = 5

_CONSTRAINT_PATTERNS: list[tuple[re.Pattern, str, str, Any]] = [
    (re.compile(r"after\s+(\d{4})\b", re.IGNORECASE), "year", "gte", lambda m: int(m.group(1))),
    (re.compile(r"before\s+(\d{4})\b", re.IGNORECASE), "year", "lte", lambda m: int(m.group(1))),
    (re.compile(r"since\s+(\d{4})\b", re.IGNORECASE), "year", "gte", lambda m: int(m.group(1))),
    (re.compile(r"from\s+(\d{4})\b", re.IGNORECASE), "year", "gte", lambda m: int(m.group(1))),
    (re.compile(r"\bhigh confidence\b", re.IGNORECASE), "confidence", "gte", lambda _: 0.7),
    (re.compile(r"\brecent\b", re.IGNORECASE), "year", "gte", lambda _: _REFERENCE_YEAR - _RECENT_WINDOW_YEARS),
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ENTITY_TYPES = frozenset({"method", "dataset", "metric", "document", "concept", "unknown"})

_ENTITY_REQUIRED_TYPES = frozenset({
    "FACTUAL", "COMPARISON", "EXPLANATION",
    "CONSENSUS", "CONTRADICTION", "MULTI_HOP", "EXPLORATION",
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class QueryParser:
    """Deterministic query parser using regex pattern cascading and entity
    index matching.

    Usage::

        parser = QueryParser(corpus=my_corpus)
        parsed = parser.parse("What datasets does BERT use?")
        # parsed.query_type == "FACTUAL"
        # parsed.primary_entity.text == "BERT"

    When no corpus is available, entity extraction is skipped and type
    detection still works.
    """

    def __init__(self, corpus: Any | None = None):
        self._corpus = corpus

    def parse(self, raw_query: str) -> ParsedQuery:
        """Parse a raw query string into a fully classified ParsedQuery."""
        normalized = _normalize(raw_query)
        warnings: list[str] = []

        # Empty query guard
        if not normalized:
            warnings.append("Empty query")
            return ParsedQuery(
                raw_query=raw_query,
                query_type=QueryType.FACTUAL.name,
                parsing_warnings=warnings,
                entities_resolved=False,
            )

        # Entity extraction (Pass 1-3 + ambiguity)
        primary, secondary, ent_warnings = _extract_entities(normalized, self._corpus)
        warnings.extend(ent_warnings)

        entity_count = (1 if primary is not None else 0) + len(secondary)

        # Type detection via cascading rules
        query_type, type_warnings = _detect_type(normalized, entity_count)
        warnings.extend(type_warnings)

        # Constraint extraction
        constraints = _extract_constraints(normalized)

        # Entity resolution flag
        resolved = primary is not None
        if not resolved and query_type in _ENTITY_REQUIRED_TYPES:
            warnings.append(
                f"No entities resolved for {query_type} query "
                f"(requires at least 1 entity)"
            )

        return ParsedQuery(
            raw_query=raw_query,
            query_type=query_type,
            primary_entity=primary,
            secondary_entities=secondary,
            constraints=constraints,
            entities_resolved=resolved,
            parsing_warnings=warnings,
        )


def parse_query(raw_query: str, corpus: Any | None = None) -> ParsedQuery:
    """Parse a raw query string into a :class:`ParsedQuery`.

    Convenience wrapper around :class:`QueryParser`.
    """
    return QueryParser(corpus=corpus).parse(raw_query)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalize(raw_query: str) -> str:
    """Lowercase and collapse whitespace."""
    return " ".join(raw_query.lower().split())


def _detect_type(normalized: str, entity_count: int) -> tuple[str, list[str]]:
    """Detect query type by cascading priority-ordered rules.

    Returns (type_name, warnings).
    """
    warnings: list[str] = []

    for type_name, patterns, min_entities in _DETECTION_COMPILED:
        if entity_count < min_entities:
            continue
        for pattern in patterns:
            if pattern.search(normalized):
                return type_name, warnings

    # No rule matched — fallback
    if entity_count > 0:
        warnings.append(
            "Unknown query type; defaulted to EXPLORATION based on entities"
        )
        return QueryType.EXPLORATION.name, warnings

    warnings.append(
        "Unknown query type and no entities found; defaulted to FACTUAL"
    )
    return QueryType.FACTUAL.name, warnings


def _extract_constraints(normalized: str) -> list[QueryConstraint]:
    """Extract constraints from normalized query text."""
    constraints: list[QueryConstraint] = []
    seen: set[tuple[str, str, Any]] = set()

    for pattern, field, operator, value_fn in _CONSTRAINT_PATTERNS:
        for match in pattern.finditer(normalized):
            value = value_fn(match)
            key = (field, operator, value)
            if key not in seen:
                seen.add(key)
                constraints.append(
                    QueryConstraint(field=field, operator=operator, value=value)
                )

    return constraints


def _extract_entities(
    normalized: str,
    corpus: Any | None = None,
) -> tuple[QueryEntity | None, list[QueryEntity], list[str]]:
    """Extract entities using optional corpus index matching.

    Three passes:
      1. Document title matching
      2. Entity cluster label matching (longest label first)
      3. Entity type refinement from cluster metadata

    Returns (primary_entity, secondary_entities, warnings).
    """
    warnings: list[str] = []
    entities: list[QueryEntity] = []

    if corpus is None:
        return None, [], warnings

    # Pass 1: Document title matching
    doc_index = _build_doc_index(corpus)
    for title, (doc_id, label) in doc_index.items():
        if title.lower() in normalized:
            entities.append(QueryEntity(
                text=title,
                entity_type="document",
                cluster_id=doc_id,
                confidence=1.0,
            ))

    # Pass 2: Entity cluster label matching (longest labels first)
    cluster_index = _build_cluster_index(corpus)
    matched_labels: set[str] = set()

    for label, clusters in sorted(
        cluster_index.items(), key=lambda x: -len(x[0])
    ):
        label_lower = label.lower()
        if label_lower in normalized and label_lower not in matched_labels:
            matched_labels.add(label_lower)
            for cluster in clusters:
                cluster_id = (
                    getattr(cluster, "cluster_id", None)
                    or getattr(cluster, "id", None)
                )
                entities.append(QueryEntity(
                    text=label,
                    entity_type="concept",
                    cluster_id=cluster_id,
                    confidence=0.9,
                ))

    # Pass 3: Refine entity types from cluster metadata
    for ent in entities:
        if ent.cluster_id:
            cluster = _get_cluster(corpus, ent.cluster_id)
            if cluster is not None:
                canonical = getattr(cluster, "canonical_entity", None)
                if canonical is not None:
                    label_obj = getattr(canonical, "label", None)
                    if label_obj is not None:
                        type_val = (
                            label_obj.value
                            if hasattr(label_obj, "value")
                            else str(label_obj)
                        )
                        if type_val in _ENTITY_TYPES:
                            ent.entity_type = type_val

    # Ambiguity detection
    _detect_ambiguity(entities)

    primary: QueryEntity | None = entities[0] if entities else None
    secondary: list[QueryEntity] = entities[1:] if len(entities) > 1 else []

    return primary, secondary, warnings


def _build_doc_index(corpus: Any) -> dict[str, tuple[str, str]]:
    """Build ``{title: (doc_id, label)}`` index from corpus documents."""
    index: dict[str, tuple[str, str]] = {}
    docs = _get_documents(corpus)

    for doc in docs:
        title = (
            getattr(doc, "title", None)
            or getattr(doc, "raw_title", None)
        )
        doc_id = (
            getattr(doc, "doc_id", None)
            or getattr(doc, "ruo_id", None)
            or getattr(doc, "id", None)
        )
        label = getattr(doc, "label", None) or title or ""
        if title and doc_id:
            index[title] = (doc_id, label)

    return index


def _build_cluster_index(corpus: Any) -> dict[str, list[Any]]:
    """Build ``{label: [cluster, ...]}`` index from corpus clusters."""
    index: dict[str, list[Any]] = {}
    clusters = _get_clusters(corpus)

    for cluster in clusters:
        label = (
            getattr(cluster, "label", None)
            or getattr(cluster, "canonical_label", None)
        )
        if label:
            index.setdefault(label, []).append(cluster)

    return index


def _get_cluster(corpus: Any, cluster_id: str) -> Any | None:
    """Retrieve a cluster by ID from corpus."""
    if hasattr(corpus, "get_cluster"):
        try:
            return corpus.get_cluster(cluster_id)
        except Exception:
            return None

    for cluster in _get_clusters(corpus):
        cid = (
            getattr(cluster, "cluster_id", None)
            or getattr(cluster, "id", None)
        )
        if cid == cluster_id:
            return cluster

    return None


def _get_documents(corpus: Any) -> list[Any]:
    """Extract document list from corpus regardless of access pattern."""
    if hasattr(corpus, "get_documents"):
        try:
            return corpus.get_documents()
        except Exception:
            return []
    return list(getattr(corpus, "documents", []))


def _get_clusters(corpus: Any) -> list[Any]:
    """Extract cluster list from corpus regardless of access pattern."""
    if hasattr(corpus, "get_clusters"):
        try:
            return corpus.get_clusters()
        except Exception:
            return []
    return list(getattr(corpus, "clusters", []))


def _detect_ambiguity(entities: list[QueryEntity]) -> None:
    """Mark entities as ambiguous when multiple distinct IDs share the same text.

    Uses cluster_id as the unique identifier.
    """
    text_groups: dict[str, list[QueryEntity]] = defaultdict(list)
    for ent in entities:
        text_groups[ent.text.lower()].append(ent)

    for _key, group in text_groups.items():
        unique_ids = {e.cluster_id for e in group if e.cluster_id}
        if len(unique_ids) > 1:
            for ent in group:
                ent.is_ambiguous = True
                ent.alternatives = [
                    e.cluster_id for e in group if e.cluster_id != ent.cluster_id
                ]
