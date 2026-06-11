"""M4-7 CorpusSynthesisEngine — cross-engine result merging.

Combines results from multiple sub-engines, resolves conflicts,
and produces a unified reasoning answer.
"""

from __future__ import annotations

from typing import Any

from researchmind.reasoning.models import (
    QueryType,
    ReasoningQuery,
    ReasoningResult,
)


class CorpusSynthesisEngine:
    """Merges results from multiple reasoning sub-engines."""

    def __init__(
        self,
        multi_hop_reasoner: Any | None = None,
        consensus_engine: Any | None = None,
        contradiction_engine: Any | None = None,
        gap_engine: Any | None = None,
    ):
        self._multi_hop = multi_hop_reasoner
        self._consensus = consensus_engine
        self._contradiction = contradiction_engine
        self._gap = gap_engine

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def synthesize(self, query: ReasoningQuery) -> ReasoningResult:
        engine_names = self._select_engines(query.query_type)
        sub_results: list[ReasoningResult] = []

        for name in engine_names:
            engine = self._get_engine(name)
            if engine is None:
                continue
            try:
                if name == "multi_hop":
                    result = engine.reason(
                        source_id=query.source_id,
                        target_id=query.target_id,
                        query=query,
                    )
                elif name == "consensus":
                    target_id = (
                        query.target_id
                        or (
                            query.node_ids[0]
                            if query.node_ids
                            else None
                        )
                    )
                    if target_id is None:
                        continue
                    consensus_result = engine.analyze(
                        target_id=target_id, query=query
                    )
                    result = self._consensus_to_result(
                        query, consensus_result
                    )
                elif name == "contradiction":
                    target_id = (
                        query.target_id
                        or (
                            query.node_ids[0]
                            if query.node_ids
                            else None
                        )
                    )
                    if target_id is None:
                        continue
                    contra_result = engine.analyze(
                        target_id=target_id, query=query
                    )
                    result = self._contradiction_to_result(
                        query, contra_result
                    )
                elif name == "gap":
                    gap_result = engine.analyze(query=query)
                    result = self._gap_to_result(query, gap_result)
                else:
                    continue
                sub_results.append(result)
            except Exception as exc:
                sub_results.append(
                    ReasoningResult(
                        query=query,
                        answer=f"Error in {name}: {exc}",
                        confidence=0.0,
                        warnings=[f"{name} raised: {exc}"],
                    )
                )

        if not sub_results:
            return ReasoningResult(
                query=query,
                answer="No sub-engines produced results.",
                confidence=0.0,
                warnings=["All sub-engines returned empty results"],
            )

        merged = self._merge_results(sub_results)
        merged = self._resolve_conflicts(merged, sub_results)
        merged = self._rank_evidence(merged)
        merged = self._synthesize_answer(merged)
        merged.confidence = self._compute_overall_confidence(merged)

        return merged

    # ------------------------------------------------------------------
    # Engine selection
    # ------------------------------------------------------------------

    def _select_engines(self, query_type: str) -> list[str]:
        dispatch: dict[str, list[str]] = {
            QueryType.ENTITY_LOOKUP: ["multi_hop"],
            QueryType.DOCUMENT_LOOKUP: ["multi_hop"],
            QueryType.GRAPH_EXPLORATION: ["multi_hop"],
            QueryType.PATH_REASONING: ["multi_hop"],
            QueryType.CONSENSUS_ANALYSIS: [
                "consensus",
                "multi_hop",
                "contradiction",
            ],
            QueryType.CONTRADICTION_ANALYSIS: [
                "contradiction",
                "consensus",
            ],
            QueryType.GAP_ANALYSIS: ["gap", "multi_hop"],
        }
        return dispatch.get(query_type, [])

    def _get_engine(self, name: str) -> Any:
        mapping = {
            "multi_hop": self._multi_hop,
            "consensus": self._consensus,
            "contradiction": self._contradiction,
            "gap": self._gap,
        }
        return mapping.get(name)

    # ------------------------------------------------------------------
    # Sub-engine result conversion
    # ------------------------------------------------------------------

    def _consensus_to_result(
        self, query: ReasoningQuery, consensus_result: Any
    ) -> ReasoningResult:
        evidence_list = []
        for entry in getattr(consensus_result, "per_document", []):
            for eid in getattr(entry, "evidence_ids", []):
                evidence_list.append(
                    {
                        "evidence_id": eid,
                        "confidence": getattr(entry, "confidence", 0.0),
                        "document_id": getattr(entry, "document_id", ""),
                    }
                )
        return ReasoningResult(
            query=query,
            answer=(
                f"Consensus: "
                f"{getattr(consensus_result, 'supporting_documents', 0)} support, "
                f"{getattr(consensus_result, 'contradicting_documents', 0)} contradict"
            ),
            confidence=getattr(consensus_result, "consensus_confidence", 0.0),
            metadata={
                "type": "consensus",
                "classification": getattr(consensus_result, "classification", ""),
            },
        )

    def _contradiction_to_result(
        self, query: ReasoningQuery, contra_result: Any
    ) -> ReasoningResult:
        return ReasoningResult(
            query=query,
            answer=(
                f"Contradictions: "
                f"{getattr(contra_result, 'contradiction_count', 0)} found"
            ),
            confidence=getattr(
                contra_result, "aggregate_confidence", 0.0
            ),
            metadata={"type": "contradiction"},
        )

    def _gap_to_result(
        self, query: ReasoningQuery, gap_result: Any
    ) -> ReasoningResult:
        return ReasoningResult(
            query=query,
            answer=(
                f"Gaps: {getattr(gap_result, 'total_gaps', 0)} found"
            ),
            confidence=0.0,
            metadata={"type": "gap"},
        )

    # ------------------------------------------------------------------
    # Merge, conflict resolution, ranking
    # ------------------------------------------------------------------

    def _merge_results(
        self, sub_results: list[ReasoningResult]
    ) -> ReasoningResult:
        if not sub_results:
            return ReasoningResult(
                query=ReasoningQuery(query_type="unknown")
            )
        merged = sub_results[0]
        for r in sub_results[1:]:
            merged.supporting_evidence.extend(r.supporting_evidence)
            merged.supporting_documents.extend(r.supporting_documents)
            merged.graph_paths.extend(r.graph_paths)
            merged.reasoning_trace.extend(r.reasoning_trace)
            merged.warnings.extend(r.warnings)
        return merged

    def _resolve_conflicts(
        self, merged: ReasoningResult, sub_results: list[ReasoningResult]
    ) -> ReasoningResult:
        return merged

    def _rank_evidence(
        self, merged: ReasoningResult
    ) -> ReasoningResult:
        merged.supporting_evidence.sort(
            key=lambda e: e.confidence, reverse=True
        )
        merged.supporting_documents = list(
            dict.fromkeys(merged.supporting_documents)
        )
        return merged

    def _synthesize_answer(
        self, merged: ReasoningResult
    ) -> ReasoningResult:
        parts = []
        for r in getattr(merged, "metadata", {}).values():
            if isinstance(r, str) and r:
                parts.append(r)
        if not parts:
            ec = len(merged.supporting_evidence)
            dc = len(merged.supporting_documents)
            parts.append(
                f"Analysis complete: {ec} evidence item(s) from "
                f"{dc} document(s)."
            )
        merged.answer = " | ".join(parts)
        return merged

    def _compute_overall_confidence(
        self, merged: ReasoningResult
    ) -> float:
        confs = [e.confidence for e in merged.supporting_evidence if e.confidence > 0]
        if not confs:
            return 0.0
        return sum(confs) / len(confs)
