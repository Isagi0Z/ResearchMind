"""Reference resolver — resolves bibliography entries to canonical identifiers.

Strategy:
1. If a raw reference already has a DOI (set by GROBID consolidation), mark as
   resolved immediately.
2. Otherwise, if CrossRef lookup is enabled, query the CrossRef API to resolve
   the reference by title + author + year.
3. Compute a ``ref_confidence`` score from field completeness and resolution
   status.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
from typing import Any
from urllib.parse import unquote

import httpx
from rapidfuzz import fuzz

from researchmind.models.enums import ResolutionSource, ResolutionStatus
from researchmind.models.intermediates import CrossRefConfig, RawReference
from researchmind.models.sro import SROReference

logger = logging.getLogger(__name__)

_CROSSREF_API_URL = "https://api.crossref.org/works"
_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.IGNORECASE)
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Author name normalisation
# ---------------------------------------------------------------------------


def _normalise_author_name(name: str) -> str:
    """Normalise an author name to 'Surname, Given' format.

    Handles common formats:
    - "John Smith" → "Smith, John"
    - "Smith, John" → "Smith, John" (already correct)
    - "J. Smith" → "Smith, J."
    - "Smith J" → "Smith, J"
    """
    name = html.unescape(name or "").strip()
    name = re.sub(r"\s+", " ", name)
    # GROBID sometimes emits compact names like "JohnDuchi" or "YBengio".
    name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)
    name = re.sub(r"^([A-Z]{1,3})([A-Z][a-z].*)$", r"\1 \2", name)
    if not name:
        return name

    # Already in "Surname, Given" format
    if "," in name:
        parts = [p.strip() for p in name.split(",", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            return f"{parts[0]}, {parts[1]}"
        return name

    tokens = name.split()
    if len(tokens) == 0:
        return name
    if len(tokens) == 1:
        return tokens[0]

    # Assume last token is surname for "Given Surname" style
    surname = tokens[-1]
    given = " ".join(tokens[:-1])
    return f"{surname}, {given}"


def _author_surname(name: str) -> str:
    """Return a lowercase surname token from a normalized or raw author name."""
    normalised = _normalise_author_name(name)
    if not normalised:
        return ""
    if "," in normalised:
        surname = normalised.split(",", 1)[0]
    else:
        surname = normalised.split()[-1]
    return re.sub(r"[^a-z0-9-]", "", surname.lower())


def _crossref_author_surnames(item: dict[str, Any]) -> set[str]:
    """Extract comparable author surnames from a CrossRef item."""
    surnames: set[str] = set()
    for author in item.get("author", []) or []:
        family = str(author.get("family", "")).strip()
        if family:
            surnames.add(_author_surname(family))
    return {s for s in surnames if s}


def _unquote_doi(text: str) -> str:
    """Safely URL-decode percent-encoded characters in a DOI string.

    Only decodes common DOI-safe encodings (``%2F``, ``%28``, ``%29``, ``%5B``,
    ``%5D``) and degrades gracefully on malformed sequences.
    """
    try:
        return unquote(text, errors="replace")
    except Exception:
        return text


def _normalise_doi(doi: str | None) -> str | None:
    """Normalize DOI strings extracted by GROBID, raw references, or CrossRef."""
    if not doi:
        return None

    cleaned = html.unescape(doi).strip()

    # --- Unicode dash normalisation ---
    cleaned = cleaned.replace("\u2010", "-").replace("\u2011", "-")
    cleaned = cleaned.replace("\u2012", "-").replace("\u2013", "-")
    cleaned = cleaned.replace("\u2014", "-").replace("\u2212", "-")

    # --- URL-decode percent-encoded characters ---
    cleaned = _unquote_doi(cleaned)

    # --- Strip common prefixes ---
    cleaned = re.sub(r"^(?:doi\s*:\s*)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", cleaned, flags=re.IGNORECASE)

    # --- Extract the DOI-like substring via pattern ---
    match = _DOI_RE.search(cleaned)
    if match:
        cleaned = match.group(1).strip()

    # --- Iteratively strip trailing punctuation and slashes ---
    prev: str | None = None
    while cleaned != prev:
        prev = cleaned
        cleaned = cleaned.strip().strip(".,;:)]}>/").strip()
        if not cleaned:
            break

    if not cleaned.lower().startswith("10."):
        return None
    return cleaned.lower()


def _extract_doi_from_raw_text(raw_text: str) -> str | None:
    """Extract the first DOI-looking token from a raw bibliography string."""
    match = _DOI_RE.search(raw_text or "")
    if not match:
        return None
    return _normalise_doi(match.group(1))


def _clean_title(title: str | None) -> str:
    """Clean title text for querying and matching without changing schema."""
    if not title:
        return ""
    cleaned = html.unescape(title)
    cleaned = cleaned.replace("\u2010", "-").replace("\u2011", "-")
    cleaned = cleaned.replace("\u2012", "-").replace("\u2013", "-")
    cleaned = cleaned.replace("\u2014", "-").replace("\u2212", "-")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.strip(" .,:;")


def _normalise_title_for_match(title: str | None) -> str:
    """Normalize title text for fuzzy matching."""
    cleaned = _clean_title(title).lower()
    cleaned = _PUNCT_RE.sub(" ", cleaned)
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def _reference_year(ref: RawReference) -> str | None:
    """Return a four-digit reference year if one is available."""
    if ref.year:
        match = re.search(r"\d{4}", ref.year)
        if match:
            return match.group(0)
    match = re.search(r"\b(19|20)\d{2}\b", ref.raw_text or "")
    return match.group(0) if match else None


def _crossref_year(item: dict[str, Any]) -> str | None:
    """Extract a four-digit publication year from common CrossRef date fields."""
    for key in ("issued", "published-print", "published-online", "published"):
        date_parts = item.get(key, {}).get("date-parts", [])
        if date_parts and date_parts[0]:
            return str(date_parts[0][0])
    return None


# ---------------------------------------------------------------------------
# Field-completeness confidence
# ---------------------------------------------------------------------------


def _compute_ref_confidence(
    ref: RawReference,
    status: ResolutionStatus,
    doi: str | None = None,
) -> float:
    """Compute a confidence score based on field completeness and resolution.

    Score breakdown:
    - title present: +0.25
    - authors present: +0.15
    - year present: +0.10
    - venue present: +0.10
    - DOI present and resolved: +0.30
    - DOI present and ambiguous: +0.18
    - raw_text non-empty: +0.10
    """
    score = 0.0

    if ref.title:
        score += 0.25
    if ref.authors:
        score += 0.15
    if ref.year:
        score += 0.10
    if ref.venue:
        score += 0.10
    if status == ResolutionStatus.RESOLVED:
        score += 0.30
    elif status == ResolutionStatus.AMBIGUOUS and doi:
        score += 0.18
    if ref.raw_text and ref.raw_text.strip():
        score += 0.10

    return round(min(score, 1.0), 4)


# ---------------------------------------------------------------------------
# CrossRef lookup
# ---------------------------------------------------------------------------


def _build_crossref_query(ref: RawReference) -> str:
    """Build a query string for CrossRef from reference fields."""
    parts: list[str] = []

    if ref.title:
        parts.append(_clean_title(ref.title))
    if ref.authors:
        # Use first author surname for disambiguation
        first_author = _author_surname(ref.authors[0])
        if first_author:
            parts.append(first_author)
    year = _reference_year(ref)
    if year:
        parts.append(year)

    return " ".join(parts)


def _build_crossref_params(ref: RawReference) -> dict[str, Any]:
    """Build robust CrossRef query parameters for one reference."""
    query = _build_crossref_query(ref)
    params: dict[str, Any] = {"rows": 5}
    title = _clean_title(ref.title)
    if title:
        params["query.title"] = title
    if ref.authors:
        surname = _author_surname(ref.authors[0])
        if surname:
            params["query.author"] = surname
    if query:
        params["query.bibliographic"] = query
    else:
        params["query"] = (ref.raw_text or "")[:300]
    return params


def _score_crossref_candidate(
    ref: RawReference,
    item: dict[str, Any],
) -> tuple[float, float, float, float, str | None]:
    """Score a CrossRef candidate using title, author, year, and DOI evidence."""
    ref_title = _normalise_title_for_match(ref.title)
    cr_title_parts = item.get("title", []) or []
    cr_title = cr_title_parts[0] if cr_title_parts else ""
    cr_title_norm = _normalise_title_for_match(cr_title)

    if ref_title and cr_title_norm:
        title_sim = max(
            fuzz.ratio(ref_title, cr_title_norm),
            fuzz.token_sort_ratio(ref_title, cr_title_norm),
            fuzz.token_set_ratio(ref_title, cr_title_norm),
        ) / 100.0
    else:
        title_sim = 0.0

    ref_surnames = {_author_surname(a) for a in ref.authors}
    ref_surnames = {s for s in ref_surnames if s}
    cr_surnames = _crossref_author_surnames(item)
    if ref_surnames and cr_surnames:
        author_score = 1.0 if ref_surnames & cr_surnames else 0.0
    elif not ref_surnames:
        author_score = 0.5
    else:
        author_score = 0.0

    ref_year = _reference_year(ref)
    cr_year = _crossref_year(item)
    if ref_year and cr_year:
        year_score = 1.0 if ref_year == cr_year else 0.0
    elif not ref_year:
        year_score = 0.5
    else:
        year_score = 0.0

    doi = _normalise_doi(item.get("DOI"))
    doi_score = 1.0 if doi else 0.0
    composite = (
        0.64 * title_sim
        + 0.18 * author_score
        + 0.12 * year_score
        + 0.06 * doi_score
    )
    return composite, title_sim, author_score, year_score, doi


def _diagnose_unresolved_reference(ref: RawReference, reason: str) -> str:
    """Build a concise diagnostic message for unresolved references."""
    bits = [reason]
    if not ref.title:
        bits.append("missing_title")
    if not ref.authors:
        bits.append("missing_authors")
    if not _reference_year(ref):
        bits.append("missing_year")
    if _extract_doi_from_raw_text(ref.raw_text):
        bits.append("raw_text_contains_doi")
    return ",".join(bits)


async def _crossref_request(
    client: httpx.AsyncClient,
    params: dict[str, Any],
    headers: dict[str, str],
    config: CrossRefConfig,
) -> httpx.Response | None:
    """Make a CrossRef API request with retry/backoff for transient errors."""
    for attempt in range(config.retry_attempts + 1):
        try:
            resp = await client.get(
                _CROSSREF_API_URL,
                params=params,
                headers=headers,
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in (429, 500, 502, 503) and attempt < config.retry_attempts:
                backoff = config.retry_backoff_seconds * (2 ** attempt)
                logger.debug(
                    "CrossRef HTTP %d, retry %d/%d after %.1fs",
                    status, attempt + 1, config.retry_attempts, backoff,
                )
                await asyncio.sleep(backoff)
                continue
            logger.warning("CrossRef HTTP %d: %s", status, exc)
            return None
        except httpx.RequestError as exc:
            if attempt < config.retry_attempts:
                backoff = config.retry_backoff_seconds * (2 ** attempt)
                logger.debug(
                    "CrossRef request error, retry %d/%d after %.1fs: %s",
                    attempt + 1, config.retry_attempts, backoff, exc,
                )
                await asyncio.sleep(backoff)
                continue
            logger.warning("CrossRef request error: %s", exc)
            return None
    return None


async def _lookup_crossref(
    ref: RawReference,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    config: CrossRefConfig,
) -> tuple[str | None, ResolutionStatus, ResolutionSource, float]:
    """Query CrossRef API for a single reference.

    Uses structured query parameters, scores multiple candidates via
    ``_score_crossref_candidate``, and applies configurable thresholds
    (``resolve_threshold``, ``ambiguous_threshold``) for resolution.

    Returns
    -------
    tuple of (doi | None, status, source, composite_confidence)
    """
    params = _build_crossref_params(ref)
    if not params.get("query") and not params.get("query.bibliographic") \
            and not params.get("query.title"):
        logger.debug("Empty CrossRef query for ref '%s' — skipping", ref.raw_text[:60])
        return None, ResolutionStatus.UNRESOLVED, ResolutionSource.NONE, 0.0

    headers: dict[str, str] = {
        "User-Agent": "ResearchMind/0.1 (mailto:researchmind@example.com)"
    }
    if config.mailto:
        headers["User-Agent"] = f"ResearchMind/0.1 (mailto:{config.mailto})"

    async with semaphore:
        resp = await _crossref_request(client, params, headers, config)
        if resp is None:
            return None, ResolutionStatus.UNRESOLVED, ResolutionSource.NONE, 0.0

        try:
            data = resp.json()
            items = data.get("message", {}).get("items", [])
        except Exception:
            logger.warning("Failed to parse CrossRef response")
            return None, ResolutionStatus.UNRESOLVED, ResolutionSource.NONE, 0.0

        if not items:
            return None, ResolutionStatus.UNRESOLVED, ResolutionSource.NONE, 0.0

        # Score all candidates using the existing scorer
        scored: list[tuple[float, str | None]] = []
        for item in items:
            composite, _title_sim, _author_score, _year_score, doi = \
                _score_crossref_candidate(ref, item)
            scored.append((composite, doi))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_composite, best_doi = scored[0]

        logger.debug(
            "CrossRef top candidate: composite=%.3f, doi=%s, total_candidates=%d",
            best_composite, best_doi, len(scored),
        )

        if best_composite >= config.resolve_threshold and best_doi:
            logger.debug(
                "CrossRef resolved: composite=%.3f, doi=%s", best_composite, best_doi,
            )
            return (
                best_doi,
                ResolutionStatus.RESOLVED,
                ResolutionSource.CROSSREF_LOOKUP,
                best_composite,
            )

        if best_composite >= config.ambiguous_threshold and best_doi:
            logger.debug(
                "CrossRef ambiguous: composite=%.3f, doi=%s", best_composite, best_doi,
            )
            return (
                best_doi,
                ResolutionStatus.AMBIGUOUS,
                ResolutionSource.CROSSREF_LOOKUP,
                best_composite,
            )

        logger.debug(
            "CrossRef unresolved: composite=%.3f for '%.60s'",
            best_composite, (ref.title or ref.raw_text)[:60],
        )
        return None, ResolutionStatus.UNRESOLVED, ResolutionSource.NONE, best_composite


# ---------------------------------------------------------------------------
# Core async resolver
# ---------------------------------------------------------------------------


async def _resolve_references_async(
    raw_refs: list[RawReference],
    config: CrossRefConfig,
) -> list[SROReference]:
    """Resolve references asynchronously (internal implementation).

    Processes each raw reference, attempting GROBID DOI first, then CrossRef.
    """
    total = len(raw_refs)
    if total == 0:
        logger.info("No references to resolve")
        return []

    semaphore = asyncio.Semaphore(config.rate_limit)
    results: list[SROReference] = []

    # Separate refs that need CrossRef lookup
    needs_lookup: list[tuple[int, RawReference]] = []

    for idx, raw in enumerate(raw_refs):
        ref_id = f"ref_{idx + 1:03d}"
        authors = [_normalise_author_name(a) for a in raw.authors]

        if raw.doi:
            # Already resolved by GROBID consolidation
            confidence = _compute_ref_confidence(raw, ResolutionStatus.RESOLVED)
            sro_ref = SROReference(
                ref_id=ref_id,
                raw_text=raw.raw_text,
                resolution_status=ResolutionStatus.RESOLVED,
                ref_confidence=confidence,
                title=raw.title,
                authors=authors,
                year=raw.year,
                venue=raw.venue,
                doi=raw.doi,
                url=raw.url,
                resolution_source=ResolutionSource.GROBID_CONSOLIDATION,
            )
            results.append(sro_ref)
            logger.debug("Ref %s pre-resolved via GROBID DOI: %s", ref_id, raw.doi)
        else:
            needs_lookup.append((idx, raw))

    logger.info(
        "References: %d pre-resolved, %d need CrossRef lookup",
        len(results), len(needs_lookup),
    )

    if needs_lookup and config.enabled:
        async with httpx.AsyncClient() as client:
            tasks = []
            for idx, raw in needs_lookup:
                tasks.append(_lookup_crossref(raw, client, semaphore, config))

            lookup_results = await asyncio.gather(*tasks, return_exceptions=True)

            for (idx, raw), lookup_result in zip(needs_lookup, lookup_results):
                ref_id = f"ref_{idx + 1:03d}"
                authors = [_normalise_author_name(a) for a in raw.authors]

                if isinstance(lookup_result, Exception):
                    logger.warning(
                        "CrossRef lookup failed for ref %s: %s", ref_id, lookup_result,
                    )
                    doi = None
                    status = ResolutionStatus.UNRESOLVED
                    source = ResolutionSource.NONE
                else:
                    doi, status, source, _sim = lookup_result

                # Update the raw ref's DOI if resolved
                confidence = _compute_ref_confidence(raw, status)

                sro_ref = SROReference(
                    ref_id=ref_id,
                    raw_text=raw.raw_text,
                    resolution_status=status,
                    ref_confidence=confidence,
                    title=raw.title,
                    authors=authors,
                    year=raw.year,
                    venue=raw.venue,
                    doi=doi if doi else raw.doi,
                    url=raw.url,
                    resolution_source=source,
                )
                results.append(sro_ref)
    elif needs_lookup and not config.enabled:
        # CrossRef disabled — mark as unresolved
        for idx, raw in needs_lookup:
            ref_id = f"ref_{idx + 1:03d}"
            authors = [_normalise_author_name(a) for a in raw.authors]
            confidence = _compute_ref_confidence(raw, ResolutionStatus.UNRESOLVED)
            sro_ref = SROReference(
                ref_id=ref_id,
                raw_text=raw.raw_text,
                resolution_status=ResolutionStatus.UNRESOLVED,
                ref_confidence=confidence,
                title=raw.title,
                authors=authors,
                year=raw.year,
                venue=raw.venue,
                doi=None,
                url=raw.url,
                resolution_source=ResolutionSource.NONE,
            )
            results.append(sro_ref)

    # Sort by original index order (ref_id encodes index)
    results.sort(key=lambda r: r.ref_id)

    resolved_count = sum(1 for r in results if r.resolution_status == ResolutionStatus.RESOLVED)
    ambiguous_count = sum(1 for r in results if r.resolution_status == ResolutionStatus.AMBIGUOUS)
    logger.info(
        "Reference resolution complete: %d resolved, %d ambiguous, %d unresolved out of %d",
        resolved_count, ambiguous_count, total - resolved_count - ambiguous_count, total,
    )

    return results


# ---------------------------------------------------------------------------
# Public API (sync wrapper)
# ---------------------------------------------------------------------------


def resolve_references(
    raw_refs: list[RawReference],
    config: CrossRefConfig,
) -> list[SROReference]:
    """Resolve raw bibliography entries into SROReference objects.

    This is the synchronous entry point for the pipeline. It creates or reuses
    an event loop to run the async CrossRef lookups.

    Parameters
    ----------
    raw_refs:
        Raw bibliography entries from the extraction stage.
    config:
        CrossRef configuration (enable/disable, rate limit, mailto).

    Returns
    -------
    list[SROReference]
        Resolved reference objects with DOIs and confidence scores.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already inside an async context — create a new thread to avoid
        # nesting event loops (common in Jupyter or async frameworks).
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                asyncio.run, _resolve_references_async(raw_refs, config),
            )
            return future.result()
    else:
        return asyncio.run(_resolve_references_async(raw_refs, config))
