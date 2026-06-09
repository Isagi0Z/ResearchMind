"""Quality layer — confidence scoring and SRO validation.

This package provides Stage 6 (quality assessment) of the ResearchMind
ingestion pipeline: per-field confidence scoring, overall quality
computation, structural validation, and derived-index population.
"""

from researchmind.quality.confidence_scorer import compute_quality
from researchmind.quality.validator import compute_derived_indices, validate_sro

__all__ = [
    "compute_quality",
    "validate_sro",
    "compute_derived_indices",
]
