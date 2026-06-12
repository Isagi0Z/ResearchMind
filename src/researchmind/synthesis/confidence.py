"""Confidence Computer — deterministic confidence at finding, section, and review level.

All values clamped to [0.0, 1.0].
"""

from __future__ import annotations

from typing import Any

from researchmind.synthesis.models import ReviewFinding, ReviewSection


def _clamp(value: float) -> float:
    if not isinstance(value, (int, float)):
        return 0.5
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


class ConfidenceComputer:
    """Computes deterministic confidence scores for findings, sections, and reviews."""

    def __init__(self) -> None:
        pass

    def compute_finding_confidence(
        self,
        finding_type: str,
        data: dict[str, Any],
    ) -> float:
        """Compute finding confidence using type-specific formula.

        Parameters
        ----------
        finding_type : str
            One of: consensus, contradiction, gap, method, dataset, relation, supporting.
        data : dict
            Type-specific keys for computation.

        Returns
        -------
        float
            Confidence clamped to [0.0, 1.0].
        """
        normalized = finding_type.strip().lower()

        if not normalized:
            return _clamp(data.get("confidence", 0.5))

        if normalized == "consensus":
            return _clamp(data.get("consensus_confidence", 0.5))

        if normalized == "contradiction":
            return _clamp(data.get("aggregate_confidence", 0.5))

        if normalized == "gap":
            return self._compute_gap_confidence(data)

        if normalized == "method":
            return self._compute_method_confidence(data)

        if normalized == "dataset":
            return self._compute_dataset_confidence(data)

        if normalized == "relation":
            return _clamp(data.get("edge_confidence", 0.5))

        return _clamp(data.get("confidence", 0.5))

    @staticmethod
    def _compute_gap_confidence(data: dict[str, Any]) -> float:
        gap_type = data.get("gap_type", "isolated")

        if gap_type in ("isolated", "missing"):
            return _clamp(data.get("gap_confidence", 0.5))

        if gap_type == "low_confidence":
            claim_conf = data.get("claim_confidence", 0.5)
            return _clamp(1.0 - claim_conf)

        if gap_type == "under_study":
            doc_count = data.get("doc_count", 0)
            threshold = data.get("doc_threshold", 1)
            ratio = doc_count / max(1, threshold)
            return _clamp(1.0 - min(1.0, ratio))

        if gap_type == "unconnected":
            entity_count = data.get("entity_count", 0)
            max_count = data.get("max_entity_count", 1)
            val = entity_count / max(1, max_count)
            return _clamp(min(1.0, val))

        return _clamp(data.get("gap_confidence", 0.5))

    @staticmethod
    def _compute_method_confidence(data: dict[str, Any]) -> float:
        edges = data.get("entity_edges", [])
        if not edges:
            return _clamp(data.get("confidence", 0.5))
        confs = [e["confidence"] for e in edges if isinstance(e, dict) and "confidence" in e]
        if not confs:
            return _clamp(data.get("confidence", 0.5))
        return _clamp(max(confs))

    @staticmethod
    def _compute_dataset_confidence(data: dict[str, Any]) -> float:
        edges = data.get("entity_edges", [])
        if not edges:
            return _clamp(data.get("confidence", 0.5))
        confs = [e["confidence"] for e in edges if isinstance(e, dict) and "confidence" in e]
        if not confs:
            return _clamp(data.get("confidence", 0.5))
        mean = sum(confs) / len(confs)
        return _clamp(mean)

    def compute_section_confidence(
        self,
        findings: list[ReviewFinding],
    ) -> float:
        """Section confidence = min(finding.confidence).

        Empty findings returns 0.0.
        """
        if not findings:
            return 0.0
        confs = [
            f.confidence for f in findings
            if hasattr(f, "confidence") and isinstance(f.confidence, (int, float))
        ]
        if not confs:
            return 0.0
        return _clamp(min(confs))

    def compute_review_confidence(
        self,
        sections: list[ReviewSection],
        mandatory_types: list[str],
        traceability_failures: int = 0,
    ) -> float:
        """Compute overall review confidence.

        base = min(section.confidence for mandatory sections with findings)
        if traceability_failures > 0: base *= 0.9 ** traceability_failures
        return max(0.0, base)
        """
        mandatory_set = {t.strip().lower() for t in mandatory_types}
        confs: list[float] = []
        for sec in sections:
            sec_type = (getattr(sec, "section_type", "") or "").strip().lower()
            findings = getattr(sec, "findings", None) or []
            if sec_type in mandatory_set and findings:
                sec_conf = getattr(sec, "confidence", 0.0)
                if isinstance(sec_conf, (int, float)):
                    confs.append(sec_conf)

        if not confs:
            base = 0.0
        else:
            base = _clamp(min(confs))

        if traceability_failures > 0:
            base *= 0.9 ** traceability_failures

        return max(0.0, base)


def compute_finding_confidence(
    finding_type: str,
    data: dict[str, Any],
) -> float:
    return ConfidenceComputer().compute_finding_confidence(
        finding_type=finding_type, data=data,
    )


def compute_section_confidence(
    findings: list[ReviewFinding],
) -> float:
    return ConfidenceComputer().compute_section_confidence(findings=findings)


def compute_review_confidence(
    sections: list[ReviewSection],
    mandatory_types: list[str],
    traceability_failures: int = 0,
) -> float:
    return ConfidenceComputer().compute_review_confidence(
        sections=sections,
        mandatory_types=mandatory_types,
        traceability_failures=traceability_failures,
    )
