"""Deterministic answer synthesizer for the Research Assistant Layer (Module 5).

Consumes ResearchQuery, ParsedQuery, ExecutionPlan, PlanResult, and
AggregatedEvidence[] to produce a ResearchAnswer with template-driven
text, confidence calculation, reasoning trace assembly, and traceability
enforcement.

Architecture coverage: Section 8 (Answer Synthesis), Section 9
(ResearchAnswer Model), Section 10 (Traceability Contract).

No execution, no corpus access, no graph traversal, no LLMs.
"""

from __future__ import annotations

import zlib
from typing import Any

from researchmind.query.models import (
    AggregatedEvidence,
    ExecutionPlan,
    ParsedQuery,
    PlanResult,
    PlanStep,
    ReasoningStep,
    ResearchAnswer,
    ResearchQuery,
)

# ---------------------------------------------------------------------------
# Architecture Section 8.2 — Template definitions
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, dict[str, str]] = {
    "FACTUAL": {
        "answer": (
            "{entity_label} is associated with {relation_type} to "
            "{related_entities} (confidence: {confidence:.2f})."
        ),
        "high_confidence": "{entity_label} {relation_type} {related_entities}.",
        "no_evidence": "No evidence found for {entity_label}.",
    },
    "COMPARISON": {
        "answer": (
            "Comparison of {entity_a} and {entity_b}:\n"
            "- Shared attributes: {shared}\n"
            "- Unique to {entity_a}: {unique_a}\n"
            "- Unique to {entity_b}: {unique_b}\n"
            "Overall confidence: {confidence:.2f}"
        ),
        "no_evidence": (
            "Insufficient evidence to compare {entity_a} and {entity_b}."
        ),
    },
    "EXPLANATION": {
        "answer": (
            "{entity} is described in {doc_count} document(s):\n"
            "{claims}"
        ),
        "no_evidence": "No explanatory evidence available for {entity}.",
    },
    "CONSENSUS": {
        "answer": (
            "Consensus analysis for {target_label} "
            "({total_docs} documents):\n"
            "- Support: {support_ratio:.0%} ({support_count} docs)\n"
            "- Contradict: {contradict_ratio:.0%} ({contradict_count} docs)\n"
            "- Neutral: {neutral_ratio:.0%} ({neutral_count} docs)\n"
            "Classification: {classification}\n"
            "Confidence: {confidence:.2f}"
        ),
        "insufficient": (
            "Insufficient evidence for consensus analysis of {target_label} "
            "(only {total_docs} document(s))."
        ),
    },
    "CONTRADICTION": {
        "answer": (
            "Contradiction analysis for {target_label}:\n"
            "- Direct contradictions: {direct_count}\n"
            "- Indirect contradictions: {indirect_count}\n"
            "- Aggregate confidence: {confidence:.2f}\n"
            "\nDetails:\n{details}"
        ),
        "none": "No contradictions found for {target_label}.",
    },
    "RESEARCH_GAP": {
        "answer": (
            "Gap analysis identified {total_gaps} gap(s):\n"
            "{gap_breakdown}\n"
            "{suggestions}"
        ),
        "none": "No research gaps identified in the current corpus.",
    },
    "MULTI_HOP": {
        "answer": (
            "Found {path_count} path(s) from {source} to {target}:\n"
            "{paths}\n"
            "Best path confidence: {confidence:.2f}"
        ),
        "no_path": "No path found from {source} to {target}.",
    },
    "EXPLORATION": {
        "answer": (
            "Exploration of {source_label} reveals "
            "{node_count} node(s) and {edge_count} edge(s).\n"
            "Key connections: {connections}"
        ),
        "empty": "No connections found for {source_label}.",
    },
}

_NO_EVIDENCE_ANSWER = (
    "Insufficient evidence to answer this query."
)

_FALLBACK_TEMPLATE = "Answer ({query_type}): {confidence:.2f} confidence based on {n} evidence item(s)."

_MAX_EVIDENCE_ITEMS = 10


# ---------------------------------------------------------------------------
# AnswerSynthesizer
# ---------------------------------------------------------------------------


