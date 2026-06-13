"""Tests for the M5 query parser.

Covers type detection (cascade + priority), constraint extraction,
entity extraction (with mocked corpus), and full end-to-end parsing.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from researchmind.query.models import (
    ParsedQuery,
    QueryConstraint,
    QueryEntity,
    QueryType,
)
from researchmind.query.parser import (
    QueryParser,
    _detect_ambiguity,
    _detect_type,
    _extract_constraints,
    _extract_entities,
    _normalize,
    parse_query,
)

# ---------------------------------------------------------------------------
# Mock helpers for entity extraction tests
# ---------------------------------------------------------------------------


class _Label:
    def __init__(self, value: str):
        self.value = value


class _CanonicalEntity:
    def __init__(self, entity_type: str):
        self.label = _Label(entity_type)


class _Cluster:
    def __init__(self, cluster_id: str, label: str, entity_type: str = "concept"):
        self.cluster_id = cluster_id
        self.label = label
        self.canonical_entity = _CanonicalEntity(entity_type)


class _Doc:
    def __init__(self, title: str, doc_id: str, label: str | None = None):
        self.title = title
        self.doc_id = doc_id
        self.label = label or title


class _Corpus:
    def __init__(self, docs: list | None = None, clusters: list | None = None):
        self.documents = docs or []
        self.clusters = clusters or []


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_lowercases(self):
        assert _normalize("What IS This") == "what is this"

    def test_collapses_whitespace(self):
        assert _normalize("  what   is   BERT  ") == "what is bert"

    def test_strips_punctuation(self):
        result = _normalize("What datasets does BERT use?")
        assert result == "what datasets does bert use?"

    def test_empty_string(self):
        assert _normalize("") == ""

    def test_whitespace_only(self):
        assert _normalize("   ") == ""

    def test_mixed_case_and_spaces(self):
        assert _normalize("  EXPLAIN   How   DOES   BERT   Work?  ") == "explain how does bert work?"


# ---------------------------------------------------------------------------
# _detect_type — cascade rules + priority + fallback
# ---------------------------------------------------------------------------


class TestTypeDetection:
    def test_contradiction_detected(self):
        qtype, warns = _detect_type("papers that contradict the findings", 0)
        assert qtype == "CONTRADICTION"
        assert warns == []

    def test_contradiction_with_disagree(self):
        qtype, warns = _detect_type("which papers disagree with this result", 0)
        assert qtype == "CONTRADICTION"
        assert warns == []

    def test_contradiction_with_conflict(self):
        qtype, warns = _detect_type("conflicting results about dropout", 0)
        assert qtype == "CONTRADICTION"

    def test_contradiction_with_inconsistent(self):
        qtype, warns = _detect_type("inconsistent findings on GAN training", 0)
        assert qtype == "CONTRADICTION"

    def test_contradiction_with_opposing(self):
        qtype, warns = _detect_type("opposing views on attention mechanisms", 0)
        assert qtype == "CONTRADICTION"

    def test_comparison_detected(self):
        qtype, warns = _detect_type("compare Adam and SGD", 2)
        assert qtype == "COMPARISON"
        assert warns == []

    def test_comparison_with_vs(self):
        qtype, warns = _detect_type("Adam vs SGD", 2)
        assert qtype == "COMPARISON"

    def test_comparison_with_difference(self):
        qtype, warns = _detect_type("difference between ResNet and U-Net", 2)
        assert qtype == "COMPARISON"

    def test_comparison_skipped_with_few_entities(self):
        qtype, warns = _detect_type("compare Adam and SGD", 1)
        assert qtype != "COMPARISON"

    def test_consensus_detected(self):
        qtype, warns = _detect_type("what is the consensus on dropout", 1)
        assert qtype == "CONSENSUS"
        assert warns == []

    def test_consensus_with_agreement(self):
        qtype, warns = _detect_type("do papers agree about Adam", 1)
        assert qtype == "CONSENSUS"

    def test_consensus_with_broadly_supported(self):
        qtype, warns = _detect_type("broadly supported claims about batch norm", 1)
        assert qtype == "CONSENSUS"

    def test_research_gap_detected(self):
        qtype, warns = _detect_type("what research gaps exist around GANs", 0)
        assert qtype == "RESEARCH_GAP"
        assert warns == []

    def test_research_gap_with_missing(self):
        qtype, warns = _detect_type("missing comparisons in GAN literature", 0)
        assert qtype == "RESEARCH_GAP"

    def test_research_gap_with_lack_of(self):
        qtype, warns = _detect_type("lack of research on transformers", 0)
        assert qtype == "RESEARCH_GAP"

    def test_research_gap_with_not_studied(self):
        qtype, warns = _detect_type("what has not been studied in RL", 0)
        assert qtype == "RESEARCH_GAP"

    def test_explanation_detected(self):
        qtype, warns = _detect_type("explain how attention works", 1)
        assert qtype == "EXPLANATION"
        assert warns == []

    def test_explanation_with_describe(self):
        qtype, warns = _detect_type("describe the attention mechanism", 1)
        assert qtype == "EXPLANATION"

    def test_explanation_with_mechanism(self):
        qtype, warns = _detect_type("what is the mechanism of batch norm", 1)
        assert qtype == "EXPLANATION"

    def test_explanation_with_how_does_work(self):
        qtype, warns = _detect_type("how does dropout work", 1)
        assert qtype == "EXPLANATION"

    def test_explanation_catches_how_is_connected(self):
        qtype, warns = _detect_type("how is BERT connected to ImageNet", 2)
        assert qtype == "EXPLANATION"

    def test_multi_hop_with_path_between(self):
        qtype, warns = _detect_type("path between BERT and ImageNet", 2)
        assert qtype == "MULTI_HOP"
        assert warns == []

    def test_multi_hop_with_connection_between(self):
        qtype, warns = _detect_type("connection between Adam and Attention", 2)
        assert qtype == "MULTI_HOP"

    def test_multi_hop_with_relationship(self):
        qtype, warns = _detect_type("relationship between Adam and Attention", 2)
        assert qtype == "MULTI_HOP"

    def test_multi_hop_with_find_paths(self):
        qtype, warns = _detect_type("find paths between BERT and GPT", 2)
        assert qtype == "MULTI_HOP"

    def test_multi_hop_skipped_with_few_entities(self):
        qtype, warns = _detect_type("path between BERT and ImageNet", 1)
        assert qtype != "MULTI_HOP"

    def test_factual_with_what_is(self):
        qtype, warns = _detect_type("what is BERT", 1)
        assert qtype == "FACTUAL"
        assert warns == []

    def test_factual_with_who_proposed(self):
        qtype, warns = _detect_type("who proposed batch normalization", 1)
        assert qtype == "FACTUAL"

    def test_factual_with_which_dataset(self):
        qtype, warns = _detect_type("which dataset is used with BERT", 1)
        assert qtype == "FACTUAL"

    def test_factual_with_how_many(self):
        qtype, warns = _detect_type("how many papers cite attention", 1)
        assert qtype == "FACTUAL"

    def test_factual_with_list(self):
        qtype, warns = _detect_type("list datasets used with BERT", 1)
        assert qtype == "FACTUAL"

    def test_exploration_detected(self):
        qtype, warns = _detect_type("show everything related to ResNet", 1)
        assert qtype == "EXPLORATION"
        assert warns == []

    def test_exploration_with_explore(self):
        qtype, warns = _detect_type("explore neighbors of BERT", 1)
        assert qtype == "EXPLORATION"

    def test_exploration_neighbors_of(self):
        qtype, warns = _detect_type("neighbors of BERT", 1)
        assert qtype == "EXPLORATION"

    # --- Priority tests ---

    def test_contradiction_priority_over_comparison(self):
        qtype, warns = _detect_type("compare contradicting results about Adam and SGD", 2)
        assert qtype == "CONTRADICTION"

    def test_contradiction_priority_over_consensus(self):
        qtype, warns = _detect_type(
            "is there a consensus on the disagreement about dropout", 1
        )
        assert qtype == "CONTRADICTION"

    def test_comparison_priority_over_multi_hop(self):
        qtype, warns = _detect_type(
            "compare the path between Adam and SGD vs BERT and GPT", 2
        )
        assert qtype == "COMPARISON"

    def test_explanation_priority_over_factual(self):
        qtype, warns = _detect_type("explain what BERT is", 1)
        assert qtype == "EXPLANATION"

    # --- Fallback tests ---

    def test_fallback_to_exploration_with_entities(self):
        qtype, warns = _detect_type("something completely random about BERT", 1)
        assert qtype == "EXPLORATION"
        assert len(warns) == 1
        assert "Unknown query type" in warns[0]

    def test_fallback_to_factual_without_entities(self):
        qtype, warns = _detect_type("something completely random", 0)
        assert qtype == "FACTUAL"
        assert len(warns) == 1
        assert "no entities" in warns[0]

    # --- Edge cases ---

    def test_no_pattern_match_zero_entities(self):
        qtype, warns = _detect_type("zzzzzzzzzzzzzzz", 0)
        assert qtype == "FACTUAL"

    def test_no_pattern_match_one_entity(self):
        qtype, warns = _detect_type("zzzzzzzzzz BERT", 1)
        assert qtype == "EXPLORATION"

    def test_case_insensitive_matching(self):
        qtype, warns = _detect_type("CONTRADICT the main claim", 0)
        assert qtype == "CONTRADICTION"


# ---------------------------------------------------------------------------
# _extract_constraints
# ---------------------------------------------------------------------------


class TestConstraintExtraction:
    def test_after_year(self):
        constraints = _extract_constraints("papers after 2018")
        assert len(constraints) == 1
        c = constraints[0]
        assert c.field == "year"
        assert c.operator == "gte"
        assert c.value == 2018

    def test_before_year(self):
        constraints = _extract_constraints("work before 2015")
        assert len(constraints) == 1
        c = constraints[0]
        assert c.field == "year"
        assert c.operator == "lte"
        assert c.value == 2015

    def test_since_year(self):
        constraints = _extract_constraints("research since 2020")
        assert len(constraints) == 1
        assert constraints[0].value == 2020

    def test_from_year(self):
        constraints = _extract_constraints("from 2017 onward")
        assert len(constraints) == 1
        assert constraints[0].value == 2017

    def test_high_confidence(self):
        constraints = _extract_constraints("show high confidence results")
        assert len(constraints) == 1
        c = constraints[0]
        assert c.field == "confidence"
        assert c.operator == "gte"
        assert c.value == 0.7

    def test_recent(self):
        constraints = _extract_constraints("recent papers about BERT")
        assert len(constraints) == 1
        c = constraints[0]
        assert c.field == "year"
        assert c.operator == "gte"
        assert c.value == 2020

    def test_multiple_constraints(self):
        constraints = _extract_constraints("papers after 2018 and before 2022")
        assert len(constraints) == 2
        years = {c.value for c in constraints if c.field == "year"}
        assert years == {2018, 2022}

    def test_constraint_with_after_and_confidence(self):
        constraints = _extract_constraints(
            "high confidence results after 2020"
        )
        assert len(constraints) == 2
        fields = {c.field for c in constraints}
        assert fields == {"year", "confidence"}

    def test_no_constraints(self):
        constraints = _extract_constraints("what datasets does BERT use")
        assert constraints == []

    def test_dedup_same_constraint(self):
        constraints = _extract_constraints("after 2018 and after 2018")
        assert len(constraints) == 1

    def test_year_edge_case_1000(self):
        constraints = _extract_constraints("after 1000")
        assert len(constraints) == 1
        assert constraints[0].value == 1000

    def test_year_edge_case_9999(self):
        constraints = _extract_constraints("before 9999")
        assert len(constraints) == 1
        assert constraints[0].value == 9999

    def test_not_a_year_in_text(self):
        constraints = _extract_constraints("what is the best method")
        assert len(constraints) == 0

    def test_recent_with_after(self):
        constraints = _extract_constraints("recent papers after 2018")
        assert len(constraints) == 2

    def test_confidence_not_extracted_without_keyword(self):
        constraints = _extract_constraints("low confidence results")
        assert len(constraints) == 0


# ---------------------------------------------------------------------------
# _extract_entities
# ---------------------------------------------------------------------------
# NOTE: _extract_entities expects a normalized (lowercased) query string.


class TestEntityExtraction:
    def test_no_corpus_returns_empty(self):
        primary, secondary, warns = _extract_entities("what is bert", None)
        assert primary is None
        assert secondary == []
        assert warns == []

    def test_document_title_matches(self):
        corpus = _Corpus(
            docs=[_Doc("BERT: Pre-training of Deep Bidirectional Transformers", "doc_001")]
        )
        primary, secondary, warns = _extract_entities(
            "what is bert: pre-training of deep bidirectional transformers", corpus
        )
        assert primary is not None
        assert primary.text == "BERT: Pre-training of Deep Bidirectional Transformers"
        assert primary.entity_type == "document"
        assert primary.cluster_id == "doc_001"
        assert primary.confidence == 1.0

    def test_document_title_partial_match(self):
        corpus = _Corpus(
            docs=[_Doc("BERT Pre-training", "doc_001")]
        )
        primary, secondary, warns = _extract_entities("explain bert pre-training", corpus)
        assert primary is not None
        assert primary.entity_type == "document"

    def test_cluster_label_matches(self):
        corpus = _Corpus(
            clusters=[_Cluster("clu_003", "BERT", "method")]
        )
        primary, secondary, warns = _extract_entities("what datasets does bert use", corpus)
        assert primary is not None
        assert primary.text == "BERT"
        assert primary.cluster_id == "clu_003"
        assert primary.confidence == 0.9
        assert primary.entity_type == "method"

    def test_cluster_label_refined_type(self):
        corpus = _Corpus(
            clusters=[_Cluster("clu_007", "SGD", "method")]
        )
        primary, secondary, warns = _extract_entities("compare adam and sgd", corpus)
        assert primary is not None
        assert primary.text == "SGD"
        assert primary.entity_type == "method"

    def test_cluster_with_dataset_type(self):
        corpus = _Corpus(
            clusters=[_Cluster("clu_020", "ImageNet", "dataset")]
        )
        primary, secondary, warns = _extract_entities("what is imagenet used for", corpus)
        assert primary is not None
        assert primary.entity_type == "dataset"

    def test_longest_label_matches_first(self):
        corpus = _Corpus(
            clusters=[
                _Cluster("clu_001", "Batch Normalization", "method"),
                _Cluster("clu_002", "Normalization", "concept"),
            ]
        )
        primary, secondary, warns = _extract_entities(
            "explain how batch normalization works", corpus
        )
        assert primary is not None
        assert primary.text == "Batch Normalization"
        assert primary.cluster_id == "clu_001"

    def test_multiple_entities_extracted(self):
        corpus = _Corpus(
            clusters=[
                _Cluster("clu_003", "BERT", "method"),
                _Cluster("clu_007", "SGD", "method"),
            ],
            docs=[_Doc("Attention Is All You Need", "doc_005")],
        )
        primary, secondary, warns = _extract_entities(
            "compare bert and sgd and attention is all you need", corpus
        )
        assert primary is not None
        assert len(secondary) >= 2

    def test_ambiguity_detected_two_clusters_same_label(self):
        entities = [
            QueryEntity(text="BERT", cluster_id="clu_001"),
            QueryEntity(text="BERT", cluster_id="clu_002"),
        ]
        _detect_ambiguity(entities)
        assert all(e.is_ambiguous for e in entities)
        assert entities[0].alternatives == ["clu_002"]
        assert entities[1].alternatives == ["clu_001"]

    def test_no_ambiguity_when_same_id(self):
        entities = [
            QueryEntity(text="BERT", cluster_id="clu_001"),
            QueryEntity(text="BERT", cluster_id="clu_001"),
        ]
        _detect_ambiguity(entities)
        assert not any(e.is_ambiguous for e in entities)

    def test_no_ambiguity_when_no_ids(self):
        entities = [
            QueryEntity(text="BERT"),
            QueryEntity(text="BERT"),
        ]
        _detect_ambiguity(entities)
        assert not any(e.is_ambiguous for e in entities)

    def test_ambiguity_mixed_doc_and_cluster(self):
        entities = [
            QueryEntity(text="Attention", cluster_id="doc_005"),
            QueryEntity(text="Attention", cluster_id="clu_012"),
        ]
        _detect_ambiguity(entities)
        assert all(e.is_ambiguous for e in entities)

    def test_empty_corpus(self):
        corpus = _Corpus()
        primary, secondary, warns = _extract_entities("what is bert", corpus)
        assert primary is None
        assert secondary == []

    def test_corpus_with_get_documents_method(self):
        class MethodCorpus:
            def get_documents(self):
                return [_Doc("BERT Paper", "doc_001")]

        primary, secondary, warns = _extract_entities(
            "bert paper", MethodCorpus()
        )
        assert primary is not None
        assert primary.cluster_id == "doc_001"

    def test_corpus_with_get_clusters_method(self):
        class MethodCorpus:
            def get_clusters(self):
                return [_Cluster("clu_003", "BERT", "method")]

        primary, secondary, warns = _extract_entities(
            "what is bert", MethodCorpus()
        )
        assert primary is not None
        assert primary.cluster_id == "clu_003"

    def test_doc_with_ruo_id(self):
        class DocWithRuo:
            def __init__(self, title, ruo_id):
                self.title = title
                self.ruo_id = ruo_id

        corpus = _Corpus(docs=[DocWithRuo("BERT Paper", "ruo_001")])
        primary, secondary, warns = _extract_entities("bert paper", corpus)
        assert primary is not None
        assert primary.cluster_id == "ruo_001"

    def test_cluster_with_id_attr(self):
        class ClusterWithId:
            def __init__(self, cid, label, entity_type):
                self.id = cid
                self.label = label
                self.canonical_entity = _CanonicalEntity(entity_type)

        corpus = _Corpus(
            clusters=[ClusterWithId("clu_003", "BERT", "method")]
        )
        primary, secondary, warns = _extract_entities("what is bert", corpus)
        assert primary is not None
        assert primary.cluster_id == "clu_003"

    def test_get_cluster_method(self):
        class MethodCorpus:
            def __init__(self):
                self.clusters = [_Cluster("clu_003", "BERT", "method")]

            def get_cluster(self, cluster_id):
                for c in self.clusters:
                    if c.cluster_id == cluster_id:
                        return c
                return None

            def get_clusters(self):
                return self.clusters

        corpus = MethodCorpus()
        primary, secondary, warns = _extract_entities("what is bert", corpus)
        assert primary is not None
        assert primary.entity_type == "method"

    def test_substring_match_finds_doc_title_in_text(self):
        corpus = _Corpus(
            docs=[_Doc("Attention Mechanism", "doc_001")]
        )
        primary, secondary, warns = _extract_entities(
            "what is the attention mechanism", corpus
        )
        assert primary is not None
        assert primary.text == "Attention Mechanism"

    def test_case_insensitive_entity_match(self):
        corpus = _Corpus(
            clusters=[_Cluster("clu_003", "BERT", "method")]
        )
        primary, secondary, warns = _extract_entities("what is bert", corpus)
        assert primary is not None
        assert primary.text == "BERT"


# ---------------------------------------------------------------------------
# QueryParser — full end-to-end
# ---------------------------------------------------------------------------


class TestQueryParser:
    def test_parse_factual_query_no_corpus(self):
        parsed = parse_query("What is BERT?")
        assert parsed.query_type == "FACTUAL"
        assert parsed.raw_query == "What is BERT?"

    def test_parse_with_corpus_factual(self):
        corpus = _Corpus(
            clusters=[_Cluster("clu_003", "BERT", "method")]
        )
        parsed = parse_query("What is BERT?", corpus=corpus)
        assert parsed.query_type == "FACTUAL"
        assert parsed.primary_entity is not None

    def test_parse_contradiction_query_with_corpus(self):
        corpus = _Corpus(
            clusters=[_Cluster("clu_007", "Adam", "method")]
        )
        parsed = parse_query(
            "What papers contradict the findings about Adam?", corpus=corpus
        )
        assert parsed.query_type == "CONTRADICTION"

    def test_parse_contradiction_no_entities_allowed(self):
        parsed = parse_query("What papers contradict the findings?")
        assert parsed.query_type == "CONTRADICTION"
        assert not parsed.entities_resolved

    def test_parse_comparison_query_with_corpus(self):
        corpus = _Corpus(
            clusters=[
                _Cluster("clu_003", "Adam", "method"),
                _Cluster("clu_007", "SGD", "method"),
            ]
        )
        parsed = parse_query("Compare Adam and SGD for optimization", corpus=corpus)
        assert parsed.query_type == "COMPARISON"

    def test_parse_consensus_query_with_corpus(self):
        corpus = _Corpus(
            clusters=[_Cluster("clu_005", "dropout", "concept")]
        )
        parsed = parse_query("What is the consensus on dropout?", corpus=corpus)
        assert parsed.query_type == "CONSENSUS"

    def test_parse_research_gap_query(self):
        parsed = parse_query("What research gaps exist around GANs?")
        assert parsed.query_type == "RESEARCH_GAP"

    def test_parse_explanation_query(self):
        corpus = _Corpus(
            clusters=[_Cluster("clu_001", "batch normalization", "method")]
        )
        parsed = parse_query("Explain how batch normalization works", corpus=corpus)
        assert parsed.query_type == "EXPLANATION"

    def test_parse_multi_hop_query_with_corpus(self):
        corpus = _Corpus(
            clusters=[
                _Cluster("clu_003", "BERT", "method"),
                _Cluster("clu_020", "ImageNet", "dataset"),
            ]
        )
        parsed = parse_query("path between BERT and ImageNet", corpus=corpus)
        assert parsed.query_type == "MULTI_HOP"

    def test_parse_exploration_query_with_corpus(self):
        corpus = _Corpus(
            clusters=[_Cluster("clu_003", "ResNet", "method")]
        )
        parsed = parse_query("Show everything related to ResNet", corpus=corpus)
        assert parsed.query_type == "EXPLORATION"

    def test_parse_with_entity_extraction(self):
        corpus = _Corpus(
            clusters=[_Cluster("clu_003", "BERT", "method")]
        )
        parser = QueryParser(corpus=corpus)
        parsed = parser.parse("What datasets does BERT use?")
        assert parsed.primary_entity is not None
        assert parsed.primary_entity.text == "BERT"
        assert parsed.primary_entity.cluster_id == "clu_003"
        assert parsed.primary_entity.entity_type == "method"

    def test_parse_with_constraints(self):
        corpus = _Corpus(
            clusters=[_Cluster("clu_003", "BERT", "method")]
        )
        parsed = parse_query("High confidence papers after 2020 about BERT", corpus=corpus)
        assert len(parsed.constraints) >= 2
        fields = {c.field for c in parsed.constraints}
        assert "year" in fields
        assert "confidence" in fields

    def test_parse_empty_query(self):
        parsed = parse_query("")
        assert parsed.query_type == "FACTUAL"
        assert not parsed.entities_resolved
        assert len(parsed.parsing_warnings) == 1
        assert "Empty query" in parsed.parsing_warnings[0]

    def test_parse_whitespace_only(self):
        parsed = parse_query("   ")
        assert parsed.query_type == "FACTUAL"
        assert len(parsed.parsing_warnings) == 1

    def test_parse_sets_entities_resolved_false_without_corpus(self):
        parsed = parse_query("What is BERT?")
        assert not parsed.entities_resolved

    def test_parse_sets_entities_resolved_true_with_corpus(self):
        corpus = _Corpus(
            clusters=[_Cluster("clu_003", "BERT", "method")]
        )
        parsed = parse_query("What is BERT?", corpus=corpus)
        assert parsed.entities_resolved

    def test_parse_contradiction_with_entity(self):
        corpus = _Corpus(
            clusters=[_Cluster("clu_007", "Adam", "method")]
        )
        parsed = parse_query(
            "What papers contradict Adam?", corpus=corpus
        )
        assert parsed.query_type == "CONTRADICTION"
        assert parsed.primary_entity is not None
        assert parsed.primary_entity.text == "Adam"

    def test_parse_entities_resolved_warning_factual(self):
        parsed = parse_query("What is BERT?")
        assert parsed.query_type == "FACTUAL"
        assert not parsed.entities_resolved
        entity_warnings = [
            w for w in parsed.parsing_warnings
            if "No entities resolved" in w
        ]
        assert len(entity_warnings) == 1

    def test_parse_factual_fallback_no_entities(self):
        parsed = parse_query("zzzzzzzzz")
        assert parsed.query_type == "FACTUAL"

    def test_parse_priority_order_correct(self):
        parsed = parse_query("disagree and compare Adam and SGD")
        assert parsed.query_type == "CONTRADICTION"

    def test_parse_with_multiple_entities(self):
        corpus = _Corpus(
            clusters=[
                _Cluster("clu_003", "BERT", "method"),
                _Cluster("clu_007", "SGD", "method"),
            ]
        )
        parsed = parse_query("Compare BERT and SGD", corpus=corpus)
        assert parsed.primary_entity is not None
        assert len(parsed.secondary_entities) >= 1

    def test_parse_with_ambiguity(self):
        corpus = _Corpus(
            clusters=[
                _Cluster("clu_001", "BERT", "method"),
                _Cluster("clu_002", "BERT", "dataset"),
            ]
        )
        parsed = parse_query("What is BERT?", corpus=corpus)
        assert parsed.primary_entity is not None
        assert parsed.primary_entity.is_ambiguous
        assert len(parsed.primary_entity.alternatives) >= 1

    def test_parse_stores_parsing_warnings_for_fallback(self):
        parsed = parse_query("complete gibberish about nothing")
        assert len(parsed.parsing_warnings) >= 1

    def test_parse_preserves_raw_query(self):
        raw = "What is BERT?"
        parsed = parse_query(raw)
        assert parsed.raw_query == raw

    def test_parse_reusable_parser(self):
        corpus = _Corpus(
            clusters=[_Cluster("clu_003", "BERT", "method")]
        )
        parser = QueryParser(corpus=corpus)
        r1 = parser.parse("What is BERT?")
        r2 = parser.parse("Explain BERT")
        assert r1.query_type == "FACTUAL"
        assert r2.query_type == "EXPLANATION"
        assert r1.primary_entity is not None
        assert r2.primary_entity is not None

    def test_query_type_matches_enum(self):
        parsed = parse_query("What is BERT?")
        assert parsed.query_type in {qt.name for qt in QueryType}


# ---------------------------------------------------------------------------
# Integration with ParsedQuery model validation
# ---------------------------------------------------------------------------


class TestParserModelIntegration:
    def test_parse_output_validates_as_parsedquery(self):
        parsed = parse_query("What is BERT?")
        assert isinstance(parsed, ParsedQuery)

    def test_parse_output_can_be_roundtripped(self):
        parsed = parse_query("What is BERT?")
        dump = parsed.model_dump()
        reloaded = ParsedQuery(**dump)
        assert reloaded.raw_query == parsed.raw_query
        assert reloaded.query_type == parsed.query_type

    def test_parse_with_entity_can_be_roundtripped(self):
        corpus = _Corpus(
            clusters=[_Cluster("clu_003", "BERT", "method")]
        )
        parsed = parse_query("What is BERT?", corpus=corpus)
        dump = parsed.model_dump()
        reloaded = ParsedQuery(**dump)
        assert reloaded.primary_entity is not None
        assert reloaded.primary_entity.text == "BERT"

    def test_constraints_from_parser_are_valid(self):
        parsed = parse_query("papers after 2020")
        for c in parsed.constraints:
            assert isinstance(c, QueryConstraint)
        assert len(parsed.constraints) == 1

    def test_entities_from_parser_are_valid_queryentity(self):
        corpus = _Corpus(
            clusters=[_Cluster("clu_003", "BERT", "method")]
        )
        parsed = parse_query("what is BERT", corpus=corpus)
        assert isinstance(parsed.primary_entity, QueryEntity)

    def test_parsedquery_without_entities_resolved_false_accepted(self):
        pq = ParsedQuery(
            raw_query="What is BERT?",
            query_type="FACTUAL",
            entities_resolved=False,
        )
        assert pq.query_type == "FACTUAL"
        assert not pq.entities_resolved

    def test_parsedquery_without_entities_resolved_true_rejected(self):
        with pytest.raises(ValidationError, match="requires at least one entity"):
            ParsedQuery(
                raw_query="What is BERT?",
                query_type="FACTUAL",
                entities_resolved=True,
            )


# ---------------------------------------------------------------------------
# Edge cases and error handling
# ---------------------------------------------------------------------------


class TestParserEdgeCases:
    def test_special_characters_in_query(self):
        parsed = parse_query("What's the difference between BERT and GPT?")
        assert parsed.query_type in ("COMPARISON", "EXPLANATION", "FACTUAL")

    def test_query_with_numbers(self):
        parsed = parse_query("List 5 datasets used with BERT")
        assert parsed.query_type == "FACTUAL"

    def test_query_with_parentheses(self):
        corpus = _Corpus(
            clusters=[_Cluster("clu_003", "BERT", "method")]
        )
        parsed = parse_query("Explain BERT (Bidirectional Encoder Representations)", corpus=corpus)
        assert parsed.query_type == "EXPLANATION"

    def test_very_long_query(self):
        long_q = "I want to know about " + "machine learning " * 50
        parsed = parse_query(long_q)
        assert parsed.raw_query == long_q

    def test_parse_query_function_same_as_parser(self):
        q1 = parse_query("What is BERT?")
        q2 = QueryParser().parse("What is BERT?")
        assert q1.query_type == q2.query_type
        assert q1.raw_query == q2.raw_query

    def test_mixed_case_query_type_detection(self):
        corpus = _Corpus(
            clusters=[_Cluster("clu_005", "dropout", "concept")]
        )
        parsed = parse_query("EXPLAIN HOW DROPOUT WORKS", corpus=corpus)
        assert parsed.query_type == "EXPLANATION"

    def test_query_with_only_stop_words(self):
        parsed = parse_query("What is the of and to in for?")
        assert parsed.query_type == "FACTUAL"

    def test_query_ending_with_question_mark(self):
        parsed = parse_query("Who proposed batch normalization?")
        assert parsed.query_type == "FACTUAL"


# ---------------------------------------------------------------------------
# _DETECTION_RULES structural tests
# ---------------------------------------------------------------------------


class TestDetectionRulesStructure:
    def test_all_eight_types_present(self):
        from researchmind.query.parser import _DETECTION_RULES
        type_names = {name for name, _ in _DETECTION_RULES}
        expected = {
            "CONTRADICTION", "COMPARISON", "CONSENSUS",
            "RESEARCH_GAP", "EXPLANATION", "MULTI_HOP",
            "FACTUAL", "EXPLORATION",
        }
        assert type_names == expected

    def test_rules_in_correct_priority_order(self):
        from researchmind.query.parser import _DETECTION_RULES
        names = [name for name, _ in _DETECTION_RULES]
        contra_idx = names.index("CONTRADICTION")
        factual_idx = names.index("FACTUAL")
        assert contra_idx < factual_idx

    def test_each_rule_has_patterns(self):
        from researchmind.query.parser import _DETECTION_RULES
        for name, rule in _DETECTION_RULES:
            assert len(rule["patterns"]) > 0, f"{name} has no patterns"
            assert "min_entities" in rule

    def test_compiled_rules_match_raw(self):
        from researchmind.query.parser import _DETECTION_COMPILED, _DETECTION_RULES
        assert len(_DETECTION_COMPILED) == len(_DETECTION_RULES)
        for (cname, cpatterns, cmin), (rname, rrule) in zip(
            _DETECTION_COMPILED, _DETECTION_RULES
        ):
            assert cname == rname
            assert len(cpatterns) == len(rrule["patterns"])
            assert cmin == rrule["min_entities"]
