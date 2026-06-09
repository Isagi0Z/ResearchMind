"""Table and figure extractor — transforms raw tables/figures into SRO models.

Assigns identifiers, maps each table/figure to the nearest section by page
proximity, and computes extraction confidence for tables.
"""

from __future__ import annotations

import logging

from researchmind.models.intermediates import RawFigure, RawTable
from researchmind.models.sro import SROFigure, SROSection, SROTable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Section-mapping helpers
# ---------------------------------------------------------------------------


def _find_nearest_section(
    page: int,
    sections: list[SROSection],
) -> SROSection | None:
    """Find the section whose page range is nearest to the given page.

    Preference order:
    1. Sections that *contain* the page (page_start ≤ page ≤ page_end).
    2. Sections closest to the page by absolute distance.
    """
    if not sections:
        return None

    # First pass: find sections that contain the page
    containing = [
        s for s in sections
        if s.page_start <= page <= s.page_end
    ]
    if containing:
        # Prefer the last one by position (deeper in the paper)
        return max(containing, key=lambda s: s.position)

    # Second pass: nearest by distance
    def distance(s: SROSection) -> int:
        if page < s.page_start:
            return s.page_start - page
        return page - s.page_end

    return min(sections, key=distance)


# ---------------------------------------------------------------------------
# Table confidence
# ---------------------------------------------------------------------------


def _compute_table_confidence(raw: RawTable) -> float:
    """Compute extraction confidence for a table based on available data.

    Scoring:
    - caption non-empty: +0.30
    - raw_content non-empty: +0.40
    - raw_content has multiple rows (contains pipe/newline): +0.15
    - grobid_id present: +0.15
    """
    score = 0.0

    if raw.caption and raw.caption.strip():
        score += 0.30

    if raw.raw_content and raw.raw_content.strip():
        score += 0.40
        # Check for multi-row content (pipe separators or multiple lines)
        content = raw.raw_content.strip()
        if "|" in content or content.count("\n") >= 1:
            score += 0.15

    if raw.grobid_id:
        score += 0.15

    return round(min(score, 1.0), 4)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def process_tables(
    raw_tables: list[RawTable],
    sections: list[SROSection],
) -> list[SROTable]:
    """Transform raw tables into SROTable objects.

    Parameters
    ----------
    raw_tables:
        Tables extracted from the PDF.
    sections:
        Normalised sections (used for page-proximity mapping).

    Returns
    -------
    list[SROTable]
        Structured table objects with IDs and section assignments.
    """
    if not raw_tables:
        logger.debug("No raw tables to process")
        return []

    results: list[SROTable] = []

    for idx, raw in enumerate(raw_tables):
        table_id = f"tbl_{idx + 1:03d}"

        # Find nearest section
        nearest = _find_nearest_section(raw.page, sections)
        section_id = nearest.section_id if nearest else "sec-fallback-0"

        confidence = _compute_table_confidence(raw)
        caption = raw.caption if raw.caption else f"Table {idx + 1}"

        try:
            sro_table = SROTable(
                table_id=table_id,
                caption=caption,
                section_id=section_id,
                page=raw.page,
                extraction_confidence=confidence,
                raw_content=raw.raw_content,
            )
            results.append(sro_table)
        except Exception:
            logger.exception(
                "Failed to create SROTable for index %d (caption='%s')",
                idx, caption[:60],
            )

    logger.info("Processed %d/%d tables", len(results), len(raw_tables))
    return results


def process_figures(
    raw_figures: list[RawFigure],
    sections: list[SROSection],
) -> list[SROFigure]:
    """Transform raw figures into SROFigure objects.

    Parameters
    ----------
    raw_figures:
        Figures extracted from the PDF.
    sections:
        Normalised sections (used for page-proximity mapping).

    Returns
    -------
    list[SROFigure]
        Structured figure objects with IDs and section assignments.
    """
    if not raw_figures:
        logger.debug("No raw figures to process")
        return []

    results: list[SROFigure] = []

    for idx, raw in enumerate(raw_figures):
        figure_id = f"fig_{idx + 1:03d}"

        # Find nearest section
        nearest = _find_nearest_section(raw.page, sections)
        section_id = nearest.section_id if nearest else "sec-fallback-0"

        caption = raw.caption if raw.caption else f"Figure {idx + 1}"

        try:
            sro_figure = SROFigure(
                figure_id=figure_id,
                caption=caption,
                section_id=section_id,
                page=raw.page,
                image_path=raw.image_path,
            )
            results.append(sro_figure)
        except Exception:
            logger.exception(
                "Failed to create SROFigure for index %d (caption='%s')",
                idx, caption[:60],
            )

    logger.info("Processed %d/%d figures", len(results), len(raw_figures))
    return results
