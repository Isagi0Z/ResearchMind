"""Confidence scorer computing per-field and overall quality for an SRO.

Implements the weighted multi-factor scoring formula defined in the
ResearchMind quality specification. Each field score is computed as a
weighted combination of sub-metrics, and the overall confidence is
a weighted sum of all field scores.
"""

from __future__ import annotations

import logging
import re

from researchmind.models.enums import CanonicalLabel, ExtractionRoute
from researchmind.models.sro import (
    SROExtractionCompleteness,
    SROFieldScores,
    SROQuality,
    StructuredResearchObject,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Weights for the overall confidence score
# ---------------------------------------------------------------------------
_OVERALL_WEIGHTS: dict[str, float] = {
    "title": 0.20,
    "authors": 0.15,
    "abstract": 0.15,
    "sections": 0.15,
    "references": 0.15,
    "citations": 0.10,
    "entities": 0.05,
    "claims": 0.05,
}

# Expected section ordering for ordering score calculation
_CANONICAL_ORDER: list[CanonicalLabel] = [
    CanonicalLabel.INTRODUCTION,
    CanonicalLabel.RELATED_WORK,
    CanonicalLabel.METHODOLOGY,
    CanonicalLabel.RESULTS,
    CanonicalLabel.DISCUSSION,
    CanonicalLabel.CONCLUSION,
    CanonicalLabel.LIMITATIONS,
    CanonicalLabel.FUTURE_WORK,
    CanonicalLabel.ACKNOWLEDGMENTS,
    CanonicalLabel.APPENDIX,
]

# Garbage character regex: control chars (except newline/tab), surrogate range
_GARBAGE_PATTERN = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ufffd\ufffe\uffff]"
)


def _has_garbage(text: str) -> bool:
    """Return True if text contains garbage/control characters."""
    return bool(_GARBAGE_PATTERN.search(text))


def _clamp(value: float) -> float:
    """Clamp a float to [0.0, 1.0]."""
    return max(0.0, min(1.0, value))


# ---------------------------------------------------------------------------
# Per-field scoring functions
# ---------------------------------------------------------------------------


def _score_title(sro: StructuredResearchObject) -> float:
    """Score the title field.

    Formula: 0.5*(grobid check) + 0.3*(length 5–30 words ok) + 0.2*(no garbage)
    """
    title = sro.header.title

    # Sub-metric 1: extraction source confidence (grobid vs fallback)
    grobid_score = 0.0
    route = sro.meta.extraction_route
    if route in (ExtractionRoute.GROBID_PRIMARY, ExtractionRoute.GROBID_WITH_FALLBACK):
        grobid_score = sro.header.title_confidence
    else:
        # OCR or hybrid — use the stored confidence but penalize slightly
        grobid_score = sro.header.title_confidence * 0.8

    # Sub-metric 2: word count in acceptable range
    word_count = len(title.split())
    if 5 <= word_count <= 30:
        length_score = 1.0
    elif word_count < 5:
        length_score = word_count / 5.0
    else:
        # Gradually penalize very long titles
        length_score = max(0.0, 1.0 - (word_count - 30) / 30.0)

    # Sub-metric 3: no garbage characters
    garbage_score = 0.0 if _has_garbage(title) else 1.0

    return _clamp(0.5 * grobid_score + 0.3 * length_score + 0.2 * garbage_score)


def _score_authors(sro: StructuredResearchObject) -> float:
    """Score the authors field.

    Formula: 0.4*(exists) + 0.3*(have surnames) + 0.3*(have affiliations)
    """
    authors = sro.header.authors

    # Sub-metric 1: any authors exist
    exists_score = 1.0 if authors else 0.0

    if not authors:
        return 0.0

    # Sub-metric 2: fraction of authors with surnames
    with_surname = sum(1 for a in authors if a.surname and a.surname.strip())
    surname_score = with_surname / len(authors)

    # Sub-metric 3: fraction of authors with at least one affiliation
    with_affiliation = sum(1 for a in authors if a.affiliations)
    affiliation_score = with_affiliation / len(authors)

    return _clamp(
        0.4 * exists_score + 0.3 * surname_score + 0.3 * affiliation_score
    )


def _score_abstract(sro: StructuredResearchObject) -> float:
    """Score the abstract field.

    Formula: 0.4*(exists) + 0.3*(word count 50–500) + 0.3*(no garbage)
    """
    abstract_text = sro.abstract.raw_text

    # Sub-metric 1: exists and non-empty
    exists_score = 1.0 if abstract_text.strip() else 0.0

    if not abstract_text.strip():
        return 0.0

    # Sub-metric 2: word count in acceptable range
    word_count = len(abstract_text.split())
    if 50 <= word_count <= 500:
        length_score = 1.0
    elif word_count < 50:
        length_score = word_count / 50.0
    else:
        length_score = max(0.0, 1.0 - (word_count - 500) / 500.0)

    # Sub-metric 3: no garbage characters
    garbage_score = 0.0 if _has_garbage(abstract_text) else 1.0

    return _clamp(
        0.4 * exists_score + 0.3 * length_score + 0.3 * garbage_score
    )


