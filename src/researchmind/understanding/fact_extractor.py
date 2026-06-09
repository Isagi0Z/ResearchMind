"""Deterministic fact extractor for the Understanding Engine pipeline stage.

Extracts high-level facts (method, dataset, metric, contribution, limitation,
future_work) from SRO objects using five strategies — no LLMs or embeddings.

Strategies
----------
1. Section-aware   — maps canonical section labels to fact types
2. Entity-aware    — maps entity labels (METHOD, DATASET, METRIC, TOOL)
3. Claim-aware     — maps claim types (METHODOLOGICAL, COMPARATIVE, …)
4. Pattern-based   — regex patterns for contribution/limitation/future_work
5. Reference-aware — reference title/raw_text keyword matching
"""

from __future__ import annotations

import logging
import re
from collections import Counter

from pydantic import BaseModel, Field, field_validator, model_validator

from researchmind.models.enums import CanonicalLabel, ClaimType, EntityLabel
from researchmind.models.sro import StructuredResearchObject

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FactType — no StrEnum import needed; uses Python 3.11+ natively
# ---------------------------------------------------------------------------

try:
    from enum import StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):
        pass


class FactType(StrEnum):
    METHOD = "method"
    DATASET = "dataset"
    METRIC = "metric"
    CONTRIBUTION = "contribution"
    LIMITATION = "limitation"
    FUTURE_WORK = "future_work"


# ---------------------------------------------------------------------------
# Priority & mapping tables
# ---------------------------------------------------------------------------

_FACT_PRIORITY: list[FactType] = [
    FactType.METHOD,
    FactType.DATASET,
    FactType.METRIC,
    FactType.CONTRIBUTION,
    FactType.LIMITATION,
    FactType.FUTURE_WORK,
]

_FACT_PRIORITY_INDEX: dict[FactType, int] = {
    ft: idx for idx, ft in enumerate(_FACT_PRIORITY)
}

_SECTION_TO_FACT: dict[CanonicalLabel, FactType] = {
    CanonicalLabel.METHODOLOGY: FactType.METHOD,
    CanonicalLabel.LIMITATIONS: FactType.LIMITATION,
    CanonicalLabel.FUTURE_WORK: FactType.FUTURE_WORK,
    CanonicalLabel.CONCLUSION: FactType.CONTRIBUTION,
}

_ENTITY_TO_FACT: dict[EntityLabel, FactType] = {
    EntityLabel.METHOD: FactType.METHOD,
    EntityLabel.DATASET: FactType.DATASET,
    EntityLabel.METRIC: FactType.METRIC,
    EntityLabel.TOOL: FactType.METHOD,
}

_CLAIM_TO_FACT: dict[ClaimType, FactType] = {
    ClaimType.METHODOLOGICAL: FactType.METHOD,
    ClaimType.COMPARATIVE: FactType.CONTRIBUTION,
    ClaimType.EXISTENCE: FactType.CONTRIBUTION,
    ClaimType.NEGATION: FactType.LIMITATION,
    ClaimType.STATISTICAL: FactType.METRIC,
}

_FACT_PATTERNS: dict[FactType, list[tuple[re.Pattern[str], str]]] = {
    FactType.CONTRIBUTION: [
        (re.compile(r"(?i)state[- ]of[- ]the[- ]art"), "state_of_art"),
        (re.compile(r"(?i)\boutperforms?\b"), "outperforms"),
        (re.compile(r"(?i)to\s+our\s+knowledge"), "to_our_knowledge"),
        (re.compile(
            r"(?i)novel\s+(?:approach|method|framework|architecture|contribution)"
        ), "novel_approach"),
        (re.compile(
            r"(?i)(?:first|first-ever)\s+(?:demonstrat|show|prove|achiev)"
        ), "first_demonstration"),
        (re.compile(r"(?i)significant\s+(?:improvement|advance|progress)"),
         "significant_advance"),
        (re.compile(r"(?i)(?:achieves?|achieved)\s+state"), "achieves_sota"),
    ],
    FactType.LIMITATION: [
        (re.compile(r"(?i)\blimitations?\b"), "limitation_keyword"),
        (re.compile(r"(?i)\bdrawback"), "drawback"),
        (re.compile(r"(?i)\bnot\s+suitable"), "not_suitable"),
        (re.compile(r"(?i)\bstruggles?\s+with"), "struggles"),
        (re.compile(r"(?i)\bfails?\s+(?:on|in|to|when)"), "fails"),
        (re.compile(r"(?i)\blimited\s+(?:by|to|in|due)"), "limited_by"),
        (re.compile(r"(?i)\bsuffers?\s+from"), "suffers_from"),
    ],
    FactType.FUTURE_WORK: [
        (re.compile(r"(?i)future\s+work"), "future_work"),
        (re.compile(r"(?i)future\s+research"), "future_research"),
        (re.compile(r"(?i)promising\s+direction"), "promising_direction"),
        (re.compile(r"(?i)we\s+plan\s+to"), "we_plan_to"),
        (re.compile(r"(?i)remains?\s+to\s+be"), "remains_to_be"),
        (re.compile(r"(?i)open\s+(?:question|problem|challenge)"), "open_question"),
    ],
}

