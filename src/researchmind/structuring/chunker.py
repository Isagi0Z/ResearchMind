"""Chunker — splits section content into paragraph-level retrieval units.

Produces ``SROChunk`` objects that serve as the atomic retrieval units for
downstream modules.  Chunks never cross section boundaries.  Small paragraphs
are merged with their neighbours; large paragraphs are split at sentence
boundaries using NLTK's Punkt tokenizer.
"""

from __future__ import annotations

import logging
import re

from researchmind.models.enums import ExtractionMethod
from researchmind.models.intermediates import ChunkingConfig
from researchmind.models.sro import SROChunk, SROSection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# NLTK sentence tokenizer (lazy init)
# ---------------------------------------------------------------------------

_sentence_tokenizer = None


def _get_sentence_tokenizer():
    """Lazily initialise the NLTK Punkt sentence tokenizer.

    Falls back to regex sentence splitting if NLTK data is unavailable.
    """
    global _sentence_tokenizer
    if _sentence_tokenizer is not None:
        return _sentence_tokenizer

    import nltk  # type: ignore[import-untyped]

    try:
        _sentence_tokenizer = nltk.data.load("tokenizers/punkt/english.pickle")
    except Exception as exc:
        logger.warning(
            "NLTK Punkt tokenizer unavailable; using regex fallback: %s", exc
        )
        _sentence_tokenizer = False

    return _sentence_tokenizer


def _sent_tokenize(text: str) -> list[str]:
    """Sentence-tokenize *text* using the cached Punkt model."""
    tokenizer = _get_sentence_tokenizer()
    if tokenizer:
        return tokenizer.tokenize(text)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def _word_count(text: str) -> int:
    """Count words by splitting on whitespace."""
    return len(text.split())


def _split_paragraphs(content: str) -> list[str]:
    """Split section content into paragraphs on double-newlines.

    Preserves paragraph ordering and strips empty entries.
    """
    raw = content.split("\n\n")
    paragraphs = [p.strip() for p in raw if p.strip()]
    return paragraphs


def _merge_small_paragraphs(
    paragraphs: list[str],
    min_words: int,
) -> list[str]:
    """Merge consecutive paragraphs that are below ``min_words``.

    A paragraph that is the *only* paragraph in its section is never merged
    (handled by the caller by not merging single-element lists).
    """
    if len(paragraphs) <= 1:
        return paragraphs

    merged: list[str] = []
    buffer: str = ""

    for para in paragraphs:
        if buffer:
            combined = buffer + "\n\n" + para
            if _word_count(buffer) < min_words:
                # Continue merging
                buffer = combined
            else:
                merged.append(buffer)
                buffer = para
        else:
            buffer = para

    if buffer:
        # If the trailing buffer is still small and we have previous chunks,
        # merge it into the last one.
        if _word_count(buffer) < min_words and merged:
            merged[-1] = merged[-1] + "\n\n" + buffer
        else:
            merged.append(buffer)

    return merged


def _split_large_paragraph(
    text: str,
    max_words: int,
) -> list[str]:
    """Split a paragraph that exceeds ``max_words`` at sentence boundaries.

    Returns a list of sub-chunks, each at or below ``max_words`` (best-effort;
    a single very long sentence will not be broken mid-sentence).
    """
    sentences = _sent_tokenize(text)
    if not sentences:
        return [text]

    sub_chunks: list[str] = []
    current: list[str] = []
    current_wc = 0

    for sent in sentences:
        sent_wc = _word_count(sent)

        if current_wc + sent_wc > max_words and current:
            sub_chunks.append(" ".join(current))
            current = [sent]
            current_wc = sent_wc
        else:
            current.append(sent)
            current_wc += sent_wc

    if current:
        sub_chunks.append(" ".join(current))

    return sub_chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def chunk_sections(
    sections: list[SROSection],
    config: ChunkingConfig,
    section_methods: dict[str, ExtractionMethod] | None = None,
) -> list[SROChunk]:
    """Split sections into paragraph-level SROChunk objects.

    Parameters
    ----------
    sections:
        Normalised sections from the section normalizer.
    config:
        Chunking configuration (``min_words``, ``max_words``).
    section_methods:
        Optional section_id -> extraction method map from the raw extractor.

    Returns
    -------
    list[SROChunk]
        Paragraph-level chunks with global reading order.
    """
    if not sections:
        logger.warning("No sections provided for chunking")
        return []

    min_words = config.min_words
    max_words = config.max_words
    section_methods = section_methods or {}

    all_chunks: list[SROChunk] = []
    global_reading_order = 0
    chunk_counter = 0

    for section in sections:
        # Split into paragraphs
        paragraphs = _split_paragraphs(section.content)

        if not paragraphs:
            logger.debug(
                "Section %s (%s) has no paragraphs — skipping",
                section.section_id, section.canonical_label.value,
            )
            continue

        # Merge small paragraphs
        paragraphs = _merge_small_paragraphs(paragraphs, min_words)

        # Split large paragraphs at sentence boundaries
        final_paragraphs: list[str] = []
        for para in paragraphs:
            if _word_count(para) > max_words:
                sub_chunks = _split_large_paragraph(para, max_words)
                final_paragraphs.extend(sub_chunks)
            else:
                final_paragraphs.append(para)

        # Create SROChunk for each final paragraph
        for para_idx, para_text in enumerate(final_paragraphs):
            wc = _word_count(para_text)
            if wc == 0:
                continue

            chunk_id = f"chk_{chunk_counter:03d}"
            chunk_counter += 1

            try:
                extraction_method = section_methods.get(
                    section.section_id, ExtractionMethod.GROBID
                )
                chunk = SROChunk(
                    chunk_id=chunk_id,
                    text=para_text,
                    word_count=wc,
                    section_id=section.section_id,
                    canonical_label=section.canonical_label,
                    page_start=section.page_start,
                    page_end=section.page_end,
                    paragraph_index=para_idx,
                    reading_order=global_reading_order,
                    extraction_method=extraction_method,
                    extraction_confidence=section.label_confidence,
                )
                all_chunks.append(chunk)
                global_reading_order += 1
            except Exception:
                logger.exception(
                    "Failed to create SROChunk for section %s, paragraph %d",
                    section.section_id, para_idx,
                )

    logger.info(
        "Chunking complete: %d chunks from %d sections (min_words=%d, max_words=%d)",
        len(all_chunks), len(sections), min_words, max_words,
    )
    return all_chunks
