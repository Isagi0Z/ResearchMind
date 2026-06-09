"""Enrichment layer — NER extraction, claim detection, and LLM fallback utilities.

This package provides Stage 4 (enrichment) of the ResearchMind ingestion
pipeline: named-entity recognition, candidate claim detection, and optional
LLM-based header classification and author normalization.
"""

from researchmind.enrichment.claim_detector import detect_claims
from researchmind.enrichment.llm_fallback import (
    classify_headers_with_llm,
    normalize_author_names_with_llm,
)
from researchmind.enrichment.ner_extractor import extract_entities

__all__ = [
    "extract_entities",
    "detect_claims",
    "classify_headers_with_llm",
    "normalize_author_names_with_llm",
]
