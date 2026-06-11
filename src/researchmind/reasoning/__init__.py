"""ResearchMind Reasoning Engine (Module 4).

Deterministic multi-hop reasoning, consensus analysis, contradiction
detection, research gap analysis, and cross-engine synthesis — all
operating over a CorpusGraph without LLMs, embeddings, or external APIs.
"""

from researchmind.reasoning.models import (
    AnswerEvidence,
    ConsensusResult,
    ContradictionResult,
    DirectContradiction,
    DocumentConsensusEntry,
    GapAnalysisResult,
    GapItem,
    GapType,
    IndirectContradiction,
    QueryType,
    ReasoningQuery,
    ReasoningResult,
    ReasoningStep,
)
from researchmind.reasoning.engine import ReasoningEngine
from researchmind.reasoning.multi_hop import MultiHopReasoner
from researchmind.reasoning.consensus import ConsensusEngine
from researchmind.reasoning.contradiction import ContradictionEngine
from researchmind.reasoning.gaps import ResearchGapEngine
from researchmind.reasoning.synthesis import CorpusSynthesisEngine

__all__ = [
    # Models
    "QueryType",
    "GapType",
    "ReasoningQuery",
    "ReasoningResult",
    "AnswerEvidence",
    "ReasoningStep",
    "ConsensusResult",
    "DocumentConsensusEntry",
    "ContradictionResult",
    "DirectContradiction",
    "IndirectContradiction",
    "GapAnalysisResult",
    "GapItem",
    # Engines
    "ReasoningEngine",
    "MultiHopReasoner",
    "ConsensusEngine",
    "ContradictionEngine",
    "ResearchGapEngine",
    "CorpusSynthesisEngine",
]
