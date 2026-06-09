"""PDF fingerprinting — compute identity hash, page metrics, and text-layer detection.

This module is the very first stage of the ResearchMind pipeline (Stage 0a).
It opens the PDF once, extracts physical properties and samples text density
to decide whether the document has a usable text layer or is a scanned image.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import fitz  # PyMuPDF

from researchmind.models.enums import ExtractionRoute
from researchmind.models.intermediates import IntakeResult, PipelineError

logger = logging.getLogger(__name__)

# Characters-per-page threshold to consider a page as having usable text.
_TEXT_DENSITY_THRESHOLD: float = 50.0


def _compute_sha256(pdf_path: Path) -> str:
    """Return the lowercase hex SHA-256 digest of the file at *pdf_path*."""
    h = hashlib.sha256()
    with open(pdf_path, "rb") as fh:
        while True:
            chunk = fh.read(1 << 16)  # 64 KiB
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _sample_page_indices(page_count: int) -> list[int]:
    """Return indices of pages to sample for text density: first, middle, last.

    Deduplicates when the document has fewer than three pages.
    """
    if page_count == 0:
        return []
    indices: set[int] = {0, page_count - 1}
    indices.add(page_count // 2)
    return sorted(indices)


def fingerprint(pdf_path: Path) -> IntakeResult:
    """Compute identity and physical properties of a PDF.

    Returns an :class:`IntakeResult` with all fields populated **except**
    ``extraction_route`` which is set to a preliminary default
    (``GROBID_PRIMARY``).  The caller must pass the result through
    :func:`researchmind.intake.router.route` to finalise routing.

    Parameters
    ----------
    pdf_path:
        Filesystem path to the PDF to analyse.

    Raises
    ------
    PipelineError
        If the file does not exist, is encrypted, or is too corrupted to open.
    """
    pdf_path = Path(pdf_path).resolve()
    logger.info("Fingerprinting PDF: %s", pdf_path)

    if not pdf_path.exists():
        raise PipelineError("intake", f"PDF file not found: {pdf_path}")

    if not pdf_path.is_file():
        raise PipelineError("intake", f"Path is not a regular file: {pdf_path}")

    # ------------------------------------------------------------------
    # SHA-256 hash
    # ------------------------------------------------------------------
    try:
        sha256 = _compute_sha256(pdf_path)
    except OSError as exc:
        raise PipelineError("intake", f"Cannot read PDF for hashing: {exc}") from exc

    logger.debug("SHA-256: %s", sha256)

    # ------------------------------------------------------------------
    # File size
    # ------------------------------------------------------------------
    file_size_bytes = pdf_path.stat().st_size

    # ------------------------------------------------------------------
    # Open with PyMuPDF
    # ------------------------------------------------------------------
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        raise PipelineError(
            "intake", f"Cannot open PDF (corrupted or unsupported format): {exc}"
        ) from exc

    try:
        # Encrypted / password-protected
        if doc.is_encrypted:
            doc.close()
            raise PipelineError(
                "intake",
                f"PDF is encrypted / password-protected: {pdf_path.name}",
            )

        page_count: int = doc.page_count
        if page_count < 1:
            doc.close()
            raise PipelineError("intake", "PDF has zero pages")

        # ------------------------------------------------------------------
        # Sample text density
        # ------------------------------------------------------------------
        sample_indices = _sample_page_indices(page_count)
        page_char_counts: list[int] = []
        all_sampled_have_text = True
        any_sampled_low_density = False

        for idx in sample_indices:
            try:
                page = doc[idx]
                text = page.get_text("text") or ""
                char_count = len(text.strip())
                page_char_counts.append(char_count)

                if char_count < _TEXT_DENSITY_THRESHOLD:
                    any_sampled_low_density = True
                if char_count < _TEXT_DENSITY_THRESHOLD:
                    all_sampled_have_text = False
            except Exception as exc:
                logger.warning(
                    "Failed to extract text from page %d: %s", idx, exc
                )
                page_char_counts.append(0)
                any_sampled_low_density = True
                all_sampled_have_text = False

        # Average chars per page across sampled pages
        text_density: float = (
            sum(page_char_counts) / len(page_char_counts) if page_char_counts else 0.0
        )

        # Determine text-layer presence
        has_text_layer: bool = all_sampled_have_text
        is_scanned: bool = any_sampled_low_density

        logger.info(
            "PDF stats: pages=%d, size=%d bytes, density=%.1f chars/page, "
            "has_text=%s, scanned=%s",
            page_count,
            file_size_bytes,
            text_density,
            has_text_layer,
            is_scanned,
        )

    finally:
        doc.close()

    # Build result with a preliminary route; router.route() will finalise it.
    return IntakeResult(
        file_path=pdf_path,
        sha256=sha256,
        page_count=page_count,
        file_size_bytes=file_size_bytes,
        has_text_layer=has_text_layer,
        is_scanned=is_scanned,
        text_density=text_density,
        extraction_route=ExtractionRoute.GROBID_PRIMARY,  # placeholder
    )
