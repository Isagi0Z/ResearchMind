"""Extraction route selection — decide which extraction pipeline to use.

This module is Stage 0b of the ResearchMind pipeline.  Given the physical
properties computed by :func:`researchmind.intake.fingerprint.fingerprint`,
the router decides whether the PDF should be processed with GROBID
(born-digital), OCR (scanned), or a hybrid approach (mixed pages).
"""

from __future__ import annotations

import logging

from researchmind.models.enums import ExtractionRoute
from researchmind.models.intermediates import ExtractionConfig, IntakeResult

logger = logging.getLogger(__name__)

# Hard threshold below which text density is considered "basically empty".
_LOW_DENSITY_HARD_THRESHOLD: float = 20.0


def route(intake: IntakeResult, config: ExtractionConfig) -> IntakeResult:
    """Determine the extraction route and return an updated :class:`IntakeResult`.

    Routing logic
    ~~~~~~~~~~~~~

    1. **Born-digital** (``grobid_primary``):
       ``has_text_layer=True`` *and* ``is_scanned=False``.
       All sampled pages had adequate text density.

    2. **Scanned** (``ocr_primary``):
       ``has_text_layer=False``, *or* ``is_scanned=True`` with average text
       density below the low-density hard threshold (< 20 chars/page).
       The document is essentially an image PDF.

    3. **Mixed / hybrid** (``hybrid``):
       Some pages have text while others are scanned images.
       Both GROBID and OCR will be run and their outputs merged.

    Parameters
    ----------
    intake:
        The partially populated :class:`IntakeResult` from fingerprinting.
    config:
        Extraction configuration (used for threshold overrides in future).

    Returns
    -------
    IntakeResult
        A **copy** of *intake* with ``extraction_route`` set.
    """
    has_text = intake.has_text_layer
    is_scanned = intake.is_scanned
    density = intake.text_density

    if has_text and not is_scanned:
        # All sampled pages are text-rich — use GROBID.
        chosen_route = ExtractionRoute.GROBID_PRIMARY
        logger.info(
            "Route decision: GROBID_PRIMARY (born-digital, density=%.1f)",
            density,
        )

    elif not has_text or (is_scanned and density < _LOW_DENSITY_HARD_THRESHOLD):
        # No usable text layer at all, or density is negligible — full OCR.
        chosen_route = ExtractionRoute.OCR_PRIMARY
        logger.info(
            "Route decision: OCR_PRIMARY (scanned/no-text, density=%.1f)",
            density,
        )

    else:
        # Mixed: some pages have text, some don't — run both.
        chosen_route = ExtractionRoute.HYBRID
        logger.info(
            "Route decision: HYBRID (mixed, has_text=%s, scanned=%s, "
            "density=%.1f)",
            has_text,
            is_scanned,
            density,
        )

    # Return an updated copy (IntakeResult is a Pydantic model).
    return intake.model_copy(update={"extraction_route": chosen_route})
