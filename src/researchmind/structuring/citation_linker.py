"""Citation linker: maps inline citation markers to resolved references.

The linker preserves the SRO schema by emitting one SROCitation per citation
edge. A raw GROBID citation with multiple targets therefore becomes multiple
SROCitation rows, each with a single ref_id.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re

from researchmind.models.enums import CitationIntent
from researchmind.models.intermediates import RawCitation, RawReference
from researchmind.models.sro import SROChunk, SROCitation, SROReference, SROSection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Intent classification patterns
# ---------------------------------------------------------------------------

_INTENT_PATTERNS: dict[CitationIntent, list[re.Pattern[str]]] = {
    CitationIntent.SUPPORTS: [
        re.compile(r"consistent\s+with", re.IGNORECASE),
        re.compile(r"in\s+agreement\s+with", re.IGNORECASE),
        re.compile(r"confirms?", re.IGNORECASE),
        re.compile(r"corroborates?", re.IGNORECASE),
        re.compile(r"support(?:s|ed|ing)\s+by", re.IGNORECASE),
        re.compile(r"in\s+line\s+with", re.IGNORECASE),
        re.compile(r"aligns?\s+with", re.IGNORECASE),
    ],
    CitationIntent.CONTRASTS: [
        re.compile(r"unlike", re.IGNORECASE),
        re.compile(r"in\s+contrast\s+to", re.IGNORECASE),
        re.compile(r"contradicts?", re.IGNORECASE),
        re.compile(r"however.*found", re.IGNORECASE),
        re.compile(r"differs?\s+from", re.IGNORECASE),
        re.compile(r"disagrees?\s+with", re.IGNORECASE),
        re.compile(r"contrary\s+to", re.IGNORECASE),
        re.compile(r"inconsistent\s+with", re.IGNORECASE),
    ],
    CitationIntent.EXTENDS: [
        re.compile(r"extends?", re.IGNORECASE),
        re.compile(r"builds?\s+on", re.IGNORECASE),
        re.compile(r"expands?", re.IGNORECASE),
        re.compile(r"generaliz(?:es?|ing)", re.IGNORECASE),
        re.compile(r"improves?\s+(?:on|upon)", re.IGNORECASE),
    ],
    CitationIntent.USES_METHOD: [
        re.compile(r"using\s+the\s+method", re.IGNORECASE),
        re.compile(r"following\s+the\s+approach", re.IGNORECASE),
        re.compile(r"as\s+described\s+in", re.IGNORECASE),
        re.compile(r"adopt(?:s|ed|ing)\s+(?:the\s+)?(?:method|approach|technique)", re.IGNORECASE),
        re.compile(r"implemented\s+(?:as|in)", re.IGNORECASE),
        re.compile(r"based\s+on\s+the\s+(?:method|framework|approach)", re.IGNORECASE),
    ],
    CitationIntent.BACKGROUND: [
        re.compile(r"has\s+shown", re.IGNORECASE),
        re.compile(r"demonstrated", re.IGNORECASE),
        re.compile(r"established", re.IGNORECASE),
        re.compile(r"well\s+known", re.IGNORECASE),
        re.compile(r"widely\s+(?:used|adopted|accepted)", re.IGNORECASE),
        re.compile(r"previous(?:ly)?\s+(?:studied|investigated|reported)", re.IGNORECASE),
        re.compile(r"it\s+is\s+known\s+that", re.IGNORECASE),
    ],
    CitationIntent.COMPARES: [
        re.compile(r"compared\s+to", re.IGNORECASE),
        re.compile(r"comparison\s+with", re.IGNORECASE),
        re.compile(r"relative\s+to", re.IGNORECASE),
        re.compile(r"outperforms?", re.IGNORECASE),
        re.compile(r"as\s+opposed\s+to", re.IGNORECASE),
    ],
}


@dataclass
class _CitationDiagnostics:
    raw_citations: int = 0
    citation_edges: int = 0
    linked_edges: int = 0
    grobid_target_edges: int = 0
    regex_edges: int = 0
    text_similarity_edges: int = 0
    unlinked_edges: int = 0
    intent_edges: int = 0
    chunk_sentence_matches: int = 0
    chunk_paragraph_matches: int = 0
    chunk_overlap_matches: int = 0
    chunk_last_resort_matches: int = 0
    missing_chunks: int = 0
    missing_grobid_targets: int = 0


def _classify_intent(
    context_sentence: str,
) -> tuple[CitationIntent | None, float | None]:
    """Classify citation intent from the sentence containing the citation."""
    match_counts: dict[CitationIntent, int] = {}

    for intent, patterns in _INTENT_PATTERNS.items():
        count = sum(1 for pattern in patterns if pattern.search(context_sentence))
        if count > 0:
            match_counts[intent] = count

    if not match_counts:
        return None, None

    best_intent = max(match_counts, key=lambda key: match_counts[key])
    confidence = 0.75 if match_counts[best_intent] >= 2 else 0.60
    return best_intent, confidence


# ---------------------------------------------------------------------------
# Reference target resolution
# ---------------------------------------------------------------------------


def _build_grobid_to_refid_map(
    raw_refs: list[RawReference],
    sro_refs: list[SROReference],
) -> dict[str, str]:
    """Build a mapping from GROBID internal ref IDs to SROReference ref_ids."""
    sro_ref_ids = {ref.ref_id for ref in sro_refs}
    mapping: dict[str, str] = {}

    for idx, raw in enumerate(raw_refs):
        if not raw.grobid_id:
            continue
        ref_id = f"ref_{idx + 1:03d}"
        if ref_id in sro_ref_ids:
            mapping[raw.grobid_id] = ref_id
            logger.debug("GROBID target map: %s -> %s", raw.grobid_id, ref_id)

    logger.debug("Built GROBID target map with %d entries", len(mapping))
    return mapping


_NUMERIC_CITATION_RE = re.compile(r"\[(\d+)\]")
_NUMERIC_LIST_RE = re.compile(r"\[([0-9,\s\-]+)\]")
_AUTHOR_YEAR_RE = re.compile(
    r"\(?([A-Z][a-zA-Z''-]+(?:\s+(?:et\s+al\.?|&\s+[A-Z][a-zA-Z''-]+|and\s+[A-Z][a-zA-Z''-]+))?)"
    r",?\s*(\d{4})\)?",
)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _split_grobid_targets(target: str | None) -> list[str]:
    """Split a GROBID target string into individual bibliography IDs."""
    if not target:
        return []
    return [
        part.lstrip("#").strip()
        for part in re.split(r"[\s,;]+", target)
        if part.lstrip("#").strip()
    ]


def _parse_numeric_marker(marker: str) -> list[str]:
    """Parse numeric citation markers like ``[1, 3-5]`` into ref IDs."""
    match = _NUMERIC_LIST_RE.search(marker)
    if not match:
        return []

    ref_ids: list[str] = []
    for part in re.split(r"\s*,\s*", match.group(1).strip()):
        if not part:
            continue
        range_match = re.match(r"^(\d+)\s*-\s*(\d+)$", part)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            if start <= end and end - start <= 50:
                ref_ids.extend(f"ref_{num:03d}" for num in range(start, end + 1))
            continue
        if part.isdigit():
            ref_ids.append(f"ref_{int(part):03d}")

    return ref_ids


def _try_regex_fallbacks(
    marker: str,
    sro_refs: list[SROReference],
    raw_refs: list[RawReference],
) -> list[str]:
    """Attempt to link a citation marker to ref_ids using regex patterns."""
    linked: list[str] = []
    existing_ref_ids = {ref.ref_id for ref in sro_refs}

    for ref_id in _parse_numeric_marker(marker):
        if ref_id in existing_ref_ids:
            logger.debug("Regex fallback: '%s' -> %s (numeric)", marker, ref_id)
            linked.append(ref_id)

    if linked:
        return _dedupe_preserve_order(linked)

    numeric_match = _NUMERIC_CITATION_RE.search(marker)
    if numeric_match:
        ref_id = f"ref_{int(numeric_match.group(1)):03d}"
        if ref_id in existing_ref_ids:
            return [ref_id]

    for ay_match in _AUTHOR_YEAR_RE.finditer(marker):
        author_fragment = ay_match.group(1).lower().strip()
        year = ay_match.group(2)

        for ref in sro_refs:
            if ref.year != year or not ref.authors:
                continue
            for author in ref.authors:
                surname = author.split(",")[0].strip().lower()
                if surname and surname in author_fragment:
                    logger.debug("Regex fallback: '%s' -> %s (author-year)", marker, ref.ref_id)
                    linked.append(ref.ref_id)
                    break

    # raw_refs is kept in the signature because callers already pass it and it
    # can still contain useful ordering/author context in future local scoring.
    _ = raw_refs
    return _dedupe_preserve_order(linked)


def _try_text_similarity_fallback(
    raw_cit: RawCitation,
    references: list[SROReference],
) -> list[str]:
    """Attempt to resolve a citation by matching sentence context against
    reference titles and authors using rapidfuzz similarity.

    Only called as a last resort when GROBID targets, numeric markers,
    and author-year regex all fail.  The thresholds are deliberately
    conservative to avoid false positives.
    """
    from rapidfuzz import fuzz

    sentence = raw_cit.sentence
    if not sentence or len(sentence.strip()) < 20:
        return []

    norm_sentence = _normalise_text(sentence)

    candidates: list[tuple[str, float]] = []

    for ref in references:
        if not ref.title or len(ref.title) < 15:
            continue

        norm_title = _normalise_text(ref.title)
        title_score = fuzz.token_set_ratio(norm_sentence, norm_title) / 100.0

        has_author = bool(
            ref.authors
            and any(
                author.split(",")[0].strip().lower() in norm_sentence
                for author in ref.authors
            )
        )

        if title_score >= 0.92:
            candidates.append((ref.ref_id, title_score))
        elif title_score >= 0.85 and has_author:
            candidates.append((ref.ref_id, title_score))

    if not candidates:
        return []

    candidates.sort(key=lambda x: x[1], reverse=True)
    best_id, best_score = candidates[0]

    if len(candidates) == 1 or best_score - candidates[1][1] >= 0.05:
        return [best_id]

    return []


def _resolve_reference_ids(
    raw_cit: RawCitation,
    grobid_map: dict[str, str],
    references: list[SROReference],
    raw_refs: list[RawReference],
    diagnostics: _CitationDiagnostics,
) -> list[str | None]:
    """Resolve one raw citation into one or more SRO reference IDs."""
    ref_ids: list[str] = []

    for target_key in _split_grobid_targets(raw_cit.grobid_ref_target):
        ref_id = grobid_map.get(target_key)
        if ref_id is None:
            diagnostics.missing_grobid_targets += 1
            logger.debug("Citation target '%s' not found in reference map", target_key)
            continue
        ref_ids.append(ref_id)
        diagnostics.grobid_target_edges += 1
        logger.debug("Citation linked via GROBID target: %s -> %s", target_key, ref_id)

    if ref_ids:
        return _dedupe_preserve_order(ref_ids)

    if raw_cit.raw_marker:
        ref_ids = _try_regex_fallbacks(raw_cit.raw_marker, references, raw_refs)
        diagnostics.regex_edges += len(ref_ids)

    if ref_ids:
        return ref_ids

    ref_ids = _try_text_similarity_fallback(raw_cit, references)
    if ref_ids:
        diagnostics.text_similarity_edges += len(ref_ids)
        logger.debug(
            "Text-similarity fallback: marker='%s', sentence='%s' -> %s",
            raw_cit.raw_marker,
            raw_cit.sentence[:80],
            ref_ids,
        )

    if ref_ids:
        return ref_ids

    return [None]


# ---------------------------------------------------------------------------
# Chunk matching
# ---------------------------------------------------------------------------


def _normalise_text(text: str) -> str:
    return " ".join(text.split()).lower()


def _find_containing_chunk(
    sentence: str,
    chunks: list[SROChunk],
) -> SROChunk | None:
    """Find the chunk that contains the given sentence text."""
    if not sentence.strip():
        return None

    norm_sentence = _normalise_text(sentence)
    for chunk in chunks:
        if norm_sentence in _normalise_text(chunk.text):
            return chunk

    if len(norm_sentence) > 80:
        short = norm_sentence[:80]
        for chunk in chunks:
            if short in _normalise_text(chunk.text):
                return chunk

    return None


def _token_overlap_score(needle: str, haystack: str) -> float:
    needle_tokens = {
        token for token in re.findall(r"[a-z0-9]+", needle.lower()) if len(token) > 2
    }
    if not needle_tokens:
        return 0.0

    haystack_tokens = {
        token for token in re.findall(r"[a-z0-9]+", haystack.lower()) if len(token) > 2
    }
    if not haystack_tokens:
        return 0.0

    return len(needle_tokens & haystack_tokens) / len(needle_tokens)


def _find_best_chunk_by_overlap(
    sentence: str,
    chunks: list[SROChunk],
) -> SROChunk | None:
    if not sentence.strip() or not chunks:
        return None

    best_chunk: SROChunk | None = None
    best_score = 0.0
    for chunk in chunks:
        score = _token_overlap_score(sentence, chunk.text)
        if score > best_score:
            best_score = score
            best_chunk = chunk

    if best_chunk is not None and best_score >= 0.35:
        return best_chunk

    return None


def _find_containing_chunk_for_citation(
    raw_cit: RawCitation,
    chunks: list[SROChunk],
    section_map: dict[int, SROSection],
    diagnostics: _CitationDiagnostics,
) -> SROChunk | None:
    """Find the best chunk for a citation using section and paragraph context."""
    section = section_map.get(raw_cit.section_index)
    section_chunks = [
        chunk for chunk in chunks if section is not None and chunk.section_id == section.section_id
    ]
    candidates = section_chunks or chunks

    if raw_cit.sentence:
        containing_chunk = _find_containing_chunk(raw_cit.sentence, candidates)
        if containing_chunk is not None:
            diagnostics.chunk_sentence_matches += 1
            return containing_chunk

    paragraph_chunks = [
        chunk for chunk in section_chunks if chunk.paragraph_index == raw_cit.paragraph_index
    ]
    if paragraph_chunks:
        if raw_cit.raw_marker:
            marker = _normalise_text(raw_cit.raw_marker)
            for chunk in paragraph_chunks:
                if marker and marker in _normalise_text(chunk.text):
                    diagnostics.chunk_paragraph_matches += 1
                    return chunk
        diagnostics.chunk_paragraph_matches += 1
        return paragraph_chunks[0]

    containing_chunk = _find_best_chunk_by_overlap(raw_cit.sentence, candidates)
    if containing_chunk is not None:
        diagnostics.chunk_overlap_matches += 1
        return containing_chunk

    containing_chunk = _find_containing_chunk(raw_cit.sentence, chunks)
    if containing_chunk is not None:
        diagnostics.chunk_sentence_matches += 1
        return containing_chunk

    containing_chunk = _find_best_chunk_by_overlap(raw_cit.sentence, chunks)
    if containing_chunk is not None:
        diagnostics.chunk_overlap_matches += 1
        return containing_chunk

    if section_chunks:
        diagnostics.chunk_last_resort_matches += 1
        return section_chunks[0]

    if chunks:
        diagnostics.chunk_last_resort_matches += 1
        return chunks[0]

    diagnostics.missing_chunks += 1
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def link_citations(
    raw_citations: list[RawCitation],
    references: list[SROReference],
    chunks: list[SROChunk],
    sections: list[SROSection],
    raw_refs: list[RawReference],
) -> list[SROCitation]:
    """Link inline citations to resolved references and classify intent."""
    if not raw_citations:
        logger.info("No raw citations to link")
        return []

    grobid_map = _build_grobid_to_refid_map(raw_refs, references)
    section_map = {section.position: section for section in sections}
    diagnostics = _CitationDiagnostics(raw_citations=len(raw_citations))

    results: list[SROCitation] = []
    citation_counter = 1

    for raw_cit in raw_citations:
        ref_ids = _resolve_reference_ids(
            raw_cit=raw_cit,
            grobid_map=grobid_map,
            references=references,
            raw_refs=raw_refs,
            diagnostics=diagnostics,
        )

        containing_chunk = _find_containing_chunk_for_citation(
            raw_cit=raw_cit,
            chunks=chunks,
            section_map=section_map,
            diagnostics=diagnostics,
        )
        if containing_chunk is None:
            logger.warning("Citation marker '%s': no chunks available, skipping", raw_cit.raw_marker)
            continue

        context_sentence = raw_cit.sentence or containing_chunk.text[:200]
        intent: CitationIntent | None = None
        intent_confidence: float | None = None
        if context_sentence:
            intent, intent_confidence = _classify_intent(context_sentence)
            if intent is None and any(ref_id is not None for ref_id in ref_ids):
                intent = CitationIntent.BACKGROUND
                intent_confidence = 0.4

        for ref_id in ref_ids:
            citation_id = f"cit_{citation_counter:03d}"
            citation_counter += 1
            diagnostics.citation_edges += 1
            if ref_id is not None:
                diagnostics.linked_edges += 1
            else:
                diagnostics.unlinked_edges += 1
            if intent is not None:
                diagnostics.intent_edges += 1

            try:
                results.append(
                    SROCitation(
                        citation_id=citation_id,
                        ref_id=ref_id,
                        chunk_id=containing_chunk.chunk_id,
                        section_id=containing_chunk.section_id,
                        context_sentence=context_sentence,
                        page=containing_chunk.page_start,
                        citation_intent=intent,
                        intent_confidence=intent_confidence,
                    )
                )
            except Exception:
                logger.exception(
                    "Failed to create SROCitation for marker='%s', ref_id='%s'",
                    raw_cit.raw_marker,
                    ref_id,
                )

    logger.info(
        "Citation linking complete: raw=%d, edges=%d, linked=%d, unlinked=%d, "
        "grobid_edges=%d, regex_edges=%d, text_similarity_edges=%d, intents=%d",
        diagnostics.raw_citations,
        diagnostics.citation_edges,
        diagnostics.linked_edges,
        diagnostics.unlinked_edges,
        diagnostics.grobid_target_edges,
        diagnostics.regex_edges,
        diagnostics.text_similarity_edges,
        diagnostics.intent_edges,
    )
    logger.debug(
        "Citation chunk diagnostics: sentence=%d, paragraph=%d, overlap=%d, "
        "last_resort=%d, missing_chunks=%d, missing_targets=%d",
        diagnostics.chunk_sentence_matches,
        diagnostics.chunk_paragraph_matches,
        diagnostics.chunk_overlap_matches,
        diagnostics.chunk_last_resort_matches,
        diagnostics.missing_chunks,
        diagnostics.missing_grobid_targets,
    )
    return results
