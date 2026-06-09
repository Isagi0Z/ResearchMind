"""Understanding Engine — fact extraction, triple extraction,
evidence/provenance, and knowledge graph.
"""

from researchmind.understanding.evidence_builder import (
    EvidenceBuildResult,
    build_evidence,
)
from researchmind.understanding.fact_extractor import (
    ExtractedFact,
    FactExtractionResult,
    FactType,
    extract_facts,
)
from researchmind.understanding.knowledge_graph import (
    GraphEdge,
    GraphNode,
    GraphPath,
    GraphQuery,
    GraphStatistics,
    KnowledgeGraph,
    KnowledgeGraphBuilder,
    Subgraph,
    build_knowledge_graph,
)
from researchmind.understanding.triple_extractor import (
    TripleExtractionResult,
    extract_triples,
)

__all__ = [
    "EvidenceBuildResult",
    "ExtractedFact",
    "FactExtractionResult",
    "FactType",
    "GraphEdge",
    "GraphNode",
    "GraphPath",
    "GraphQuery",
    "GraphStatistics",
    "KnowledgeGraph",
    "KnowledgeGraphBuilder",
    "Subgraph",
    "TripleExtractionResult",
    "build_evidence",
    "build_knowledge_graph",
    "extract_facts",
    "extract_triples",
]
