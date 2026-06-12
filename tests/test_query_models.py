"""Tests for Module 5 Research Assistant query models.

Covers all models, validators, enums, and edge cases defined in
architecture/query_planner.md (v1.1).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from researchmind.query.models import (
    AggregatedEvidence,
    ExecutionPlan,
    ParsedQuery,
    PlanStep,
    QueryConstraint,
    QueryEntity,
    QueryType,
    ReasoningStep,
    ResearchAnswer,
    ResearchQuery,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def valid_query_entity(**kw):
    defaults = dict(
        text="BERT",
        entity_type="method",
        cluster_id="clu_003",
        confidence=0.9,
    )
    defaults.update(kw)
    return QueryEntity(**defaults)


def valid_query_constraint(**kw):
    defaults = dict(field="year", operator="gte", value=2018)
    defaults.update(kw)
    return QueryConstraint(**defaults)


def valid_parsed_query(**kw):
    defaults = dict(
        raw_query="What datasets does BERT use?",
        query_type="FACTUAL",
        primary_entity=valid_query_entity(),
        entities_resolved=True,
    )
    defaults.update(kw)
    return ParsedQuery(**defaults)


def valid_research_query(**kw):
    defaults = dict(
        query_id="qry_001",
        raw_query="What datasets does BERT use?",
        created_at=NOW,
    )
    defaults.update(kw)
    return ResearchQuery(**defaults)


def valid_plan_step(step_id="ps_001", **kw):
    defaults = dict(
        step_id=step_id,
        sequence=1,
        engine="multi_hop",
        query_type="ENTITY_LOOKUP",
        target_id="clu_003",
    )
    defaults.update(kw)
    return PlanStep(**defaults)


def valid_execution_plan(**kw):
    step = valid_plan_step()
    defaults = dict(
        plan_id="plan_abc123",
        query_id="qry_001",
        query_type="FACTUAL",
        steps=[step],
    )
    defaults.update(kw)
    return ExecutionPlan(**defaults)


def valid_aggregated_evidence(**kw):
    defaults = dict(
        evidence_id="ev_001",
        source_text="BERT uses BookCorpus and Wikipedia.",
        confidence=0.85,
        source_engine="multi_hop",
        source_document_id="doc_001",
        source_document_title="BERT: Pre-training of Deep Bidirectional Transformers",
        evidence_type="path_edge",
        trace=["chunk_001", "chunk_002"],
    )
    defaults.update(kw)
    return AggregatedEvidence(**defaults)


def valid_reasoning_step(**kw):
    defaults = dict(
        step_id="rs_001",
        engine="multi_hop",
        description="Executed entity lookup for BERT",
        confidence=0.85,
        evidence_ids=["ev_001"],
    )
    defaults.update(kw)
    return ReasoningStep(**defaults)


def valid_research_answer(**kw):
    rq = valid_research_query()
    plan = valid_execution_plan()
    ev = valid_aggregated_evidence()
    rs = valid_reasoning_step()
    defaults = dict(
        answer_id="ans_001",
        query=rq,
        plan=plan,
        answer="BERT is associated with USES_DATASET to BookCorpus.",
        confidence=0.85,
        generated_at=NOW,
        evidence=[ev],
        evidence_ids=["ev_001"],
        supporting_documents=["doc_001"],
        supporting_document_titles=["BERT: Pre-training of Deep Bidirectional Transformers"],
        reasoning_trace=[rs],
        query_type="FACTUAL",
    )
    defaults.update(kw)
    return ResearchAnswer(**defaults)


# ===========================================================================
# QueryType
# ===========================================================================


class TestQueryType:
    def test_enum_values(self):
        assert QueryType.FACTUAL.value == "factual"
        assert QueryType.COMPARISON.value == "comparison"
        assert QueryType.EXPLANATION.value == "explanation"
        assert QueryType.CONSENSUS.value == "consensus"
        assert QueryType.CONTRADICTION.value == "contradiction"
        assert QueryType.RESEARCH_GAP.value == "research_gap"
        assert QueryType.MULTI_HOP.value == "multi_hop"
        assert QueryType.EXPLORATION.value == "exploration"

    def test_enum_count(self):
        assert len(QueryType) == 8

    def test_enum_members_are_strings(self):
        for qt in QueryType:
            assert isinstance(qt.value, str)

    def test_enum_serialization(self):
        assert QueryType("factual") is QueryType.FACTUAL
        assert QueryType("explanation") is QueryType.EXPLANATION

    def test_enum_from_string(self):
        assert QueryType["FACTUAL"] is QueryType.FACTUAL
        assert QueryType["RESEARCH_GAP"] is QueryType.RESEARCH_GAP

    def test_enum_invalid_value(self):
        with pytest.raises(ValueError, match="'invalid_type'"):
            QueryType("invalid_type")


# ===========================================================================
# QueryEntity
# ===========================================================================


class TestQueryEntity:
    def test_valid_creation(self):
        ent = valid_query_entity()
        assert ent.text == "BERT"
        assert ent.entity_type == "method"
        assert ent.cluster_id == "clu_003"
        assert ent.confidence == 0.9
        assert ent.is_ambiguous is False
        assert ent.alternatives == []

    def test_minimal_entity(self):
        ent = QueryEntity(text="Adam")
        assert ent.text == "Adam"
        assert ent.entity_type is None
        assert ent.cluster_id is None
        assert ent.confidence == 0.0
        assert ent.is_ambiguous is False

    def test_confidence_bounds_high(self):
        with pytest.raises(ValidationError):
            valid_query_entity(confidence=1.5)

    def test_confidence_bounds_low(self):
        with pytest.raises(ValidationError):
            valid_query_entity(confidence=-0.1)

    def test_confidence_at_edges(self):
        ent = valid_query_entity(confidence=0.0)
        assert ent.confidence == 0.0
        ent = valid_query_entity(confidence=1.0)
        assert ent.confidence == 1.0

    def test_invalid_entity_type(self):
        with pytest.raises(ValidationError, match="entity_type"):
            valid_query_entity(entity_type="invalid_type")

    def test_valid_entity_types(self):
        for etype in ("method", "dataset", "metric", "document", "concept", "unknown", None):
            ent = valid_query_entity(entity_type=etype)
            assert ent.entity_type == etype

    def test_ambiguous_flag(self):
        ent = valid_query_entity(is_ambiguous=True, alternatives=["clu_004", "clu_005"])
        assert ent.is_ambiguous is True
        assert len(ent.alternatives) == 2

    def test_alternatives_default(self):
        ent = valid_query_entity()
        assert ent.alternatives == []

    def test_text_required(self):
        with pytest.raises(ValidationError):
            QueryEntity(text="")


# ===========================================================================
# QueryConstraint
# ===========================================================================


class TestQueryConstraint:
    def test_valid_creation(self):
        c = valid_query_constraint()
        assert c.field == "year"
        assert c.operator == "gte"
        assert c.value == 2018

    def test_field_normalization(self):
        c = valid_query_constraint(field="  YEAR  ")
        assert c.field == "year"

    def test_invalid_field(self):
        with pytest.raises(ValidationError, match="constraint field"):
            valid_query_constraint(field="color")

    def test_operator_normalization(self):
        c = valid_query_constraint(operator="  GTE  ")
        assert c.operator == "gte"

    def test_invalid_operator(self):
        with pytest.raises(ValidationError, match="operator"):
            valid_query_constraint(operator="==")

    def test_year_value_must_be_int(self):
        c = valid_query_constraint(field="year", value=2020)
        assert c.value == 2020

    def test_confidence_value_bounds(self):
        with pytest.raises(ValidationError, match="confidence"):
            valid_query_constraint(field="confidence", value=1.5)

    def test_confidence_value_valid(self):
        c = valid_query_constraint(field="confidence", value=0.7)
        assert c.value == 0.7

    def test_in_operator(self):
        c = valid_query_constraint(field="year", operator="in", value=[2018, 2019, 2020])
        assert c.operator == "in"

    def test_document_field(self):
        c = valid_query_constraint(field="document", operator="eq", value="doc_001")
        assert c.field == "document"

    def test_relation_type_field(self):
        c = valid_query_constraint(field="relation_type", operator="eq", value="USES_DATASET")
        assert c.field == "relation_type"


# ===========================================================================
# ParsedQuery
# ===========================================================================


class TestParsedQuery:
    def test_valid_creation(self):
        pq = valid_parsed_query()
        assert pq.raw_query == "What datasets does BERT use?"
        assert pq.query_type == "FACTUAL"
        assert pq.primary_entity is not None
        assert pq.primary_entity.text == "BERT"
        assert pq.entities_resolved is True
        assert pq.parsing_warnings == []

    def test_query_type_normalized(self):
        pq = valid_parsed_query(query_type="  factual  ")
        assert pq.query_type == "FACTUAL"

    def test_invalid_query_type(self):
        with pytest.raises(ValidationError, match="query_type"):
            valid_parsed_query(query_type="UNKNOWN")

    def test_no_entity_for_requiring_type(self):
        with pytest.raises(ValidationError, match="requires at least one entity"):
            valid_parsed_query(primary_entity=None, secondary_entities=[])

    def test_research_gap_allows_no_entity(self):
        pq = valid_parsed_query(
            query_type="RESEARCH_GAP",
            primary_entity=None,
            secondary_entities=[],
            entities_resolved=True,
        )
        assert pq.query_type == "RESEARCH_GAP"

    def test_secondary_entities(self):
        secondary = [
            valid_query_entity(text="SQuAD", cluster_id="clu_010"),
            valid_query_entity(text="GLUE", cluster_id="clu_011"),
        ]
        pq = valid_parsed_query(secondary_entities=secondary)
        assert len(pq.secondary_entities) == 2

    def test_constraints_list(self):
        c = valid_query_constraint()
        pq = valid_parsed_query(constraints=[c])
        assert len(pq.constraints) == 1

    def test_max_hops_default(self):
        pq = valid_parsed_query()
        assert pq.max_hops == 3

    def test_max_hops_clamping(self):
        pq = valid_parsed_query(max_hops=20)
        assert pq.max_hops == 10
        pq = valid_parsed_query(max_hops=-1)
        assert pq.max_hops == 1

    def test_min_confidence_clamping(self):
        pq = valid_parsed_query(min_confidence=1.5)
        assert pq.min_confidence == 1.0
        pq = valid_parsed_query(min_confidence=-0.5)
        assert pq.min_confidence == 0.0

    def test_parsing_warnings(self):
        pq = valid_parsed_query(parsing_warnings=["Ambiguous entity match"])
        assert len(pq.parsing_warnings) == 1

    def test_all_types_produce_valid(self):
        for qt in QueryType:
            if qt == QueryType.RESEARCH_GAP:
                pq = ParsedQuery(raw_query="test", query_type=qt.name, entities_resolved=True)
            else:
                pq = ParsedQuery(
                    raw_query="test",
                    query_type=qt.name,
                    primary_entity=valid_query_entity(),
                    entities_resolved=True,
                )
            assert pq.query_type == qt.name


# ===========================================================================
# ResearchQuery
# ===========================================================================


class TestResearchQuery:
    def test_valid_creation(self):
        rq = valid_research_query()
        assert rq.query_id == "qry_001"
        assert rq.raw_query == "What datasets does BERT use?"
        assert rq.created_at == NOW
        assert rq.parsed is None

    def test_empty_raw_query(self):
        with pytest.raises(ValidationError, match="non-empty"):
            valid_research_query(raw_query="")

    def test_whitespace_raw_query(self):
        with pytest.raises(ValidationError, match="non-empty"):
            valid_research_query(raw_query="   ")

    def test_max_hops_default(self):
        rq = valid_research_query()
        assert rq.max_hops == 3

    def test_max_hops_clamp(self):
        rq = valid_research_query(max_hops=50)
        assert rq.max_hops == 10

    def test_min_confidence_clamp(self):
        rq = valid_research_query(min_confidence=-0.5)
        assert rq.min_confidence == 0.0

    def test_with_parsed_query(self):
        pq = valid_parsed_query()
        rq = valid_research_query(parsed=pq)
        assert rq.parsed is not None
        assert rq.parsed.query_type == "FACTUAL"

    def test_constraints(self):
        c = valid_query_constraint()
        rq = valid_research_query(constraints=[c])
        assert len(rq.constraints) == 1

    def test_include_flags(self):
        rq = valid_research_query(include_reasoning=False, include_evidence=False)
        assert rq.include_reasoning is False
        assert rq.include_evidence is False

    def test_parsed_mutability(self):
        rq = valid_research_query()
        pq = valid_parsed_query()
        rq.parsed = pq
        assert rq.parsed.query_type == "FACTUAL"

    def test_minimal_valid(self):
        rq = ResearchQuery(
            query_id="qry_999",
            raw_query="Explain batch normalization",
            created_at=NOW,
        )
        assert rq.max_hops == 3


# ===========================================================================
# PlanStep
# ===========================================================================


class TestPlanStep:
    def test_valid_creation(self):
        ps = valid_plan_step()
        assert ps.step_id == "ps_001"
        assert ps.sequence == 1
        assert ps.engine == "multi_hop"
        assert ps.status == "pending"
        assert ps.confidence == 0.0

    def test_invalid_engine(self):
        with pytest.raises(ValidationError, match="engine"):
            valid_plan_step(engine="vector_search")

    def test_valid_engines(self):
        for eng in ("multi_hop", "consensus", "contradiction", "gap", "aggregate", "synthesize"):
            ps = valid_plan_step(engine=eng)
            assert ps.engine == eng

    def test_engine_normalized(self):
        ps = valid_plan_step(engine="  MULTI_HOP  ")
        assert ps.engine == "multi_hop"

    def test_invalid_status(self):
        with pytest.raises(ValidationError, match="status"):
            valid_plan_step(status="crashed")

    def test_valid_statuses(self):
        for st in ("pending", "running", "completed", "failed", "skipped"):
            ps = valid_plan_step(status=st)
            assert ps.status == st

    def test_status_normalized(self):
        ps = valid_plan_step(status="  PENDING  ")
        assert ps.status == "pending"

    def test_dependencies(self):
        ps = valid_plan_step(dependencies=["ps_001"])
        assert "ps_001" in ps.dependencies

    def test_parameters(self):
        ps = valid_plan_step(parameters={"max_depth": 3, "min_confidence": 0.3})
        assert ps.parameters["max_depth"] == 3

    def test_secondary_ids(self):
        ps = valid_plan_step(secondary_ids=["clu_004", "clu_005"])
        assert len(ps.secondary_ids) == 2

    def test_result_storage(self):
        ps = valid_plan_step(result={"paths": []})
        assert ps.result == {"paths": []}

    def test_sequence_must_be_positive(self):
        with pytest.raises(ValidationError):
            valid_plan_step(sequence=0)


# ===========================================================================
# ExecutionPlan
# ===========================================================================


class TestExecutionPlan:
    def test_valid_creation(self):
        ep = valid_execution_plan()
        assert ep.plan_id == "plan_abc123"
        assert len(ep.steps) == 1
        assert ep.total_steps == 1

    def test_total_steps_auto_computed(self):
        step_a = valid_plan_step(step_id="ps_001", sequence=1)
        step_b = valid_plan_step(step_id="ps_002", sequence=2)
        ep = valid_execution_plan(steps=[step_a, step_b], total_steps=0)
        assert ep.total_steps == 2

    def test_duplicate_step_ids(self):
        step_a = valid_plan_step(step_id="ps_001")
        step_b = valid_plan_step(step_id="ps_001", sequence=2)
        with pytest.raises(ValidationError, match="Duplicate step_id"):
            valid_execution_plan(steps=[step_a, step_b])

    def test_missing_dependency(self):
        step_a = valid_plan_step(step_id="ps_001", dependencies=["ps_999"])
        with pytest.raises(ValidationError, match="depends on"):
            valid_execution_plan(steps=[step_a])

    def test_valid_dependency(self):
        step_a = valid_plan_step(step_id="ps_001", sequence=1)
        step_b = valid_plan_step(step_id="ps_002", sequence=2, dependencies=["ps_001"])
        ep = valid_execution_plan(steps=[step_a, step_b])
        assert len(ep.steps) == 2

    def test_invalid_complexity(self):
        with pytest.raises(ValidationError, match="complexity"):
            valid_execution_plan(estimated_complexity="extreme")

    def test_complexity_normalized(self):
        ep = valid_execution_plan(estimated_complexity="  HIGH  ")
        assert ep.estimated_complexity == "high"

    def test_parallel_groups(self):
        ep = valid_execution_plan(parallel_groups=[["ps_001"]])
        assert ep.parallel_groups == [["ps_001"]]

    def test_warnings(self):
        ep = valid_execution_plan(warnings=["No planner for query type"])
        assert len(ep.warnings) == 1

    def test_multiple_steps_ordering(self):
        steps = [
            valid_plan_step(step_id="ps_001", sequence=1),
            valid_plan_step(step_id="ps_002", sequence=2),
            valid_plan_step(step_id="ps_003", sequence=3, dependencies=["ps_001"]),
        ]
        ep = valid_execution_plan(steps=steps)
        assert ep.total_steps == 3

    def test_empty_step_ids_rejected(self):
        with pytest.raises(ValidationError, match="non-empty"):
            valid_execution_plan(steps=[valid_plan_step(step_id="")])

    def test_no_steps_valid(self):
        ep = valid_execution_plan(steps=[])
        assert ep.total_steps == 0


# ===========================================================================
# AggregatedEvidence
# ===========================================================================


class TestAggregatedEvidence:
    def test_valid_creation(self):
        ev = valid_aggregated_evidence()
        assert ev.evidence_id == "ev_001"
        assert ev.confidence == 0.85
        assert len(ev.trace) == 2

    def test_invalid_confidence(self):
        with pytest.raises(ValidationError):
            valid_aggregated_evidence(confidence=1.5)

    def test_confidence_low_bound(self):
        ev = valid_aggregated_evidence(confidence=0.0)
        assert ev.confidence == 0.0

    def test_path_edge_requires_trace(self):
        with pytest.raises(ValidationError, match="trace chain"):
            valid_aggregated_evidence(evidence_type="path_edge", trace=[])

    def test_contradiction_requires_trace(self):
        with pytest.raises(ValidationError, match="trace chain"):
            valid_aggregated_evidence(evidence_type="contradiction", trace=[])

    def test_consensus_entry_requires_trace(self):
        with pytest.raises(ValidationError, match="trace chain"):
            valid_aggregated_evidence(evidence_type="consensus_entry", trace=[])

    def test_gap_item_allows_empty_trace(self):
        ev = valid_aggregated_evidence(evidence_type="gap_item", trace=[])
        assert ev.evidence_type == "gap_item"
        assert ev.trace == []

    def test_evidence_id_empty_allowed(self):
        ev = valid_aggregated_evidence(evidence_id="")
        assert ev.evidence_id == ""

    def test_source_engine(self):
        ev = valid_aggregated_evidence(source_engine="consensus")
        assert ev.source_engine == "consensus"

    def test_relation_type(self):
        ev = valid_aggregated_evidence(relation_type="USES_DATASET")
        assert ev.relation_type == "USES_DATASET"

    def test_all_fields(self):
        ev = AggregatedEvidence(
            evidence_id="ev_042",
            source_text="Dropout reduces overfitting.",
            confidence=0.75,
            source_engine="consensus",
            source_document_id="doc_007",
            source_document_title="Dropout: A Simple Way to Prevent Neural Networks from Overfitting",
            relation_type="SUPPORTS",
            evidence_type="consensus_entry",
            trace=["chunk_042"],
            metadata={"document_count": 5},
        )
        assert ev.evidence_id == "ev_042"
        assert ev.metadata["document_count"] == 5
        assert len(ev.trace) == 1


# ===========================================================================
# ReasoningStep
# ===========================================================================


class TestReasoningStep:
    def test_valid_creation(self):
        rs = valid_reasoning_step()
        assert rs.step_id == "rs_001"
        assert rs.engine == "multi_hop"
        assert rs.confidence == 0.85
        assert rs.evidence_ids == ["ev_001"]

    def test_confidence_default(self):
        rs = ReasoningStep(step_id="rs_002", engine="consensus")
        assert rs.confidence == 0.0

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            ReasoningStep(step_id="rs_003", engine="gap", confidence=-0.1)

    def test_confidence_at_bound(self):
        rs = ReasoningStep(step_id="rs_004", engine="synthesize", confidence=1.0)
        assert rs.confidence == 1.0

    def test_metadata(self):
        rs = ReasoningStep(
            step_id="rs_005",
            engine="multi_hop",
            metadata={"paths_found": 3},
        )
        assert rs.metadata["paths_found"] == 3

    def test_empty_evidence_ids(self):
        rs = valid_reasoning_step(evidence_ids=[])
        assert rs.evidence_ids == []

    def test_serialization(self):
        rs = valid_reasoning_step()
        d = rs.model_dump()
        assert d["step_id"] == "rs_001"
        assert d["engine"] == "multi_hop"
        assert d["confidence"] == 0.85


# ===========================================================================
# ResearchAnswer
# ===========================================================================


class TestResearchAnswer:
    def test_valid_full_answer(self):
        ans = valid_research_answer()
        assert ans.answer_id == "ans_001"
        assert ans.answer == "BERT is associated with USES_DATASET to BookCorpus."
        assert ans.confidence == 0.85
        assert ans.traceability_verified is False
        assert len(ans.evidence) == 1
        assert len(ans.reasoning_trace) == 1

    def test_non_empty_answer_required(self):
        with pytest.raises(ValidationError, match="non-empty"):
            valid_research_answer(answer="")

    def test_whitespace_answer_rejected(self):
        with pytest.raises(ValidationError, match="non-empty"):
            valid_research_answer(answer="   ")

    def test_confidence_bounds_high(self):
        with pytest.raises(ValidationError):
            valid_research_answer(confidence=1.5)

    def test_confidence_bounds_low(self):
        with pytest.raises(ValidationError):
            valid_research_answer(confidence=-0.5)

    def test_traceability_flag_consistency(self):
        with pytest.raises(ValidationError, match="traceability_verified"):
            valid_research_answer(
                traceability_failures=["Missing document"],
                traceability_verified=True,
            )

    def test_traceability_failures_allow_false(self):
        ans = valid_research_answer(
            traceability_failures=["Missing document"],
            traceability_verified=False,
        )
        assert not ans.traceability_verified
        assert len(ans.traceability_failures) == 1

    def test_evidence_ids_dedup(self):
        ev1 = valid_aggregated_evidence(evidence_id="ev_001")
        ev2 = valid_aggregated_evidence(evidence_id="ev_002", source_text="Second evidence.")
        ans = valid_research_answer(
            evidence=[ev1, ev2],
            evidence_ids=["ev_001", "ev_001", "ev_002"],
        )
        assert ans.evidence_ids == ["ev_001", "ev_002"]

    def test_supporting_documents_dedup(self):
        ans = valid_research_answer(supporting_documents=["doc_001", "doc_001", "doc_002"])
        assert ans.supporting_documents == ["doc_001", "doc_002"]

    def test_evidence_consistency(self):
        ev = valid_aggregated_evidence(evidence_id="ev_001")
        ans = valid_research_answer(evidence=[ev], evidence_ids=["ev_001"])
        assert ans.evidence[0].evidence_id == "ev_001"

    def test_evidence_consistency_mismatch(self):
        ev = valid_aggregated_evidence(evidence_id="ev_001")
        with pytest.raises(ValidationError, match="evidence_ids"):
            valid_research_answer(evidence=[ev], evidence_ids=["ev_999"])

    def test_evidence_consistency_empty_flat_list(self):
        ev = valid_aggregated_evidence(evidence_id="ev_001")
        ans = valid_research_answer(evidence=[ev], evidence_ids=[])
        assert ans.evidence[0].evidence_id == "ev_001"

    def test_no_evidence_policy(self):
        ans = valid_research_answer(
            evidence=[],
            evidence_ids=[],
            confidence=0.0,
        )
        assert ans.confidence == 0.0
        assert len(ans.evidence) == 0

    def test_minimal_valid(self):
        rq = valid_research_query()
        ans = ResearchAnswer(
            answer_id="ans_999",
            query=rq,
            answer="No evidence found.",
            confidence=0.0,
            generated_at=NOW,
            query_type="FACTUAL",
        )
        assert ans.answer_id == "ans_999"

    def test_classification_field(self):
        ans = valid_research_answer(classification="strong_consensus")
        assert ans.classification == "strong_consensus"

    def test_classification_none_by_default(self):
        ans = valid_research_answer()
        assert ans.classification is None

    def test_engines_invoked(self):
        ans = valid_research_answer(engines_invoked=["multi_hop", "consensus"])
        assert len(ans.engines_invoked) == 2

    def test_steps_counters(self):
        ans = valid_research_answer(steps_executed=3, steps_failed=0)
        assert ans.steps_executed == 3
        assert ans.steps_failed == 0

    def test_warnings_and_errors(self):
        ans = valid_research_answer(
            warnings=["Low confidence"],
            errors=["Engine timeout"],
        )
        assert len(ans.warnings) == 1
        assert len(ans.errors) == 1

    def test_processing_time(self):
        ans = valid_research_answer(processing_time_ms=150)
        assert ans.processing_time_ms == 150

    def test_serialization_roundtrip(self):
        ans = valid_research_answer()
        d = ans.model_dump()
        restored = ResearchAnswer(**d)
        assert restored.answer_id == ans.answer_id
        assert restored.confidence == ans.confidence
        assert len(restored.evidence) == len(ans.evidence)
        assert len(restored.reasoning_trace) == len(ans.reasoning_trace)

    def test_source_attribution(self):
        ans = valid_research_answer(
            source_attribution={"doc_001": ["ev_001", "ev_002"]},
        )
        assert "doc_001" in ans.source_attribution
        assert len(ans.source_attribution["doc_001"]) == 2


# ===========================================================================
# Cross-model integration
# ===========================================================================


class TestCrossModel:
    def test_full_pipeline_types(self):
        rq = valid_research_query()
        pq = valid_parsed_query()
        rq.parsed = pq
        step = valid_plan_step()
        plan = valid_execution_plan(steps=[step])
        ev = valid_aggregated_evidence()
        rs = valid_reasoning_step()
        ans = ResearchAnswer(
            answer_id="ans_full",
            query=rq,
            plan=plan,
            answer="Complete pipeline test.",
            confidence=0.9,
            generated_at=NOW,
            evidence=[ev],
            evidence_ids=[ev.evidence_id],
            reasoning_trace=[rs],
            query_type=pq.query_type,
        )
        assert ans.query.parsed.query_type == "FACTUAL"
        assert ans.plan.steps[0].engine == "multi_hop"
        assert ans.evidence[0].confidence == 0.85

    def test_research_gap_no_entities(self):
        rq = ResearchQuery(
            query_id="qry_gap",
            raw_query="What research gaps exist?",
            created_at=NOW,
        )
        pq = ParsedQuery(
            raw_query=rq.raw_query,
            query_type="RESEARCH_GAP",
            entities_resolved=True,
        )
        rq.parsed = pq
        assert pq.query_type == "RESEARCH_GAP"

    def test_constraint_propagation(self):
        c = valid_query_constraint(field="year", operator="gte", value=2020)
        rq = valid_research_query(constraints=[c])
        assert len(rq.constraints) == 1
        assert rq.constraints[0].value == 2020

    def test_entity_confidence_to_answer(self):
        ent = valid_query_entity(confidence=0.95)
        pq = valid_parsed_query(primary_entity=ent)
        assert pq.primary_entity.confidence == 0.95


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases:
    def test_entity_type_none(self):
        ent = QueryEntity(text="ResNet")
        assert ent.entity_type is None

    def test_constraint_field_empty(self):
        with pytest.raises(ValidationError):
            valid_query_constraint(field="")

    def test_constraint_operator_empty(self):
        with pytest.raises(ValidationError):
            valid_query_constraint(operator="")

    def test_sequence_zero_rejected(self):
        with pytest.raises(ValidationError):
            valid_plan_step(sequence=0)

    def test_negative_sequence_rejected(self):
        with pytest.raises(ValidationError):
            valid_plan_step(sequence=-1)

    def test_empty_step_id(self):
        with pytest.raises(ValidationError, match="non-empty"):
            valid_execution_plan(steps=[valid_plan_step(step_id="")])

    def test_value_error_contains_field_name(self):
        with pytest.raises(ValidationError):
            QueryEntity(text="test", entity_type="not_valid")

    def test_all_query_types_str(self):
        for qt in QueryType:
            assert isinstance(str(qt), str)

    def test_query_entity_text_empty(self):
        with pytest.raises(ValidationError):
            QueryEntity(text="")

    def test_aggregated_evidence_trace_mutation(self):
        ev = valid_aggregated_evidence()
        ev.trace.append("chunk_003")
        assert len(ev.trace) == 3

    def test_research_answer_no_plan(self):
        rq = valid_research_query()
        ans = valid_research_answer(plan=None)
        assert ans.plan is None

    def test_research_answer_default_traceability(self):
        ans = valid_research_answer()
        assert ans.traceability_verified is False
        assert ans.traceability_failures == []

    def test_plan_step_warnings_immutable_default(self):
        ps = valid_plan_step()
        assert isinstance(ps.warnings, list)
        assert len(ps.warnings) == 0

    def test_execution_plan_default_complexity(self):
        ep = valid_execution_plan()
        assert ep.estimated_complexity == "low"

    def test_research_query_parsed_none(self):
        rq = valid_research_query()
        assert rq.parsed is None

    def test_parsed_query_entity_not_resolved_default(self):
        pq = valid_parsed_query(entities_resolved=False)
        assert pq.entities_resolved is False
