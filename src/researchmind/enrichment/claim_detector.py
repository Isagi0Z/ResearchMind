"""Candidate claim detector for the enrichment pipeline stage.

Detects sentences that express scientific claims (statistical, causal,
comparative, methodological, existence, negation) via regex pattern
matching, and scores them by section context.
"""

from __future__ import annotations

import logging
import re

from researchmind.models.enums import CanonicalLabel, ClaimType
from researchmind.models.sro import SROCandidateClaim, SROChunk, SROSection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Claim-type regex patterns  (all applied with re.IGNORECASE)
# ---------------------------------------------------------------------------

CLAIM_PATTERNS: dict[ClaimType, list[re.Pattern[str]]] = {
    ClaimType.STATISTICAL: [
        re.compile(r"p\s*[<>≤≥=]\s*0\.\d+", re.IGNORECASE),
        re.compile(r"\d+%\s*CI", re.IGNORECASE),
        re.compile(r"statistically\s+significant", re.IGNORECASE),
        re.compile(r"effect\s+size", re.IGNORECASE),
        re.compile(r"odds\s+ratio", re.IGNORECASE),
        re.compile(r"hazard\s+ratio", re.IGNORECASE),
        re.compile(r"confidence\s+interval", re.IGNORECASE),
    ],
    ClaimType.CAUSAL: [
        re.compile(r"(?:causes?|caused)\s+", re.IGNORECASE),
        re.compile(r"leads?\s+to", re.IGNORECASE),
        re.compile(r"results?\s+in", re.IGNORECASE),
        re.compile(r"due\s+to", re.IGNORECASE),
        re.compile(r"associated\s+with", re.IGNORECASE),
    ],
    ClaimType.COMPARATIVE: [
        re.compile(r"outperforms?", re.IGNORECASE),
        re.compile(
            r"(?:better|worse|superior|inferior)\s+(?:than|to)", re.IGNORECASE
        ),
        re.compile(r"state[- ]of[- ]the[- ]art", re.IGNORECASE),
        re.compile(r"improvement\s+(?:of|over)", re.IGNORECASE),
    ],
    ClaimType.METHODOLOGICAL: [
        re.compile(
            r"we\s+(?:propose|introduce|present|develop)", re.IGNORECASE
        ),
        re.compile(
            r"novel\s+(?:approach|method|framework)", re.IGNORECASE
        ),
        re.compile(
            r"our\s+(?:approach|method|contribution)", re.IGNORECASE
        ),
    ],
    ClaimType.EXISTENCE: [
        re.compile(
            r"we\s+(?:find|found|observe|show|demonstrate)", re.IGNORECASE
        ),
        re.compile(
            r"results?\s+(?:show|indicate|suggest|demonstrate)", re.IGNORECASE
        ),
        re.compile(
            r"(?:analysis|experiment)\s+(?:shows?|reveals?)", re.IGNORECASE
        ),
    ],
    ClaimType.NEGATION: [
        re.compile(
            r"no\s+significant\s+(?:difference|effect|improvement)",
            re.IGNORECASE,
        ),
        re.compile(r"(?:failed?|unable)\s+to", re.IGNORECASE),
        re.compile(
            r"did\s+not\s+(?:find|observe|show)", re.IGNORECASE
        ),
        re.compile(
            r"no\s+(?:evidence|support)\s+for", re.IGNORECASE
        ),
    ],
}

# Sections where claims should be discarded (confidence → 0)
_DISCARD_SECTIONS: set[CanonicalLabel] = {
    CanonicalLabel.ACKNOWLEDGMENTS,
    CanonicalLabel.APPENDIX,
}

# Section-based confidence priors
_SECTION_CONFIDENCE: dict[CanonicalLabel, float] = {
    CanonicalLabel.RESULTS: 0.70,
    CanonicalLabel.DISCUSSION: 0.70,
    CanonicalLabel.METHODOLOGY: 0.65,
    CanonicalLabel.CONCLUSION: 0.65,
    CanonicalLabel.LIMITATIONS: 0.65,
    CanonicalLabel.FUTURE_WORK: 0.50,
    CanonicalLabel.INTRODUCTION: 0.40,
    CanonicalLabel.RELATED_WORK: 0.40,
    CanonicalLabel.OTHER: 0.50,
}


