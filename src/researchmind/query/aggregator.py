"""Evidence aggregation engine for the Research Assistant Layer (Module 5).

Collects raw evidence from executed PlanStep results, deduplicates, ranks,
applies confidence downgrades, detects anomalies, and produces a clean,
ranked list of AggregatedEvidence objects for Answer Synthesis.

Architecture coverage: Section 7 (Evidence Aggregation), Section 10.4
(Confidence Downgrades), Section 10.5 (No-Evidence Policy).
"""

from __future__ import annotations

from typing import Any

from researchmind.query.models import (
    AggregatedEvidence,
    PlanResult,
)

# ---------------------------------------------------------------------------
# No-evidence policy (architecture 10.5)
# ---------------------------------------------------------------------------

_NO_EVIDENCE_RESPONSE = (
    "Insufficient evidence to answer this query. "
    "The corpus does not contain documents that address this question."
)

# ---------------------------------------------------------------------------
# Evidence ranker (architecture 7.3)
# ---------------------------------------------------------------------------


class EvidenceRanker:
    """Ranks evidence by confidence, document attribution, and trace quality."""

    def rank(self, evidence: list[AggregatedEvidence]) -> list[AggregatedEvidence]:
        """Sort evidence descending by composite score."""
        evidence.sort(key=self._score, reverse=True)
        return evidence

    @staticmethod
    def _score(e: AggregatedEvidence) -> float:
        s = e.confidence
        if e.evidence_type == "path_edge":
            s += 0.1
        if e.source_document_id:
            s += 0.05
        if not e.source_text:
            s -= 0.2
        if not e.trace:
            s -= 0.3
        return max(s, 0.0)


# ---------------------------------------------------------------------------
# Evidence aggregator (architecture 7)
# ---------------------------------------------------------------------------


