"""ResearchMind Synthesis Engine (Module 6).

Literature review generation — theme detection, evidence collection,
finding generation, section construction, traceability verification,
confidence scoring, and pipeline orchestration.
"""

from researchmind.synthesis.models import (
    EvidenceBundle,
    ReviewFinding,
    ReviewRequest,
    ReviewResult,
    ReviewSection,
    ReviewType,
    ThemeCluster,
    ThemeType,
    _SECTION_ORDER,
    _SECTION_REQUIREMENTS,
    _SECTION_TITLES,
    _generate_id,
)
from researchmind.synthesis.orchestrator import ReviewOrchestrator
from researchmind.synthesis.theme_detector import ThemeDetector
from researchmind.synthesis.evidence_collector import EvidenceCollector
from researchmind.synthesis.finding_generator import FindingGenerator
from researchmind.synthesis.section_builder import SectionBuilder
from researchmind.synthesis.traceability import TraceabilityVerifier
from researchmind.synthesis.confidence import ConfidenceComputer

__all__ = [
    "ReviewType",
    "ThemeType",
    "ReviewRequest",
    "ReviewFinding",
    "ReviewSection",
    "ReviewResult",
    "EvidenceBundle",
    "ThemeCluster",
    "ReviewOrchestrator",
    "ThemeDetector",
    "EvidenceCollector",
    "FindingGenerator",
    "SectionBuilder",
    "TraceabilityVerifier",
    "ConfidenceComputer",
    "_generate_id",
    "_SECTION_ORDER",
    "_SECTION_REQUIREMENTS",
    "_SECTION_TITLES",
]
