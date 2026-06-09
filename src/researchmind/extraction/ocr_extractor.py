"""OCR-based text extraction for scanned or image-only PDFs.

This module renders PDF pages to images using PyMuPDF, preprocesses them
with OpenCV (grayscale, adaptive threshold, deskew), and runs OCR via
Tesseract (default) or Surya (if available and configured).

Pages are processed one at a time to keep memory usage predictable.
"""

from __future__ import annotations

import io
import logging
import math
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import numpy as np

from researchmind.models.enums import ExtractionMethod
from researchmind.models.intermediates import ExtractionConfig, RawSection

logger = logging.getLogger(__name__)

# Maximum pixel dimension for page rendering safety valve.
_MAX_RENDER_DIM = 6000

# Minimum number of OCR'd characters to consider a page successfully processed.
_MIN_PAGE_CHARS = 10


# ---------------------------------------------------------------------------
# Image pre-processing helpers
# ---------------------------------------------------------------------------


def _render_page_to_image(page: fitz.Page, dpi: int) -> np.ndarray:
    """Render a PyMuPDF page to a NumPy BGR image array.

    Parameters
    ----------
    page:
        The PyMuPDF page object.
    dpi:
        Rendering resolution in dots-per-inch.

    Returns
    -------
    np.ndarray
        BGR image (H × W × 3).
    """
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    # Clamp to safety limit
    expected_w = page.rect.width * zoom
    expected_h = page.rect.height * zoom
    if max(expected_w, expected_h) > _MAX_RENDER_DIM:
        scale = _MAX_RENDER_DIM / max(expected_w, expected_h)
        mat = fitz.Matrix(zoom * scale, zoom * scale)
        logger.debug(
            "Clamped render matrix to fit %dx%d (scale=%.2f)",
            int(expected_w * scale),
            int(expected_h * scale),
            scale,
        )

    pix = page.get_pixmap(matrix=mat, alpha=False)
    img_bytes = pix.tobytes("png")

    # Decode via OpenCV
    import cv2

    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def _preprocess_image(img: np.ndarray) -> np.ndarray:
    """Apply grayscale, adaptive threshold, and deskew to an image.

    Parameters
    ----------
    img:
        BGR input image (H × W × 3).

    Returns
    -------
    np.ndarray
        Preprocessed grayscale image ready for OCR.
    """
    import cv2

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Adaptive thresholding — works better than global for scanned docs
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 10
    )

    # Deskew
    binary = _deskew(binary)

    return binary


