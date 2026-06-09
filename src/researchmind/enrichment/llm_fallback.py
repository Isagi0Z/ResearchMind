"""LLM fallback utilities for header classification and author normalization.

Uses Google Gemini (via ``google.genai``) for tasks where rule-based
approaches fail. All calls degrade gracefully: if the API key is missing,
the library is not installed, or the API returns an error, functions
return safe defaults and log warnings.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from researchmind.models.enums import CanonicalLabel
from researchmind.models.intermediates import LLMFallbackConfig
from researchmind.models.sro import SROLLMCall

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical labels as a string set for validation
# ---------------------------------------------------------------------------
_VALID_LABELS: set[str] = {label.value for label in CanonicalLabel}

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_HEADER_CLASSIFICATION_PROMPT = """\
You are a scientific-paper section classifier. Given a list of section headers \
from a research paper, classify each one into exactly one of these canonical labels:

{labels}

Respond ONLY with a JSON array of objects, one per header, in the same order \
as the input. Each object must have two keys:
- "label": one of the canonical labels above (lowercase string)
- "confidence": a float between 0.0 and 1.0

Input headers (one per line):
{headers}

JSON response:"""

_AUTHOR_NORMALIZATION_PROMPT = """\
You are a bibliographic metadata specialist. Given the following list of \
author name strings extracted from a research paper PDF, normalize each name \
to the format "Given Name Surname" (Western order). Fix OCR artifacts, remove \
extra whitespace, correct obvious misspellings, and separate conjoined names. \
If a name is already correct, return it unchanged.

Respond ONLY with a JSON array of strings, one normalized name per input, \
in the same order as the input.

Input names (one per line):
{names}

JSON response:"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_api_key(config: LLMFallbackConfig) -> str | None:
    """Retrieve the Gemini API key from the environment."""
    key = os.environ.get(config.api_key_env, "").strip()
    if not key:
        logger.warning(
            "Environment variable '%s' is not set — LLM fallback disabled",
            config.api_key_env,
        )
        return None
    return key


def _call_gemini(
    prompt: str,
    config: LLMFallbackConfig,
    purpose: str,
) -> tuple[str | None, SROLLMCall | None]:
    """Call the Gemini API and return (response_text, llm_call_log).

    Returns (None, log) on any failure so callers can fall back.
    """
    api_key = _get_api_key(config)
    if api_key is None:
        return None, None

    try:
        from google import genai  # type: ignore[import-untyped]
    except ImportError:
        logger.warning(
            "google-genai package is not installed — LLM fallback disabled"
        )
        return None, None

    timestamp = datetime.now(tz=timezone.utc)
    input_tokens = 0
    output_tokens = 0

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=config.model,
            contents=prompt,
        )

        response_text = response.text or ""

        # Extract token counts from usage metadata if available
        usage: Any = getattr(response, "usage_metadata", None)
        if usage is not None:
            input_tokens = getattr(usage, "prompt_token_count", 0) or 0
            output_tokens = getattr(usage, "candidates_token_count", 0) or 0

        llm_call = SROLLMCall(
            purpose=purpose,
            model=config.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            timestamp=timestamp,
        )

        logger.info(
            "LLM call '%s' succeeded: %d input tokens, %d output tokens",
            purpose,
            input_tokens,
            output_tokens,
        )
        return response_text, llm_call

    except Exception:
        logger.warning(
            "Gemini API call failed for '%s' — falling back to defaults",
            purpose,
            exc_info=True,
        )
        # Still log the failed call
        llm_call = SROLLMCall(
            purpose=f"{purpose} (failed)",
            model=config.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            timestamp=timestamp,
        )
        return None, llm_call


def _parse_json_response(text: str) -> Any | None:
    """Best-effort parse a JSON response, stripping markdown fences."""
    cleaned = text.strip()
    # Remove markdown code fences if present
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Drop first and last lines (``` markers)
        lines = [
            line for line in lines
            if not line.strip().startswith("```")
        ]
        cleaned = "\n".join(lines).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM JSON response: %.200s", cleaned)
        return None


