"""Finding Generator — deterministic template-driven findings.

Transforms ThemeCluster + EvidenceBundle inputs into ReviewFinding objects.
Template-only — no LLMs, no free-form generation.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from researchmind.query.models import AggregatedEvidence
from researchmind.synthesis.models import (
    EvidenceBundle,
    ReviewFinding,
    ThemeCluster,
    _generate_id,
)

_EVIDENCE_TYPE_MAP: dict[str, str] = {
    "fact": "supporting",
    "claim": "supporting",
    "path_edge": "supporting",
    "consensus_entry": "consensus",
    "contradiction": "contradiction",
    "gap_item": "gap",
    "semantic_triple": "relation",
}

_FINDING_TEMPLATES: dict[str, str] = {
    "supporting": "Evidence suggests that {theme_label} is associated with {summary}.",
    "consensus": "Sources show consensus regarding {theme_label}.",
    "contradiction": "Conflicting evidence exists regarding {theme_label}.",
    "gap": "Limited evidence exists for {theme_label}.",
    "relation": "Relationships involving {theme_label} were identified.",
}


def _categorize(evidence_type: str) -> str:
    return _EVIDENCE_TYPE_MAP.get(evidence_type, "supporting")


def _extract_summary(items: list[AggregatedEvidence]) -> str:
    if not items:
        return "unknown evidence"
    best = max(items, key=lambda e: (e.confidence, len(e.source_text), e.evidence_id))
    text = best.source_text or "unknown evidence"
    text = " ".join(text.split())
    if len(text) > 80:
        text = text[:80].rstrip() + "..."
    return text


def _make_statement(finding_type: str, theme_label: str, summary: str) -> str:
    template = _FINDING_TEMPLATES.get(finding_type, _FINDING_TEMPLATES["supporting"])
    return template.format(theme_label=theme_label, summary=summary)


class FindingGenerator:
    """Generates evidence-backed findings using deterministic templates."""

    def __init__(self) -> None:
        pass

    def generate_findings(
        self,
        theme: ThemeCluster,
        evidence_bundles: list[EvidenceBundle],
        max_findings_per_section: int = 20,
    ) -> list[ReviewFinding]:
        """Generate findings for a single theme.

        Parameters
        ----------
        theme : ThemeCluster
            The target theme for finding generation.
        evidence_bundles : list[EvidenceBundle]
            Collected evidence bundles for the theme.
        max_findings_per_section : int
            Maximum number of findings to return.

        Returns
        -------
        list[ReviewFinding]
            Generated findings sorted by confidence desc,
            evidence count desc, statement asc.
        """
        if theme is None:
            return []

        theme_label = theme.label or ""
        if not theme_label:
            return []

        all_evidence: list[AggregatedEvidence] = []
        for bundle in evidence_bundles or []:
            if bundle.evidence_count == 0:
                continue
            all_evidence.extend(bundle.evidence_items or [])

        if not all_evidence:
            return []

        categorized: dict[str, list[AggregatedEvidence]] = defaultdict(list)
        for ev in all_evidence:
            etype = getattr(ev, "evidence_type", "") or ""
            cat = _categorize(etype)
            categorized[cat].append(ev)

        findings: list[ReviewFinding] = []
        for finding_type, ev_list in categorized.items():
            if not ev_list:
                continue

            summary = _extract_summary(ev_list)
            statement = _make_statement(finding_type, theme_label, summary)
            confidence = max(e.confidence for e in ev_list)
            confidence = max(0.0, min(1.0, confidence))

            evidence_ids: list[str] = sorted({
                e.evidence_id for e in ev_list if e.evidence_id
            })
            source_doc_ids: list[str] = sorted({
                e.source_document_id for e in ev_list if e.source_document_id
            })
            traces: list[str] = []
            for e in ev_list:
                traces.extend(getattr(e, "trace", []) or [])
            traces = sorted(set(traces))

            finding_id = _generate_id(
                "finding",
                theme.cluster_id or theme_label,
                finding_type,
            )

            supporting = len(ev_list)
            finding = ReviewFinding(
                finding_id=finding_id,
                finding_type=finding_type,
                statement=statement,
                confidence=confidence,
                evidence_ids=evidence_ids,
                source_document_ids=source_doc_ids,
                supporting_count=supporting,
                trace=traces,
                metadata={
                    "theme_label": theme_label,
                    "theme_type": theme.theme_type or "",
                    "evidence_count": len(ev_list),
                },
            )
            findings.append(finding)

        findings = _deduplicate(findings)
        findings.sort(key=lambda f: (-f.confidence, -f.supporting_count, f.statement))

        return findings[:max_findings_per_section]


def _deduplicate(findings: list[ReviewFinding]) -> list[ReviewFinding]:
    seen: dict[str, ReviewFinding] = {}
    for f in findings:
        key = f"{f.statement}||{'|'.join(sorted(f.evidence_ids))}"
        existing = seen.get(key)
        if existing is None or f.confidence > existing.confidence:
            seen[key] = f
    return list(seen.values())


def generate_findings(
    theme: ThemeCluster,
    evidence_bundles: list[EvidenceBundle],
    max_findings_per_section: int = 20,
) -> list[ReviewFinding]:
    """Convenience helper for finding generation.

    See :meth:`FindingGenerator.generate_findings`.
    """
    return FindingGenerator().generate_findings(
        theme=theme,
        evidence_bundles=evidence_bundles,
        max_findings_per_section=max_findings_per_section,
    )
