"""M4-2 ReasoningEngine — query dispatcher.

Routes reasoning queries to the appropriate sub-engine, resolves evidence,
and constructs answers per query type.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from researchmind.corpus.graph import CorpusGraphPath
from researchmind.models.ruo_enums import EvidenceType

from researchmind.reasoning.models import (
    AnswerEvidence,
    QueryType,
    ReasoningQuery,
    ReasoningResult,
    ReasoningStep,
)


class ReasoningEngine:
    """Central dispatcher for all reasoning queries."""

    def __init__(
        self,
        multi_hop_reasoner: Any | None = None,
        consensus_engine: Any | None = None,
        contradiction_engine: Any | None = None,
        gap_engine: Any | None = None,
        synthesis_engine: Any | None = None,
    ):
        self._multi_hop = multi_hop_reasoner
        self._consensus = consensus_engine
        self._contradiction = contradiction_engine
        self._gap = gap_engine
        self._synthesis = synthesis_engine
        self._evidence_provider: Callable[[list[str]], list] | None = None

    def register_evidence_provider(
        self, provider: Callable[[list[str]], list]
    ) -> None:
        """Register a callable that resolves evidence_ids -> evidence records."""
        self._evidence_provider = provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reason(self, query: ReasoningQuery) -> ReasoningResult:
        """Route a single query to the appropriate sub-engine."""
        dispatch_map = {
            QueryType.ENTITY_LOOKUP: self._route_multi_hop,
            QueryType.DOCUMENT_LOOKUP: self._route_multi_hop,
            QueryType.GRAPH_EXPLORATION: self._route_multi_hop,
            QueryType.PATH_REASONING: self._route_multi_hop,
            QueryType.CONSENSUS_ANALYSIS: self._route_consensus,
            QueryType.CONTRADICTION_ANALYSIS: self._route_contradiction,
            QueryType.GAP_ANALYSIS: self._route_gap,
        }
        handler = dispatch_map.get(query.query_type)
        if handler is None:
            return ReasoningResult(
                query=query,
                answer=f"Unknown query_type: {query.query_type}",
                confidence=0.0,
                warnings=[f"No handler for query_type={query.query_type}"],
            )
        return handler(query)

    def reason_batch(
        self, queries: list[ReasoningQuery]
    ) -> list[ReasoningResult]:
        """Process multiple queries (sequential)."""
        return [self.reason(q) for q in queries]

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _route_multi_hop(self, query: ReasoningQuery) -> ReasoningResult:
        if self._multi_hop is None:
            return self._no_engine_result(query, "MultiHopReasoner")
        return self._multi_hop.reason(source_id=query.source_id, target_id=query.target_id, query=query)

    def _route_consensus(self, query: ReasoningQuery) -> ReasoningResult:
        if self._consensus is None:
            return self._no_engine_result(query, "ConsensusEngine")
        target_id = query.target_id or (query.node_ids[0] if query.node_ids else None)
        if target_id is None:
            return ReasoningResult(
                query=query,
                answer="No target_id provided for consensus analysis.",
                confidence=0.0,
                warnings=["target_id or node_ids[0] required for CONSENSUS_ANALYSIS"],
            )
        result = self._consensus.analyze(target_id=target_id, query=query)
        return self._build_answer_from_consensus(query, result)

    def _route_contradiction(self, query: ReasoningQuery) -> ReasoningResult:
        if self._contradiction is None:
            return self._no_engine_result(query, "ContradictionEngine")
        target_id = query.target_id or (query.node_ids[0] if query.node_ids else None)
        if target_id is None:
            return ReasoningResult(
                query=query,
                answer="No target_id provided for contradiction analysis.",
                confidence=0.0,
                warnings=["target_id or node_ids[0] required for CONTRADICTION_ANALYSIS"],
            )
        result = self._contradiction.analyze(target_id=target_id, query=query)
        return self._build_answer_from_contradiction(query, result)

    def _route_gap(self, query: ReasoningQuery) -> ReasoningResult:
        if self._gap is None:
            return self._no_engine_result(query, "ResearchGapEngine")
        result = self._gap.analyze(query=query)
        return self._build_answer_from_gaps(query, result)

    # ------------------------------------------------------------------
    # Answer building
    # ------------------------------------------------------------------

    def _build_answer_from_consensus(self, query: ReasoningQuery, result: Any) -> ReasoningResult:
        evidence_list = []
        for entry in result.per_document:
            for eid in entry.evidence_ids:
                evidence_list.append(
                    AnswerEvidence(
                        evidence_id=eid,
                        source_text="",
                        confidence=entry.confidence,
                        document_id=entry.document_id,
                        evidence_type=EvidenceType.DERIVED,
                    )
                )
        answer_parts = []
        answer_parts.append(
            f"Consensus for '{result.target_label}' "
            f"({result.total_documents} docs): "
            f"{result.supporting_documents} support, "
            f"{result.contradicting_documents} contradict, "
            f"{result.neutral_documents} neutral. "
            f"Classification: {result.classification}."
        )
        if result.warnings:
            answer_parts.extend(f"Warning: {w}" for w in result.warnings)

        return ReasoningResult(
            query=query,
            answer=" ".join(answer_parts),
            confidence=result.consensus_confidence,
            supporting_evidence=evidence_list,
            supporting_documents=list({e.document_id for e in evidence_list}),
            metadata={
                "support_ratio": result.support_ratio,
                "contradiction_ratio": result.contradiction_ratio,
                "neutral_ratio": result.neutral_ratio,
                "classification": result.classification,
                "total_documents": result.total_documents,
            },
            warnings=result.warnings,
        )

    def _build_answer_from_contradiction(self, query: ReasoningQuery, result: Any) -> ReasoningResult:
        evidence_list = []
        for dc in result.direct_contradictions:
            for eid in dc.evidence_ids:
                evidence_list.append(
                    AnswerEvidence(
                        evidence_id=eid,
                        source_text=dc.source_text or "",
                        confidence=dc.confidence,
                        document_id=dc.source_document_id,
                        evidence_type=EvidenceType.DIRECT_QUOTE,
                    )
                )
        answer_parts = [
            f"Contradiction analysis for '{result.target_label}': "
            f"{result.contradiction_count} contradiction(s) found "
            f"(confidence={result.aggregate_confidence:.3f})."
        ]
        for dc in result.direct_contradictions:
            answer_parts.append(
                f"  Direct: {dc.source_document_title} <-> {dc.target_document_title} "
                f"(conf={dc.confidence:.2f})"
            )
        for ic in result.indirect_contradictions:
            answer_parts.append(
                f"  Indirect: {ic.description} "
                f"(conf={ic.confidence:.2f})"
            )
        return ReasoningResult(
            query=query,
            answer="\n".join(answer_parts),
            confidence=result.aggregate_confidence,
            supporting_evidence=evidence_list,
            metadata={"contradiction_count": result.contradiction_count},
            warnings=result.warnings,
        )

    def _build_answer_from_gaps(self, query: ReasoningQuery, result: Any) -> ReasoningResult:
        evidence_list = []
        all_gaps = (
            result.isolated_entities
            + result.missing_comparisons
            + result.low_confidence_claims
            + result.under_studied_datasets
            + result.unconnected_documents
        )
        for gap in all_gaps:
            evidence_list.append(
                AnswerEvidence(
                    evidence_id=gap.node_id,
                    source_text=gap.description,
                    confidence=gap.confidence,
                    document_id="",
                    evidence_type=EvidenceType.DERIVED,
                )
            )
        return ReasoningResult(
            query=query,
            answer=result.summary or f"Gap analysis: {result.total_gaps} gap(s) found.",
            confidence=min((g.confidence for g in all_gaps), default=0.0),
            supporting_evidence=evidence_list,
            metadata={"total_gaps": result.total_gaps},
            warnings=result.warnings,
        )

    def _build_answer(
        self,
        query: ReasoningQuery,
        evidence: list[AnswerEvidence],
        paths: list[CorpusGraphPath],
        trace: list[ReasoningStep] | None = None,
    ) -> ReasoningResult:
        if not evidence:
            return ReasoningResult(
                query=query,
                answer="Insufficient evidence to answer this query.",
                confidence=0.0,
                warnings=["No evidence found"],
            )
        answer_parts = []
        if paths:
            best = max(paths, key=lambda p: p.confidence)
            answer_parts.append(
                f"Found {len(paths)} path(s) (best confidence={best.confidence:.3f})."
            )
        else:
            answer_parts.append(
                f"Found {len(evidence)} evidence item(s) "
                f"(confidence={self._compute_confidence(evidence, 'min'):.3f})."
            )
        return ReasoningResult(
            query=query,
            answer=" ".join(answer_parts),
            confidence=self._compute_confidence(evidence, "min"),
            supporting_evidence=evidence,
            supporting_documents=list({e.document_id for e in evidence if e.document_id}),
            graph_paths=paths,
            reasoning_trace=trace or [],
            metadata={"path_count": len(paths), "evidence_count": len(evidence)},
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _resolve_evidence(self, evidence_ids: list[str]) -> list[AnswerEvidence]:
        if self._evidence_provider is None or not evidence_ids:
            return []
        records = self._evidence_provider(evidence_ids)
        result = []
        for r in records:
            result.append(
                AnswerEvidence(
                    evidence_id=getattr(r, "evidence_id", ""),
                    source_text=getattr(r, "source_text", ""),
                    confidence=getattr(r, "confidence", 0.0),
                    document_id=getattr(r, "document_id", ""),
                    evidence_type=getattr(r, "evidence_type", EvidenceType.DIRECT_QUOTE),
                    location=getattr(r, "location", None),
                )
            )
        return result

    def _compute_confidence(
        self, evidence_list: list[AnswerEvidence], method: str = "min"
    ) -> float:
        if not evidence_list:
            return 0.0
        if method == "min":
            return min(e.confidence for e in evidence_list)
        elif method == "avg":
            return sum(e.confidence for e in evidence_list) / len(evidence_list)
        elif method == "product":
            prod = 1.0
            for e in evidence_list:
                prod *= e.confidence
            return prod
        return 0.0

    def _format_answer_text(self, query: ReasoningQuery, metadata: dict) -> str:
        parts = [f"Query type: {query.query_type}"]
        if metadata:
            for k, v in metadata.items():
                parts.append(f"{k}={v}")
        return "; ".join(parts)

    def _no_engine_result(self, query: ReasoningQuery, engine_name: str) -> ReasoningResult:
        return ReasoningResult(
            query=query,
            answer=f"{engine_name} not available.",
            confidence=0.0,
            warnings=[f"{engine_name} was not provided to ReasoningEngine"],
        )