# ---------------------------------------------------------------------------
# Module-level list collecting LLM call logs
# ---------------------------------------------------------------------------
_llm_call_log: list[SROLLMCall] = []


def get_llm_call_log() -> list[SROLLMCall]:
    """Return and clear the accumulated LLM call log entries.

    This allows the pipeline orchestrator to collect log entries
    after calling the LLM fallback functions.
    """
    entries = list(_llm_call_log)
    _llm_call_log.clear()
    return entries


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_headers_with_llm(
    headers: list[str],
    config: LLMFallbackConfig,
) -> list[tuple[str, float]]:
    """Classify section headers into canonical labels using Gemini.

    Parameters
    ----------
    headers:
        Raw section header strings to classify.
    config:
        LLM fallback configuration (model name, API key env var, etc.).

    Returns
    -------
    list[tuple[str, float]]
        A list of (canonical_label, confidence) tuples, one per header.
        Falls back to ``("other", 0.3)`` for each header on any failure.
    """
    fallback = [("other", 0.3)] * len(headers)

    if not headers:
        return []

    if not config.enabled:
        logger.info("LLM fallback is disabled — returning default labels")
        return fallback

    labels_str = ", ".join(sorted(_VALID_LABELS))
    headers_str = "\n".join(f"- {h}" for h in headers)

    prompt = _HEADER_CLASSIFICATION_PROMPT.format(
        labels=labels_str,
        headers=headers_str,
    )

    response_text, llm_call = _call_gemini(
        prompt, config, purpose="header_classification"
    )
    if llm_call is not None:
        _llm_call_log.append(llm_call)

    if response_text is None:
        return fallback

    parsed = _parse_json_response(response_text)
    if not isinstance(parsed, list):
        logger.warning(
            "LLM header classification returned non-list — using fallback"
        )
        return fallback

    results: list[tuple[str, float]] = []
    for i, header in enumerate(headers):
        if i < len(parsed) and isinstance(parsed[i], dict):
            item = parsed[i]
            label = str(item.get("label", "other")).lower().strip()
            confidence = float(item.get("confidence", 0.5))

            # Validate the label
            if label not in _VALID_LABELS:
                logger.debug(
                    "LLM returned invalid label '%s' for header '%s' "
                    "— defaulting to 'other'",
                    label,
                    header,
                )
                label = "other"

            # Clamp confidence
            confidence = max(0.0, min(1.0, confidence))
            results.append((label, confidence))
        else:
            results.append(("other", 0.3))

    return results


def normalize_author_names_with_llm(
    names: list[str],
    config: LLMFallbackConfig,
) -> list[str]:
    """Normalize author names using Gemini.

    Parameters
    ----------
    names:
        Raw author name strings potentially containing OCR artifacts,
        unusual formatting, or concatenated names.
    config:
        LLM fallback configuration.

    Returns
    -------
    list[str]
        Cleaned author name strings.  On failure, returns the input
        names unchanged.
    """
    if not names:
        return []

    if not config.enabled:
        logger.info(
            "LLM fallback is disabled — returning author names unchanged"
        )
        return list(names)

    names_str = "\n".join(f"- {n}" for n in names)
    prompt = _AUTHOR_NORMALIZATION_PROMPT.format(names=names_str)

    response_text, llm_call = _call_gemini(
        prompt, config, purpose="author_name_normalization"
    )
    if llm_call is not None:
        _llm_call_log.append(llm_call)

    if response_text is None:
        return list(names)

    parsed = _parse_json_response(response_text)
    if not isinstance(parsed, list):
        logger.warning(
            "LLM author normalization returned non-list — returning originals"
        )
        return list(names)

    results: list[str] = []
    for i, original in enumerate(names):
        if i < len(parsed) and isinstance(parsed[i], str):
            cleaned = parsed[i].strip()
            results.append(cleaned if cleaned else original)
        else:
            results.append(original)

    logger.info(
        "Author name normalization complete: %d names processed", len(results)
    )
    return results
