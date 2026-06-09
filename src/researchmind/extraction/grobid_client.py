"""HTTP client for the GROBID service — TEI XML extraction from PDFs.

Sends PDFs to a running GROBID instance and returns the raw TEI XML response.
Designed to never raise on transient failures — returns ``None`` so callers
can fall back to alternative extractors.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx

from researchmind.models.intermediates import GrobidConfig

logger = logging.getLogger(__name__)

_TRANSIENT_HTTP_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.RemoteProtocolError,
    httpx.NetworkError,
)


class GrobidClient:
    """Thin wrapper around the GROBID REST API.

    Parameters
    ----------
    config:
        Connection parameters (URL, timeout, consolidation flags).
    """

    def __init__(self, config: GrobidConfig) -> None:
        self._base_url: str = config.url.rstrip("/")
        self._timeout: float = float(config.timeout_seconds)
        self._consolidate_header: bool = config.consolidate_header
        self._consolidate_citations: bool = config.consolidate_citations
        self._retry_attempts: int = config.retry_attempts
        self._retry_backoff_initial: float = config.retry_backoff_initial_seconds
        self._retry_backoff_max: float = config.retry_backoff_max_seconds
        self._retry_status_codes: set[int] = set(config.retry_status_codes)
        logger.info(
            "GrobidClient initialised: base_url=%s, timeout=%.1fs, retries=%d",
            self._base_url,
            self._timeout,
            self._retry_attempts,
        )

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def is_alive(self) -> bool:
        """Return ``True`` if the GROBID service responds to a health-check.

        Sends ``GET /api/isalive`` and checks for a 200 status code.
        """
        url = f"{self._base_url}/api/isalive"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url)
            alive = resp.status_code == 200
            logger.debug("GROBID health-check %s → %s", url, alive)
            return alive
        except Exception as exc:
            logger.warning("GROBID health-check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Full-text processing
    # ------------------------------------------------------------------

    def _post_fulltext_once(self, pdf_path: Path) -> httpx.Response:
        """POST the PDF to GROBID and return the raw response.

        The caller handles retry policy. This method intentionally reopens the
        PDF for every attempt so the multipart stream is never reused after a
        failed request.
        """
        url = f"{self._base_url}/api/processFulltextDocument"
        logger.debug("Posting PDF to GROBID: %s", pdf_path.name)

        with open(pdf_path, "rb") as fh:
            files = {"input": (pdf_path.name, fh, "application/pdf")}
            data: dict[str, str] = {
                "teiCoordinates": "persName,figure,ref,biblStruct,formula,s",
            }
            if self._consolidate_header:
                data["consolidateHeader"] = "1"
            if self._consolidate_citations:
                data["consolidateCitations"] = "1"

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(url, files=files, data=data)
        return resp

    def _backoff_seconds(self, attempt: int) -> float:
        """Return exponential backoff delay for a 1-based failed attempt."""
        if self._retry_backoff_initial <= 0:
            return 0.0
        delay = self._retry_backoff_initial * (2 ** max(attempt - 1, 0))
        if self._retry_backoff_max > 0:
            return min(delay, self._retry_backoff_max)
        return delay

    def _post_fulltext(self, pdf_path: Path) -> httpx.Response:
        """POST the PDF to GROBID with configurable transient-failure retries."""
        last_exc: Exception | None = None

        for attempt in range(1, self._retry_attempts + 1):
            try:
                logger.info(
                    "GROBID fulltext attempt %d/%d for %s",
                    attempt,
                    self._retry_attempts,
                    pdf_path.name,
                )
                resp = self._post_fulltext_once(pdf_path)
                if resp.status_code in self._retry_status_codes:
                    message = (
                        f"GROBID returned retryable HTTP {resp.status_code} "
                        f"for {pdf_path.name}"
                    )
                    last_exc = httpx.HTTPStatusError(
                        message,
                        request=resp.request,
                        response=resp,
                    )
                    raise last_exc

                resp.raise_for_status()
                if attempt > 1:
                    logger.info(
                        "GROBID fulltext succeeded on attempt %d/%d for %s",
                        attempt,
                        self._retry_attempts,
                        pdf_path.name,
                    )
                return resp
            except _TRANSIENT_HTTP_EXCEPTIONS as exc:
                last_exc = exc
                if attempt >= self._retry_attempts:
                    break
                delay = self._backoff_seconds(attempt)
                logger.warning(
                    "Transient GROBID transport failure on attempt %d/%d for %s: "
                    "%s. Retrying in %.1fs",
                    attempt,
                    self._retry_attempts,
                    pdf_path.name,
                    exc,
                    delay,
                )
                if delay > 0:
                    time.sleep(delay)
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code not in self._retry_status_codes:
                    raise
                if attempt >= self._retry_attempts:
                    break
                delay = self._backoff_seconds(attempt)
                logger.warning(
                    "Retryable GROBID HTTP status on attempt %d/%d for %s: "
                    "HTTP %d. Retrying in %.1fs",
                    attempt,
                    self._retry_attempts,
                    pdf_path.name,
                    exc.response.status_code,
                    delay,
                )
                if delay > 0:
                    time.sleep(delay)

        assert last_exc is not None
        raise last_exc

    def process_fulltext(self, pdf_path: Path) -> str | None:
        """Send a PDF to GROBID and return the TEI XML string.

        Returns ``None`` if GROBID is unreachable, the request fails after
        retries, or the response is not valid XML.  The caller should fall
        back to :func:`researchmind.extraction.pymupdf_extractor.extract_with_pymupdf`.

        Parameters
        ----------
        pdf_path:
            Filesystem path to the PDF to process.
        """
        pdf_path = Path(pdf_path).resolve()
        if not pdf_path.exists():
            logger.error("PDF not found for GROBID: %s", pdf_path)
            return None

        try:
            resp = self._post_fulltext(pdf_path)
        except Exception as exc:
            logger.warning(
                "GROBID fulltext processing failed after retries: %s", exc
            )
            return None

        tei_xml: str = resp.text
        if not tei_xml or not tei_xml.strip().startswith("<?xml"):
            # Sometimes GROBID returns a non-XML error body.
            if tei_xml and "<TEI" in tei_xml:
                # Looks like valid TEI without the XML prolog — accept it.
                logger.debug(
                    "GROBID response lacks XML prolog but contains <TEI>; accepting."
                )
            else:
                logger.warning(
                    "GROBID returned non-XML response (%d bytes)", len(tei_xml)
                )
                return None

        logger.info(
            "GROBID extracted TEI XML: %d bytes from %s",
            len(tei_xml),
            pdf_path.name,
        )
        return tei_xml