class AnswerSynthesizer:
    """Deterministic answer assembly from aggregated evidence.

    Usage::

        synthesizer = AnswerSynthesizer()
        answer = synthesizer.synthesize(
            query, parsed_query, plan, plan_result, evidence,
        )
    """

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def synthesize(
        self,
        query: ResearchQuery,
        parsed_query: ParsedQuery,
        plan: ExecutionPlan,
        plan_result: PlanResult,
        evidence: list[AggregatedEvidence],
    ) -> ResearchAnswer:
        """Synthesize a complete ResearchAnswer from plan outputs.

        Pipeline:
          1. Select evidence (max 10, confidence > 0)
          2. Check no-evidence policy
          3. Traceability verification (remove untraceable items)
          4. Build reasoning trace from plan_result.step_results
          5. Compute confidence per query-type formula
          6. Apply traceability confidence downgrade
          7. Build answer text from query-type template
          8. Assemble final ResearchAnswer
        """
        # Step 1: Select evidence
        selected = self._select_evidence(evidence)

        # Step 2: No-evidence policy
        if not selected:
            return self._build_no_evidence_answer(query, plan, parsed_query, plan_result)

        # Step 3: Traceability verification
        verified, failures = self._verify_traceability(selected)
        if not verified:
            return self._build_no_evidence_answer(query, plan, parsed_query, plan_result)

        # Step 4: Reasoning trace
        reasoning_trace = self._build_reasoning_trace(plan_result)

        # Step 5: Compute confidence
        confidence = self._compute_confidence(parsed_query.query_type, verified)

        # Step 6: Apply traceability downgrade
        final_confidence = self._apply_downgrade(confidence, failures)

        # Step 7: Build answer text
        answer_text = self._build_answer_text(
            parsed_query, verified, final_confidence,
        )

        # Step 8: Assemble
        return self._assemble_answer(
            query=query,
            parsed_query=parsed_query,
            plan=plan,
            plan_result=plan_result,
            answer_text=answer_text,
            confidence=final_confidence,
            evidence=verified,
            reasoning_trace=reasoning_trace,
            failures=failures,
        )

    # ------------------------------------------------------------------
    # Evidence selection (max 10, confidence > 0, preserve order)
    # ------------------------------------------------------------------

    @staticmethod
    def _select_evidence(
        evidence: list[AggregatedEvidence],
    ) -> list[AggregatedEvidence]:
        return [e for e in evidence if e.confidence > 0][:_MAX_EVIDENCE_ITEMS]

    # ------------------------------------------------------------------
    # Traceability verification
    # ------------------------------------------------------------------

    @staticmethod
    def _verify_traceability(
        evidence: list[AggregatedEvidence],
    ) -> tuple[list[AggregatedEvidence], int]:
        """Verify every evidence item has source_document_id and trace.

        gap_item is exempt from both requirements (absence-of-evidence
        is inherently document-free).

        Returns ``(verified_list, failure_count)``.
        """
        verified: list[AggregatedEvidence] = []
        failures = 0

        for e in evidence:
            if e.evidence_type == "gap_item":
                verified.append(e)
                continue
            if not e.source_document_id or not e.trace:
                failures += 1
                continue
            verified.append(e)

        return verified, failures

    # ------------------------------------------------------------------
    # Reasoning trace assembly
    # ------------------------------------------------------------------

    def _build_reasoning_trace(
        self, plan_result: PlanResult,
    ) -> list[ReasoningStep]:
        """Build reasoning trace from PlanResult step_results.

        Preserves execution order (sorted by step_id).
        """
        trace: list[ReasoningStep] = []
        step_map = {s.step_id: s for s in plan_result.plan.steps}

        for step_id in sorted(plan_result.step_results.keys()):
            step = step_map.get(step_id)
            result = plan_result.step_results[step_id]
            conf = self._extract_step_confidence(result)
            ev_ids = self._extract_evidence_ids(result)

            trace.append(ReasoningStep(
                step_id=step_id,
                engine=step.engine if step else "unknown",
                description=(
                    f"{step.engine}:{step.query_type}"
                    if step else "unknown:unknown"
                ),
                confidence=conf,
                evidence_ids=ev_ids,
            ))

        return trace

    @staticmethod
    def _extract_step_confidence(result: Any) -> float:
        if result is None:
            return 0.0
        if isinstance(result, AggregatedEvidence):
            return result.confidence
        if isinstance(result, list):
            confs = [
                e.confidence for e in result
                if isinstance(e, AggregatedEvidence)
            ]
            return max(confs) if confs else 0.0
        if isinstance(result, dict):
            return float(result.get("confidence", 0.0))
        return 0.0

    @staticmethod
    def _extract_evidence_ids(result: Any) -> list[str]:
        if result is None:
            return []
        if isinstance(result, AggregatedEvidence):
            return [result.evidence_id] if result.evidence_id else []
        if isinstance(result, list):
            ids: list[str] = []
            for item in result:
                if isinstance(item, AggregatedEvidence) and item.evidence_id:
                    ids.append(item.evidence_id)
            return ids
        if isinstance(result, dict):
            eid = result.get("evidence_id", "")
            return [eid] if eid else []
        return []

    # ------------------------------------------------------------------
    # Confidence computation (architecture Section 8.4 / user formula spec)
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_confidence(
        query_type: str, evidence: list[AggregatedEvidence],
    ) -> float:
        if not evidence:
            return 0.0

        formulas = {
            "FACTUAL": AnswerSynthesizer._max_confidence,
            "EXPLANATION": AnswerSynthesizer._max_confidence,
            "COMPARISON": AnswerSynthesizer._mean_confidence,
            "CONSENSUS": AnswerSynthesizer._consensus_confidence,
            "CONTRADICTION": AnswerSynthesizer._contradiction_confidence,
            "RESEARCH_GAP": AnswerSynthesizer._gap_confidence,
            "MULTI_HOP": AnswerSynthesizer._max_confidence,
            "EXPLORATION": AnswerSynthesizer._mean_confidence,
        }
        fn = formulas.get(query_type, AnswerSynthesizer._max_confidence)
        return max(0.0, min(fn(evidence), 1.0))

    @staticmethod
    def _max_confidence(evidence: list[AggregatedEvidence]) -> float:
        return max(e.confidence for e in evidence)

    @staticmethod
    def _mean_confidence(evidence: list[AggregatedEvidence]) -> float:
        return sum(e.confidence for e in evidence) / len(evidence)

    @staticmethod
    def _consensus_confidence(
        evidence: list[AggregatedEvidence],
    ) -> float:
        consensus = [
            e for e in evidence if e.evidence_type == "consensus_entry"
        ]
        if consensus:
            return max(e.confidence for e in consensus)
        return AnswerSynthesizer._max_confidence(evidence)

    @staticmethod
    def _contradiction_confidence(
        evidence: list[AggregatedEvidence],
    ) -> float:
        contradictions = [
            e for e in evidence if e.evidence_type == "contradiction"
        ]
        if contradictions:
            return max(e.confidence for e in contradictions)
        return AnswerSynthesizer._max_confidence(evidence)

    @staticmethod
    def _gap_confidence(evidence: list[AggregatedEvidence]) -> float:
        gaps = [e for e in evidence if e.evidence_type == "gap_item"]
        if gaps:
            return min(e.confidence for e in gaps)
        return AnswerSynthesizer._mean_confidence(evidence)

    @staticmethod
    def _apply_downgrade(confidence: float, failures: int) -> float:
        if failures <= 0:
            return confidence
        downgraded = confidence * (0.9 ** failures)
        return max(0.0, min(downgraded, 1.0))

    # ------------------------------------------------------------------
    # Answer text assembly
    # ------------------------------------------------------------------

    def _build_answer_text(
        self,
        parsed_query: ParsedQuery,
        evidence: list[AggregatedEvidence],
        confidence: float,
    ) -> str:
        """Build answer text using the appropriate template."""
        qt = parsed_query.query_type
        template_group = _TEMPLATES.get(qt)
        if template_group is None:
            return _FALLBACK_TEMPLATE.format(
                query_type=qt, confidence=confidence, n=len(evidence),
            )

        try:
            slots = self._extract_template_slots(parsed_query, evidence, confidence)
            return template_group["answer"].format(**slots)
        except (KeyError, ValueError):
            return _FALLBACK_TEMPLATE.format(
                query_type=qt, confidence=confidence, n=len(evidence),
            )

    def _extract_template_slots(
        self,
        parsed_query: ParsedQuery,
        evidence: list[AggregatedEvidence],
        confidence: float,
    ) -> dict[str, Any]:
        """Extract template slot values from parsed query and evidence."""
        builders = {
            "FACTUAL": self._slots_factual,
            "COMPARISON": self._slots_comparison,
            "EXPLANATION": self._slots_explanation,
            "CONSENSUS": self._slots_consensus,
            "CONTRADICTION": self._slots_contradiction,
            "RESEARCH_GAP": self._slots_gap,
            "MULTI_HOP": self._slots_multi_hop,
            "EXPLORATION": self._slots_exploration,
        }
        fn = builders.get(parsed_query.query_type)
        if fn is None:
            return {"confidence": confidence, "query_type": parsed_query.query_type}
        return fn(parsed_query, evidence, confidence)

    @staticmethod
    def _slots_factual(
        parsed_query: ParsedQuery,
        evidence: list[AggregatedEvidence],
        confidence: float,
    ) -> dict[str, Any]:
        entity_label = (
            parsed_query.primary_entity.text
            if parsed_query.primary_entity else "Unknown"
        )
        rel_types = [
            e.relation_type for e in evidence if e.relation_type
        ]
        relation_type = rel_types[0] if rel_types else "related to"
        titles = list(dict.fromkeys(
            e.source_document_title or e.source_text[:60]
            for e in evidence if e.source_document_title or e.source_text
        ))
        related = ", ".join(titles) if titles else "mentioned entities"
        return {
            "entity_label": entity_label,
            "relation_type": relation_type,
            "related_entities": related,
            "confidence": confidence,
        }

    @staticmethod
    def _slots_comparison(
        parsed_query: ParsedQuery,
        evidence: list[AggregatedEvidence],
        confidence: float,
    ) -> dict[str, Any]:
        entity_a = (
            parsed_query.primary_entity.text
            if parsed_query.primary_entity else "Entity A"
        )
        entity_b = (
            parsed_query.secondary_entities[0].text
            if parsed_query.secondary_entities else "Entity B"
        )
        all_rels = [
            e.relation_type for e in evidence if e.relation_type
        ]
        unique_rels = sorted(set(all_rels))
        shared = ", ".join(unique_rels) if unique_rels else "unknown"
        unique_a = (
            f"{len([e for e in evidence if e.relation_type])} associated attribute(s)"
        )
        return {
            "entity_a": entity_a,
            "entity_b": entity_b,
            "shared": shared,
            "unique_a": unique_a,
            "unique_b": unique_a,
            "confidence": confidence,
        }

    @staticmethod
    def _slots_explanation(
        parsed_query: ParsedQuery,
        evidence: list[AggregatedEvidence],
        confidence: float,
    ) -> dict[str, Any]:
        entity = (
            parsed_query.primary_entity.text
            if parsed_query.primary_entity else "Unknown"
        )
        doc_ids = list(dict.fromkeys(
            e.source_document_id for e in evidence if e.source_document_id
        ))
        doc_count = len(doc_ids)
        claims_lines = []
        for i, e in enumerate(evidence, 1):
            txt = e.source_text or f"Evidence item {i}"
            claims_lines.append(f"  - {txt}")
        claims = "\n".join(claims_lines) if claims_lines else "  - No details available"
        return {
            "entity": entity,
            "doc_count": doc_count,
            "claims": claims,
            "confidence": confidence,
        }

    @staticmethod
    def _slots_consensus(
        parsed_query: ParsedQuery,
        evidence: list[AggregatedEvidence],
        confidence: float,
    ) -> dict[str, Any]:
        target_label = (
            parsed_query.primary_entity.text
            if parsed_query.primary_entity else "Unknown"
        )
        doc_ids = list(dict.fromkeys(
            e.source_document_id for e in evidence if e.source_document_id
        ))
        total_docs = len(doc_ids) or len(evidence)
        # Estimate ratios from evidence metadata
        support = sum(
            1 for e in evidence
            if e.metadata.get("stance") == "support"
        )
        contradict = sum(
            1 for e in evidence
            if e.metadata.get("stance") in ("contradict", "contradiction")
        )
        neutral = total_docs - support - contradict
        if total_docs:
            support_ratio = support / total_docs
            contradict_ratio = contradict / total_docs
            neutral_ratio = neutral / total_docs
        else:
            support_ratio = contradict_ratio = neutral_ratio = 0.0
        if support_ratio >= 0.7:
            classification = "strong"
        elif support_ratio >= 0.4:
            classification = "moderate"
        else:
            classification = "weak"
        return {
            "target_label": target_label,
            "total_docs": total_docs,
            "support_ratio": support_ratio,
            "support_count": support,
            "contradict_ratio": contradict_ratio,
            "contradict_count": contradict,
            "neutral_ratio": neutral_ratio,
            "neutral_count": neutral,
            "classification": classification,
            "confidence": confidence,
        }

    @staticmethod
    def _slots_contradiction(
        parsed_query: ParsedQuery,
        evidence: list[AggregatedEvidence],
        confidence: float,
    ) -> dict[str, Any]:
        target_label = (
            parsed_query.primary_entity.text
            if parsed_query.primary_entity else "Unknown"
        )
        contradictions = [
            e for e in evidence if e.evidence_type == "contradiction"
        ]
        direct = sum(
            1 for e in contradictions
            if e.metadata.get("contradiction_type") == "direct"
        )
        indirect = len(contradictions) - direct
        details_lines = [
            f"  - {e.source_text or 'Contradiction (no details)'}"
            for e in contradictions
        ]
        details = "\n".join(details_lines) if details_lines else "  - No contradiction details available"
        return {
            "target_label": target_label,
            "direct_count": direct,
            "indirect_count": indirect,
            "confidence": confidence,
            "details": details,
        }

    @staticmethod
    def _slots_gap(
        parsed_query: ParsedQuery,
        evidence: list[AggregatedEvidence],
        confidence: float,
    ) -> dict[str, Any]:
        gaps = [e for e in evidence if e.evidence_type == "gap_item"]
        total_gaps = len(gaps)
        # Group gaps by gap_type
        by_type: dict[str, list[AggregatedEvidence]] = {}
        for g in gaps:
            g_type = g.metadata.get("gap_type", "unknown")
            by_type.setdefault(g_type, []).append(g)
        breakdown_lines = []
        for g_type, items in sorted(by_type.items()):
            breakdown_lines.append(
                f"  - {g_type}: {len(items)} item(s)"
            )
        gap_breakdown = "\n".join(breakdown_lines) if breakdown_lines else "  - No gaps categorized"
        suggestions_lines = [
            f"  - {e.metadata.get('suggestion', e.source_text or 'Consider investigating this gap.')}"
            for e in gaps
        ]
        suggestions = "\n".join(suggestions_lines) if suggestions_lines else "  - No suggestions available"
        return {
            "total_gaps": total_gaps,
            "gap_breakdown": gap_breakdown,
            "suggestions": suggestions,
        }

    @staticmethod
    def _slots_multi_hop(
        parsed_query: ParsedQuery,
        evidence: list[AggregatedEvidence],
        confidence: float,
    ) -> dict[str, Any]:
        source = (
            parsed_query.primary_entity.text
            if parsed_query.primary_entity else "Source"
        )
        target = (
            parsed_query.secondary_entities[0].text
            if parsed_query.secondary_entities else "Target"
        )
        path_count = len(evidence)
        paths_lines = [
            f"  - Path {i}: {e.source_text or 'Path found'}"
            for i, e in enumerate(evidence, 1)
        ]
        paths = "\n".join(paths_lines) if paths_lines else "  - No path details"
        return {
            "path_count": path_count,
            "source": source,
            "target": target,
            "paths": paths,
            "confidence": confidence,
        }

    @staticmethod
    def _slots_exploration(
        parsed_query: ParsedQuery,
        evidence: list[AggregatedEvidence],
        confidence: float,
    ) -> dict[str, Any]:
        source_label = (
            parsed_query.primary_entity.text
            if parsed_query.primary_entity else "Unknown"
        )
        node_ids = list(dict.fromkeys(
            e.metadata.get("node_id", "") for e in evidence if e.metadata.get("node_id")
        ))
        edge_count = len(evidence)
        node_count = len(node_ids) or edge_count
        conns = [
            e.relation_type or e.source_text[:40]
            for e in evidence[:5] if e.relation_type or e.source_text
        ]
        connections = ", ".join(conns) if conns else "various"
        return {
            "source_label": source_label,
            "node_count": node_count,
            "edge_count": edge_count,
            "connections": connections,
        }

    # ------------------------------------------------------------------
    # ResearchAnswer assembly
    # ------------------------------------------------------------------

    def _assemble_answer(
        self,
        query: ResearchQuery,
        parsed_query: ParsedQuery,
        plan: ExecutionPlan,
        plan_result: PlanResult,
        answer_text: str,
        confidence: float,
        evidence: list[AggregatedEvidence],
        reasoning_trace: list[ReasoningStep],
        failures: int,
    ) -> ResearchAnswer:
        evidence_ids = [
            e.evidence_id for e in evidence if e.evidence_id
        ]
        docs = list(dict.fromkeys(
            e.source_document_id for e in evidence if e.source_document_id
        ))
        titles = list(dict.fromkeys(
            e.source_document_title for e in evidence if e.source_document_title
        ))
        sources = list(docs)
        engines = list(dict.fromkeys(
            e.source_engine for e in evidence if e.source_engine
        ))
        source_attr: dict[str, list[str]] = {}
        for e in evidence:
            if e.source_document_id and e.evidence_id:
                source_attr.setdefault(e.source_document_id, []).append(e.evidence_id)

        return ResearchAnswer(
            answer_id=self._generate_answer_id(query, parsed_query, answer_text, confidence),
            query=query,
            plan=plan,
            answer=answer_text,
            confidence=confidence,
            classification=self._extract_classification(parsed_query, evidence),
            evidence=evidence,
            evidence_ids=evidence_ids,
            supporting_documents=docs,
            supporting_document_titles=titles,
            reasoning_trace=reasoning_trace,
            sources=sources,
            source_attribution=source_attr,
            query_type=parsed_query.query_type,
            generated_at=query.created_at,
            steps_executed=len(reasoning_trace),
            steps_failed=len(plan_result.failed_steps),
            warnings=list(plan_result.plan_warnings),
            traceability_verified=failures == 0,
            traceability_failures=(
                [f"Traceability failure #{i + 1}" for i in range(failures)]
                if failures else []
            ),
            engines_invoked=engines,
        )

    @staticmethod
    def _generate_answer_id(
        query: ResearchQuery,
        parsed_query: ParsedQuery,
        answer_text: str,
        confidence: float,
    ) -> str:
        key = (
            f"{query.query_id}::{parsed_query.query_type}::"
            f"{answer_text[:100]}::{confidence:.4f}"
        )
        h = zlib.crc32(key.encode()) & 0xFFFFFFFF
        return f"ans_{h:012x}"

    @staticmethod
    def _extract_classification(
        parsed_query: ParsedQuery,
        evidence: list[AggregatedEvidence],
    ) -> str | None:
        qt = parsed_query.query_type
        if qt == "CONSENSUS":
            support = sum(
                1 for e in evidence
                if e.metadata.get("stance") == "support"
            )
            total = len(evidence) or 1
            ratio = support / total
            if ratio >= 0.7:
                return "strong"
            if ratio >= 0.4:
                return "moderate"
            return "weak"
        if qt == "CONTRADICTION":
            contra_count = sum(
                1 for e in evidence if e.evidence_type == "contradiction"
            )
            return "contradiction_found" if contra_count > 0 else "no_contradiction"
        if qt == "RESEARCH_GAP":
            gap_count = sum(
                1 for e in evidence if e.evidence_type == "gap_item"
            )
            return f"{gap_count}_gap(s)" if gap_count else "no_gaps"
        return None

    # ------------------------------------------------------------------
    # No-evidence fallback
    # ------------------------------------------------------------------

    def _build_no_evidence_answer(
        self,
        query: ResearchQuery,
        plan: ExecutionPlan,
        parsed_query: ParsedQuery,
        plan_result: PlanResult,
    ) -> ResearchAnswer:
        trace = self._build_reasoning_trace(plan_result)
        return ResearchAnswer(
            answer_id=self._generate_answer_id(
                query, parsed_query, _NO_EVIDENCE_ANSWER, 0.0,
            ),
            query=query,
            plan=plan,
            answer=_NO_EVIDENCE_ANSWER,
            confidence=0.0,
            classification=None,
            evidence=[],
            evidence_ids=[],
            supporting_documents=[],
            supporting_document_titles=[],
            reasoning_trace=trace,
            sources=[],
            source_attribution={},
            query_type=parsed_query.query_type,
            generated_at=query.created_at,
            steps_executed=len(trace),
            steps_failed=len(plan_result.failed_steps),
            warnings=["No evidence available"],
            traceability_verified=True,
            engines_invoked=[],
        )


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def synthesize_answer(
    query: ResearchQuery,
    parsed_query: ParsedQuery,
    plan: ExecutionPlan,
    plan_result: PlanResult,
    evidence: list[AggregatedEvidence],
) -> ResearchAnswer:
    """Convenience function to synthesize an answer."""
    return AnswerSynthesizer().synthesize(
        query, parsed_query, plan, plan_result, evidence,
    )
