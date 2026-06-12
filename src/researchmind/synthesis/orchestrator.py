"""Review Orchestrator — top-level pipeline for Module 6.

Runs the 8-stage synthesis pipeline:
1. Theme Detection
2. Evidence Collection
3. Finding Generation
4. Group Findings
5. Section Building
6. Traceability Verification
7. Confidence Computation
8. Final Assembly

Never raises — failures are captured in ReviewResult.warnings / errors.
"""

from __future__ import annotations

from typing import Any

from researchmind.synthesis.confidence import ConfidenceComputer
from researchmind.synthesis.evidence_collector import EvidenceCollector
from researchmind.synthesis.finding_generator import FindingGenerator
from researchmind.synthesis.models import (
    ReviewFinding,
    ReviewRequest,
    ReviewResult,
    ReviewSection,
    ReviewType,
    _SECTION_REQUIREMENTS,
    _generate_id,
)
from researchmind.synthesis.section_builder import SectionBuilder
from researchmind.synthesis.theme_detector import ThemeDetector
from researchmind.synthesis.traceability import TraceabilityVerifier


class ReviewOrchestrator:
    """Top-level orchestrator for Module 6."""

    def __init__(
        self,
        corpus_manager: Any,
        graph: Any,
        consensus_engine: Any = None,
        contradiction_engine: Any = None,
        gap_engine: Any = None,
        multi_hop_reasoner: Any = None,
        document_store: Any = None,
    ) -> None:
        self._corpus_manager = corpus_manager
        self._graph = graph
        self._consensus = consensus_engine
        self._contradiction = contradiction_engine
        self._gap = gap_engine
        self._multi_hop = multi_hop_reasoner
        self._document_store = document_store

    def generate(self, request: ReviewRequest) -> ReviewResult:
        """Generate a literature review from a ReviewRequest.

        Runs the full 8-stage pipeline. Never raises — failures
        are captured in ReviewResult.warnings / errors.
        """
        warnings: list[str] = []
        errors: list[str] = []

        max_themes = getattr(request, "max_themes", None)
        if not isinstance(max_themes, int) or max_themes < 1:
            max_themes = 20

        max_findings_per_section = getattr(
            request, "max_findings_per_section", None
        )
        if not isinstance(max_findings_per_section, int) or max_findings_per_section < 1:
            max_findings_per_section = 50

        min_confidence = getattr(request, "min_confidence", 0.3)
        if not isinstance(min_confidence, (int, float)):
            min_confidence = 0.3

        corpus_metadata = getattr(request, "metadata", {})
        if not isinstance(corpus_metadata, dict):
            corpus_metadata = {}

        chunk_index = getattr(request, "chunk_index", None)

        review_id = getattr(request, "review_id", "")
        if not isinstance(review_id, str):
            review_id = ""
        raw_review_type = getattr(request, "review_type", "general")
        title = getattr(request, "title", "")

        if not isinstance(raw_review_type, str) or not raw_review_type.strip():
            review_type = "general"
        else:
            normalized_rt = raw_review_type.strip().lower()
            known_types = {rt.value for rt in ReviewType}
            if normalized_rt in known_types:
                review_type = normalized_rt
            else:
                warnings.append(
                    f"Unknown review_type '{raw_review_type}', "
                    f"defaulting to 'general'"
                )
                review_type = "general"

        # ---- Stage 1: Theme Detection ----
        theme_detector = ThemeDetector()
        try:
            themes = theme_detector.detect_themes(
                self._graph,
                max_themes=max_themes,
            )
        except Exception as exc:
            warnings.append(f"Theme detection failed: {exc}")
            themes = []

        if not isinstance(themes, list):
            themes = []

        # ---- Stage 2: Evidence Collection ----
        evidence_collector = EvidenceCollector()
        try:
            bundles = evidence_collector.collect(
                self._corpus_manager,
                self._graph,
                themes,
                min_confidence=min_confidence,
            )
        except Exception as exc:
            warnings.append(f"Evidence collection failed: {exc}")
            bundles = []

        if not isinstance(bundles, list):
            bundles = []

        # ---- Stage 3: Finding Generation ----
        finding_generator = FindingGenerator()
        all_findings: list[ReviewFinding] = []
        try:
            bundle_by_theme: dict[str, list] = {}
            for b in bundles:
                theme_label = getattr(b, "theme", None)
                if theme_label is None:
                    theme_label = getattr(b, "metadata", {}).get("theme_label", "")
                if not isinstance(theme_label, str):
                    theme_label = ""
                bundle_by_theme.setdefault(theme_label, []).append(b)

            for theme in themes:
                theme_label = getattr(theme, "label", "") or ""
                theme_bundles = bundle_by_theme.get(theme_label, [])
                try:
                    findings = finding_generator.generate_findings(
                        theme,
                        theme_bundles,
                        max_findings_per_section=max_findings_per_section,
                    )
                    if isinstance(findings, list):
                        all_findings.extend(findings)
                except Exception as exc:
                    warnings.append(
                        f"Finding generation for theme '{theme_label}' failed: {exc}"
                    )
        except Exception as exc:
            warnings.append(f"Finding generation failed: {exc}")

        # ---- Stage 4: Group Findings ----
        findings_by_type: dict[str, list[ReviewFinding]] = {
            "supporting": [],
            "consensus": [],
            "contradiction": [],
            "gap": [],
            "relation": [],
        }
        try:
            for f in all_findings:
                ft = getattr(f, "finding_type", "") or ""
                normalized = ft.strip().lower()
                if normalized in findings_by_type:
                    findings_by_type[normalized].append(f)
                else:
                    findings_by_type["supporting"].append(f)

            for key in findings_by_type:
                findings_by_type[key].sort(
                    key=lambda x: (
                        -getattr(x, "confidence", 0.0),
                        getattr(x, "finding_id", ""),
                    )
                )
        except Exception as exc:
            warnings.append(f"Finding grouping failed: {exc}")

        # ---- Stage 5: Section Building ----
        section_builder = SectionBuilder()
        try:
            sections = section_builder.build_sections(
                review_type,
                findings_by_type,
                corpus_metadata=corpus_metadata,
                max_findings=max_findings_per_section,
            )
        except Exception as exc:
            warnings.append(f"Section building failed: {exc}")
            sections = []

        if not isinstance(sections, list):
            sections = []

        # ---- Stage 6: Traceability Verification ----
        traceability_verifier = TraceabilityVerifier()
        traceability_failures = 0
        try:
            review_stub = self._build_stub_review(
                review_id, review_type, title, sections,
            )
            is_valid, trace_warnings = traceability_verifier.verify_review(
                review_stub,
                self._corpus_manager,
                chunk_index=chunk_index,
            )
            warnings.extend(trace_warnings)
            if not is_valid:
                traceability_failures = sum(
                    1 for w in trace_warnings
                    if "missing" in w or "requires" in w or "invalid" in w
                )
        except Exception as exc:
            warnings.append(f"Traceability verification failed: {exc}")

        # ---- Stage 7: Confidence Computation ----
        confidence_computer = ConfidenceComputer()
        try:
            mandatory, _ = _SECTION_REQUIREMENTS.get(
                review_type.strip().lower(), ([], [])
            )
            review_confidence = confidence_computer.compute_review_confidence(
                sections,
                mandatory,
                traceability_failures=traceability_failures,
            )
        except Exception as exc:
            warnings.append(f"Confidence computation failed: {exc}")
            review_confidence = 0.0

        # ---- Stage 8: Final Assembly ----
        try:
            total_findings = sum(len(s.findings) for s in sections)
        except Exception:
            total_findings = 0

        try:
            total_words = sum(
                getattr(s, "word_count", 0) for s in sections
            )
        except Exception:
            total_words = 0

        abstract = ""
        try:
            if sections:
                first = sections[0]
                if getattr(first, "section_type", "") == "abstract":
                    abstract = getattr(first, "content", "") or getattr(first, "summary", "") or ""
        except Exception:
            abstract = ""

        if not abstract and sections:
            abstract = "A review of the literature."

        warnings.sort()

        result = ReviewResult(
            review_id=review_id,
            review_type=review_type,
            title=title or "Literature Review",
            abstract=abstract,
            sections=sections,
            total_findings=total_findings,
            total_words=total_words,
            confidence=review_confidence,
            traceability_verified=(traceability_failures == 0),
            traceability_failures=[],
            warnings=warnings,
            errors=errors,
            metadata={
                "pipeline_version": "1.0",
                "max_themes": max_themes,
                "max_findings_per_section": max_findings_per_section,
                "min_confidence": min_confidence,
            },
        )

        return result

    @staticmethod
    def _build_stub_review(
        review_id: str,
        review_type: str,
        title: str,
        sections: list[ReviewSection],
    ) -> ReviewResult:
        total_f = sum(len(s.findings) for s in sections)
        total_w = sum(s.word_count for s in sections)
        return ReviewResult(
            review_id=review_id,
            review_type=review_type,
            title=title or "Review",
            abstract="A review of the literature." if sections else "",
            sections=sections,
            total_findings=total_f,
            total_words=total_w,
        )


def generate_review(
    orchestrator: ReviewOrchestrator,
    request: ReviewRequest,
) -> ReviewResult:
    """Convenience helper for review generation."""
    return orchestrator.generate(request)