def _score_sections(sro: StructuredResearchObject) -> float:
    """Score the sections field.

    Formula: 0.5*(avg label confidence) + 0.3*(count>=4 ? 1 : count/4)
             + 0.2*(ordering score)
    """
    sections = sro.body.sections

    if not sections:
        return 0.0

    # Sub-metric 1: average label confidence
    avg_confidence = sum(s.label_confidence for s in sections) / len(sections)

    # Sub-metric 2: count adequacy
    count = len(sections)
    count_score = 1.0 if count >= 4 else count / 4.0

    # Sub-metric 3: ordering score — how well sections follow canonical order
    # Build a list of (position, canonical_order_index) and compute Kendall-tau-ish
    order_map = {label: idx for idx, label in enumerate(_CANONICAL_ORDER)}
    section_orders: list[int] = []
    for s in sections:
        if s.canonical_label in order_map:
            section_orders.append(order_map[s.canonical_label])

    if len(section_orders) <= 1:
        ordering_score = 1.0
    else:
        # Count concordant pairs
        concordant = 0
        total_pairs = 0
        for i in range(len(section_orders)):
            for j in range(i + 1, len(section_orders)):
                total_pairs += 1
                if section_orders[i] <= section_orders[j]:
                    concordant += 1
        ordering_score = concordant / total_pairs if total_pairs > 0 else 1.0

    return _clamp(
        0.5 * avg_confidence + 0.3 * count_score + 0.2 * ordering_score
    )


def _score_references(sro: StructuredResearchObject) -> float:
    """Score the references field.

    Formula: 0.5*(resolved/total) + 0.3*(field completeness) + 0.2*(count>5)
    """
    refs = sro.references

    if not refs:
        return 0.0

    total = len(refs)

    # Sub-metric 1: resolution ratio
    resolved = sum(1 for r in refs if r.resolution_status.value == "resolved")
    resolution_score = resolved / total

    # Sub-metric 2: field completeness — average fraction of optional fields filled
    completeness_scores: list[float] = []
    for r in refs:
        fields_present = 0
        fields_total = 5  # title, authors, year, venue, doi
        if r.title:
            fields_present += 1
        if r.authors:
            fields_present += 1
        if r.year:
            fields_present += 1
        if r.venue:
            fields_present += 1
        if r.doi:
            fields_present += 1
        completeness_scores.append(fields_present / fields_total)
    avg_completeness = (
        sum(completeness_scores) / len(completeness_scores)
        if completeness_scores
        else 0.0
    )

    # Sub-metric 3: adequate count
    count_score = 1.0 if total > 5 else total / 5.0

    return _clamp(
        0.5 * resolution_score + 0.3 * avg_completeness + 0.2 * count_score
    )


def _score_citations(sro: StructuredResearchObject) -> float:
    """Score the citations field.

    Formula: 0.6*(linked/total) + 0.4*(count>0)
    """
    citations = sro.citations

    if not citations:
        return 0.0

    total = len(citations)
    linked = sum(1 for c in citations if c.ref_id is not None)

    link_score = linked / total
    count_score = 1.0  # count > 0 is guaranteed here

    return _clamp(0.6 * link_score + 0.4 * count_score)


def _score_entities(sro: StructuredResearchObject) -> float:
    """Score the entities field.

    Formula: 0.5*(avg confidence) + 0.3*(count>10 ? 1 : count/10)
             + 0.2*(type diversity)
    """
    entities = sro.entities

    if not entities:
        return 0.0

    # Sub-metric 1: average confidence
    avg_confidence = sum(e.confidence for e in entities) / len(entities)

    # Sub-metric 2: count adequacy
    count = len(entities)
    count_score = 1.0 if count > 10 else count / 10.0

    # Sub-metric 3: type diversity — fraction of entity types represented
    from researchmind.models.enums import EntityLabel

    total_types = len(EntityLabel)
    unique_types = len({e.label for e in entities})
    diversity_score = unique_types / total_types

    return _clamp(
        0.5 * avg_confidence + 0.3 * count_score + 0.2 * diversity_score
    )


def _score_claims(sro: StructuredResearchObject) -> float:
    """Score the candidate claims field.

    Formula: 0.5*(avg confidence) + 0.3*(count>3) + 0.2*(section distribution)
    """
    claims = sro.candidate_claims

    if not claims:
        return 0.0

    # Sub-metric 1: average confidence
    avg_confidence = sum(c.confidence for c in claims) / len(claims)

    # Sub-metric 2: count adequacy
    count = len(claims)
    count_score = 1.0 if count > 3 else count / 3.0

    # Sub-metric 3: section distribution — fraction of body sections containing claims
    sections_with_claims = len({c.section_id for c in claims})
    total_sections = len(sro.body.sections) if sro.body.sections else 1
    distribution_score = min(1.0, sections_with_claims / max(1, total_sections))

    return _clamp(
        0.5 * avg_confidence + 0.3 * count_score + 0.2 * distribution_score
    )


# ---------------------------------------------------------------------------
# Extraction completeness
# ---------------------------------------------------------------------------