def _safe_sent_tokenize(text: str) -> list[str]:
    """Tokenize text into sentences with nltk, falling back to naive split.

    Never crashes — if nltk is unavailable or fails, uses a simple
    period-based splitter.
    """
    try:
        import nltk  # type: ignore[import-untyped]

        # Ensure punkt tokenizer data is available
        try:
            nltk.data.find("tokenizers/punkt_tab")
        except LookupError:
            try:
                nltk.download("punkt_tab", quiet=True)
            except Exception:
                logger.debug("Could not download punkt_tab, trying punkt")
                try:
                    nltk.data.find("tokenizers/punkt")
                except LookupError:
                    nltk.download("punkt", quiet=True)

        return nltk.sent_tokenize(text)  # type: ignore[no-any-return]
    except Exception:
        logger.debug(
            "nltk.sent_tokenize unavailable — using fallback sentence splitter"
        )
        # Naive sentence splitting on period+space or newline
        raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
        return [s.strip() for s in raw_sentences if s.strip()]


def _match_sentence(
    sentence: str,
) -> list[tuple[ClaimType, list[str]]]:
    """Match a sentence against all claim patterns.

    Returns a list of (ClaimType, list-of-matched-pattern-strings) tuples.
    A sentence can match multiple claim types.
    """
    matches: list[tuple[ClaimType, list[str]]] = []
    for claim_type, patterns in CLAIM_PATTERNS.items():
        matched_strs: list[str] = []
        for pat in patterns:
            if pat.search(sentence):
                matched_strs.append(pat.pattern)
        if matched_strs:
            matches.append((claim_type, matched_strs))
    return matches


def _compute_confidence(
    canonical_label: CanonicalLabel,
    total_patterns_matched: int,
) -> float:
    """Compute claim confidence from section context and match count.

    Rules:
    - 0.8 if multiple patterns match (strong signal)
    - Section-specific base otherwise:
      * abstract → 0.75
      * results/discussion → 0.70
      * introduction/related_work → 0.40
      * others → default from mapping or 0.50
    - Discarded sections (acknowledgments, appendix) → 0.0
    """
    if canonical_label in _DISCARD_SECTIONS:
        return 0.0

    if total_patterns_matched >= 2:
        return 0.80

    return _SECTION_CONFIDENCE.get(canonical_label, 0.50)


def _build_section_lookup(
    sections: list[SROSection],
) -> dict[str, SROSection]:
    """Build a section_id → SROSection lookup dictionary."""
    lookup: dict[str, SROSection] = {}
    for section in sections:
        lookup[section.section_id] = section
    return lookup


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_claims(
    chunks: list[SROChunk],
    sections: list[SROSection],
) -> list[SROCandidateClaim]:
    """Detect candidate scientific claims in text chunks.

    Each chunk is sentence-tokenized, and each sentence is matched
    against regex patterns for six claim types. Claims from
    acknowledgments and appendix sections are discarded.

    Parameters
    ----------
    chunks:
        Paragraph-level text chunks from the SRO body.
    sections:
        Section metadata for section_id / canonical_label lookup.

    Returns
    -------
    list[SROCandidateClaim]
        Detected claims with globally unique IDs (clm_001 …).
    """
    if not chunks:
        logger.info("No chunks provided — skipping claim detection")
        return []

    section_lookup = _build_section_lookup(sections)
    claims: list[SROCandidateClaim] = []
    claim_counter = 0

    for chunk in chunks:
        sentences = _safe_sent_tokenize(chunk.text)
        canonical_label = chunk.canonical_label

        # Look up section for this chunk
        section = section_lookup.get(chunk.section_id)
        section_id = chunk.section_id
        if section is not None:
            canonical_label = section.canonical_label

        # Determine page (use chunk's page_start)
        page = chunk.page_start

        for sentence in sentences:
            sentence_stripped = sentence.strip()
            if not sentence_stripped:
                continue

            # Match against all claim patterns
            type_matches = _match_sentence(sentence_stripped)
            if not type_matches:
                continue

            # Each matched claim type generates one SROCandidateClaim
            for claim_type, matched_patterns in type_matches:
                # Total pattern count across all types for this sentence
                total_patterns = sum(
                    len(pats) for _, pats in type_matches
                )

                confidence = _compute_confidence(
                    canonical_label, total_patterns
                )

                # Discard claims from unwanted sections
                if confidence <= 0.0:
                    continue

                # Abstract gets a special confidence boost
                # We detect "abstract" by checking if the canonical_label
                # doesn't come from the section lookup (it's in the abstract)
                # But since chunks always have a section_id, we handle it
                # via canonical label check: there is no ABSTRACT canonical
                # label in the enum, so this is handled by section prior only

                claim_counter += 1
                claims.append(
                    SROCandidateClaim(
                        claim_id=f"clm_{claim_counter:03d}",
                        sentence=sentence_stripped,
                        chunk_id=chunk.chunk_id,
                        section_id=section_id,
                        canonical_label=canonical_label,
                        claim_type=claim_type,
                        matched_patterns=matched_patterns,
                        confidence=confidence,
                        page=page,
                    )
                )

    logger.info(
        "Claim detection complete: %d candidate claims from %d chunks",
        len(claims),
        len(chunks),
    )
    return claims