def _deskew(img: np.ndarray) -> np.ndarray:
    """Deskew a binary image using minimum-area-rectangle on contours.

    Corrects rotation up to ±15°.  If the detected angle is negligible
    (< 0.5°) the image is returned unchanged.
    """
    import cv2

    # Invert for contour detection (text → white)
    inverted = cv2.bitwise_not(img)
    coords = np.column_stack(np.where(inverted > 0))

    if len(coords) < 100:
        return img

    # minAreaRect returns angle in [-90, 0)
    rect = cv2.minAreaRect(coords)
    angle = rect[-1]

    # Normalize angle
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    # Only correct meaningful skew
    if abs(angle) < 0.5 or abs(angle) > 15.0:
        return img

    logger.debug("Deskew angle: %.2f°", angle)
    h, w = img.shape[:2]
    centre = (w // 2, h // 2)
    rot_mat = cv2.getRotationMatrix2D(centre, angle, 1.0)
    rotated = cv2.warpAffine(
        img, rot_mat, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    return rotated


# ---------------------------------------------------------------------------
# OCR engines
# ---------------------------------------------------------------------------


def _ocr_tesseract(img: np.ndarray) -> str:
    """Run Tesseract OCR on a preprocessed image.

    Parameters
    ----------
    img:
        Grayscale/binary image.

    Returns
    -------
    str
        Extracted text.
    """
    import pytesseract

    text: str = pytesseract.image_to_string(img, config="--psm 3")
    return text.strip()


def _ocr_surya(img: np.ndarray) -> str | None:
    """Attempt OCR using the Surya library.

    Returns ``None`` if Surya is not installed or fails, so the caller
    can fall back to Tesseract.

    Parameters
    ----------
    img:
        Grayscale/binary image.

    Returns
    -------
    str | None
        Extracted text, or ``None`` on failure.
    """
    try:
        from surya.ocr import run_ocr  # type: ignore[import-untyped]
        from surya.model.detection import segformer as det_model  # type: ignore[import-untyped]
        from surya.model.recognition import model as rec_model  # type: ignore[import-untyped]
        from PIL import Image
    except ImportError:
        logger.debug("Surya not available — will use Tesseract")
        return None

    try:
        # Convert numpy array to PIL Image
        if len(img.shape) == 2:
            pil_img = Image.fromarray(img)
        else:
            import cv2

            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)

        # Load models (cached globally by Surya)
        det = det_model.load_model()
        det_proc = det_model.load_processor()
        rec = rec_model.load_model()
        rec_proc = rec_model.load_processor()

        results = run_ocr(
            [pil_img],
            [["en"]],
            det,
            det_proc,
            rec,
            rec_proc,
        )

        if results and results[0].text_lines:
            text = "\n".join(line.text for line in results[0].text_lines)
            return text.strip()

        return ""

    except Exception as exc:
        logger.warning("Surya OCR failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Section grouping from OCR output
# ---------------------------------------------------------------------------


def _group_ocr_text_into_sections(
    pages_text: list[tuple[int, str]],
) -> list[RawSection]:
    """Group OCR'd page texts into :class:`RawSection` objects.

    Heuristics:
    - Lines that are short (< 80 chars), end without punctuation, and are
      preceded by a blank line are treated as potential section headers.
    - Otherwise, consecutive non-empty lines are grouped into paragraphs.
    - Page boundaries are always potential section breaks.

    Parameters
    ----------
    pages_text:
        List of (page_number, ocr_text) tuples.

    Returns
    -------
    list[RawSection]
        Sections with extraction method set appropriately.
    """
    sections: list[RawSection] = []
    current_header = ""
    current_paragraphs: list[str] = []
    current_page_start = 0
    current_page_end = 0
    extraction_method = ExtractionMethod.OCR_TESSERACT  # Will be overridden by caller

    def _flush() -> None:
        nonlocal current_header, current_paragraphs
        if current_paragraphs or current_header:
            sections.append(
                RawSection(
                    header=current_header,
                    level=1,
                    parent_index=None,
                    paragraphs=list(current_paragraphs),
                    page_start=current_page_start,
                    page_end=current_page_end,
                    extraction_method=extraction_method,
                )
            )
            current_header = ""
            current_paragraphs = []

    for page_num, page_text in pages_text:
        if not page_text.strip():
            continue

        lines = page_text.split("\n")
        prev_blank = True  # Start of page counts as "after blank"

        for line in lines:
            stripped = line.strip()

            if not stripped:
                prev_blank = True
                continue

            # Heading heuristic: short line after blank, no trailing punctuation
            is_heading = (
                prev_blank
                and len(stripped) < 80
                and not stripped.endswith((".", ",", ";", ":", "?", "!"))
                and stripped[0].isupper()
            )

            if is_heading and (current_paragraphs or current_header):
                # Flush previous section and start a new one
                _flush()
                current_header = stripped
                current_page_start = page_num
                current_page_end = page_num
            elif is_heading and not current_header:
                current_header = stripped
                current_page_start = page_num
                current_page_end = page_num
            else:
                current_paragraphs.append(stripped)
                current_page_end = page_num
                if not current_header and len(current_paragraphs) == 1:
                    current_page_start = page_num

            prev_blank = False

    _flush()
    return sections


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_with_ocr(
    pdf_path: Path, config: ExtractionConfig
) -> list[RawSection]:
    """Extract text from a scanned/image PDF via OCR.

    Renders each page at ``config.ocr_dpi``, preprocesses with OpenCV,
    and runs OCR.  If ``config.ocr_engine == 'surya'``, attempts Surya
    first and falls back to Tesseract on failure.

    Parameters
    ----------
    pdf_path:
        Filesystem path to the PDF.
    config:
        Extraction configuration with OCR settings.

    Returns
    -------
    list[RawSection]
        Extracted sections with ``extraction_method`` set to
        ``OCR_TESSERACT`` or ``OCR_SURYA``.
        Returns an empty list on unrecoverable errors.
    """
    pdf_path = Path(pdf_path).resolve()
    logger.info("OCR extraction starting: %s (dpi=%d)", pdf_path, config.ocr_dpi)

    if not pdf_path.exists():
        logger.error("PDF not found: %s", pdf_path)
        return []

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        logger.error("Cannot open PDF for OCR: %s", exc)
        return []

    use_surya = config.ocr_engine.lower() == "surya"
    surya_available = False
    if use_surya:
        try:
            import surya  # type: ignore[import-untyped]
            surya_available = True
            logger.info("Surya OCR engine selected and available")
        except ImportError:
            logger.warning(
                "Surya requested but not installed — falling back to Tesseract"
            )

    actual_method = (
        ExtractionMethod.OCR_SURYA
        if (use_surya and surya_available)
        else ExtractionMethod.OCR_TESSERACT
    )

    pages_text: list[tuple[int, str]] = []
    total_pages = min(doc.page_count, config.max_pages)

    if doc.page_count > config.max_pages:
        logger.warning(
            "PDF has %d pages, capping OCR at %d",
            doc.page_count,
            config.max_pages,
        )

    try:
        for page_num in range(total_pages):
            logger.debug("OCR page %d / %d", page_num + 1, total_pages)
            try:
                page = doc[page_num]

                # Render to image
                img = _render_page_to_image(page, config.ocr_dpi)

                # Preprocess
                processed = _preprocess_image(img)

                # Run OCR
                text: str | None = None

                if use_surya and surya_available:
                    text = _ocr_surya(processed)
                    if text is None:
                        logger.debug(
                            "Surya failed on page %d, falling back to Tesseract",
                            page_num,
                        )

                if text is None:
                    text = _ocr_tesseract(processed)
                    # If we fell back from Surya, note it
                    if use_surya and surya_available:
                        actual_method = ExtractionMethod.OCR_TESSERACT

                if text and len(text.strip()) >= _MIN_PAGE_CHARS:
                    pages_text.append((page_num, text))
                else:
                    logger.debug(
                        "Page %d produced insufficient OCR text (%d chars)",
                        page_num,
                        len(text) if text else 0,
                    )

            except Exception as exc:
                logger.warning("OCR failed on page %d: %s", page_num, exc)
                continue
    finally:
        doc.close()

    if not pages_text:
        logger.warning("No text extracted via OCR from %s", pdf_path.name)
        return []

    # Group into sections
    sections = _group_ocr_text_into_sections(pages_text)

    # Override extraction method on all sections
    for sec in sections:
        sec.extraction_method = actual_method

    logger.info(
        "OCR extracted %d sections from %d pages (%s) in %s",
        len(sections),
        len(pages_text),
        actual_method.value,
        pdf_path.name,
    )

    return sections