def _compute_extraction_completeness(
    sro: StructuredResearchObject,
) -> SROExtractionCompleteness:
    """Populate raw counts for extraction completeness."""
    total_pages = sro.meta.source_file.page_count

    # Count pages that have at least one chunk
    pages_with_text: set[int] = set()
    for chunk in sro.body.chunks:
        for page in range(chunk.page_start, chunk.page_end + 1):
            pages_with_text.add(page)

    refs_total = len(sro.references)
    refs_resolved = sum(
        1 for r in sro.references if r.resolution_status.value == "resolved"
    )

    citations_total = len(sro.citations)
    citations_linked = sum(1 for c in sro.citations if c.ref_id is not None)

    return SROExtractionCompleteness(
        total_pages=total_pages,
        pages_with_text_extracted=len(pages_with_text),
        sections_detected=len(sro.body.sections),
        references_total=refs_total,
        references_resolved=refs_resolved,
        citations_total=citations_total,
        citations_linked=citations_linked,
        chunks_total=len(sro.body.chunks),
        entities_total=len(sro.entities),
        claims_total=len(sro.candidate_claims),
    )


# ---------------------------------------------------------------------------
# Manual review triggers
# ---------------------------------------------------------------------------


def _check_manual_review(
    sro: StructuredResearchObject,
    field_scores: SROFieldScores,
    overall: float,
) -> tuple[bool, list[str]]:
    """Determine if the SRO requires manual review.

    Returns (requires_review, list_of_reasons).
    """
    reasons: list[str] = []

    if overall < 0.5:
        reasons.append(f"Overall confidence is low ({overall:.2f} < 0.50)")

    if field_scores.title < 0.4:
        reasons.append(
            f"Title confidence is very low ({field_scores.title:.2f} < 0.40)"
        )

    if field_scores.sections < 0.4:
        reasons.append(
            f"Sections confidence is very low ({field_scores.sections:.2f} < 0.40)"
        )

    # OCR with low confidence
    route = sro.meta.extraction_route
    if route in (ExtractionRoute.OCR_PRIMARY, ExtractionRoute.HYBRID):
        # Check average chunk extraction confidence
        chunks = sro.body.chunks
        if chunks:
            avg_chunk_conf = sum(c.extraction_confidence for c in chunks) / len(chunks)
            if avg_chunk_conf < 0.6:
                reasons.append(
                    f"OCR extraction with low average chunk confidence "
                    f"({avg_chunk_conf:.2f} < 0.60)"
                )

    # >30% citations unlinked
    if sro.citations:
        total_cit = len(sro.citations)
        unlinked = sum(1 for c in sro.citations if c.ref_id is None)
        unlinked_ratio = unlinked / total_cit
        if unlinked_ratio > 0.3:
            reasons.append(
                f"More than 30% of citations are unlinked "
                f"({unlinked}/{total_cit} = {unlinked_ratio:.0%})"
            )

    return bool(reasons), reasons


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_quality(sro: StructuredResearchObject) -> SROQuality:
    """Compute quality scores for a Structured Research Object.

    Calculates per-field confidence scores using multi-factor formulas,
    computes an overall weighted score, checks manual review triggers,
    and populates extraction completeness counts.

    Parameters
    ----------
    sro:
        The fully-populated SRO (with entities, claims, etc.).

    Returns
    -------
    SROQuality
        Updated quality object with all scores, completeness, and
        review triggers populated.
    """
    # Compute per-field scores
    field_scores = SROFieldScores(
        title=_score_title(sro),
        authors=_score_authors(sro),
        abstract=_score_abstract(sro),
        sections=_score_sections(sro),
        references=_score_references(sro),
        citations=_score_citations(sro),
        entities=_score_entities(sro),
        claims=_score_claims(sro),
    )

    # Compute overall weighted score
    overall = 0.0
    for field_name, weight in _OVERALL_WEIGHTS.items():
        score = getattr(field_scores, field_name, 0.0)
        overall += weight * score
    overall = _clamp(overall)

    # Check manual review triggers
    requires_review, review_reasons = _check_manual_review(
        sro, field_scores, overall
    )

    # Compute extraction completeness
    completeness = _compute_extraction_completeness(sro)

    # Preserve existing validation errors/warnings and pipeline log
    existing_quality = sro.quality
    quality = SROQuality(
        overall_confidence=overall,
        field_scores=field_scores,
        extraction_completeness=completeness,
        validation_errors=existing_quality.validation_errors,
        validation_warnings=existing_quality.validation_warnings,
        requires_manual_review=requires_review,
        manual_review_reasons=review_reasons,
        pipeline_log=existing_quality.pipeline_log,
        llm_calls=existing_quality.llm_calls,
    )

    logger.info(
        "Quality scoring complete: overall=%.3f, title=%.2f, authors=%.2f, "
        "abstract=%.2f, sections=%.2f, refs=%.2f, citations=%.2f, "
        "entities=%.2f, claims=%.2f, manual_review=%s",
        overall,
        field_scores.title,
        field_scores.authors,
        field_scores.abstract,
        field_scores.sections,
        field_scores.references,
        field_scores.citations,
        field_scores.entities,
        field_scores.claims,
        requires_review,
    )

    return quality
