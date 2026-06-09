"""Structuring layer — transforms raw extraction outputs into normalised SRO components.

This package contains:
- section_normalizer: maps raw section headers to canonical labels
- reference_resolver: resolves bibliography entries via CrossRef
- citation_linker: links inline citations to resolved references
- chunker: splits section content into paragraph-level retrieval units
- table_figure_extractor: processes raw tables and figures into SRO models
"""

from researchmind.structuring.section_normalizer import normalize_sections
from researchmind.structuring.reference_resolver import resolve_references
from researchmind.structuring.citation_linker import link_citations
from researchmind.structuring.chunker import chunk_sections
from researchmind.structuring.table_figure_extractor import (
    process_tables,
    process_figures,
)

__all__ = [
    "normalize_sections",
    "resolve_references",
    "link_citations",
    "chunk_sections",
    "process_tables",
    "process_figures",
]
