"""Entity resolution for RUOCorpus — deterministic cross-document entity merging."""

from researchmind.corpus.entity_resolution import (
    DEFAULT_FUZZY_THRESHOLD,
    LABEL_COMPATIBILITY,
    CanonicalEntity,
    EntityAlias,
    EntityCluster,
    EntityResolver,
    ResolutionResult,
    normalize_entity_text,
)

__all__ = [
    "DEFAULT_FUZZY_THRESHOLD",
    "LABEL_COMPATIBILITY",
    "CanonicalEntity",
    "EntityAlias",
    "EntityCluster",
    "EntityResolver",
    "ResolutionResult",
    "normalize_entity_text",
]
