# Module 5 — Research Assistant Layer Architecture

**Status:** Design Document (remediated per audit)
**Date:** 2026-06-11
**Version:** 1.1

---
- [1. Scope](#1-scope)
- [2. Query Taxonomy](#2-query-taxonomy)
- [3. Query Models](#3-query-models)
- [4. Query Parsing Architecture](#4-query-parsing-architecture)
- [5. Query Planner](#5-query-planner)
- [6. Routing Engine](#6-routing-engine)
- [7. Evidence Aggregation](#7-evidence-aggregation)
- [8. Answer Synthesis](#8-answer-synthesis)
- [9. ResearchAnswer Model](#9-researchanswer-model)
- [10. Traceability Contract](#10-traceability-contract)
- [11. Query Lifecycle](#11-query-lifecycle)
- [12. Failure Modes](#12-failure-modes)
- [13. Integration Plan](#13-integration-plan)
- [14. Evaluation Plan](#14-evaluation-plan)
- [Appendix A: Query Example Catalog](#appendix-a-query-example-catalog)
- [Appendix B: Template Library](#appendix-b-template-library)
- [Appendix C: Index Requirements](#appendix-c-index-requirements)

---

## 1. Scope

### 1.1 What Module 5 IS

Module 5 transforms ResearchMind from a data processing system into a **Research Assistant** — a layer that accepts natural research questions and produces answers, confidence scores, evidence chains, reasoning traces, and source attributions using only existing Modules 1–4.

| Capability | Description |
|---|---|
| **Query classification** | Deterministically classify natural-language research questions into 8 query types |
| **Entity extraction** | Extract research entities (methods, datasets, metrics, papers) from questions using corpus indexes |
| **Execution planning** | Decompose complex questions into multi-step execution plans over reasoning engines |
| **Engine routing** | Dispatch plan steps to the correct M4 sub-engines (MultiHop, Consensus, Contradiction, Gap) |
| **Evidence aggregation** | Collect, rank, deduplicate, and validate evidence from all M4 result types |
| **Answer synthesis** | Generate deterministic, template-driven answers with confidence and traceability |
| **Traceability enforcement** | Guarantee every output is traceable to source documents through evidence chains |

### 1.2 What Module 5 DOES NOT DO

| Out of Scope | Rationale |
|---|---|
| Natural language understanding | No LLMs, no embeddings, no NLU classifiers — only regex + dictionary + index matching |
| Knowledge creation | Cannot invent facts not present in the corpus |
| Evidence fabrication | Every claim must trace to a source document chunk |
| Corpus mutation | Read-only — never modifies RUO documents, graphs, or indexes |
| Query expansion or reformulation | No synonym expansion, no paraphrase detection, no spelling correction |
| Multi-turn conversation | Each query is independent — no session state, no context carry-over |
| Ranking or search | No vector search, BM25, or any document retrieval beyond corpus indexes |
| Code generation | No code output, no script generation, no API call construction |
| Document ingestion | Module 1 responsibility |
| Entity resolution | Module 3 responsibility |
| Reasoning execution | Module 4 responsibility |

### 1.3 Position in Pipeline

```
PDF → M1: Extraction → SRO → M2: Understanding → RUO
  → M3: Corpus Intelligence → CorpusGraph + Entity Clusters + Relations
    → M4: Reasoning Engine → MultiHop / Consensus / Contradiction / Gap results
      → **M5: Research Assistant ← YOU ARE HERE**
        → ResearchAnswer (answer + confidence + evidence + trace)
```

### 1.4 Consumption Boundary

| Consumed From | Artifact | Purpose |
|---|---|---|
| M3 `CorpusManager` | Entity index (entity label → cluster IDs) | Entity extraction from query text |
| M3 `CorpusManager` | Document index (title/DOI → RUO IDs) | Document disambiguation |
| M3 `CorpusGraphResult` | Node labels | Query entity → node ID resolution |
| M4 `ReasoningEngine` | `reason()` / `reason_batch()` | Primary query execution |
| M4 `MultiHopReasoner` | Exploration & path-finding | FACTUAL, EXPLORATION, MULTI_HOP queries |
| M4 `ConsensusEngine` | `analyze()` | CONSENSUS queries |
| M4 `ContradictionEngine` | `analyze()` | CONTRADICTION queries |
| M4 `ResearchGapEngine` | `analyze()` | RESEARCH_GAP queries |
| M4 `CorpusSynthesisEngine` | `synthesize()` | Cross-engine answer synthesis |

---

## 2. Query Taxonomy

### 2.1 Query Type Definitions

#### FACTUAL

| Aspect | Value |
|---|---|
| **Definition** | Ask for specific facts about entities, datasets, methods, or documents in the corpus |
| **Examples** | "What datasets are used with BERT?", "Who proposed Batch Normalization?", "What is the Adam optimizer?" |
| **Required inputs** | At least one entity or document reference |
| **Output expectations** | Concise factual answer with supporting evidence |
| **Routing target** | `MultiHopReasoner` (exploration mode) |
| **Answer template** | `Entity X [relation] Entity Y with confidence C` |

#### COMPARISON

| Aspect | Value |
|---|---|
| **Definition** | Compare two or more entities along a shared dimension |
| **Examples** | "How does Adam compare to SGD?", "Is ResNet better than U-Net for segmentation?" |
| **Required inputs** | Two or more entity references |
| **Output expectations** | Side-by-side comparison with shared/different attributes |
| **Routing target** | `MultiHopReasoner` + `ConsensusEngine` |
| **Answer template** | `X and Y share {attributes}, differ in {attributes}` |

#### EXPLANATION

| Aspect | Value |
|---|---|
| **Definition** | Explain a concept, method, or relationship using corpus evidence |
| **Examples** | "How does Batch Normalization work?", "Explain the attention mechanism." |
| **Required inputs** | One entity or concept reference |
| **Output expectations** | Multi-sentence explanation derived from document claims and triples |
| **Routing target** | `MultiHopReasoner` (path-finding) → answer built from chained evidence |
| **Answer template** | `X is described as {claim_1}. Further, {claim_2}.` |

#### CONSENSUS

| Aspect | Value |
|---|---|
| **Definition** | Assess agreement level across corpus documents about a claim or entity |
| **Examples** | "What is the consensus on Dropout?", "Do papers agree about Adam's effectiveness?" |
| **Required inputs** | Entity or claim reference |
| **Output expectations** | Support/contradict/neutral ratios, classification, per-document breakdown |
| **Routing target** | `ConsensusEngine` |
| **Answer template** | `Consensus on X: {ratio} support, {ratio} contradict, classification: {class}` |

#### CONTRADICTION

| Aspect | Value |
|---|---|
| **Definition** | Detect direct or indirect disagreements about a claim or entity |
| **Examples** | "What contradictions exist about GAN training stability?", "Which papers disagree with the Attention paper?" |
| **Required inputs** | Entity or document reference |
| **Output expectations** | List of direct and indirect contradictions with evidence |
| **Routing target** | `ContradictionEngine` |
| **Answer template** | `Found {N} contradiction(s): {list}` |

#### RESEARCH_GAP

| Aspect | Value |
|---|---|
| **Definition** | Identify under-explored areas, missing comparisons, or weak evidence |
| **Examples** | "What research gaps exist around GANs?", "Which methods lack comparisons?" |
| **Required inputs** | Optional entity filter; corpus-level if omitted |
| **Output expectations** | Categorized gaps with confidence and suggestions |
| **Routing target** | `ResearchGapEngine` |
| **Answer template** | `Gap analysis: {N} gap(s) found. {breakdown}` |

#### MULTI_HOP

| Aspect | Value |
|---|---|
| **Definition** | Trace multi-step relationships between entities across the graph |
| **Examples** | "How is BERT connected to ImageNet?", "Find paths between Adam and Attention." |
| **Required inputs** | Source entity, target entity (or exploration from source) |
| **Output expectations** | Paths with nodes, edges, confidence, and reasoning trace |
| **Routing target** | `MultiHopReasoner` (path-finding mode) |
| **Answer template** | `Path: X → Y → Z (confidence C, length L)` |

#### EXPLORATION

| Aspect | Value |
|---|---|
| **Definition** | Explore the neighborhood of an entity — what is connected and how |
| **Examples** | "What is connected to BERT?", "Show me everything related to ResNet." |
| **Required inputs** | Source entity reference |
| **Output expectations** | Neighboring nodes, edges, relationship types |
| **Routing target** | `MultiHopReasoner` (exploration mode) |
| **Answer template** | `Found {N} nodes and {M} edges connected to X` |

### 2.2 Query Type Comparison Matrix

| Property | FACTUAL | COMPARISON | EXPLANATION | CONSENSUS | CONTRADICTION | RESEARCH_GAP | MULTI_HOP | EXPLORATION |
|---|---|---|---|---|---|---|---|---|
| **Min entities** | 1 | 2 | 1 | 1 | 1 | 0 | 2 | 1 |
| **Sub-engines** | MultiHop | MultiHop+Consensus | MultiHop | Consensus | Contradiction | Gap | MultiHop | MultiHop |
| **Evidence depth** | 1 hop | N-hop + stance | Path chain | Per-doc | Per-edge | Per-gap | Path chain | 1-N hops |
| **Confidence method** | max edge | min(sub-results) | max(path) | consensus formula | max(edge) | gap formula | max(path) | max(edge) |
| **Evidence dedup** | edge_id | yes | path_id | doc_id | pair_id | gap key | path_seq | edge_id |
| **Answer format** | single fact | comparison table | paragraph | ratios | list | categories | path list | neighbor list |
| **Template type** | factual | comparative | explanatory | consensus | contradiction | gap | path | exploration |

---

## 3. Query Models

### 3.1 QueryEntity

```python
class QueryEntity(BaseModel):
    """An entity mention extracted from the user's question."""

    text: str                        # Raw text from query
    entity_type: str | None = None   # "method" | "dataset" | "metric" | "document" | "concept" | "unknown"
    node_id: str | None = None       # Resolved CorpusGraphNode.node_id (if found)
    cluster_id: str | None = None    # Resolved EntityCluster.cluster_id (if entity)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)  # Match confidence
    is_ambiguous: bool = False       # Multiple possible matches
    alternatives: list[str] = Field(default_factory=list)    # Alternative node_ids
```

### 3.2 QueryConstraint

```python
class QueryConstraint(BaseModel):
    """Constraint or filter on a query."""

    field: str                       # "year" | "confidence" | "document" | "relation_type"
    operator: str                    # "eq" | "neq" | "gt" | "gte" | "lt" | "lte" | "in"
    value: Any                       # Constraint value
```

**Validation rules:**
- `field` must be one of the recognized constraint fields
- `operator` must be a valid comparison operator
- `value` type must be compatible with `field` (e.g., `year` → int, `confidence` → float)

### 3.3 ParsedQuery

```python
class ParsedQuery(BaseModel):
    """Fully parsed and classified query ready for planning."""

    raw_query: str
    query_type: str                  # One of QueryType.*
    primary_entity: QueryEntity | None = None
    secondary_entities: list[QueryEntity] = Field(default_factory=list)
    constraints: list[QueryConstraint] = Field(default_factory=list)
    max_hops: int = Field(default=3, ge=1, le=10)
    min_confidence: float = Field(default=0.3, ge=0.0, le=1.0)
    include_reasoning: bool = True
    include_evidence: bool = True
    entities_resolved: bool = False
    parsing_warnings: list[str] = Field(default_factory=list)
```

**Validation rules:**
- `query_type` must be a known type from the taxonomy
- If `query_type` requires entities (FACTUAL, COMPARISON, etc.), at least one entity must be resolved
- `max_hops` clamped to `[1, 10]`
- `min_confidence` clamped to `[0.0, 1.0]`

### 3.4 ResearchQuery

```python
class ResearchQuery(BaseModel):
    """The top-level user query, before parsing."""

    query_id: str
    raw_query: str                   # Original user question
    created_at: datetime
    constraints: list[QueryConstraint] = Field(default_factory=list)
    max_hops: int = Field(default=3, ge=1, le=10)
    min_confidence: float = Field(default=0.3, ge=0.0, le=1.0)
    include_reasoning: bool = True
    include_evidence: bool = True
    parsed: ParsedQuery | None = None   # Populated after parsing
```

**Validation rules:**
- `raw_query` must be non-empty
- If `min_confidence` is set via constraint, it overrides the default
- `max_hops` is silently clamped to `[1, 10]`

---

## 4. Query Parsing Architecture

### 4.1 Design Principles

- **No NLP classifiers.** No spaCy, no NLTK, no LLMs.
- **No embeddings.** No vector similarity, no semantic search.
- **Deterministic only.** Same input → same parse every time.
- **Index-driven entity resolution.** Uses M3 entity and document indexes.
- **Pattern-based type detection.** Uses regex dictionaries keyed by query structure.

### 4.2 Query Type Detection

The detector uses a cascading set of regex patterns applied in priority order.

```python
_DETECTION_RULES: list[tuple[str, dict]] = [
    # Priority 1: CONTRADICTION (detect disagreement keywords first)
    ("CONTRADICTION", {
        "patterns": [
            r"contradict", r"disagree", r"conflict", r"inconsistent",
            r"opposing", r"different (results|findings|conclusions)",
            r"which papers (contradict|disagree with|refute)",
        ],
        "min_entities": 0,
    }),
    # Priority 2: COMPARISON (compare keywords)
    ("COMPARISON", {
        "patterns": [
            r"compare", r"difference between", r"better (than|worse)",
            r"vs\.?", r"versus", r"similarities", r"trade.?off",
            r"how does .* compare",
        ],
        "min_entities": 2,
    }),
    # Priority 3: CONSENSUS (agreement keywords)
    ("CONSENSUS", {
        "patterns": [
            r"consensus", r"agreement", r"do .* agree",
            r"what is the (general|prevailing|common) (view|opinion|wisdom)",
            r"broadly (accepted|supported)",
        ],
        "min_entities": 1,
    }),
    # Priority 4: RESEARCH_GAP
    ("RESEARCH_GAP", {
        "patterns": [
            r"research gap", r"under.?explored", r"missing",
            r"what (is|are) (the )?(open|remaining|unsolved) (questions|problems|challenges)",
            r"lack of (research|studies|work)",
            r"what (has|have) not been (studied|explored|investigated)",
        ],
        "min_entities": 0,
    }),
    # Priority 5: EXPLANATION (explicit explanation keywords only)
    ("EXPLANATION", {
        "patterns": [
            r"explain", r"how does .* work",
            r"describe", r"what (is|are) the (mechanism|principle|idea|concept)",
            r"how (is|are|does|do)",
        ],
        "min_entities": 1,
    }),
    # Priority 6: MULTI_HOP (path between two entities)
    ("MULTI_HOP", {
        "patterns": [
            r"(path|chain|sequence|route|connection) .* (between|from|to)",
            r"how (is|are) .* (connected|related|linked) (to|with)",
            r"find.*paths?",
            r"relationship between.*and",
        ],
        "min_entities": 2,
    }),
    # Priority 7: FACTUAL (fallback for entity queries)
    ("FACTUAL", {
        "patterns": [
            r"what (is|are|was|were|does|do|did)",  # Broadest pattern — catch-all
            r"who (proposed|introduced|created|developed|invented)",
            r"which (dataset|method|model|metric|technique)",
            r"how many",
            r"list",
        ],
        "min_entities": 1,
    }),
    # Priority 8: EXPLORATION (broad exploration)
    ("EXPLORATION", {
        "patterns": [
            r"(what|show|find|list|tell|display).*(connected|related|associated|linked|neighbor)",
            r"explore", r"neighbors? of", r"relationships? (involving|with|for)",
            r"everything (about|related|connected|associated)",
        ],
        "min_entities": 1,
    }),
]
```

**Algorithm:**
1. Normalize query (lowercase, strip punctuation)
2. Iterate rules in priority order
3. Return first rule where at least one pattern matches AND entity count ≥ `min_entities`
4. If no rule matches, default to `EXPLORATION` if any entity found, or `UNKNOWN`

**FACTUAL vs EXPLANATION precedence:**

The cascade prioritizes EXPLANATION (priority 5) before FACTUAL (priority 7). Since `r"what is (a|an|the) .*"` was removed from EXPLANATION patterns, the distinction is now pattern-driven:

| Query Pattern | Matches | Type | Reason |
|---|---|---|---|
| `explain ...` | EXPLANATION | EXPLANATION | Explicit explanation keyword |
| `how does ... work` | EXPLANATION | EXPLANATION | Mechanism question |
| `what is the mechanism/priniciple/idea/concept of ...` | EXPLANATION | EXPLANATION | Concept-level question |
| `what is the Adam optimizer` | FACTUAL | FACTUAL | Entity lookup, no explanation keyword |
| `who proposed ...` | FACTUAL | FACTUAL | Attribution question |
| `compare ...` | COMPARISON | COMPARISON | Caught at higher priority (2) |
| `what is connected to ...` | EXPLORATION | EXPLORATION | Caught at lower priority (8) |

Any query matching both EXPLANATION and FACTUAL patterns (e.g., "describe what BERT is") will resolve to EXPLANATION due to priority order. The `min_entities` guard also prevents EXPLANATION matching when no entity is found.

### 4.3 Entity Extraction

Entity extraction uses **three passes** against corpus indexes:

```python
class EntityExtractor:
    """Deterministic entity extraction using corpus indexes."""

    def extract(self, query: str, corpus: Any) -> list[QueryEntity]:
        entities = []

        # Pass 1: Document title matching
        doc_index = self._build_doc_index(corpus)  # title → (ruo_id, label)
        for title, (ruo_id, label) in doc_index.items():
            if title.lower() in query.lower():
                entities.append(QueryEntity(
                    text=title,
                    entity_type="document",
                    node_id=ruo_id,
                    confidence=1.0,
                ))

        # Pass 2: Entity cluster label matching (handles 1:many labels-to-clusters)
        cluster_index = self._build_cluster_index(corpus)  # label → list[EntityCluster]
        matched_labels = set()
        for label, clusters in sorted(cluster_index.items(),
                                      key=lambda x: -len(x[0])):
            if label.lower() in query.lower() and label.lower() not in matched_labels:
                matched_labels.add(label.lower())
                for cluster in clusters:
                    node_id = cluster.node_id if hasattr(cluster, 'node_id') else None
                    entities.append(QueryEntity(
                        text=label,
                        entity_type="concept",  # refined below
                        cluster_id=cluster.cluster_id,
                        node_id=node_id,
                        confidence=0.9,
                    ))

        # Pass 3: Refine entity types from cluster metadata
        for ent in entities:
            if ent.cluster_id:
                cluster = self._get_cluster(corpus, ent.cluster_id)
                if cluster and cluster.canonical_entity:
                    ent.entity_type = cluster.canonical_entity.label.value

        # Ambiguity detection: flag entities whose text matches multiple distinct node_ids
        self._detect_ambiguity(entities)

        return entities

    def _detect_ambiguity(self, entities: list[QueryEntity]) -> None:
        """Mark entities as ambiguous when multiple distinct node_ids share the same text."""
        from collections import defaultdict
        text_groups: dict[str, list[QueryEntity]] = defaultdict(list)
        for ent in entities:
            text_groups[ent.text.lower()].append(ent)

        for key, group in text_groups.items():
            unique_nodes = {e.node_id for e in group if e.node_id}
            if len(unique_nodes) > 1:
                for ent in group:
                    ent.is_ambiguous = True
                    ent.alternatives = [
                        e.node_id for e in group if e.node_id != ent.node_id
                    ]
```

### 4.4 Constraint Extraction

Constraints are extracted via post-processing patterns:

| Pattern | Constraint | Example |
|---|---|---|
| `after\s+(\d{4})\b` | `year ≥ value` | "papers after 2018" |
| `before\s+(\d{4})\b` | `year ≤ value` | "work before 2015" |
| `since\s+(\d{4})\b` | `year ≥ value` | "since 2020" |
| `from\s+(\d{4})\b` | `year ≥ value` | "from 2017 onward" |
| `high confidence` | `min_confidence = 0.7` | "high confidence results" |
| `recent\b` | `year ≥ current_year - 5` | "recent papers" |

### 4.5 Ambiguity Handling

| Scenario | Detection | Action |
|---|---|---|
| Multiple entities match same text | `alternatives.length > 1` | Set `is_ambiguous=True`, include all alternatives; planner will fan out |
| Entity matches both document and cluster | Both passes match | Prefer cluster match for concept queries, document for reference queries |
| No entity found for required type | Entity list is empty | Return parsing failure with `UNKNOWN_ENTITY` error |
| Multiple entities with same node_id | Dedup by node_id | Keep highest-confidence match |

### 4.6 Error Handling

| Error Code | Condition | Handler |
|---|---|---|
| `EMPTY_QUERY` | `raw_query` blank | Return `ParsedQuery(query_type="UNKNOWN")` with warning |
| `UNKNOWN_TYPE` | No pattern matches | Default to `EXPLORATION` if entities found, else `FACTUAL` |
| `UNKNOWN_ENTITY` | No entities resolved for required type | Return `ParsedQuery` with `entities_resolved=False`, warning |
| `AMBIGUOUS_ENTITY` | Entity with alternatives | Include all alternatives; planner creates fan-out steps |
| `INVALID_CONSTRAINT` | Constraint field/operator unrecognized | Drop constraint, add warning |
| `EXCESSIVE_HOPS` | `max_hops > 10` | Clamp to 10, add warning |
| `CASE_MISMATCH` | Entity text has unusual casing | Normalize before matching |

---

## 5. Query Planner

### 5.1 PlanStep

```python
class PlanStep(BaseModel):
    """A single step in an execution plan."""

    step_id: str                     # "plan_step_001"
    sequence: int                    # Execution order (1-indexed)
    engine: str                      # "multi_hop" | "consensus" | "contradiction" | "gap" | "aggregate" | "synthesize"
    query_type: str                  # The specific M4 query type to invoke
    target_id: str | None = None     # Primary entity/document/cluster ID
    secondary_ids: list[str] = Field(default_factory=list)
    parameters: dict = Field(default_factory=dict)  # Engine-specific params
    dependencies: list[str] = Field(default_factory=list)  # step_ids this step depends on
    status: str = "pending"          # "pending" | "running" | "completed" | "failed" | "skipped"
    result: Any = None               # Populated after execution
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)
```

### 5.2 ExecutionPlan

```python
class ExecutionPlan(BaseModel):
    """A complete execution plan for a parsed query."""

    plan_id: str
    query_id: str
    query_type: str
    steps: list[PlanStep]
    total_steps: int = 0
    parallel_groups: list[list[str]] = Field(default_factory=list)  # Steps that can run in parallel
    estimated_complexity: str = "low"  # "low" | "medium" | "high"
    warnings: list[str] = Field(default_factory=list)
```

### 5.3 Planning Algorithm

```python
class QueryPlanner:
    """Creates execution plans from parsed queries."""

    def plan(self, parsed: ParsedQuery, corpus: Any) -> ExecutionPlan:
        plan_id = f"plan_{uuid4().hex[:12]}"
        steps: list[PlanStep] = []
        seq = 0

        builders = {
            "FACTUAL": self._plan_factual,
            "COMPARISON": self._plan_comparison,
            "EXPLANATION": self._plan_explanation,
            "CONSENSUS": self._plan_consensus,
            "CONTRADICTION": self._plan_contradiction,
            "RESEARCH_GAP": self._plan_research_gap,
            "MULTI_HOP": self._plan_multi_hop,
            "EXPLORATION": self._plan_exploration,
        }
        builder = builders.get(parsed.query_type)
        if builder is None:
            return ExecutionPlan(
                plan_id=plan_id, query_id="", query_type=parsed.query_type,
                steps=[], total_steps=0, warnings=["No planner for query type"],
            )

        steps = builder(parsed, seq)
        total = len(steps)

        # Determine parallel groups (steps with no dependencies on each other)
        parallel = self._compute_parallel_groups(steps)

        # Estimate complexity
        complexity = self._estimate_complexity(steps)

        return ExecutionPlan(
            plan_id=plan_id,
            query_id=parsed.query_id if hasattr(parsed, 'query_id') else "",
            query_type=parsed.query_type,
            steps=steps,
            total_steps=total,
            parallel_groups=parallel,
            estimated_complexity=complexity,
        )
```

    def _compute_parallel_groups(self, steps: list[PlanStep]) -> list[list[str]]:
        """Identify sets of steps whose dependencies are independent.

        Uses topological layering: step A and step B can run in parallel if
        neither depends on the other, directly or transitively.
        """
        deps = {s.step_id: set(s.dependencies) for s in steps}
        groups = []
        remaining = set(deps.keys())
        while remaining:
            ready = {sid for sid in remaining if not deps[sid] & remaining}
            if not ready:
                break  # Cycle detected
            groups.append(sorted(ready))
            remaining -= ready
        return groups

    def _estimate_complexity(self, steps: list[PlanStep]) -> str:
        """Estimate execution complexity from step count and engine diversity."""
        if len(steps) <= 2:
            return "low"
        elif len(steps) <= 5:
            return "medium"
        else:
            return "high"

### 5.4 Execution Plan Examples

#### Example 1: "What datasets are commonly used with BERT?"

**Parsed query:**
```python
{
    "query_type": "FACTUAL",
    "primary_entity": {"text": "BERT", "cluster_id": "clu_003", "entity_type": "method"},
    "constraints": [],
    "entities_resolved": True,
}
```

**Execution plan:**
```yaml
plan_id: plan_a1b2c3d4e5f6
query_type: FACTUAL
steps:
  - step_id: ps_001
    sequence: 1
    engine: multi_hop
    query_type: ENTITY_LOOKUP
    target_id: "clu_003"           # BERT entity cluster
    parameters: {max_depth: 2, relation_types: [USES_DATASET, EXTENDS]}
    dependencies: []
  - step_id: ps_002
    sequence: 2
    engine: aggregate
    query_type: EVIDENCE_COLLECT
    target_id: "clu_003"
    parameters: {dedup_by: node_id}
    dependencies: [ps_001]
  - step_id: ps_003
    sequence: 3
    engine: synthesize
    query_type: ANSWER_BUILD
    parameters: {template: "factual_datasets"}
    dependencies: [ps_002]
parallel_groups: []
estimated_complexity: low
```

#### Example 2: "What papers contradict Adam?"

**Parsed query:**
```python
{
    "query_type": "CONTRADICTION",
    "primary_entity": {"text": "Adam", "cluster_id": "clu_007", "entity_type": "method"},
    "constraints": [],
    "entities_resolved": True,
}
```

**Execution plan:**
```yaml
plan_id: plan_x9y8z7w6v5u4
query_type: CONTRADICTION
steps:
  - step_id: ps_001
    sequence: 1
    engine: contradiction
    query_type: CONTRADICTION_ANALYSIS
    target_id: "clu_007"
    parameters: {min_confidence: 0.3}
    dependencies: []
  - step_id: ps_002
    sequence: 2
    engine: multi_hop
    query_type: PATH_REASONING
    target_id: "clu_007"
    parameters: {max_depth: 3, relation_types: [CONTRADICTS]}
    dependencies: []
  - step_id: ps_003
    sequence: 3
    engine: aggregate
    query_type: MERGE_CONTRADICTIONS
    dependencies: [ps_001, ps_002]
  - step_id: ps_004
    sequence: 4
    engine: synthesize
    query_type: ANSWER_BUILD
    parameters: {template: "contradiction_list"}
    dependencies: [ps_003]
parallel_groups: [["ps_001", "ps_002"]]
estimated_complexity: medium
```

#### Example 3: "What research gaps exist around GANs?"

**Parsed query:**
```python
{
    "query_type": "RESEARCH_GAP",
    "primary_entity": {"text": "GAN", "cluster_id": "clu_001", "entity_type": "method"},
    "constraints": [],
    "entities_resolved": True,
}
```

**Execution plan:**
```yaml
plan_id: plan_m4n3b2v1c0x9
query_type: RESEARCH_GAP
steps:
  - step_id: ps_001
    sequence: 1
    engine: gap
    query_type: GAP_ANALYSIS
    target_id: null               # Corpus-level gap analysis
    parameters: {gap_types: [ISOLATED_ENTITY, MISSING_COMPARISON, LOW_CONFIDENCE_CLAIM]}
    dependencies: []
  - step_id: ps_002
    sequence: 2
    engine: aggregate
    query_type: FILTER_GAPS
    parameters: {filter_by_entity: "clu_001"}
    dependencies: [ps_001]
  - step_id: ps_003
    sequence: 3
    engine: synthesize
    query_type: ANSWER_BUILD
    parameters: {template: "gap_analysis"}
    dependencies: [ps_002]
parallel_groups: []
estimated_complexity: low
```

### 5.5 PlanResult

```python
class PlanResult(BaseModel):
    """The accumulated result of executing a plan."""

    plan: ExecutionPlan
    step_results: dict[str, Any] = Field(default_factory=dict)  # step_id → result
    final_confidence: float = 0.0
    merged_evidence: list = Field(default_factory=list)
    plan_warnings: list[str] = Field(default_factory=list)
    execution_time_ms: int = 0
    all_steps_completed: bool = False
    failed_steps: list[str] = Field(default_factory=list)
```

---

## 6. Routing Engine

### 6.1 Routing Table

The router maps parsed query types to concrete engine invocations. Each route specifies the engine, the query type to pass, and any parameter mappings.

| Query Type | Primary Engine | M4 Query Type | Parameters | Secondary Engine(s) |
|---|---|---|---|---|
| **FACTUAL** | MultiHopReasoner | `ENTITY_LOOKUP` | `max_depth=2` | — |
| **COMPARISON** | MultiHopReasoner | `ENTITY_LOOKUP` × 2 | `max_depth=2` | ConsensusEngine |
| **EXPLANATION** | MultiHopReasoner | `GRAPH_EXPLORATION` + path sorting | `max_depth=3` | — |
| **CONSENSUS** | ConsensusEngine | `CONSENSUS_ANALYSIS` | `min_confidence=0.3` | MultiHopReasoner (enrich: find additional supporting/contradicting edges for cross-validation) |
| **CONTRADICTION** | ContradictionEngine | `CONTRADICTION_ANALYSIS` | `min_confidence=0.3` | MultiHopReasoner (paths: find alternative contradictory paths beyond direct edges) |
| **RESEARCH_GAP** | ResearchGapEngine | `GAP_ANALYSIS` | `gap_types=all` | — |
| **MULTI_HOP** | MultiHopReasoner | `PATH_REASONING` | `max_depth=4` | — |
| **EXPLORATION** | MultiHopReasoner | `GRAPH_EXPLORATION` | `max_depth=2` | — |

### 6.2 Routing Logic

```python
class QueryRouter:
    """Routes parsed queries to the correct M4 engines."""

    ROUTING_TABLE = {
        "FACTUAL":         {"primary": "multi_hop",    "m4_type": "ENTITY_LOOKUP",     "params": {"max_depth": 2}},
        "COMPARISON":      {"primary": "multi_hop",    "m4_type": "ENTITY_LOOKUP",     "params": {"max_depth": 2},
                            "secondary": ["consensus"]},
        "EXPLANATION":     {"primary": "multi_hop",    "m4_type": "GRAPH_EXPLORATION", "params": {"max_depth": 3}},
        "CONSENSUS":       {"primary": "consensus",    "m4_type": "CONSENSUS_ANALYSIS","params": {"min_confidence": 0.3},
                            "secondary": ["multi_hop"]},
        "CONTRADICTION":   {"primary": "contradiction","m4_type": "CONTRADICTION_ANALYSIS","params": {"min_confidence": 0.3},
                            "secondary": ["multi_hop"]},
        "RESEARCH_GAP":    {"primary": "gap",          "m4_type": "GAP_ANALYSIS",      "params": {}},
        "MULTI_HOP":       {"primary": "multi_hop",    "m4_type": "PATH_REASONING",    "params": {"max_depth": 4}},
        "EXPLORATION":     {"primary": "multi_hop",    "m4_type": "GRAPH_EXPLORATION", "params": {"max_depth": 2}},
    }

    def route(self, parsed: ParsedQuery) -> RoutingDirective:
        entry = self.ROUTING_TABLE.get(parsed.query_type)
        if not entry:
            return RoutingDirective(error=f"No route for {parsed.query_type}")

        return RoutingDirective(
            query_type=parsed.query_type,
            primary_engine=entry["primary"],
            m4_query_type=entry["m4_type"],
            parameters={**entry["params"],
                        "min_confidence": parsed.min_confidence,
                        "max_depth": parsed.max_hops},
            secondary_engines=entry.get("secondary", []),
            target_id=(
                parsed.primary_entity.cluster_id
                if parsed.primary_entity else None
            ),
            secondary_ids=[
                e.cluster_id for e in parsed.secondary_entities
                if e.cluster_id
            ],
        )
```

### 6.3 Conflict Resolution

| Conflict | Source | Resolution |
|---|---|---|
| Multiple entities match ambiguity | `QueryEntity.is_ambiguous=True` | Fan-out: create parallel PlanSteps for each alternative, merge results |
| Entity resolves to both cluster and document | Both `cluster_id` and `node_id` set | Primary route uses `cluster_id` (concept), secondary route documents |
| COMPARISON route needs 2 entities but only 1 found | Parsed entities < 2 | Downgrade to FACTUAL, add warning |
| CONSENSUS + CONTRADICTION requested simultaneously | Query spans both types | Route to SynthesisEngine for cross-engine merge |
| Unrecognized entity type in secondary_engines | Entity not in routing table | Skip secondary, log warning |
| Entity resolves but no edges exist | Empty M4 result | Return "No evidence found" with confidence 0 |

---

## 7. Evidence Aggregation

### 7.1 Evidence Sources

| Source | M4 Component | Fields Available |
|---|---|---|
| `CorpusGraphPath` | MultiHopReasoner | edges, confidence, length, node_ids |
| `CorpusGraphEdge` | Graph traversal | edge_id, source_id, target_id, relation_type, confidence, evidence_ids, metadata |
| `CorpusGraphNode` | Graph traversal | node_id, node_type, label, weight, metadata |
| `ConsensusResult` | ConsensusEngine | target_id, support_ratio, contradiction_ratio, per_document entries |
| `ContradictionResult` | ContradictionEngine | direct_contradictions, indirect_contradictions |
| `GapAnalysisResult` | ResearchGapEngine | isolated_entities, missing_comparisons, etc. |
| `DirectContradiction` | ContradictionEngine | source_document_id, target_document_id, confidence, evidence_ids |
| `IndirectContradiction` | ContradictionEngine | description, claim_a, claim_b, confidence |
| `GapItem` | ResearchGapEngine | gap_type, node_id, confidence, supporting_metrics, suggestion |

### 7.2 Evidence Data Model

```python
class AggregatedEvidence(BaseModel):
    """A single piece of aggregated, deduplicated evidence."""

    evidence_id: str
    source_text: str = ""
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_engine: str = ""          # "multi_hop" | "consensus" | "contradiction" | "gap"
    source_document_id: str = ""
    source_document_title: str = ""
    relation_type: str | None = None
    evidence_type: str = ""          # "path_edge" | "consensus_entry" | "contradiction" | "gap_item"
    trace: list[str] = Field(default_factory=list)  # Evidence → Chunk → Document chain
    metadata: dict = Field(default_factory=dict)
```

### 7.3 Evidence Ranking

```python
class EvidenceRanker:
    """Ranks evidence by confidence, recency, and relevance."""

    def rank(self, evidence: list[AggregatedEvidence]) -> list[AggregatedEvidence]:
        def score(e: AggregatedEvidence) -> float:
            s = e.confidence                         # Base: confidence [0, 1]
            if e.evidence_type == "path_edge":       # Path edges are direct
                s += 0.1
            if e.source_document_id:                 # Has document attribution
                s += 0.05
            if not e.source_text:                    # Missing source text
                s -= 0.2
            if not e.trace:                          # No trace chain
                s -= 0.3
            return max(s, 0.0)  # Clamp to non-negative

        evidence.sort(key=score, reverse=True)
        return evidence
```

### 7.4 Evidence Deduplication

| Dedup Key | Scope | Rule |
|---|---|---|
| `evidence_id` | Global | Exact ID match → keep higher confidence |
| `(source_document_id, relation_type)` | Per-query | Same doc, same relation → keep highest confidence |
| `(node_id, gap_type)` | Gap-only | Same entity + gap type → keep once |
| `(claim_a_document, claim_b_document)` | Contradiction-only | Same doc pair → keep higher confidence |
| Normalized source text | Per-query | Same text after normalization → dedup |

### 7.5 Anomaly Detection

| Anomaly | Detection | Action |
|---|---|---|
| Confidence exceeds max edge confidence | `agg_confidence > max(edge.confidence)` | Clamp to max edge confidence |
| Conflicting evidence from same document | Same doc has support + contradict | Flag as `mixed_evidence`, use stance priority |
| Circular evidence chain | Evidence IDs form a cycle | Break cycle, keep first occurrence |
| Evidence from missing document | `source_document_id` not in corpus | Drop evidence, log warning |
| Empty evidence_ids on edge | Edge with confidence > 0 but no evidence_ids | Accept but reduce confidence by 0.1 |

### 7.6 Failure Conditions

| Condition | Action |
|---|---|
| No evidence collected from any source | Return "Insufficient evidence" with confidence 0.0 |
| All evidence confidence < 0.1 | Return "Very low confidence evidence" with confidence 0.0 |
| Evidence source document unresolvable | Drop evidence, log anomaly |
| Evidence dedup removes all items | Keep highest-confidence item, log warning |
| Contradictory evidence cannot be resolved | Include both stances, set `mixed_evidence=True` |

---

## 8. Answer Synthesis

### 8.1 Design Principles

- **Template-driven.** No generative text — answers are assembled from pre-defined templates.
- **Evidence-grounded.** Every sentence in the answer maps to one or more evidence items.
- **Type-specific.** Each query type has its own template with slots for entities, numbers, and confidence.
- **Deterministic.** Same evidence → same answer every time.

### 8.2 Template Definitions

```python
_TEMPLATES: dict[str, dict] = {
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
        "no_evidence": "Insufficient evidence to compare {entity_a} and {entity_b}.",
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
```

### 8.3 Answer Builder Algorithm

```python
class AnswerSynthesizer:
    """Deterministic answer assembly from aggregated evidence."""

    def build(self, query_type: str, evidence: list[AggregatedEvidence],
              metadata: dict, confidence: float) -> ResearchAnswer:
        builder = {
            "FACTUAL": self._build_factual,
            "COMPARISON": self._build_comparison,
            "EXPLANATION": self._build_explanation,
            "CONSENSUS": self._build_consensus,
            "CONTRADICTION": self._build_contradiction,
            "RESEARCH_GAP": self._build_gap,
            "MULTI_HOP": self._build_multi_hop,
            "EXPLORATION": self._build_exploration,
        }
        fn = builder.get(query_type, self._build_fallback)
        return fn(evidence, metadata, confidence)
```

### 8.4 Confidence Formula

| Query Type | Confidence Formula |
|---|---|
| **FACTUAL** | `max(e.confidence for e in evidence)` |
| **COMPARISON** | `min(conf_a, conf_b, consensus_conf)` |
| **EXPLANATION** | `max(path.confidence for path in paths)` (best explanatory path bounds the answer; path confidence is product of edge confidences along that path) |
| **CONSENSUS** | `sr * avg(support_conf) + cr * avg(contradict_conf) + nr * 0.5` |
| **CONTRADICTION** | `max(c.confidence for c in contradictions)` |
| **RESEARCH_GAP** | `min(g.confidence for g in gaps)` (weakest gap signal) |
| **MULTI_HOP** | `max(path.confidence for path in paths)` |
| **EXPLORATION** | `max(e.confidence for e in edges)` |
| **Default (no evidence)** | `0.0` |

### 8.5 Example Answers

#### FACTUAL: "What datasets are used with BERT?"

> BERT is associated with USES_DATASET to SQuAD, GLUE, BookCorpus (confidence: 0.85).
>
> Evidence:
> - BERT paper (Devlin et al., 2019): pre-trained on BookCorpus and Wikipedia
> - Fine-tuned on SQuAD 1.1/2.0 and GLUE benchmark

#### CONSENSUS: "What is the consensus on Dropout?"

> Consensus analysis for Dropout (8 documents):
> - Support: 87.5% (7 docs)
> - Contradict: 0% (0 docs)
> - Neutral: 12.5% (1 doc)
> Classification: strong
> Confidence: 0.69

#### EXPLANATION: "How does Batch Normalization work?"

> Batch Normalization is described in 3 document(s):
> - Ioffe & Szegedy (2015): normalizes layer inputs to reduce internal covariate shift, allowing higher learning rates and reducing dropout dependence
> - Santurkar et al. (2018): challenges the covariate shift explanation; suggests BN smoothens the optimization landscape
> - Bjorck et al. (2018): shows BN enables faster training by allowing larger step sizes
>
> Confidence: 0.85 (best path: Ioffe → normalizes_inputs → BN)

#### RESEARCH_GAP: "What gaps exist around GANs?"

> Gap analysis identified 5 gap(s):
> - 2 missing comparison(s): GAN vs VAE, GAN vs Flow-based models
> - 1 under-studied dataset(s): CIFAR-10 (only 1 doc)
> - 2 unconnected document(s): paper X, paper Y
>
> Suggestions:
> - Consider designing a study comparing GAN with alternative generative approaches.
> - CIFAR-10 may be underexplored for GAN evaluation.

---

### 8.6 ReasoningStep Model

```python
class ReasoningStep(BaseModel):
    """A single step in the reasoning trace, recording what was executed and what it found."""

    step_id: str                         # "rs_001"
    engine: str                          # "multi_hop" | "consensus" | "contradiction" | "gap" | "aggregate" | "synthesize"
    description: str = ""                # Human-readable description of what this step did
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)  # Evidence items produced by this step
    metadata: dict = Field(default_factory=dict)
```

---

## 9. ResearchAnswer Model

### 9.1 Complete Schema

```python
class ResearchAnswer(BaseModel):
    """The final response from the Research Assistant."""

    answer_id: str                           # Unique answer identifier
    query: ResearchQuery                     # Original query (includes parsing)
    plan: ExecutionPlan | None = None        # Execution plan used

    # Core answer
    answer: str                              # Synthesized answer text
    confidence: float = Field(..., ge=0.0, le=1.0)
    classification: str | None = None        # consensus classification, gap type, etc.

    # Evidence
    evidence: list[AggregatedEvidence] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)   # Flat list for quick lookup
    supporting_documents: list[str] = Field(default_factory=list)  # Document IDs
    supporting_document_titles: list[str] = Field(default_factory=list)

    # Reasoning trace (one entry per plan step executed showing engine, input, output)
    reasoning_trace: list[ReasoningStep] = Field(default_factory=list)

    # Sources
    sources: list[str] = Field(default_factory=list)  # All source document IDs
    source_attribution: dict[str, list[str]] = Field(default_factory=dict)  # document → evidence_ids

    # Metadata
    query_type: str = ""
    generated_at: datetime
    processing_time_ms: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    # Traceability
    traceability_verified: bool = False      # Set during post-processing
    traceability_failures: list[str] = Field(default_factory=list)

    # Engines used
    engines_invoked: list[str] = Field(default_factory=list)
    steps_executed: int = 0
    steps_failed: int = 0
```

### 9.2 Validation Rules

| Rule | Validation | Consequence |
|---|---|---|
| Confidence bounds | `0.0 ≤ confidence ≤ 1.0` | Clamp if violated |
| Evidence traceability | Every `evidence_id` in `evidence` must have a source document | Drop untraceable evidence |
| Non-empty answer | `answer` must be non-empty | Fallback to template with `"No answer available"` |
| Evidence → answer correlation | Each sentence in answer maps to ≥1 evidence item | If unmapped, log warning |
| Document dedup | `supporting_documents` must be unique | Dedup on assembly |
| Timestamp validity | `generated_at` must be ≤ current time | Set to current time on validation |
| Traceability flag | If `traceability_failures` is non-empty, `traceability_verified = False` | Force false if any failure |

---

## 10. Traceability Contract

### 10.1 The Contract

**Every answer must be traceable to source documents through a maximum of 3 hops:**

```
Answer sentence
  ↓  (via evidence_id)
AggregatedEvidence
  ↓  (via trace chain)
CorpusGraphEdge / ConsensusEntry / Contradiction / GapItem
  ↓  (via source_document_id)
RUODocument
```

### 10.2 Traceability Verification

```python
class TraceabilityVerifier:
    """Verifies the traceability contract for a ResearchAnswer."""

    def verify(self, answer: ResearchAnswer, corpus: Any) -> ResearchAnswer:
        failures = []

        for ev in answer.evidence:
            # Hop 1: Evidence must have an ID
            if not ev.evidence_id:
                failures.append(f"Evidence missing ID: {ev}")
                continue

            # Hop 2: Evidence must trace to a source document
            # Consensus entries always require a source document (they are document-derived).
            # Gap items may lack a source document (absence-of-evidence is inherently
            # document-free); for gap items, skip Hop 2 but still validate referenced entities.
            if not ev.source_document_id:
                if ev.evidence_type not in ("gap_item",):
                    failures.append(
                        f"Evidence {ev.evidence_id} has no source document"
                    )
                continue

            # Hop 3: Source document must exist in corpus
            doc = corpus.get_document(ev.source_document_id)
            if doc is None:
                failures.append(
                    f"Evidence {ev.evidence_id} references "
                    f"non-existent document {ev.source_document_id}"
                )
                continue

            # Trace chain: Evidence → Chunk → Document
            trace_ok = self._verify_trace_chain(ev, doc)
            if not trace_ok:
                failures.append(
                    f"Evidence {ev.evidence_id} trace chain broken: "
                    f"no chunk found matching evidence"
                )

        answer.traceability_failures = failures
        answer.traceability_verified = len(failures) == 0
        return answer

    def _verify_trace_chain(self, ev: AggregatedEvidence, doc: Any) -> bool:
        """Verify every trace ID in the evidence chain resolves to a chunk in the document.

        Failure conditions:
        - trace contains an ID that does not match any chunk in the document
        - trace is empty but evidence_type requires chunk resolution (path_edge, contradiction)
        """
        if not ev.trace:
            # Evidence types that inherently require chunk traces
            if ev.evidence_type in ("path_edge", "contradiction"):
                return False
            # Consensus entries and gap items may be derived; accept without chunk trace
            return True
        for trace_id in ev.trace:
            chunk = doc.get_chunk(trace_id)
            if chunk is None:
                return False  # Trace ID does not resolve to a document chunk
        return True
```

### 10.3 Failure Handling

| Failure | Detection | Action |
|---|---|---|
| Missing evidence_id | Empty `evidence_id` | Drop evidence, log failure |
| Missing source document | `source_document_id` not in corpus | Drop evidence, log failure |
| Broken trace chain | Evidence → chunk link fails | Keep evidence but reduce confidence by 0.2 |
| Circular trace | Evidence references itself | Break cycle, keep first occurrence |
| Orphaned evidence | Evidence with no answer mapping | Log warning, exclude from answer |

### 10.4 Confidence Downgrades

| Condition | Downgrade |
|---|---|
| Evidence has no source document | confidence *= 0.5 |
| Evidence has no trace chain | confidence *= 0.8 |
| Evidence source is derived (not direct) | confidence *= 0.9 |
| Evidence is from gap analysis (inferred) | confidence *= 0.7 |
| More than 2 hops from source | confidence *= 0.9 per extra hop |

### 10.5 No-Evidence Policy

If evidence collection produces zero items with `confidence > 0`:

```python
_NO_EVIDENCE_RESPONSE = (
    "Insufficient evidence to answer this query. "
    "The corpus does not contain documents that address this question."
)
```

The answer is returned with `confidence=0.0`, a clear statement of insufficiency, and no fabricated content. This policy is non-negotiable — it prevents hallucination by design.

---

## 11. Query Lifecycle

### 11.1 Lifecycle Diagram

```
User Question
    │
    ▼
┌──────────────────────────────────────────────────────┐
│ 1. RECEIVE                                            │
│    • Validate non-empty                               │
│    • Assign query_id                                  │
│    • Timestamp                                        │
└──────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────┐
│ 2. PARSE                                              │
│    • Normalize text                                   │
│    • Detect query type (regex cascade)                │
│    • Extract entities (3-pass index lookup)           │
│    • Extract constraints                              │
│    • Detect ambiguity                                 │
└──────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────┐
│ 3. CLASSIFY                                           │
│    • Validate query type                              │
│    • Validate entity requirements                     │
│    • Fallback if ambiguous                            │
│    • Assign to taxonomy category                      │
└──────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────┐
│ 4. BUILD PLAN                                         │
│    • Create PlanSteps for query type                  │
│    • Resolve dependencies                             │
│    • Identify parallel groups                         │
│    • Estimate complexity                              │
└──────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────┐
│ 5. ROUTE & EXECUTE                                    │
│    • Route each step to correct engine                │
│    • Execute steps in order (parallel where possible) │
│    • Collect results per step                         │
│    • Handle step failures gracefully                  │
└──────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────┐
│ 6. AGGREGATE EVIDENCE                                 │
│    • Collect evidence from all step results           │
│    • Deduplicate by evidence_id / semantic key        │
│    • Rank by confidence                               │
│    • Detect anomalies                                 │
└──────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────┐
│ 7. SYNTHESIZE ANSWER                                  │
│    • Select template by query type                    │
│    • Fill template slots from evidence                │
│    • Compute final confidence                         │
│    • Build reasoning trace                            │
└──────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────┐
│ 8. VALIDATE TRACEABILITY                              │
│    • Verify evidence → document chain                 │
│    • Drop untraceable evidence                        │
│    • Apply confidence downgrades                      │
│    • Set traceability_verified flag                   │
└──────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────┐
│ 9. RETURN                                             │
│    • Assemble ResearchAnswer                          │
│    • Log metrics                                      │
│    • Return to caller                                 │
└──────────────────────────────────────────────────────┘
    │
    ▼
  Response (ResearchAnswer)
```

### 11.2 Stage Descriptions

| Stage | Duration | Input | Output | Failure Mode |
|---|---|---|---|---|
| **1. RECEIVE** | Instant | Raw query string | `ResearchQuery` | Empty query → error |
| **2. PARSE** | < 50ms | `ResearchQuery` | `ParsedQuery` | Unknown type → fallback |
| **3. CLASSIFY** | < 10ms | `ParsedQuery` | Validated `ParsedQuery` | Insufficient entities → error |
| **4. BUILD PLAN** | < 20ms | `ParsedQuery` | `ExecutionPlan` | No planner for type → error |
| **5. EXECUTE** | Varies (100ms-10s) | `ExecutionPlan` | `PlanResult` | Engine failure → skip step |
| **6. AGGREGATE** | < 50ms | `PlanResult` | Aggregated evidence | No evidence → empty answer |
| **7. SYNTHESIZE** | < 30ms | Evidence + metadata | Answer text | Template not found → fallback |
| **8. VALIDATE** | < 20ms | Draft answer | Verified answer | Trace failure → downgrade |
| **9. RETURN** | < 10ms | Verified answer | `ResearchAnswer` | Serialization error → error |

---

## 12. Failure Modes

### 12.1 Query Parsing Failures

| # | Failure | Description | Impact | Mitigation |
|---|---|---|---|---|
| F-01 | **Empty query** | User submits blank or whitespace-only query | No answer possible | Return error with `"Please provide a question."` |
| F-02 | **Unrecognized query type** | No regex pattern matches | Query type defaulted to EXPLORATION | Default to FACTUAL if entities found |
| F-03 | **Entity extraction failure** | No entities found despite required type | Plan cannot proceed | Return `"I couldn't identify the research entity in your question."` |
| F-04 | **Ambiguous entity match** | Multiple entities match same text | Planner fans out to multiple parallel steps | Select highest-degree node; log ambiguity |
| F-05 | **Constraint parse failure** | Constraint field or operator unrecognized | Constraint dropped | Log warning, continue without constraint |
| F-06 | **Entity not in corpus** | Entity text matches no index entry | Primary entity unresolved | Return `"No information about {entity} in the current corpus."` |

### 12.2 Planning Failures

| # | Failure | Description | Impact | Mitigation |
|---|---|---|---|---|
| F-07 | **No planner for query type** | Query type missing from planner dispatch | Plan not created | Return error, log as bug |
| F-08 | **Plan step dependency cycle** | Step dependencies form a cycle | Plan execution deadlocks | Detect cycle during plan creation; break by removing lowest-confidence step |
| F-09 | **Plan too complex** | Steps > 20 or depth > 5 | Long execution time | Warn user, offer simplified plan |
| F-10 | **Entity resolution fails mid-plan** | Entity resolves in parse but not in execution | Step target_id is invalid | Skip step, log failure |

### 12.3 Execution Failures

| # | Failure | Description | Impact | Mitigation |
|---|---|---|---|---|
| F-11 | **Engine not configured** | Required M4 engine is None | Step cannot execute | Skip step, return partial answer |
| F-12 | **Engine timeout** | M4 engine exceeds time budget | Step result lost | Move to next step, log timeout |
| F-13 | **Engine exception** | M4 engine raises unhandled exception | Step failed | Catch, log, continue with remaining steps |
| F-14 | **Empty engine result** | Engine returns 0 results | No evidence for that step | Continue; empty results are valid (no evidence == no answer) |

### 12.4 Evidence Failures

| # | Failure | Description | Impact | Mitigation |
|---|---|---|---|---|
| F-15 | **No evidence collected** | All steps return empty results | Answer confidence = 0.0 | Return `"Insufficient evidence"` |
| F-16 | **All evidence below threshold** | All evidence < `min_confidence` | Answer confidence = 0.0 | Return with warning about low confidence |
| F-17 | **Evidence dedup removes everything** | Dedup key collision removes all items | Keep highest-confidence survivor | Log warning |
| F-18 | **Contradictory evidence unresolvable** | Support and contradict equally strong | Answer flagged as disputed | Set `classification="disputed"`, include both sides |

### 12.5 Traceability Failures

| # | Failure | Description | Impact | Mitigation |
|---|---|---|---|---|
| F-19 | **Untraceable evidence** | Evidence has no source document chain | Evidence confidence halved | Apply 0.5 confidence penalty |
| F-20 | **Missing document in corpus** | Evidence references non-existent document | Evidence dropped | Log error, exclude from answer |
| F-21 | **Broken evidence chain** | Evidence IDs don't resolve to chunks | Trace incomplete | Accept with reduced confidence (×0.8) |
| F-22 | **Circular trace** | Evidence IDs form a reference cycle | Trace invalid | Break cycle by removing last element |

### 12.6 Answer Synthesis Failures

| # | Failure | Description | Impact | Mitigation |
|---|---|---|---|---|
| F-23 | **Template not found** | Query type has no registered template | Answer empty | Fallback to generic template |
| F-24 | **Template slot missing** | Required slot value not in evidence | Partial answer with placeholder | Use `"[unknown]"` placeholder |
| F-25 | **All evidence below min_confidence threshold** | Every evidence item has confidence < `parsed.min_confidence` | Answer confidence clamped to 0.0 | Return with warning about low confidence; the no-evidence policy (Section 10.5) prohibits fabricating a non-zero confidence |
| F-26 | **Answer text exceeds length limit** | Answer > 10000 characters | Truncation | Truncate to 10000 chars, add warning |

### 12.7 System Failures

| # | Failure | Description | Impact | Mitigation |
|---|---|---|---|---|
| F-27 | **Corpus not loaded** | No RUO documents in memory | No queries possible | Return `"Corpus not loaded"` error |
| F-28 | **Corpus indexes stale** | Entity/document indexes outdated | Entity extraction may miss targets | Indexes are built once at startup and invalidated only when the corpus changes (see Appendix C.4). Corpus mutation triggers immediate rebuild on the next query (< 50ms). |
| F-29 | **Concurrent query limit** | > 10 simultaneous queries | Performance degradation | Queue excess, process sequentially |
| F-30 | **Disk/resource exhaustion** | Out of memory or disk | Unstable system | Fail gracefully with error message |

---

## 13. Integration Plan

### 13.1 File Structure

```
src/researchmind/assistant/
├── __init__.py                 # Package exports
├── models.py                   # ResearchQuery, ParsedQuery, QueryEntity, QueryConstraint,
│                               #   ExecutionPlan, PlanStep, AggregatedEvidence,
│                               #   ResearchAnswer, RoutingDirective
├── query_parser.py             # QueryParser — type detection, entity extraction, constraints
├── query_planner.py            # QueryPlanner — plan creation per query type
├── router.py                   # QueryRouter — route to M4 engines
├── evidence_aggregator.py      # EvidenceAggregator — collect, dedup, rank, validate
├── answer_synthesizer.py       # AnswerSynthesizer — template-driven answer assembly
├── traceability.py             # TraceabilityVerifier — enforce traceability contract
└── research_assistant.py       # ResearchAssistant — top-level orchestrator
```

### 13.2 Dependency Graph

```
                    ┌──────────────────────────────┐
                    │     ResearchAssistant         │
                    │   (top-level orchestrator)    │
                    └──────┬──────────┬─────────────┘
                           │          │
              ┌────────────▼──┐  ┌────▼──────────────┐
              │ QueryParser   │  │ TraceabilityVerif │
              │ (parse+clsfy) │  │ (post-validate)   │
              └───────┬───────┘  └────────────────────┘
                      │
              ┌───────▼───────┐
              │ QueryPlanner  │
              │ (build plan)  │
              └───────┬───────┘
                      │
              ┌───────▼───────┐
              │ QueryRouter   │
              │ (route steps) │
              └───────┬───────┘
                      │
              ┌───────▼──────────────┐
              │ EvidenceAggregator   │
              │ (collect + dedup)    │
              └───────┬──────────────┘
                      │
              ┌───────▼──────────────┐
              │ AnswerSynthesizer    │
              │ (template + fill)    │
              └───────┬──────────────┘
                      │
              ┌───────▼───────┐
              │  Return       │
              │ ResearchAnswer│
              └───────────────┘
```

### 13.3 Implementation Order

| Phase | Files | Depends On | Estimated Effort |
|---|---|---|---|
| **Phase 1: Models** | `models.py`, `__init__.py` | None | 1 day |
| **Phase 2: Parser** | `query_parser.py` | Phase 1 | 2 days |
| **Phase 3: Planner** | `query_planner.py` | Phase 1 | 1 day |
| **Phase 4: Router** | `router.py` | Phase 1 | 1 day |
| **Phase 5: Aggregator** | `evidence_aggregator.py` | Phase 1 | 2 days |
| **Phase 6: Synthesizer** | `answer_synthesizer.py` | Phase 1, 5 | 2 days |
| **Phase 7: Traceability** | `traceability.py` | Phase 1 | 1 day |
| **Phase 8: Orchestrator** | `research_assistant.py` | Phases 2–7 | 2 days |
| **Phase 9: Tests** | `tests/test_assistant*.py` | Phases 1–8 | 3 days |

**Total estimated effort: 15 days**

### 13.4 Integration Checkpoints

| Checkpoint | Criteria | Validation |
|---|---|---|
| CP-1 | All Pydantic models load without validation errors | `python -c "from researchmind.assistant.models import *"` |
| CP-2 | Parser correctly classifies 20/20 known query types | Unit test with 20 representative queries |
| CP-3 | Planner creates valid plans for all 8 query types | Unit test: plan → execute on empty corpus |
| CP-4 | Router correctly maps all 8 types to M4 engines | Unit test: routing table coverage |
| CP-5 | Evidence aggregator deduplicates correctly | Unit test: 10 duplicate patterns |
| CP-6 | Answer synthesizer produces valid answers | Unit test: all 8 templates with mock evidence |
| CP-7 | Traceability verifier catches known failures | Unit test: 5 broken-trace scenarios |
| CP-8 | End-to-end: 30 queries on 8-paper corpus pass | Integration test against eval corpus |

---

## 14. Evaluation Plan

### 14.1 Evaluation Dimensions

| Dimension | Metric | Target | Measurement |
|---|---|---|---|
| **Correctness** | Answer matches ground truth | ≥ 90% | Manual review of 50 queries |
| **Traceability** | Evidence → document chain verified | 100% | Automated: `TraceabilityVerifier.verify()` |
| **Confidence calibration** | Confidence correlates with accuracy | ≥ 0.8 Spearman | Statistical: confidence vs. correctness |
| **Determinism** | Same query → same answer | 100% | Run twice, compare hashes |
| **Routing accuracy** | Correct engine selected | ≥ 95% | Audit routing decisions for 100 queries |
| **Parse accuracy** | Query type correctly identified | ≥ 90% | Confusion matrix on 200 queries |
| **Entity extraction precision** | Extracted entities correct | ≥ 85% | Precision@K against manual annotation |
| **Plan optimality** | Steps ≥ 1 and ≤ correct path length | ≥ 90% | Manual review of 30 plans |
| **No-answer rate** | Queries returning "insufficient evidence" | ≤ 30% | Count (low = corpus may be too narrow) |
| **Response time** | P50 / P95 latency | < 5s / < 15s | Automated timing harness |

### 14.2 Test Corpus

| Corpus | Size | Purpose |
|---|---|---|
| 8-paper evaluation corpus | 57 nodes, 1458 edges | Current — identical to M3/M4 evaluation |
| 20-paper ML methods corpus | ~200 nodes, ~5000 edges | Mid-scale validation (future) |
| 100-paper multi-domain corpus | ~1000 nodes, ~30000 edges | Scale testing (future) |

### 14.3 Test Queries

| Query Type | Count | Example |
|---|---|---|
| FACTUAL | 25 | "What datasets does BERT use?" |
| COMPARISON | 10 | "Compare Adam and SGD." |
| EXPLANATION | 10 | "Explain batch normalization." |
| CONSENSUS | 10 | "What is the consensus on dropout?" |
| CONTRADICTION | 10 | "What contradicts the attention mechanism?" |
| RESEARCH_GAP | 10 | "What gaps exist around GANs?" |
| MULTI_HOP | 10 | "Find paths between ResNet and ImageNet." |
| EXPLORATION | 10 | "What is connected to BERT?" |
| Malformed | 10 | Empty, gibberish, unknown entities |
| **Total** | **105** | |

### 14.4 Evaluation Script

```python
class AssistantEvaluator:
    """Evaluates the Research Assistant against a test corpus."""

    def run(self, assistant: ResearchAssistant,
            queries: list[tuple[str, str]]) -> dict:
        """Run evaluation. queries is list of (query_type, raw_query)."""
        results = []

        for query_type, raw_query in queries:
            research_query = ResearchQuery(
                query_id=f"eval_{len(results)}",
                raw_query=raw_query,
                created_at=datetime.now(timezone.utc),
            )
            answer = assistant.answer(research_query)

            correctness = self._check_correctness(
                query_type, raw_query, answer
            )
            trace_ok = answer.traceability_verified
            routing_ok = (answer.query_type == query_type)

            results.append({
                "query": raw_query,
                "expected_type": query_type,
                "got_type": answer.query_type,
                "confidence": answer.confidence,
                "correct": correctness,
                "traceable": trace_ok,
                "routing_ok": routing_ok,
                "evidence_count": len(answer.evidence),
                "warnings": answer.warnings,
            })

        return self._compute_metrics(results)
```

### 14.5 Pass/Fail Criteria

| Gate | Criteria | Action |
|---|---|---|
| **GATE 1: Determinism** | 100% identical on repeat run | Blocking — must fix non-determinism |
| **GATE 2: Traceability** | 100% evidence traceability | Blocking — must fix untraceable evidence |
| **GATE 3: Confidence bounds** | 0 violations | Blocking — must clamp confidence |
| **GATE 4: Correctness** | ≥ 80% | Non-blocking — must document gaps |
| **GATE 5: Routing** | ≥ 90% | Non-blocking — must fix misroutes |
| **GATE 6: No fabricated evidence** | 0 fabricated items | Blocking — must fix evidence sourcing |

### 14.6 Final Verdict Criteria

| Verdict | Criteria |
|---|---|
| **READY** | All 6 gates pass |
| **READY WITH FIXES** | Gates 1-3 pass, 4-6 documented |
| **NOT READY** | Any of gates 1-3 fail |

---

## Appendix A: Query Example Catalog

### A.1 FACTUAL

| Query | Primary Entity | Expected Engine | Expected Answer Contains |
|---|---|---|---|
| "What is the Adam optimizer?" | Adam | MultiHop (entity) | "optimizer", "stochastic", "adaptive" |
| "What datasets does BERT use?" | BERT | MultiHop (entity) | "BookCorpus", "Wikipedia", "SQuAD" |
| "Who proposed Batch Normalization?" | Batch Normalization | MultiHop (entity) | "Ioffe", "Szegedy" |
| "Which method is U-Net?" | U-Net | MultiHop (entity) | "segmentation", "biomedical" |
| "What is the ResNet architecture?" | ResNet | MultiHop (entity) | "residual", "skip connection" |

### A.2 COMPARISON

| Query | Entities | Expected Engine | Expected Answer Contains |
|---|---|---|---|
| "Compare Adam and SGD." | Adam, SGD | MultiHop + Consensus | "difference", "adaptive", "learning rate" |
| "How does ResNet compare to U-Net?" | ResNet, U-Net | MultiHop + Consensus | "architecture", "segmentation" |
| "What is the difference between Dropout and BatchNorm?" | Dropout, BatchNorm | MultiHop | "regularization", "normalization" |

### A.3 CONSENSUS

| Query | Target | Expected Engine | Expected Answer Contains |
|---|---|---|---|
| "What is the consensus on Dropout?" | Dropout | Consensus | "support", "strong", "ratio" |
| "Do papers agree on Adam?" | Adam | Consensus | "support", "moderate", "ratio" |
| "Is there agreement about BERT?" | BERT | Consensus | "support", "strong", "ratio" |

### A.4 EXPLANATION

| Query | Entity | Expected Engine | Expected Answer Contains |
|---|---|---|---|
| "Explain the attention mechanism." | Attention | MultiHop (path) | "attention", "weight", "query", "key" |
| "How does Batch Normalization work?" | Batch Normalization | MultiHop | "normalize", "layer", "distribution" |

---

## Appendix B: Template Library

### B.1 Generic Templates

```python
_TEMPLATES["ERROR"] = {
    "empty_query": "Please provide a question.",
    "unknown_type": (
        "I couldn't determine what kind of research question this is. "
        "Try asking about a specific entity, comparison, or research gap."
    ),
    "no_entity": (
        "I couldn't identify any research entity (method, dataset, paper) "
        "in your question. Try mentioning a specific name."
    ),
    "no_evidence": "Insufficient evidence to answer this query.",
    "low_confidence": (
        "Very low confidence evidence (max: {confidence:.2f}). "
        "The corpus may not contain reliable information for this question."
    ),
}
```

### B.2 Traceability Templates

```python
_TEMPLATES["TRACE"] = {
    "verified": (
        "This answer is fully traceable: each claim maps to "
        "source evidence in the corpus documents."
    ),
    "partial": (
        "Some evidence could not be fully traced to source documents "
        "({failures} failure(s)). Confidence has been adjusted."
    ),
    "failed": (
        "Traceability verification failed for some evidence items. "
        "Proceed with caution."
    ),
}
```

---

## Appendix C: Index Requirements

### C.1 Entity Label Index

| Index | Key | Value | Purpose |
|---|---|---|---|
| `entity_label_to_cluster` | Entity label (lowercase) | `list[EntityCluster]` | Query entity extraction |
| `entity_label_to_node` | Entity label (lowercase) | `CorpusGraphNode` | Query → node ID resolution |
| `entity_type_index` | `EntityLabel` enum | `list[EntityCluster]` | Type-filtered entity lookup |

### C.2 Document Index

| Index | Key | Value | Purpose |
|---|---|---|---|
| `doc_title_index` | Title (lowercase) | `RUODocument` | Document reference resolution |
| `doc_doi_index` | DOI (lowercase) | `RUODocument` | DOI-based resolution |
| `doc_ruo_id_index` | `ruo_id` | `RUODocument` | Direct document lookup |

### C.3 Graph Index

| Index | Key | Value | Purpose |
|---|---|---|---|
| `node_label_to_id` | Node label (lowercase) | `list[node_id]` | Query entity → graph node |
| `node_id_to_label` | `node_id` | Label string | Answer template filling |
| `edge_type_index` | `RelationType` | `list[CorpusGraphEdge]` | Relation-filtered queries |

### C.4 Maintenance

All indexes are **built once at CorportManager initialization** and **invalidated only when the corpus changes** (add/remove document). Since M5 is read-only (Section 1.2), corpus mutation is rare — indexes remain valid across all queries within a session. Rebuilding a full index from a 57-node, 1458-edge graph takes < 50ms in memory.

```
Index lifecycle:
  CorpusManager initialized
    → build_entity_index()    # M3 ResolutionResult
    → build_doc_index()       # RUOCorpus.document_ids
    → build_graph_index()     # CorpusGraphResult.nodes + edges
    → store in AssistantIndex (frozen dict)

  On corpus mutation (rare, M5 is read-only):
    → invalidate AssistantIndex
    → rebuild on next query (< 50ms)

  Normal query execution (no mutation):
    → reuse existing AssistantIndex (zero overhead)
```