_REFERENCE_PATTERNS: list[tuple[re.Pattern[str], FactType, str]] = [
    (re.compile(r"(?i)\b(dataset|corpus|benchmark)\b"),
     FactType.DATASET, "dataset_keyword"),
    (re.compile(
        r"(?i)\b(method|approach|algorithm|framework|model|architecture)\b"
    ), FactType.METHOD, "method_keyword"),
    (re.compile(r"(?i)\b(survey|review|overview)\b"),
     FactType.CONTRIBUTION, "survey_keyword"),
    (re.compile(r"(?i)\b(metric|measure|evaluation|score)\b"),
     FactType.METRIC, "metric_keyword"),
    (re.compile(r"(?i)\b(limitations?|drawback|challenges?)\b"),
     FactType.LIMITATION, "limitation_keyword"),
]

_MIN_CONFIDENCE: float = 0.3

_MAX_VALUE_LENGTH: int = 300
_MAX_EVIDENCE_LENGTH: int = 200


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ExtractedFact(BaseModel):
    """A single fact extracted from one of the five strategies."""

    fact_id: str
    fact_type: FactType
    value: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_type: str
    source_id: str
    section_id: str | None = None
    chunk_id: str | None = None
    context_sentence: str | None = None
    evidence_text: str | None = None
    matched_pattern: str | None = None

    @field_validator("source_type")
    @classmethod
    def _validate_source_type(cls, v: str) -> str:
        allowed = {"section", "entity", "claim", "pattern", "reference"}
        if v not in allowed:
            raise ValueError(f"source_type must be one of {allowed}")
        return v


class FactExtractionResult(BaseModel):
    """Container for all facts extracted from a single SRO."""

    facts: list[ExtractedFact]
    summary: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _compute_summary(self) -> "FactExtractionResult":
        self.summary = dict(Counter(f.fact_type.value for f in self.facts))
        return self

    def by_type(self, fact_type: FactType) -> list[ExtractedFact]:
        return [f for f in self.facts if f.fact_type == fact_type]

    def deduplicated(self) -> list[ExtractedFact]:
        """Return a deduplicated copy with priority resolution.

        1. Within (normalized_value, fact_type): keep highest confidence.
        2. Across types with same normalized_value:
           - same confidence → pick highest priority type
           - different confidences → keep all
        """
        if not self.facts:
            return []

        # --- Step 1: group by (normalized_value, fact_type) ---
        groups: dict[tuple[str, FactType], list[ExtractedFact]] = {}
        for fact in self.facts:
            key = (fact.value.strip().lower(), fact.fact_type)
            groups.setdefault(key, []).append(fact)

        # Within each group keep the highest confidence
        deduped: dict[tuple[str, FactType], ExtractedFact] = {}
        for key, group in groups.items():
            best = max(
                group,
                key=lambda f: (
                    f.confidence,
                    -_FACT_PRIORITY_INDEX.get(f.fact_type, 99),
                ),
            )
            deduped[key] = best

        # --- Step 2: cross-type resolution on same normalized value ---
        value_groups: dict[str, dict[FactType, ExtractedFact]] = {}
        for (norm_val, ft), fact in deduped.items():
            value_groups.setdefault(norm_val, {})[ft] = fact

        result: list[ExtractedFact] = []
        for norm_val, type_map in value_groups.items():
            if len(type_map) == 1:
                result.append(next(iter(type_map.values())))
                continue

            confs = {ft: f.confidence for ft, f in type_map.items()}
            if len(set(confs.values())) == 1:
                best_type = min(
                    type_map.keys(), key=lambda ft: _FACT_PRIORITY_INDEX[ft]
                )
                result.append(type_map[best_type])
            else:
                result.extend(type_map.values())

        # Re-number IDs
        for idx, fact in enumerate(result, start=1):
            fact.fact_id = f"fact_{idx:03d}"

        return sorted(result, key=lambda f: (f.fact_type.value, f.fact_id))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_sentence(text: str, char_pos: int) -> str | None:
    """Extract the sentence containing *char_pos*."""
    if not text or char_pos < 0 or char_pos >= len(text):
        return None
    start = char_pos
    while start > 0 and text[start - 1] not in ".!?\n":
        start -= 1
    end = char_pos
    while end < len(text) and text[end] not in ".!?\n":
        end += 1
    if end < len(text):
        end += 1
    sentence = text[start:end].strip()
    return sentence or None