class EvidenceAggregator:
    """Collects, deduplicates, ranks, and validates evidence from PlanStep results."""

    def __init__(self) -> None:
        self.ranker = EvidenceRanker()

    # ---- Public API -------------------------------------------------------

    def aggregate(
        self,
        plan_result: PlanResult,
    ) -> list[AggregatedEvidence]:
        """Produce a clean, ranked list of aggregated evidence.

        Pipeline:
          1. Collect raw evidence from all step results
          2. Apply confidence downgrades
          3. Deduplicate by multiple keys
          4. Rank by composite score
          5. Detect and handle anomalies
        """
        raw = self._collect(plan_result)
        downgraded = self._apply_downgrades(raw)
        deduped = self._deduplicate(downgraded)
        ranked = self.ranker.rank(deduped)
        cleaned = self._detect_anomalies(ranked)
        return cleaned

    def compute_confidence(
        self, evidence: list[AggregatedEvidence]
    ) -> float:
        """Compute overall confidence from a set of aggregated evidence.

        Uses the weakest-evidence-bounds-answer rule (architecture 8.4).
        Returns 0.0 for empty evidence (no-evidence policy).
        """
        if not evidence:
            return 0.0
        return min(e.confidence for e in evidence)

    # ---- Step 1: Collect --------------------------------------------------

    def _collect(
        self, plan_result: PlanResult
    ) -> list[AggregatedEvidence]:
        """Extract AggregatedEvidence objects from all step results.

        Handles multiple result formats:
        - A single AggregatedEvidence
        - A list of AggregatedEvidence
        - A dict with AggregatedEvidence-compatible keys
        - A list of dicts
        """
        result: list[AggregatedEvidence] = []
        for step_result in plan_result.step_results.values():
            extracted = self._extract_from_step(step_result)
            result.extend(extracted)
        return result

    def _extract_from_step(
        self, step_result: Any
    ) -> list[AggregatedEvidence]:
        """Normalize a single step result into a list of evidence items."""
        if step_result is None:
            return []
        if isinstance(step_result, AggregatedEvidence):
            return [step_result]
        if isinstance(step_result, list):
            items: list[AggregatedEvidence] = []
            for item in step_result:
                items.extend(self._extract_from_step(item))
            return items
        if isinstance(step_result, dict):
            try:
                return [AggregatedEvidence(**step_result)]
            except (TypeError, ValueError):
                return []
        return []

    # ---- Step 2: Confidence downgrades (architecture 10.4) ----------------

    def _apply_downgrades(
        self, evidence: list[AggregatedEvidence]
    ) -> list[AggregatedEvidence]:
        """Apply confidence penalties based on evidence quality."""
        result = []
        for e in evidence:
            c = e.confidence
            if not e.source_document_id:
                c *= 0.5
            if not e.trace:
                c *= 0.8
            if e.metadata.get("source_type") == "derived":
                c *= 0.9
            if e.evidence_type == "gap_item":
                c *= 0.7
            if len(e.trace) > 2:
                c *= 0.9 ** (len(e.trace) - 2)
            downgraded = e.model_copy(update={"confidence": max(min(round(c, 4), 1.0), 0.0)})
            result.append(downgraded)
        return result

    # ---- Step 3: Deduplication (architecture 7.4) -------------------------

    def _deduplicate(
        self, evidence: list[AggregatedEvidence]
    ) -> list[AggregatedEvidence]:
        """Remove duplicate evidence by multiple dedup keys.

        Priority order of dedup rules:
          1. evidence_id exact match
          2. (source_document_id, relation_type) per-query
          3. (node_id, gap_type) gap-only
          4. (claim_a, claim_b) contradiction-only
          5. Normalized source text
        """
        if not evidence:
            return []

        seen_ids: set[str] = set()
        seen_doc_rel: set[tuple[str, str]] = set()
        seen_gap: set[tuple[str, str]] = set()
        seen_contra: set[tuple[str, str]] = set()
        seen_text: set[str] = set()

        # Start with highest-confidence items first for deterministic results
        sorted_ev = sorted(evidence, key=lambda e: e.confidence, reverse=True)
        result: list[AggregatedEvidence] = []

        for e in sorted_ev:
            # Rule 1: evidence_id
            if e.evidence_id:
                if e.evidence_id in seen_ids:
                    continue
                seen_ids.add(e.evidence_id)

            # Rule 2: (source_document_id, relation_type)
            if e.source_document_id and e.relation_type:
                key = (e.source_document_id, e.relation_type)
                if key in seen_doc_rel:
                    continue
                seen_doc_rel.add(key)

            # Rule 3: Gap-only (node_id, gap_type)
            if e.evidence_type == "gap_item":
                node_id = e.metadata.get("node_id", "")
                gap_type = e.metadata.get("gap_type", "")
                if node_id and gap_type:
                    gap_key = (node_id, gap_type)
                    if gap_key in seen_gap:
                        continue
                    seen_gap.add(gap_key)

            # Rule 4: Contradiction-only (claim_a_document, claim_b_document)
            if e.evidence_type == "contradiction":
                claim_a = e.metadata.get("claim_a_document", "")
                claim_b = e.metadata.get("claim_b_document", "")
                if claim_a and claim_b:
                    contra_key = (claim_a, claim_b)
                    if contra_key in seen_contra:
                        continue
                    seen_contra.add(contra_key)

            # Rule 5: Normalized source text
            if e.source_text:
                norm = self._normalize_text(e.source_text)
                if norm in seen_text:
                    continue
                seen_text.add(norm)

            result.append(e)

        return result

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text for dedup comparison."""
        return " ".join(text.lower().split())

    # ---- Step 4: Anomaly detection (architecture 7.5) ---------------------

    def _detect_anomalies(
        self, evidence: list[AggregatedEvidence]
    ) -> list[AggregatedEvidence]:
        """Detect and handle anomalous evidence."""
        result = []
        for e in evidence:
            # Break circular evidence chains
            e = self._break_cycle(e)

            # Empty evidence_ids on high-confidence edges
            if (
                e.evidence_type in ("path_edge",)
                and e.confidence > 0
                and not e.metadata.get("evidence_ids")
            ):
                e = e.model_copy(
                    update={"confidence": max(0.0, round(e.confidence - 0.1, 4))}
                )

            result.append(e)
        return result

    @staticmethod
    def _break_cycle(
        e: AggregatedEvidence,
    ) -> AggregatedEvidence:
        """Break circular reference chains in evidence trace."""
        if not e.trace:
            return e
        seen: set[str] = set()
        new_trace: list[str] = []
        for tid in e.trace:
            if tid in seen:
                continue
            seen.add(tid)
            new_trace.append(tid)
        if len(new_trace) != len(e.trace):
            return e.model_copy(update={"trace": new_trace})
        return e

    # ---- Introspection ----------------------------------------------------

    @staticmethod
    def no_evidence_response() -> str:
        """Return the standard no-evidence response string."""
        return _NO_EVIDENCE_RESPONSE

    @staticmethod
    def check_no_evidence(
        evidence: list[AggregatedEvidence], min_confidence: float = 0.0
    ) -> bool:
        """Check if evidence is effectively empty (below threshold)."""
        if not evidence:
            return True
        if all(e.confidence < min_confidence for e in evidence):
            return True
        return False
