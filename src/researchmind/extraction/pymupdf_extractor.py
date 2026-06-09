"""PyMuPDF-based text extraction with column-aware reading order.

This module serves as the **fallback** extractor when GROBID is unavailable or
produces low-quality output.  It uses PyMuPDF (fitz) to extract text blocks
with bounding boxes and font metadata, detects multi-column layouts, sorts
blocks in reading order, and groups paragraphs under detected section headers.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import NamedTuple

import fitz  # PyMuPDF

from researchmind.models.enums import ExtractionMethod
from researchmind.models.intermediates import RawSection

logger = logging.getLogger(__name__)

# Minimum number of characters in a text block to be considered non-trivial.
_MIN_BLOCK_CHARS = 3

# If a font size exceeds body_avg × this multiplier, treat it as a heading.
_HEADING_FONT_SIZE_RATIO = 1.2

# Minimum number of blocks needed to attempt column detection.
_MIN_BLOCKS_FOR_COLUMNS = 4


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


class _TextBlock(NamedTuple):
    """A single text block extracted from a page."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    font_size: float
    font_name: str
    page_num: int  # 0-indexed

    @property
    def x_mid(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def width(self) -> float:
        return self.x1 - self.x0


# ---------------------------------------------------------------------------
# Column detection — simple k-means (k=1 vs k=2)
# ---------------------------------------------------------------------------


def _kmeans_1d(values: list[float], k: int, max_iter: int = 50) -> list[float]:
    """Run 1-D k-means and return cluster centres.

    Parameters
    ----------
    values:
        The 1-D data points.
    k:
        Number of clusters (1 or 2 for our use-case).
    max_iter:
        Maximum iterations.

    Returns
    -------
    list[float]
        Sorted cluster centres.
    """
    if not values or k < 1:
        return []
    if k == 1:
        return [sum(values) / len(values)]

    # Initialise centres at min and max
    centres = [min(values), max(values)]
    if centres[0] == centres[1]:
        return [centres[0]]

    for _ in range(max_iter):
        # Assign each value to nearest centre
        clusters: dict[int, list[float]] = {i: [] for i in range(k)}
        for v in values:
            dists = [abs(v - c) for c in centres]
            nearest = dists.index(min(dists))
            clusters[nearest].append(v)

        # Recompute centres
        new_centres: list[float] = []
        for i in range(k):
            if clusters[i]:
                new_centres.append(sum(clusters[i]) / len(clusters[i]))
            else:
                new_centres.append(centres[i])

        if all(abs(a - b) < 1.0 for a, b in zip(centres, new_centres)):
            break
        centres = new_centres

    return sorted(centres)


def _compute_inertia(values: list[float], centres: list[float]) -> float:
    """Sum of squared distances from each value to its nearest centre."""
    total = 0.0
    for v in values:
        min_dist = min(abs(v - c) for c in centres)
        total += min_dist * min_dist
    return total


def _detect_columns(blocks: list[_TextBlock], page_width: float) -> int:
    """Detect whether the page has 1 or 2 columns.

    Uses the ratio of k=2 inertia to k=1 inertia.  If k=2 reduces inertia
    significantly (< 40 % of k=1) *and* the two centres are well separated,
    we declare 2 columns.

    Returns
    -------
    int
        1 or 2.
    """
    if len(blocks) < _MIN_BLOCKS_FOR_COLUMNS:
        return 1

    x_mids = [b.x_mid for b in blocks]

    centres_1 = _kmeans_1d(x_mids, k=1)
    centres_2 = _kmeans_1d(x_mids, k=2)

    if len(centres_2) < 2:
        return 1

    inertia_1 = _compute_inertia(x_mids, centres_1)
    inertia_2 = _compute_inertia(x_mids, centres_2)

    # Avoid division by zero
    if inertia_1 < 1e-6:
        return 1

    ratio = inertia_2 / inertia_1

    # Also require the two centres to be separated by at least 20 % of page width
    sep = abs(centres_2[1] - centres_2[0])
    well_separated = sep > page_width * 0.20

    if ratio < 0.40 and well_separated:
        logger.debug(
            "Detected 2-column layout: centres=[%.0f, %.0f], "
            "inertia_ratio=%.3f, sep=%.0f",
            centres_2[0],
            centres_2[1],
            ratio,
            sep,
        )
        return 2

    return 1


def _sort_blocks_reading_order(
    blocks: list[_TextBlock], num_columns: int, page_width: float
) -> list[_TextBlock]:
    """Sort blocks in reading order, accounting for column layout.

    For single-column: sort top-to-bottom.
    For two-column: split into left/right by page midpoint, sort each column
    top-to-bottom, then concatenate left before right.
    """
    if not blocks:
        return []

    if num_columns == 1:
        return sorted(blocks, key=lambda b: (b.y0, b.x0))

    mid_x = page_width / 2.0
    left = [b for b in blocks if b.x_mid < mid_x]
    right = [b for b in blocks if b.x_mid >= mid_x]

    left.sort(key=lambda b: (b.y0, b.x0))
    right.sort(key=lambda b: (b.y0, b.x0))

    return left + right


# ---------------------------------------------------------------------------
# Font-size analysis for heading detection
# ---------------------------------------------------------------------------


def _compute_body_font_size(blocks: list[_TextBlock]) -> float:
    """Estimate the most common (body) font size as the weighted median.

    Weights blocks by character count so that body text dominates over
    headings / captions.
    """
    if not blocks:
        return 12.0  # Reasonable default

    # Build (font_size, weight) pairs
    pairs: list[tuple[float, int]] = []
    for b in blocks:
        weight = max(len(b.text), 1)
        pairs.append((b.font_size, weight))

    pairs.sort(key=lambda p: p[0])
    total_weight = sum(w for _, w in pairs)
    half = total_weight / 2.0

    cumulative = 0
    for size, weight in pairs:
        cumulative += weight
        if cumulative >= half:
            return size

    return pairs[len(pairs) // 2][0]


# ---------------------------------------------------------------------------
# Block extraction from a single page
# ---------------------------------------------------------------------------


def _extract_blocks_from_page(page: fitz.Page, page_num: int) -> list[_TextBlock]:
    """Extract text blocks from a single PyMuPDF page.

    Uses ``page.get_text("dict")`` to obtain blocks with font metadata.
    """
    blocks: list[_TextBlock] = []

    try:
        page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
    except Exception as exc:
        logger.warning("Failed to get text dict from page %d: %s", page_num, exc)
        return blocks

    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:  # type 0 = text block
            continue

        # Aggregate text and font info from spans
        block_text_parts: list[str] = []
        font_sizes: list[float] = []
        font_names: list[str] = []

        for line in block.get("lines", []):
            line_text = ""
            for span in line.get("spans", []):
                span_text = span.get("text", "")
                line_text += span_text
                if span_text.strip():
                    font_sizes.append(span.get("size", 12.0))
                    font_names.append(span.get("font", ""))
            block_text_parts.append(line_text)

        text = "\n".join(block_text_parts).strip()
        if len(text) < _MIN_BLOCK_CHARS:
            continue

        bbox = block.get("bbox", (0, 0, 0, 0))
        avg_font_size = (
            sum(font_sizes) / len(font_sizes) if font_sizes else 12.0
        )
        primary_font = font_names[0] if font_names else ""

        blocks.append(
            _TextBlock(
                text=text,
                x0=bbox[0],
                y0=bbox[1],
                x1=bbox[2],
                y1=bbox[3],
                font_size=round(avg_font_size, 2),
                font_name=primary_font,
                page_num=page_num,
            )
        )

    return blocks


# ---------------------------------------------------------------------------
# Section grouping
# ---------------------------------------------------------------------------


def _group_into_sections(
    blocks: list[_TextBlock], body_font_size: float
) -> list[RawSection]:
    """Group blocks into sections using font-size heuristics.

    Blocks whose font size exceeds ``body_font_size * _HEADING_FONT_SIZE_RATIO``
    are treated as section headers.  All subsequent blocks until the next
    header are grouped as paragraphs under that section.
    """
    if not blocks:
        return []

    heading_threshold = body_font_size * _HEADING_FONT_SIZE_RATIO
    sections: list[RawSection] = []

    current_header = ""
    current_paragraphs: list[str] = []
    current_page_start = 0
    current_page_end = 0

    def _flush() -> None:
        """Flush the current section buffer."""
        if current_paragraphs or current_header:
            sections.append(
                RawSection(
                    header=current_header,
                    level=1,
                    parent_index=None,
                    paragraphs=list(current_paragraphs),
                    page_start=current_page_start,
                    page_end=current_page_end,
                    extraction_method=ExtractionMethod.PYMUPDF_FALLBACK,
                )
            )

    for block in blocks:
        is_heading = (
            block.font_size > heading_threshold
            and len(block.text) < 200  # Headings are short
            and "\n" not in block.text.strip()  # Single line
        )

        if is_heading:
            _flush()
            current_header = block.text.strip()
            current_paragraphs = []
            current_page_start = block.page_num
            current_page_end = block.page_num
        else:
            current_paragraphs.append(block.text)
            if not current_header and not current_paragraphs[:-1]:
                current_page_start = block.page_num
            current_page_end = block.page_num

    _flush()

    return sections


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_with_pymupdf(pdf_path: Path) -> list[RawSection]:
    """Extract structured text from a PDF using PyMuPDF with column detection.

    This is the fallback extractor used when GROBID is unavailable or
    produces low-quality output.

    Parameters
    ----------
    pdf_path:
        Filesystem path to the PDF to process.

    Returns
    -------
    list[RawSection]
        Extracted sections with ``extraction_method=PYMUPDF_FALLBACK``.
        Returns an empty list on unrecoverable errors.
    """
    pdf_path = Path(pdf_path).resolve()
    logger.info("PyMuPDF extraction starting: %s", pdf_path)

    if not pdf_path.exists():
        logger.error("PDF not found: %s", pdf_path)
        return []

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        logger.error("Cannot open PDF with PyMuPDF: %s", exc)
        return []

    all_blocks: list[_TextBlock] = []

    try:
        for page_num in range(doc.page_count):
            try:
                page = doc[page_num]
                page_blocks = _extract_blocks_from_page(page, page_num)

                # Detect columns per page
                page_width = page.rect.width
                num_cols = _detect_columns(page_blocks, page_width)

                # Sort in reading order
                sorted_blocks = _sort_blocks_reading_order(
                    page_blocks, num_cols, page_width
                )
                all_blocks.extend(sorted_blocks)

            except Exception as exc:
                logger.warning(
                    "Error extracting page %d: %s", page_num, exc
                )
                continue
    finally:
        doc.close()

    if not all_blocks:
        logger.warning("No text blocks extracted from %s", pdf_path.name)
        return []

    # Determine body font size across the entire document
    body_font = _compute_body_font_size(all_blocks)
    logger.debug("Estimated body font size: %.1f pt", body_font)

    # Group into sections
    sections = _group_into_sections(all_blocks, body_font)
    logger.info(
        "PyMuPDF extracted %d sections from %d text blocks in %s",
        len(sections),
        len(all_blocks),
        pdf_path.name,
    )

    return sections
