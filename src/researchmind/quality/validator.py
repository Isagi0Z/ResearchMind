"""Structural validator and derived-index builder for the SRO.

Validates cross-references between SRO components (chunks ↔ sections,
citations ↔ references, entities ↔ chunks, claims ↔ chunks/sections)
and populates derived index fields on chunks.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from researchmind.models.sro import StructuredResearchObject

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API — Validation
# ---------------------------------------------------------------------------


def validate_sro(
    sro: StructuredResearchObject,
) -> tuple[list[str], list[str]]:
    """Validate structural integrity of a Structured Research Object.

    Checks that all cross-references between SRO components are valid:
    every chunk points to an existing section, every citation points to
    existing chunks and optionally references, etc.

    Parameters
    ----------
    sro:
        The SRO to validate.

    Returns
    -------
    tuple[list[str], list[str]]
        A tuple of (errors, warnings). Errors represent broken references
        that should be fixed; warnings represent non-critical issues.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Build lookup sets
    section_ids: set[str] = {s.section_id for s in sro.body.sections}
    chunk_ids: set[str] = {c.chunk_id for c in sro.body.chunks}
    ref_ids: set[str] = {r.ref_id for r in sro.references}

    # --- Check every chunk.section_id exists in sections ---
    for chunk in sro.body.chunks:
        if chunk.section_id not in section_ids:
            errors.append(
                f"Chunk '{chunk.chunk_id}' references non-existent "
                f"section_id '{chunk.section_id}'"
            )

    # --- Check every citation.ref_id (when not null) exists in references ---
    for cit in sro.citations:
        if cit.ref_id is not None and cit.ref_id not in ref_ids:
            errors.append(
                f"Citation '{cit.citation_id}' references non-existent "
                f"ref_id '{cit.ref_id}'"
            )

    # --- Check every citation.chunk_id exists in chunks ---
    for cit in sro.citations:
        if cit.chunk_id not in chunk_ids:
            errors.append(
                f"Citation '{cit.citation_id}' references non-existent "
                f"chunk_id '{cit.chunk_id}'"
            )

    # --- Check every entity.chunk_id exists in chunks ---
    for ent in sro.entities:
        if ent.chunk_id not in chunk_ids:
            errors.append(
                f"Entity '{ent.entity_id}' references non-existent "
                f"chunk_id '{ent.chunk_id}'"
            )

    # --- Check every claim.chunk_id exists in chunks ---
    for claim in sro.candidate_claims:
        if claim.chunk_id not in chunk_ids:
            errors.append(
                f"Claim '{claim.claim_id}' references non-existent "
                f"chunk_id '{claim.chunk_id}'"
            )

    # --- Check every claim.section_id exists in sections ---
    for claim in sro.candidate_claims:
        if claim.section_id not in section_ids:
            errors.append(
                f"Claim '{claim.claim_id}' references non-existent "
                f"section_id '{claim.section_id}'"
            )

    # --- Check chunk.reading_order values are unique and contiguous 0..N ---
    reading_orders = [c.reading_order for c in sro.body.chunks]
    n_chunks = len(sro.body.chunks)

    if n_chunks > 0:
        # Check uniqueness
        if len(set(reading_orders)) != n_chunks:
            duplicates = [
                ro for ro in set(reading_orders)
                if reading_orders.count(ro) > 1
            ]
            errors.append(
                f"Duplicate reading_order values found: {sorted(duplicates)}"
            )

        # Check contiguity (0 .. N-1)
        expected = set(range(n_chunks))
        actual = set(reading_orders)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            parts: list[str] = []
            if missing:
                parts.append(f"missing={missing}")
            if extra:
                parts.append(f"extra={extra}")
            warnings.append(
                f"reading_order values are not contiguous 0..{n_chunks - 1}: "
                + ", ".join(parts)
            )

    # --- Check no empty chunk.text ---
    for chunk in sro.body.chunks:
        if not chunk.text.strip():
            errors.append(
                f"Chunk '{chunk.chunk_id}' has empty or whitespace-only text"
            )

    # --- Additional warnings ---

    # Warn if there are sections with no chunks
    sections_with_chunks: set[str] = {c.section_id for c in sro.body.chunks}
    for section in sro.body.sections:
        if section.section_id not in sections_with_chunks:
            warnings.append(
                f"Section '{section.section_id}' ('{section.original_header}') "
                f"has no associated chunks"
            )

    # Warn if citation section_id is inconsistent with chunk's section
    chunk_to_section: dict[str, str] = {
        c.chunk_id: c.section_id for c in sro.body.chunks
    }
    for cit in sro.citations:
        expected_section = chunk_to_section.get(cit.chunk_id)
        if expected_section and cit.section_id != expected_section:
            warnings.append(
                f"Citation '{cit.citation_id}' has section_id "
                f"'{cit.section_id}' but its chunk '{cit.chunk_id}' "
                f"belongs to section '{expected_section}'"
            )

    logger.info(
        "SRO validation complete: %d errors, %d warnings",
        len(errors),
        len(warnings),
    )

    return errors, warnings


# ---------------------------------------------------------------------------
# Public API — Derived indices
# ---------------------------------------------------------------------------


def compute_derived_indices(sro: StructuredResearchObject) -> None:
    """Populate derived index fields on chunks by cross-referencing entities and claims.

    Mutates the SRO in place:
    - Sets ``chunk.entity_ids`` for each chunk from matching entities.
    - Sets ``chunk.claim_ids`` for each chunk from matching claims.

    Parameters
    ----------
    sro:
        The SRO to mutate. Must have entities and candidate_claims
        already populated.
    """
    # Build entity_ids by chunk
    entity_ids_by_chunk: dict[str, list[str]] = defaultdict(list)
    for entity in sro.entities:
        entity_ids_by_chunk[entity.chunk_id].append(entity.entity_id)

    # Build claim_ids by chunk
    claim_ids_by_chunk: dict[str, list[str]] = defaultdict(list)
    for claim in sro.candidate_claims:
        claim_ids_by_chunk[claim.chunk_id].append(claim.claim_id)

    # Populate chunks
    chunks_updated = 0
    for chunk in sro.body.chunks:
        new_entity_ids = entity_ids_by_chunk.get(chunk.chunk_id, [])
        new_claim_ids = claim_ids_by_chunk.get(chunk.chunk_id, [])

        if new_entity_ids or new_claim_ids:
            chunk.entity_ids = new_entity_ids
            chunk.claim_ids = new_claim_ids
            chunks_updated += 1
        else:
            # Clear any stale data
            chunk.entity_ids = []
            chunk.claim_ids = []

    logger.info(
        "Derived indices computed: %d/%d chunks have entities or claims",
        chunks_updated,
        len(sro.body.chunks),
    )
