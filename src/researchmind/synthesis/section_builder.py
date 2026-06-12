"""Section Builder — construct review sections from findings.

Assembles mandatory and optional sections per ReviewType,
composes content, computes statistics, and enforces ordering.
"""

from __future__ import annotations

from typing import Any

from researchmind.synthesis.models import (
    ReviewFinding,
    ReviewSection,
    ReviewType,
    _SECTION_ORDER,
    _SECTION_REQUIREMENTS,
    _SECTION_TITLES,
    _generate_id,
)

_SECTION_FINDING_MAP: dict[str, set[str]] = {
    "abstract": set(),
    "introduction": set(),
    "conclusion": set(),
    "consensus": {"consensus"},
    "contradictions": {"contradiction"},
    "research_gaps": {"gap"},
    "methods_landscape": {"supporting", "relation"},
    "datasets": {"supporting", "relation"},
    "comparative": {"supporting", "contradiction"},
    "future_work": {"supporting", "gap"},
}

_CONTENT_TEMPLATES: dict[str, str] = {
    "abstract": "This review examines {review_type} evidence across {document_count} documents.",
    "introduction": "This section introduces the review context and scope.",
    "methods_landscape": "{n} findings were identified.",
    "datasets": "{n} findings were identified.",
    "consensus": "Consensus evidence was identified.",
    "contradictions": "Contradictory evidence was identified.",
    "comparative": "{n} findings were identified.",
    "research_gaps": "Research gaps were identified.",
    "future_work": "Future work directions were identified.",
    "conclusion": "The evidence reviewed supports the findings summarized above.",
}

_FALLBACK_TEMPLATE = "Section generated from available findings."


def _assign_findings(
    section_type: str,
    findings_by_type: dict[str, list[ReviewFinding]],
) -> list[ReviewFinding]:
    allowed = _SECTION_FINDING_MAP.get(section_type)
    if allowed is None:
        result: list[ReviewFinding] = []
        for flist in findings_by_type.values():
            result.extend(flist)
        return result
    if not allowed:
        return []
    result: list[ReviewFinding] = []
    for ft in allowed:
        flist = findings_by_type.get(ft, [])
        result.extend(flist)
    return result


def _make_content(section_type: str, n: int, review_type: str, document_count: int) -> str:
    template = _CONTENT_TEMPLATES.get(section_type, _FALLBACK_TEMPLATE)
    try:
        return template.format(n=n, review_type=review_type, document_count=document_count)
    except (KeyError, ValueError):
        return _FALLBACK_TEMPLATE


def _make_paragraphs(findings: list[ReviewFinding]) -> list[str]:
    return [f.statement for f in findings]


def _compute_confidence(findings: list[ReviewFinding]) -> float:
    if not findings:
        return 0.0
    return max(0.0, min(1.0, min(f.confidence for f in findings)))


def _compute_statistics(
    findings: list[ReviewFinding],
) -> dict[str, int]:
    evidence_ids: set[str] = set()
    doc_ids: set[str] = set()
    for f in findings:
        evidence_ids.update(f.evidence_ids)
        doc_ids.update(f.source_document_ids)
    return {
        "finding_count": len(findings),
        "evidence_count": len(evidence_ids),
        "document_count": len(doc_ids),
    }


class SectionBuilder:
    """Builds review sections from findings for a given ReviewType."""

    def __init__(self) -> None:
        pass

    def build_sections(
        self,
        review_type: str,
        findings_by_type: dict[str, list[ReviewFinding]],
        corpus_metadata: dict[str, Any] | None = None,
        max_findings: int = 50,
    ) -> list[ReviewSection]:
        """Build review sections for a given ReviewType.

        Parameters
        ----------
        review_type : str
            Review type string (e.g. "general", "method").
        findings_by_type : dict[str, list[ReviewFinding]]
            Findings grouped by finding type.
        corpus_metadata : dict or None
            Optional corpus-level metadata.
        max_findings : int
            Maximum findings per section.

        Returns
        -------
        list[ReviewSection]
            Sections in document order.
        """
        if not review_type:
            return []

        normalized_type = review_type.strip().lower()
        known = {rt.value for rt in ReviewType}
        if normalized_type not in known:
            return []

        requirements = _SECTION_REQUIREMENTS.get(normalized_type)
        if requirements is None:
            return []

        mandatory, optional = requirements
        all_section_types = mandatory + optional

        fbt = findings_by_type or {}
        meta = corpus_metadata or {}
        document_count = meta.get("document_count", 0)

        sections: list[ReviewSection] = []
        for section_type in _SECTION_ORDER:
            if section_type not in all_section_types:
                continue

            findings = _assign_findings(section_type, fbt)
            capped = findings[:max_findings]

            n = len(capped)
            content = _make_content(section_type, n, normalized_type, document_count)
            paragraphs = _make_paragraphs(capped)
            confidence = _compute_confidence(capped)
            statistics = _compute_statistics(capped)

            title = _SECTION_TITLES.get(section_type, section_type.replace("_", " ").title())
            section_id = _generate_id("section", normalized_type, section_type)

            is_mandatory = section_type in mandatory

            section = ReviewSection(
                section_id=section_id,
                section_type=section_type,
                title=title,
                content=content,
                findings=capped,
                paragraphs=paragraphs,
                confidence=confidence,
                word_count=len(content.split()) + sum(len(p.split()) for p in paragraphs),
                is_mandatory=is_mandatory,
                statistics=statistics,
                metadata={
                    "review_type": normalized_type,
                    "section_index": _SECTION_ORDER.index(section_type),
                },
            )
            sections.append(section)

        return sections


def build_sections(
    review_type: str,
    findings_by_type: dict[str, list[ReviewFinding]],
    corpus_metadata: dict[str, Any] | None = None,
    max_findings: int = 50,
) -> list[ReviewSection]:
    """Convenience helper for section building.

    See :meth:`SectionBuilder.build_sections`.
    """
    return SectionBuilder().build_sections(
        review_type=review_type,
        findings_by_type=findings_by_type,
        corpus_metadata=corpus_metadata,
        max_findings=max_findings,
    )
