"""Deterministic semantic triple extractor.

Converts SRO entities, claims, and extracted facts into SemanticTriple
objects using five strategies — no LLMs, embeddings, or graph databases.

Strategies
----------
1. Entity-Entity      — pattern-based relation extraction from chunk text
2. Method → Dataset   — (method, evaluated_on, dataset) pairs
3. Method → Metric    — (method, achieves, metric) pairs
4. Method → Contrib   — (method, introduces, contribution) from facts
5. Claim-derived      — candidate claims mapped to predicate structures
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any

from pydantic import BaseModel, Field, model_validator

from researchmind.models.enums import CanonicalLabel, ClaimType, EntityLabel
from researchmind.models.ruo import SemanticTriple
from researchmind.models.sro import (
    SROEntity,
    StructuredResearchObject,
)
from researchmind.understanding.fact_extractor import (
    ExtractedFact,
    FactExtractionResult,
    FactType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Predicate vocabulary (closed set — no free-text predicates)
# ---------------------------------------------------------------------------

VALID_PREDICATES: set[str] = {
    "introduces",
    "uses",
    "evaluated_on",
    "outperforms",
    "improves",
    "replaces",
    "supports",
    "contradicts",
    "achieves",
    "contains",
    "depends_on",
}

# Raw verb / phrase → canonical predicate
_PREDICATE_NORM: dict[str, str] = {
    "outperforms": "outperforms",
    "outperform": "outperforms",
    "outperformed": "outperforms",
    "outperforming": "outperforms",
    "improves": "improves",
    "improve": "improves",
    "improved": "improves",
    "improving": "improves",
    "better than": "improves",
    "superior to": "improves",
    "uses": "uses",
    "use": "uses",
    "using": "uses",
    "used": "uses",
    "employs": "uses",
    "employs": "uses",
    "employed": "uses",
    "introduces": "introduces",
    "introduce": "introduces",
    "introduced": "introduces",
    "introducing": "introduces",
    "proposes": "introduces",
    "proposed": "introduces",
    "replaces": "replaces",
    "replace": "replaces",
    "replaced": "replaces",
    "replacing": "replaces",
    "supports": "supports",
    "support": "supports",
    "supported": "supports",
    "supporting": "supports",
    "contradicts": "contradicts",
    "contradict": "contradicts",
    "contradicted": "contradicts",
    "contradicting": "contradicts",
    "achieves": "achieves",
    "achieve": "achieves",
    "achieved": "achieves",
    "achieving": "achieves",
    "obtains": "achieves",
    "obtained": "achieves",
    "contains": "contains",
    "contain": "contains",
    "contained": "contains",
    "containing": "contains",
    "consists of": "contains",
    "includes": "contains",
    "included": "contains",
    "depends on": "depends_on",
    "depended on": "depends_on",
    "depending on": "depends_on",
    "relies on": "depends_on",
    "relied on": "depends_on",
    "based on": "depends_on",
    "evaluated on": "evaluated_on",
    "tested on": "evaluated_on",
    "applied to": "evaluated_on",
    "benchmarked on": "evaluated_on",
    "measured on": "evaluated_on",
}

# Sentence-level relation patterns: (regex, canonical_predicate)
_RELATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(
        r"(?i)(\w+(?:\s+\w+){0,4})\s+outperforms?\s+(\w+(?:\s+\w+){0,4})"
    ), "outperforms"),
    (re.compile(
        r"(?i)(\w+(?:\s+\w+){0,4})\s+improves?\s+(?:upon\s+)?(\w+(?:\s+\w+){0,4})"
    ), "improves"),
    (re.compile(
        r"(?i)(\w+(?:\s+\w+){0,4})\s+achieves?\s+(\w+(?:\s+\w+){0,4})"
    ), "achieves"),
    (re.compile(
        r"(?i)(\w+(?:\s+\w+){0,4})\s+uses?\s+(\w+(?:\s+\w+){0,4})"
    ), "uses"),
    (re.compile(
        r"(?i)(\w+(?:\s+\w+){0,4})\s+introduces?\s+(\w+(?:\s+\w+){0,4})"
    ), "introduces"),
    (re.compile(
        r"(?i)(\w+(?:\s+\w+){0,4})\s+based\s+on\s+(\w+(?:\s+\w+){0,4})"
    ), "depends_on"),
    (re.compile(
        r"(?i)(\w+(?:\s+\w+){0,4})\s+evaluated\s+on\s+(\w+(?:\s+\w+){0,4})"
    ), "evaluated_on"),
    (re.compile(
        r"(?i)(\w+(?:\s+\w+){0,4})\s+replaces?\s+(\w+(?:\s+\w+){0,4})"
    ), "replaces"),
    (re.compile(
        r"(?i)(\w+(?:\s+\w+){0,4})\s+supports?\s+(\w+(?:\s+\w+){0,4})"
    ), "supports"),
    (re.compile(
        r"(?i)(\w+(?:\s+\w+){0,4})\s+contradicts?\s+(\w+(?:\s+\w+){0,4})"
    ), "contradicts"),
    (re.compile(
        r"(?i)(\w+(?:\s+\w+){0,4})\s+contains?\s+(\w+(?:\s+\w+){0,4})"
    ), "contains"),
    (re.compile(
        r"(?i)(\w+(?:\s+\w+){0,4})\s+(?:is\s+)?better\s+than\s+(\w+(?:\s+\w+){0,4})"
    ), "improves"),
]

# Claim type → default predicate
_CLAIM_TO_PREDICATE: dict[ClaimType, str] = {
    ClaimType.METHODOLOGICAL: "introduces",
    ClaimType.COMPARATIVE: "outperforms",
    ClaimType.EXISTENCE: "supports",
    ClaimType.NEGATION: "contradicts",
    ClaimType.STATISTICAL: "achieves",
    ClaimType.CAUSAL: "depends_on",
}

# Max pairs to avoid combinatorial explosion
_MAX_PAIRS = 20

_MIN_CONFIDENCE = 0.3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize_predicate(raw: str) -> str:
    """Normalize a raw verb/phrase to the controlled predicate vocabulary.

    Returns the canonical predicate if recognised, or the input unchanged.
    """
    key = raw.strip().lower()
    return _PREDICATE_NORM.get(key, key)


def _match_entity(text: str, entities: list[SROEntity]) -> SROEntity | None:
    """Return the first entity whose text matches *text*.

    Priority:
    1. Exact equality (case-insensitive)
    2. Full single-token match
    3. Contiguous multi-token subsequence (avoids false substring
       matches like "bert" → "roberta" for single tokens).
    """
    text_lower = text.strip().lower()
    tokens = text_lower.split()
    for ent in entities:
        ent_lower = ent.text.strip().lower()
        if not ent_lower:
            continue
        if ent_lower == text_lower:
            return ent
        if ent_lower in tokens:
            return ent
        # Multi-token entity: check as contiguous phrase
        ent_tokens = ent_lower.split()
        if len(ent_tokens) > 1 and ent_lower in text_lower:
            return ent
    return None


def _find_entity_by_label(
    entities: list[SROEntity], label: EntityLabel,
) -> SROEntity | None:
    for ent in entities:
        if ent.label == label:
            return ent
    return None


def _entities_in_section(
    sro: StructuredResearchObject, section_id: str,
) -> list[SROEntity]:
    chunk_ids = {
        c.chunk_id for c in sro.body.chunks if c.section_id == section_id
    }
    return [e for e in sro.entities if e.chunk_id in chunk_ids]


# ---------------------------------------------------------------------------
# Strategy 1 — Entity-Entity from relation patterns
# ---------------------------------------------------------------------------


def _extract_entity_relation_triples(
    sro: StructuredResearchObject,
    entities_by_chunk: dict[str, list[SROEntity]],
    counter: list[int],
) -> list[SemanticTriple]:
    """Extract (entity_A, predicate, entity_B) from chunk text patterns."""
    triples: list[SemanticTriple] = []
    for chunk in sro.body.chunks:
        entities = entities_by_chunk.get(chunk.chunk_id, [])
        if len(entities) < 2:
            continue

        text = chunk.text
        for pattern, predicate in _RELATION_PATTERNS:
            for match in pattern.finditer(text):
                group_a, group_b = match.group(1), match.group(2)
                ent_a = _match_entity(group_a, entities)
                ent_b = _match_entity(group_b, entities)
                if ent_a is None or ent_b is None:
                    continue
                if ent_a.entity_id == ent_b.entity_id:
                    continue

                confidence = round(
                    min(ent_a.confidence, ent_b.confidence) * 0.85, 4
                )
                if confidence < _MIN_CONFIDENCE:
                    continue

                counter[0] += 1
                triples.append(SemanticTriple(
                    triple_id=f"triple_{counter[0]:03d}",
                    subject_id=ent_a.entity_id,
                    subject_text=ent_a.text,
                    predicate=predicate,
                    object_id=ent_b.entity_id,
                    object_text=ent_b.text,
                    confidence=confidence,
                    chunk_id=chunk.chunk_id,
                    evidence_ids=["_".join([ent_a.entity_id, ent_b.entity_id])],
                ))
    return triples


# ---------------------------------------------------------------------------
# Strategy 2 — Method → Dataset
# ---------------------------------------------------------------------------


def _extract_method_dataset_triples(
    sro: StructuredResearchObject,
    entities_by_chunk: dict[str, list[SROEntity]],
    entities_by_label: dict[EntityLabel, list[SROEntity]],
    counter: list[int],
) -> list[SemanticTriple]:
    """Extract (method, evaluated_on, dataset) pairs."""
    triples: list[SemanticTriple] = []

    methods = entities_by_label.get(EntityLabel.METHOD, [])
    datasets = entities_by_label.get(EntityLabel.DATASET, [])
    if not methods or not datasets:
        return triples

    pairs: list[tuple[SROEntity, SROEntity]] = []
    # Same-chunk pairs first
    for chunk_id, chunk_entities in entities_by_chunk.items():
        chunk_methods = [e for e in chunk_entities if e.label == EntityLabel.METHOD]
        chunk_datasets = [e for e in chunk_entities if e.label == EntityLabel.DATASET]
        for m in chunk_methods:
            for d in chunk_datasets:
                pairs.append((m, d))

    # Cross-chunk pairs (only if we haven't reached the limit)
    if len(pairs) < _MAX_PAIRS:
        for m in methods:
            for d in datasets:
                pair_key = (m.entity_id, d.entity_id)
                if pair_key not in {(p[0].entity_id, p[1].entity_id) for p in pairs}:
                    pairs.append((m, d))
                    if len(pairs) >= _MAX_PAIRS:
                        break
            if len(pairs) >= _MAX_PAIRS:
                break

    for method, dataset in pairs:
        same_chunk = method.chunk_id == dataset.chunk_id
        confidence = round(
            min(method.confidence, dataset.confidence) * (0.90 if same_chunk else 0.70),
            4,
        )
        if confidence < _MIN_CONFIDENCE:
            continue

        chunk_id = method.chunk_id or dataset.chunk_id or ""
        counter[0] += 1
        triples.append(SemanticTriple(
            triple_id=f"triple_{counter[0]:03d}",
            subject_id=method.entity_id,
            subject_text=method.text,
            predicate="evaluated_on",
            object_id=dataset.entity_id,
            object_text=dataset.text,
            confidence=confidence,
            chunk_id=chunk_id,
            evidence_ids=[method.entity_id, dataset.entity_id],
        ))

    return triples


# ---------------------------------------------------------------------------
# Strategy 3 — Method → Metric
# ---------------------------------------------------------------------------


def _extract_method_metric_triples(
    sro: StructuredResearchObject,
    entities_by_chunk: dict[str, list[SROEntity]],
    entities_by_label: dict[EntityLabel, list[SROEntity]],
    counter: list[int],
) -> list[SemanticTriple]:
    """Extract (method, achieves, metric) pairs."""
    triples: list[SemanticTriple] = []

    methods = entities_by_label.get(EntityLabel.METHOD, [])
    metrics = entities_by_label.get(EntityLabel.METRIC, [])
    if not methods or not metrics:
        return triples

    pairs: list[tuple[SROEntity, SROEntity]] = []
    for chunk_id, chunk_entities in entities_by_chunk.items():
        chunk_methods = [e for e in chunk_entities if e.label == EntityLabel.METHOD]
        chunk_metrics = [e for e in chunk_entities if e.label == EntityLabel.METRIC]
        for m in chunk_methods:
            for met in chunk_metrics:
                pairs.append((m, met))

    if len(pairs) < _MAX_PAIRS:
        for m in methods:
            for met in metrics:
                pair_key = (m.entity_id, met.entity_id)
                if pair_key not in {(p[0].entity_id, p[1].entity_id) for p in pairs}:
                    pairs.append((m, met))
                    if len(pairs) >= _MAX_PAIRS:
                        break
            if len(pairs) >= _MAX_PAIRS:
                break

    for method, metric in pairs:
        same_chunk = method.chunk_id == metric.chunk_id
        confidence = round(
            min(method.confidence, metric.confidence) * (0.85 if same_chunk else 0.65),
            4,
        )
        if confidence < _MIN_CONFIDENCE:
            continue

        chunk_id = method.chunk_id or metric.chunk_id or ""
        counter[0] += 1
        triples.append(SemanticTriple(
            triple_id=f"triple_{counter[0]:03d}",
            subject_id=method.entity_id,
            subject_text=method.text,
            predicate="achieves",
            object_id=metric.entity_id,
            object_text=metric.text,
            confidence=confidence,
            chunk_id=chunk_id,
            evidence_ids=[method.entity_id, metric.entity_id],
        ))

    return triples


# ---------------------------------------------------------------------------
# Strategy 4 — Method → Contribution (from ExtractedFact)
# ---------------------------------------------------------------------------


def _extract_method_contribution_triples(
    sro: StructuredResearchObject,
    fact_result: FactExtractionResult,
    entities_by_chunk: dict[str, list[SROEntity]],
    entities_by_label: dict[EntityLabel, list[SROEntity]],
    counter: list[int],
) -> list[SemanticTriple]:
    """Extract (method, introduces, contribution) from facts."""
    triples: list[SemanticTriple] = []
    all_methods = entities_by_label.get(EntityLabel.METHOD, [])

    for fact in fact_result.facts:
        if fact.fact_type != FactType.CONTRIBUTION:
            continue

        # Find a method entity in the same context
        method: SROEntity | None = None
        chunk_methods: list[SROEntity] = []
        if fact.chunk_id and fact.chunk_id in entities_by_chunk:
            chunk_methods = [
                e for e in entities_by_chunk[fact.chunk_id]
                if e.label == EntityLabel.METHOD
            ]
        if chunk_methods:
            method = chunk_methods[0]
        elif fact.section_id:
            sec_methods = [
                e for e in all_methods
                if any(
                    c.section_id == fact.section_id and e.chunk_id == c.chunk_id
                    for c in sro.body.chunks
                )
            ]
            method = sec_methods[0] if sec_methods else None

        if method:
            subject_id = method.entity_id
            subject_text = method.text
            base_conf = method.confidence
            chunk_id = method.chunk_id or fact.chunk_id or ""
        else:
            subject_id = f"sub_{counter[0] + 1:03d}"
            subject_text = sro.header.title
            base_conf = 0.60
            chunk_id = fact.chunk_id or fact.section_id or ""

        confidence = round(base_conf * 0.75, 4)
        if confidence < _MIN_CONFIDENCE:
            continue

        counter[0] += 1
        obj_id = f"obj_{counter[0]:03d}"
        triples.append(SemanticTriple(
            triple_id=f"triple_{counter[0]:03d}",
            subject_id=subject_id,
            subject_text=subject_text,
            predicate="introduces",
            object_id=obj_id,
            object_text=fact.value[:120],
            confidence=confidence,
            chunk_id=chunk_id,
            evidence_ids=[fact.fact_id],
        ))

    return triples


# ---------------------------------------------------------------------------
# Strategy 5 — Claim-derived triples
# ---------------------------------------------------------------------------


def _extract_claim_derived_triples(
    sro: StructuredResearchObject,
    entities_by_chunk: dict[str, list[SROEntity]],
    counter: list[int],
) -> list[SemanticTriple]:
    """Convert candidate claims into predicate structures."""
    triples: list[SemanticTriple] = []
    for claim in sro.candidate_claims:
        predicate = _CLAIM_TO_PREDICATE.get(claim.claim_type)
        if predicate is None:
            continue

        # Find a method entity in the same chunk as subject
        method: SROEntity | None = None
        chunk_entities = entities_by_chunk.get(claim.chunk_id, [])
        method = _find_entity_by_label(chunk_entities, EntityLabel.METHOD)

        if method:
            subject_id = method.entity_id
            subject_text = method.text
            base_conf = method.confidence
            chunk_id = method.chunk_id or claim.chunk_id
        else:
            subject_id = f"sub_{counter[0] + 1:03d}"
            subject_text = sro.header.title
            base_conf = 0.60
            chunk_id = claim.chunk_id

        is_negated = claim.claim_type == ClaimType.NEGATION

        counter[0] += 1
        obj_id = f"clm_{counter[0]:03d}"
        confidence = round(claim.confidence * 0.80, 4)
        if confidence < _MIN_CONFIDENCE:
            continue

        triples.append(SemanticTriple(
            triple_id=f"triple_{counter[0]:03d}",
            subject_id=subject_id,
            subject_text=subject_text,
            predicate=predicate,
            object_id=obj_id,
            object_text=claim.sentence[:150],
            is_negated=is_negated,
            confidence=confidence,
            chunk_id=chunk_id,
            evidence_ids=[claim.claim_id],
        ))

    return triples


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def _deduplicate_triples(
    triples: list[SemanticTriple],
) -> list[SemanticTriple]:
    """Remove duplicates by (subject_id, predicate, object_id).

    Keeps the triple with highest confidence; merges evidence_ids.
    """
    groups: dict[tuple[str, str, str], list[SemanticTriple]] = {}
    for t in triples:
        key = (t.subject_id, t.predicate, t.object_id)
        groups.setdefault(key, []).append(t)

    result: list[SemanticTriple] = []
    for key, group in groups.items():
        best = max(group, key=lambda t: t.confidence)
        merged_evidence = list({
            eid for t in group for eid in t.evidence_ids
        })
        result.append(best.model_copy(update={"evidence_ids": merged_evidence}))

    # Re-number
    for idx, t in enumerate(result, start=1):
        t.triple_id = f"triple_{idx:03d}"

    return sorted(result, key=lambda t: (t.predicate, t.triple_id))


# ---------------------------------------------------------------------------
# Output model & public API
# ---------------------------------------------------------------------------


class TripleExtractionResult(BaseModel):
    """Container for all semantic triples extracted from an SRO."""

    triples: list[SemanticTriple]
    statistics: dict[str, int] = Field(default_factory=dict)
    confidence_metrics: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _compute_metrics(self) -> "TripleExtractionResult":
        if not self.triples:
            self.statistics = {"total": 0}
            self.confidence_metrics = {"mean": 0.0, "min": 0.0, "max": 0.0}
            return self
        confs = [t.confidence for t in self.triples]
        self.statistics = {"total": len(self.triples)}
        self.confidence_metrics = {
            "mean": round(sum(confs) / len(confs), 4),
            "min": round(min(confs), 4),
            "max": round(max(confs), 4),
        }
        return self

    def predicate_distribution(self) -> dict[str, int]:
        return dict(Counter(t.predicate for t in self.triples))

    def by_predicate(self, predicate: str) -> list[SemanticTriple]:
        return [t for t in self.triples if t.predicate == predicate]

    def deduplicated(self) -> list[SemanticTriple]:
        return _deduplicate_triples(self.triples)


def _build_entities_by_chunk(
    sro: StructuredResearchObject,
) -> dict[str, list[SROEntity]]:
    lookup: dict[str, list[SROEntity]] = {}
    for ent in sro.entities:
        lookup.setdefault(ent.chunk_id, []).append(ent)
    return lookup


def _build_entities_by_label(
    sro: StructuredResearchObject,
) -> dict[EntityLabel, list[SROEntity]]:
    lookup: dict[EntityLabel, list[SROEntity]] = {}
    for ent in sro.entities:
        lookup.setdefault(ent.label, []).append(ent)
    return lookup


def extract_triples(
    sro: StructuredResearchObject,
    fact_result: FactExtractionResult | None = None,
) -> TripleExtractionResult:
    """Extract semantic triples from an SRO (and optional facts).

    Parameters
    ----------
    sro:
        The structured research object.
    fact_result:
        Optional pre-extracted facts. If ``None``, facts are computed from
        the fact extractor internally.

    Returns
    -------
    TripleExtractionResult
        Container with all triples, statistics, and confidence metrics.
    """
    from researchmind.understanding.fact_extractor import extract_facts

    if fact_result is None:
        fact_result = extract_facts(sro)

    if not sro.entities and not sro.candidate_claims and not fact_result.facts:
        logger.info("No entities, claims, or facts — returning empty result")
        return TripleExtractionResult(triples=[])

    entities_by_chunk = _build_entities_by_chunk(sro)
    entities_by_label = _build_entities_by_label(sro)
    counter: list[int] = [0]
    all_triples: list[SemanticTriple] = []

    # Strategy 1
    s1 = _extract_entity_relation_triples(sro, entities_by_chunk, counter)
    all_triples.extend(s1)
    logger.info("Strategy 1 (entity-relation): %d triples", len(s1))

    # Strategy 2
    s2 = _extract_method_dataset_triples(
        sro, entities_by_chunk, entities_by_label, counter,
    )
    all_triples.extend(s2)
    logger.info("Strategy 2 (method-dataset): %d triples", len(s2))

    # Strategy 3
    s3 = _extract_method_metric_triples(
        sro, entities_by_chunk, entities_by_label, counter,
    )
    all_triples.extend(s3)
    logger.info("Strategy 3 (method-metric): %d triples", len(s3))

    # Strategy 4
    s4 = _extract_method_contribution_triples(
        sro, fact_result, entities_by_chunk, entities_by_label, counter,
    )
    all_triples.extend(s4)
    logger.info("Strategy 4 (method-contribution): %d triples", len(s4))

    # Strategy 5
    s5 = _extract_claim_derived_triples(sro, entities_by_chunk, counter)
    all_triples.extend(s5)
    logger.info("Strategy 5 (claim-derived): %d triples", len(s5))

    # Deduplicate
    deduped = _deduplicate_triples(all_triples)
    logger.info(
        "Triple extraction complete: %d raw → %d unique",
        len(all_triples),
        len(deduped),
    )

    return TripleExtractionResult(triples=deduped)