# ---------------------------------------------------------------------------
# Strategy 1 — Section-aware
# ---------------------------------------------------------------------------


def _extract_section_facts(
    sro: StructuredResearchObject,
    counter: list[int],
) -> list[ExtractedFact]:
    """Map canonical section labels → facts."""
    facts: list[ExtractedFact] = []
    for section in sro.body.sections:
        fact_type = _SECTION_TO_FACT.get(section.canonical_label)
        if fact_type is None:
            continue
        if not section.content.strip():
            continue
        confidence = round(section.label_confidence * 0.6, 4)
        if confidence < _MIN_CONFIDENCE:
            continue
        counter[0] += 1
        facts.append(ExtractedFact(
            fact_id=f"fact_{counter[0]:03d}",
            fact_type=fact_type,
            value=section.content.strip()[:_MAX_VALUE_LENGTH],
            confidence=confidence,
            source_type="section",
            source_id=section.section_id,
            section_id=section.section_id,
            evidence_text=section.content[:_MAX_EVIDENCE_LENGTH],
            matched_pattern=section.canonical_label.value,
        ))
    return facts


# ---------------------------------------------------------------------------
# Strategy 2 — Entity-aware
# ---------------------------------------------------------------------------


def _extract_entity_facts(
    sro: StructuredResearchObject,
    counter: list[int],
) -> list[ExtractedFact]:
    """Map entity labels → facts."""
    facts: list[ExtractedFact] = []
    for entity in sro.entities:
        fact_type = _ENTITY_TO_FACT.get(entity.label)
        if fact_type is None:
            continue
        text = entity.text.strip()
        if not text:
            continue
        if entity.confidence < _MIN_CONFIDENCE:
            continue
        counter[0] += 1
        facts.append(ExtractedFact(
            fact_id=f"fact_{counter[0]:03d}",
            fact_type=fact_type,
            value=text,
            confidence=entity.confidence,
            source_type="entity",
            source_id=entity.entity_id,
            chunk_id=entity.chunk_id,
            context_sentence=entity.sentence,
            evidence_text=entity.sentence,
            matched_pattern=entity.source,
        ))
    return facts


# ---------------------------------------------------------------------------
# Strategy 3 — Claim-aware
# ---------------------------------------------------------------------------


def _extract_claim_facts(
    sro: StructuredResearchObject,
    counter: list[int],
) -> list[ExtractedFact]:
    """Map claim types → facts."""
    facts: list[ExtractedFact] = []
    for claim in sro.candidate_claims:
        fact_type = _CLAIM_TO_FACT.get(claim.claim_type)
        if fact_type is None:
            continue
        confidence = round(claim.confidence * 0.8, 4)
        if confidence < _MIN_CONFIDENCE:
            continue
        counter[0] += 1
        facts.append(ExtractedFact(
            fact_id=f"fact_{counter[0]:03d}",
            fact_type=fact_type,
            value=claim.sentence,
            confidence=confidence,
            source_type="claim",
            source_id=claim.claim_id,
            section_id=claim.section_id,
            chunk_id=claim.chunk_id,
            context_sentence=claim.sentence,
            evidence_text=claim.sentence,
            matched_pattern=claim.claim_type.value,
        ))
    return facts


# ---------------------------------------------------------------------------
# Strategy 4 — Pattern-based
# ---------------------------------------------------------------------------


def _extract_pattern_facts(
    sro: StructuredResearchObject,
    counter: list[int],
) -> list[ExtractedFact]:
    """Regex pattern matching on chunk text."""
    facts: list[ExtractedFact] = []
    for chunk in sro.body.chunks:
        text = chunk.text
        for fact_type, patterns in _FACT_PATTERNS.items():
            for pattern, pattern_name in patterns:
                for match in pattern.finditer(text):
                    sentence = _find_sentence(text, match.start())
                    if not sentence:
                        continue
                    counter[0] += 1
                    facts.append(ExtractedFact(
                        fact_id=f"fact_{counter[0]:03d}",
                        fact_type=fact_type,
                        value=sentence,
                        confidence=0.65,
                        source_type="pattern",
                        source_id=f"ptn_{counter[0]:03d}",
                        section_id=chunk.section_id,
                        chunk_id=chunk.chunk_id,
                        context_sentence=sentence,
                        evidence_text=sentence,
                        matched_pattern=pattern_name,
                    ))
    return facts


# ---------------------------------------------------------------------------
# Strategy 5 — Reference-aware
# ---------------------------------------------------------------------------


def _extract_reference_facts(
    sro: StructuredResearchObject,
    counter: list[int],
) -> list[ExtractedFact]:
    """Keyword matching on reference titles / raw text."""
    facts: list[ExtractedFact] = []
    for ref in sro.references:
        target_text = ref.title or ref.raw_text
        if not target_text or not target_text.strip():
            continue
        target_stripped = target_text.strip()
        for pattern, fact_type, pattern_name in _REFERENCE_PATTERNS:
            if pattern.search(target_stripped):
                counter[0] += 1
                facts.append(ExtractedFact(
                    fact_id=f"fact_{counter[0]:03d}",
                    fact_type=fact_type,
                    value=target_stripped[:_MAX_VALUE_LENGTH],
                    confidence=0.5,
                    source_type="reference",
                    source_id=ref.ref_id,
                    evidence_text=target_stripped[:_MAX_EVIDENCE_LENGTH],
                    matched_pattern=pattern_name,
                ))
    return facts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_facts(sro: StructuredResearchObject) -> FactExtractionResult:
    """Extract facts from a structured research object.

    Parameters
    ----------
    sro:
        The structured research object to extract facts from.

    Returns
    -------
    FactExtractionResult
        Container with all extracted facts and per-type summary counts.
    """
    if not sro.body.chunks:
        logger.info("No body chunks — returning empty fact extraction result")
        return FactExtractionResult(facts=[])

    counter: list[int] = [0]
    all_facts: list[ExtractedFact] = []

    section_facts = _extract_section_facts(sro, counter)
    all_facts.extend(section_facts)
    logger.info("Section extraction: %d facts", len(section_facts))

    entity_facts = _extract_entity_facts(sro, counter)
    all_facts.extend(entity_facts)
    logger.info("Entity extraction: %d facts", len(entity_facts))

    claim_facts = _extract_claim_facts(sro, counter)
    all_facts.extend(claim_facts)
    logger.info("Claim extraction: %d facts", len(claim_facts))

    pattern_facts = _extract_pattern_facts(sro, counter)
    all_facts.extend(pattern_facts)
    logger.info("Pattern extraction: %d facts", len(pattern_facts))

    reference_facts = _extract_reference_facts(sro, counter)
    all_facts.extend(reference_facts)
    logger.info("Reference extraction: %d facts", len(reference_facts))

    logger.info(
        "Fact extraction complete: %d raw facts", len(all_facts)
    )

    return FactExtractionResult(facts=all_facts)
