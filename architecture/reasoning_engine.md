# Module 4 — Reasoning Engine Architecture

**Status:** Design Document  
**Date:** 2026-06-11  
**Version:** 1.0  

---

## Table of Contents

1. [Reasoning Scope](#1-reasoning-scope)
2. [Query Model](#2-query-model)
3. [Reasoning Result Model](#3-reasoning-result-model)
4. [Multi-Hop Reasoning Engine](#4-multi-hop-reasoning-engine)
5. [Evidence-Backed Answering](#5-evidence-backed-answering)
6. [Consensus Engine](#6-consensus-engine)
7. [Contradiction Engine](#7-contradiction-engine)
8. [Research Gap Engine](#8-research-gap-engine)
9. [Failure Modes](#9-failure-modes)
10. [Integration Plan](#10-integration-plan)

---

## 1. Reasoning Scope

### 1.1 Position in Pipeline

```
PDF → SRO → RUO → Fact Extraction → Triple Extraction → Evidence Builder
  → Knowledge Graph → Entity Resolution → Document Relations → Corpus Graph
  → **Module 4: Reasoning Engine** ← YOU ARE HERE
```

Module 4 sits directly above the Corpus Graph. It consumes the outputs of
Modules 1–3 and produces corpus-level reasoning. It operates **deterministically**
using graph traversal and evidence aggregation — no LLMs, no embeddings, no
vector databases, no external APIs.

### 1.2 What Module 4 IS Responsible For

| Capability | Description |
|---|---|
| **Multi-hop reasoning** | Traverse the corpus graph along relation edges to connect indirectly related entities, documents, and claims. Example: Paper A cites Paper B, Paper B uses Dataset X → infer Paper A indirectly depends on Dataset X. |
| **Evidence-backed answering** | Construct natural-language answers from `EvidenceRecord`, `EvidenceChain`, `SemanticTriple`, and `DocumentRelation` objects. Every answer must be traceable to source evidence; no answer may exist without supporting evidence. |
| **Cross-document synthesis** | Aggregate information about the same entity, claim, or method across multiple documents in the corpus. Combine evidence from all sources into a unified answer. |
| **Consensus analysis** | Measure the degree of agreement across documents about a specific claim, entity, or relationship. Compute support/contradiction/neutral ratios with deterministic confidence. |
| **Contradiction analysis** | Detect direct and indirect contradictions between claims, entities, or document findings. Leverage `RelationType.CONTRADICTS`, claim polarity, and negated triples. |
| **Research gap identification** | Discover isolated entities, missing comparisons, weak-evidence regions, and under-studied datasets using deterministic graph-structural criteria. |
| **Graph exploration** | Expose the corpus graph through a query API that supports entity lookup, document lookup, path finding, neighbor traversal, and filtered edge/node queries. |

### 1.3 What Module 4 Is NOT Responsible For

| Out of Scope | Rationale |
|---|---|
| Fact extraction | Belongs to Module 2 (Understanding Engine) |
| Triple extraction | Belongs to Module 2 |
| Evidence building | Belongs to Module 2 (`EvidenceBuilder`) |
| Knowledge Graph construction | Belongs to Module 2 (`KnowledgeGraphBuilder`) |
| Entity resolution | Belongs to Module 3 (`EntityResolver`) |
| Document relation detection | Belongs to Module 3 (`DocumentRelationEngine`) |
| Corpus graph construction | Belongs to Module 3 (`CorpusGraphBuilder`) |
| LLM-based reasoning | Deterministic-only constraint |
| Embedding generation | Out of scope |
| External knowledge retrieval | No external APIs |
| Document ingestion | Belongs to Module 1 |
| Schema modifications | All reasoning must use existing RUO/CorpusGraph structures |

### 1.4 Inputs Consumed

| Input | Source Module | Type | Usage in M4 |
|---|---|---|---|
| `CorpusGraphResult` | M3 | `CorpusGraphResult` | Primary reasoning substrate — all traversal, query, and path-finding APIs |
| `ResolutionResult` | M3 | `ResolutionResult` | Entity cluster metadata (cluster size, variants, canonical text, confidence) |
| `DocumentRelationResult` | M3 | `DocumentRelationResult` | Relation evidence metadata, relation detection statistics |
| `EvidenceChain` list | M2 | `list[EvidenceChain]` | Per-claim evidence chains with `aggregate_confidence`, `supporting_document_ids` |
| `EvidenceRecord` list | M2 | `list[EvidenceRecord]` | Atomic evidence units with `source_text`, `confidence`, `location` |
| `SemanticTriple` list | M2 | `list[SemanticTriple]` | Structured subject-predicate-object facts with `is_negated`, `evidence_ids` |
| `RUOClaim` list | M2 | `list[RUOClaim]` | Per-document claims with `claim_type`, `is_contradicted`, `evidence_chain_id` |

### 1.5 System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      MODULE 4 — REASONING ENGINE                     │
│                                                                     │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────────┐  │
│  │  Query Engine  │  │  Multi-Hop     │  │  Evidence-Backed     │  │
│  │  (M4-2)        │─▶│  Reasoner      │─▶│  Answer Builder      │  │
│  │                │  │  (M4-3)        │  │  (M4-2 internal)     │  │
│  └───────┬────────┘  └───────┬────────┘  └──────────┬───────────┘  │
│          │                   │                       │              │
│          ▼                   ▼                       ▼              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Corpus Graph Layer                        │   │
│  │  (CorpusGraphResult — get_neighbors, shortest_path,         │   │
│  │   find_paths, connected_components, subgraph, query_nodes,  │   │
│  │   query_edges, top_entities, top_documents)                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                          │                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │   │
│  │  │ Consensus    │  │ Contradiction│  │ Research Gap     │  │   │
│  │  │ Engine       │  │ Engine       │  │ Engine           │  │   │
│  │  │ (M4-4)       │  │ (M4-5)       │  │ (M4-6)           │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                          │                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Corpus Synthesis Engine (M4-7)                  │   │
│  │  (Aggregates all sub-engine outputs into unified answers)    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Query Model

### 2.1 `QueryType` Enum

```python
class QueryType(StrEnum):
    """Top-level classification for a reasoning query."""

    # --- Lookups ---
    ENTITY_LOOKUP       = "entity_lookup"
    """Retrieve all graph information about a specific entity cluster."""
    DOCUMENT_LOOKUP     = "document_lookup"
    """Retrieve all graph information about a specific document."""

    # --- Path reasoning ---
    PATH_REASONING      = "path_reasoning"
    """Multi-hop traversal to find indirect connections between two nodes."""

    # --- Analytic queries ---
    CONSENSUS_ANALYSIS  = "consensus_analysis"
    """Measure cross-document agreement about a claim, entity, or relationship."""
    CONTRADICTION_ANALYSIS = "contradiction_analysis"
    """Detect contradictions involving a claim, entity, or across document pairs."""
    GAP_ANALYSIS        = "gap_analysis"
    """Identify research gaps: isolated entities, missing comparisons, weaknesses."""

    # --- Exploration ---
    GRAPH_EXPLORATION   = "graph_exploration"
    """Open-ended traversal: neighbors, paths, connected components."""
```

### 2.2 `ReasoningQuery` Model

```python
class ReasoningQuery(BaseModel):
    """A complete reasoning query accepted by the ReasoningEngine."""

    query_type: QueryType
    """What kind of reasoning to perform."""

    # --- Node selection ---
    source_id: str | None = None
    """Primary node ID (document, entity_cluster, or claim)."""
    target_id: str | None = None
    """Secondary node ID (for pair-wise queries like path_reasoning)."""
    node_ids: list[str] | None = None
    """Multiple node IDs for batch operations."""

    # --- Entity / claim filters ---
    entity_label: EntityLabel | None = None
    """Filter to specific entity types (METHOD, DATASET, METRIC, etc.)."""
    claim_type: ClaimType | None = None
    """Filter to specific claim types (STATISTICAL, CAUSAL, COMPARATIVE, etc.)."""
    relation_types: list[RelationType] | None = None
    """Restrict traversal/analysis to specific relation types."""

    # --- Traversal parameters ---
    max_depth: int = Field(default=3, ge=1, le=100)
    """Maximum number of hops for path-finding and exploration."""
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    """Minimum confidence threshold for edges, claims, and evidence."""

    # --- Result control ---
    max_results: int = Field(default=100, ge=1, le=10000)
    """Maximum number of results to return."""
    include_evidence: bool = Field(default=True)
    """Whether to attach supporting EvidenceRecord data to results."""
    include_trace: bool = Field(default=True)
    """Whether to include the full reasoning_trace in results."""
    include_graph_paths: bool = Field(default=True)
    """Whether to include CorpusGraphPath objects in results."""

    # --- Gap analysis specific ---
    gap_types: list[GapType] | None = None
    """Specific gap types to detect (only for GAP_ANALYSIS)."""
```

### 2.3 Per-QueryType Requirements Matrix

| QueryType | Required Inputs | Optional Inputs | Expected Output |
|---|---|---|---|
| `ENTITY_LOOKUP` | `source_id` (entity cluster ID) | `min_confidence`, `include_evidence`, `include_trace` | Entity cluster metadata, all connecting documents, all connecting entity clusters, all claims mentioning entity, evidence chains |
| `DOCUMENT_LOOKUP` | `source_id` (document ID) | `min_confidence`, `include_evidence`, `include_trace` | Document metadata, all entity clusters in doc, all relations to other docs, all claims, citation network neighbors |
| `PATH_REASONING` | `source_id`, `target_id` | `max_depth`, `relation_types`, `min_confidence`, `include_graph_paths` | List of `CorpusGraphPath` objects connecting source→target, with confidence per path, intermediate node labels |
| `CONSENSUS_ANALYSIS` | `source_id` (claim or entity cluster ID) | `relation_types`, `min_confidence`, `include_evidence` | `ConsensusResult` with `support_ratio`, `contradiction_ratio`, `neutral_ratio`, per-document breakdown, aggregate confidence |
| `CONTRADICTION_ANALYSIS` | `source_id` | `target_id`, `relation_types`, `min_confidence` | `ContradictionResult` with direct contradiction edges, indirect contradictions (polarity-mismatched claims), confidence |
| `GAP_ANALYSIS` | (none — runs on full corpus) | `gap_types`, `entity_label`, `min_confidence` | `GapAnalysisResult` with categorized gaps: isolated entities, missing comparisons, weak evidence regions, under-studied datasets |
| `GRAPH_EXPLORATION` | `source_id` | `max_depth`, `relation_types`, `min_confidence`, `max_results` | Neighborhood subgraph (`CorpusGraphResult`), path list, statistics |

### 2.4 `GapType` Enum

```python
class GapType(StrEnum):
    ISOLATED_ENTITY        = "isolated_entity"
    """Entity appearing in only one document with no inter-cluster edges."""
    MISSING_COMPARISON     = "missing_comparison"
    """Entity cluster with no COMPARES_WITH edges to other clusters."""
    WEAK_EVIDENCE_REGION   = "weak_evidence_region"
    """Group of entities/claims with below-threshold confidence."""
    UNDER_STUDIED_DATASET  = "under_studied_dataset"
    """Dataset-type entity appearing in fewer than N documents."""
    UNCONNECTED_DOCUMENT   = "unconnected_document"
    """Document node with degree below a threshold (few relations)."""
```

---

## 3. Reasoning Result Model

### 3.1 `ReasoningResult` Model

```python
class ReasoningResult(BaseModel):
    """Top-level result from any ReasoningEngine query."""

    query: ReasoningQuery
    """The query that produced this result."""

    answer: str
    """Natural-language answer synthesised from evidence."""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    """Aggregate confidence in the answer (deterministic)."""

    supporting_evidence: list[AnswerEvidence] = Field(default_factory=list)
    """Atomic evidence units supporting the answer."""
    supporting_documents: list[str] = Field(default_factory=list)
    """Document IDs that contributed evidence."""

    graph_paths: list[CorpusGraphPath] = Field(default_factory=list)
    """Graph paths traversed to produce the answer (if applicable)."""
    reasoning_trace: list[ReasoningStep] = Field(default_factory=list)
    """Ordered trace of reasoning steps (if include_trace=True)."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Additional structured data, varies by query_type:
       - ENTITY_LOOKUP: entity cluster metadata
       - CONSENSUS_ANALYSIS: ConsensusResult dict
       - CONTRADICTION_ANALYSIS: ContradictionResult dict
       - GAP_ANALYSIS: GapAnalysisResult dict
       - GRAPH_EXPLORATION: CorpusGraphStatistics dict
    """

    warnings: list[str] = Field(default_factory=list)
    """Non-fatal warnings (low confidence, sparse evidence, etc.)."""

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, v: float) -> float:
        return round(v, 6)
```

### 3.2 `AnswerEvidence` Model

```python
class AnswerEvidence(BaseModel):
    """A single traceable piece of evidence supporting an answer."""

    evidence_id: str
    """ID of the originating EvidenceRecord or RelationEvidence."""
    source_text: str
    """Excerpt of text constituting the evidence."""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    """Confidence of this evidence piece."""
    document_id: str
    """RUO document ID where this evidence originates."""
    evidence_type: EvidenceType
    """Type of evidence (DIRECT_QUOTE, PARAPHRASE, STATISTICAL, etc.)."""
    location: EvidenceSpan | None = None
    """Precise location in the source document."""

    relation_type: RelationType | None = None
    """If this evidence supports a specific relation, which one."""
    chain_id: str | None = None
    """ID of the parent EvidenceChain, if applicable."""
    triple_id: str | None = None
    """ID of the parent SemanticTriple, if applicable."""
```

### 3.3 `ReasoningStep` Model

```python
class ReasoningStep(BaseModel):
    """A single atomic step in a reasoning trace."""

    step_number: int = Field(ge=1)
    """Sequential step number (1-indexed)."""
    description: str
    """Human-readable description of this step."""
    source_node_id: str
    """Node ID at the start of this step."""
    target_node_id: str
    """Node ID at the end of this step."""
    relation_type: RelationType | None = None
    """Relation traversed in this step."""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    """Confidence of this step (edge or claim confidence)."""
    evidence_ids: list[str] = Field(default_factory=list)
    """Evidence IDs supporting this step."""

    @field_validator("step_number")
    @classmethod
    def _step_number_positive(cls, v: int) -> int:
        return v
```

### 3.4 Deterministic Confidence Computation

All confidence computation in Module 4 is deterministic. The following formulas apply throughout:

| Operation | Formula | Use Case |
|---|---|---|
| **Path confidence (product)** | `Π(ci)` for edges `e1...en` | Overall likelihood across independent edges |
| **Path confidence (min)** | `min(c1...cn)` | Worst-case bound on reliability |
| **Evidence aggregate (min)** | `min(c1...cn)` | Chain strength = weakest link |
| **Evidence aggregate (avg)** | `(Σ ci) / n` | Balanced per-document confidence |
| **Evidence aggregate (weighted)** | `Σ(wi * ci) / Σ wi` | Weighted by evidence quality or source reliability |
| **Consensus confidence** | `(support_ratio * avg(support_conf) + contradiction_ratio * avg(contradict_conf))` | Blended by proportion |
| **Gap confidence** | `1.0 - max(entity_confidence, edge_confidence)` | Higher = more confident gap (i.e., more certain something is missing) |

---

## 4. Multi-Hop Reasoning Engine

### 4.1 Overview

The Multi-Hop Reasoner performs traversal-based reasoning over the `CorpusGraphResult`. It uses BFS for shortest-path and DFS for exhaustive path enumeration, both available natively from the corpus graph's traversal APIs.

### 4.2 Algorithm: `find_indirect_relation`

```
Input:
  graph         : CorpusGraphResult
  source_id     : str           # Starting node
  target_id     : str           # Target node (or None for exploration)
  max_depth     : int           # Max hops (default: 3)
  relation_types: list[RelT]    # Allowed relations (default: all)
  min_conf      : float         # Min edge confidence (default: 0.0)

Output:
  paths         : list[CorpusGraphPath]

Algorithm:

  1. If target_id is None (exploration mode):
     a. Return graph.get_neighbors(source_id, depth=max_depth)
        filtered by relation_types and min_confidence.

  2. If target_id is set (path-finding mode):
     a. Leverage graph.find_paths(source_id, target_id, max_depth).
        This is the existing DFS-based all-paths enumeration.

     b. Apply post-filtering:
        - Remove paths containing edges with confidence < min_conf
        - Remove paths using non-allowed relation types
        - Remove paths that revisit nodes (if cycle_handling == strict)

     c. Sort results:
        - Primary: ascending path length (shortest first)
        - Secondary: descending path confidence (most confident first)

     d. Truncate to max_results.

  3. Compute path confidence:
     For each path:
       path_confidence = Π(edge.confidence for edge in path.edges)
       path_worst_case = min(edge.confidence for edge in path.edges)

     Return both in path metadata.

  4. Attach supporting evidence:
     For each edge in each path:
       - Look up edge.evidence_ids
       - Resolve to EvidenceRecord objects (if available)
       - Attach as AnswerEvidence objects
```

### 4.3 Traversal Evidence Flow

```
Query: "Does Paper A indirectly depend on Dataset X?"

Step 1: source = Paper A, target = Dataset X, max_depth = 3

Step 2: graph.find_paths("Paper_A", "Dataset_X", max_depth=3)
        → Finds: Paper_A ─CITES─→ Paper_B ─USES_DATASET─→ Dataset_X

Step 3: Path confidence = confidence(CITES) * confidence(USES_DATASET)
        = 0.95 * 0.90 = 0.855

Step 4: AnswerEvidence:
  - evidence_id: "ev_001" (from CITES edge)
    source_text: "As shown in Paper B, ..."
    document_id: "Paper_A"
  - evidence_id: "ev_002" (from USES_DATASET edge)
    source_text: "We evaluate on Dataset X ..."
    document_id: "Paper_B"

Step 5: ReasoningTrace:
  1. Paper_A → Paper_B [CITES, conf=0.95]
  2. Paper_B → Dataset_X [USES_DATASET, conf=0.90]
```

### 4.4 Confidence Propagation Rules

```
Edge confidence: CorpusGraphEdge.confidence (already computed by M3)

Path confidence (product model):
  P_path = Π(edge.confidence for edge in path)
  Rationale: Independent evidence — each edge is an independent claim.
             If edge 1 has 0.9 and edge 2 has 0.8, the combined
             probability both are true is 0.9 * 0.8 = 0.72.

Path confidence (minimum model):
  P_path_min = min(edge.confidence for edge in path)
  Rationale: Worst-case bound — the path is only as reliable as its
             weakest edge. Used when reporting lower bounds.

Aggregate across multiple paths:
  P_aggregate = 1 - Π(1 - P_path_i)
  Rationale: Multiple independent paths increase overall confidence.
             If path A has 0.7 and path B has 0.6, the combined
             probability at least one is correct = 1 - (0.3 * 0.4) = 0.88.
```

### 4.5 Cycle Handling

| Strategy | Implementation | When Used |
|---|---|---|
| **Per-query visited set** | `visited: set[str] = {source_id}`; skip nodes already visited | Default for all traversal |
| **Per-path visited set** | Each path tracks its own `node_ids`; skip if node already in current path | Strict mode (avoiding any cycles) |
| **Allow cycles (max_depth cap)** | Allow revisiting nodes but cap at `max_depth` | Exploration mode only |
| **Cycle detection in output** | Deduplicate paths with identical node-ID sequences | Post-processing |

### 4.6 Stopping Criteria

| Criterion | Condition | Behaviour |
|---|---|---|
| Target found | `current_node == target_id` | Record path and continue searching for alternates (DFS), or stop (BFS shortest-path) |
| Max depth | `depth >= max_depth` | Stop expanding from this node |
| Max paths | `len(paths) >= max_results` | Stop searching entirely |
| Confidence floor | `path_confidence < min_confidence` | Prune this path |
| No more neighbors | `len(neighbors) == 0` | Backtrack (DFS) or queue empty (BFS) |

### 4.7 Multi-Hop Confidence Worked Example

```
Query: Find indirect connection between "Attention Is All You Need" and "ImageNet"

Graph edges:
  Attention ─CITES──▶ BERT               (c=0.95)
  BERT      ─EXTENDS─▶ Transformer        (c=0.85)
  BERT      ─USES───▶ BookCorpus          (c=0.90)
  ResNet    ─USES───▶ ImageNet            (c=0.92)
  Attention ─COMPARES_WITH─▶ ResNet       (c=0.80)
  BERT      ─COMPARES_WITH─▶ ResNet       (c=0.75)

Paths found (depth ≤ 3):

Path 1: Attention ─CITES─→ BERT ─COMPARES_WITH─→ ResNet ─USES─→ ImageNet
  Length: 3
  Product confidence: 0.95 * 0.75 * 0.92 = 0.656
  Min confidence: min(0.95, 0.75, 0.92) = 0.75

Path 2: Attention ─COMPARES_WITH─→ ResNet ─USES─→ ImageNet
  Length: 2
  Product confidence: 0.80 * 0.92 = 0.736
  Min confidence: min(0.80, 0.92) = 0.80

Aggregate confidence (multiple paths):
  P = 1 − (1 − 0.656) × (1 − 0.736) = 1 − 0.344 × 0.264 = 1 − 0.091 = 0.909

Result: "Attention Is All You Need" is indirectly related to ImageNet
        via ResNet (confidence: 0.909 aggregate).
```

---

## 5. Evidence-Backed Answering

### 5.1 Answer Construction Pipeline

```
CorpusGraphEdge / SemanticTriple / RUOClaim / EvidenceChain
                          │
                          ▼
             ┌──────────────────────┐
             │  Evidence Resolver   │
             │  Maps evidence_ids   │
             │  → EvidenceRecord    │
             └──────────┬───────────┘
                        │
                        ▼
             ┌──────────────────────┐
             │  AnswerEvidence      │
             │  Builder             │
             │  Wraps each record   │
             │  → AnswerEvidence    │
             └──────────┬───────────┘
                        │
                        ▼
             ┌──────────────────────┐
             │  Confidence          │
             │  Aggregator          │
             │  Applies formula     │
             └──────────┬───────────┘
                        │
                        ▼
             ┌──────────────────────┐
             │  Answer Synthesizer  │
             │  Builds answer text  │
             │  from evidence       │
             └──────────┬───────────┘
                        │
                        ▼
               ReasoningResult
```

### 5.2 Evidence Validation Rules

Every `AnswerEvidence` must satisfy:

| Rule | Condition | Consequence |
|---|---|---|
| **Traceability** | `evidence_id` must be resolvable to an `EvidenceRecord`, `RelationEvidence`, or `SemanticTriple` | Reject if unresolvable |
| **Source attribution** | `document_id` must be a known document in the corpus | Reject if unknown |
| **Confidence bounds** | `confidence` in [0.0, 1.0] | Clamp if out of bounds |
| **Non-empty source text** | `source_text` must have length ≥ 1 | Reject if empty |
| **Temporal consistency** | Evidence timestamps must not contradict chain ordering | Warn if out of order |
| **Chain membership** | If `chain_id` set, must reference a valid `EvidenceChain` | Reject if invalid |

### 5.3 Answer Construction Rules

| Query Type | Answer Construction | Evidence Selection |
|---|---|---|
| `ENTITY_LOOKUP` | "Entity X appears in N documents: doc1, doc2, ... It is most related to entities Y, Z via COMPARES_WITH edges." | All edges touching entity cluster node; deduplicate by semantic triple |
| `DOCUMENT_LOOKUP` | "Document 'Title' contains N entities, M claims, and is connected to K other documents via relations: ..." | All edges from document node; all claims and entities in document |
| `PATH_REASONING` | "Path found: source → intermediate1 → ... → target (confidence X). Evidence: ..." | Evidence from each edge in the path |
| `CONSENSUS_ANALYSIS` | "Claim '...' is supported by X% of documents (Y out of Z), contradicted by W%, neutral by V%." | Evidence from edges connecting claim/entity to each document |
| `CONTRADICTION_ANALYSIS` | "Direct contradiction found between doc1 and doc2 regarding claim '...'." | CONTRADICTS edges + polarity-mismatched claims |
| `GAP_ANALYSIS` | "Entity 'X' is isolated (appears only in doc1, no co-occurrence edges). Suggest exploring comparisons with related entities." | Graph structural analysis (degree, connectivity) |

### 5.4 No-Answer-Without-Evidence Guarantee

```python
def build_answer(self, query, evidence_list, graph_paths) -> ReasoningResult:
    """Guarantee: every answer has at least one AnswerEvidence."""
    if not evidence_list:
        return ReasoningResult(
            query=query,
            answer="Insufficient evidence to answer this query.",
            confidence=0.0,
            supporting_evidence=[],
            supporting_documents=[],
            warnings=["No supporting evidence found."],
        )
    # ... normal construction ...
```

---

## 6. Consensus Engine

### 6.1 Overview

The Consensus Engine measures the degree of cross-document agreement about a specific claim, entity, or relationship. It operates over the corpus graph by examining edges from documents to the target node, combined with claim-level polarity information from `RUOClaim` and `SemanticTriple`.

### 6.2 `ConsensusResult` Model

```python
class ConsensusResult(BaseModel):
    """Result of consensus analysis for a claim or entity."""

    target_id: str
    """The node ID (claim or entity cluster) being analysed."""
    target_label: str
    """Human-readable label of the target."""

    # --- Ratios ---
    total_documents: int = Field(ge=0)
    """Total documents in the corpus that mention this target."""
    supporting_documents: int = Field(ge=0)
    """Documents with supporting evidence."""
    contradicting_documents: int = Field(ge=0)
    """Documents with contradicting evidence."""
    neutral_documents: int = Field(ge=0)
    """Documents mentioning the target without clear support/contradiction."""

    support_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    """Fraction of documents that support the target."""
    contradiction_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    """Fraction of documents that contradict the target."""
    neutral_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    """Fraction of documents that are neutral about the target."""

    # --- Confidence ---
    consensus_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    """Aggregate confidence in the consensus assessment."""

    # --- Per-document breakdown ---
    per_document: list[DocumentConsensusEntry] = Field(default_factory=list)
    """Per-document consensus details."""


class DocumentConsensusEntry(BaseModel):
    document_id: str
    document_title: str
    stance: str  # "supports" | "contradicts" | "neutral"
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
```

### 6.3 Aggregation Method

```
For a given claim or entity C:

1. Find all documents D = {d1...dn} that are connected to C via:
   - An EXTENDS edge (document contains entity cluster C)
   - A SUPPORTS edge (document contains claim C)
   - A CONTRADICTS edge (document contradicts claim C)

2. For each document di in D:

   a. Determine stance:
      - "supports" if:
          - Edge from di to C has relation_type SUPPORTS, EXTENDS,
            USES_METHOD, USES_DATASET, REPRODUCES
          - OR claim C has is_supported_by containing di
          - OR SemanticTriple mentioning C has is_negated=False
      - "contradicts" if:
          - Edge from di to C has relation_type CONTRADICTS
          - OR claim C has is_contradicted=True
          - OR SemanticTriple mentioning C has is_negated=True
      - "neutral" if:
          - No supporting or contradicting evidence found

   b. Compute stance confidence:
      - "supports": max(edge.confidence for supporting edges)
      - "contradicts": max(edge.confidence for contradicting edges)
      - "neutral": 1.0 - max(support_evidence_confidence,
                              contradict_evidence_confidence)

3. Aggregate:

   n = len(D)
   n_support = count("supports")
   n_contradict = count("contradicts")
   n_neutral = n - n_support - n_contradict

   support_ratio = n_support / n
   contradiction_ratio = n_contradict / n
   neutral_ratio = n_neutral / n

   avg_support_conf = avg(stance_confidence for "supports" entries)
   avg_contradict_conf = avg(stance_confidence for "contradicts" entries)

   consensus_confidence = (
       support_ratio * avg_support_conf
       + contradiction_ratio * avg_contradict_conf
       + neutral_ratio * 0.5  # neutral default confidence
   )
```

### 6.4 Consensus Classification

| Support Ratio | Contradiction Ratio | Classification | Interpretation |
|---|---|---|---|
| ≥ 0.8 | < 0.2 | **STRONG CONSENSUS** | Overwhelming agreement across documents |
| ≥ 0.6 | < 0.2 | **MODERATE CONSENSUS** | Majority agreement |
| ≥ 0.4 | < 0.2 | **WEAK CONSENSUS** | Plurality agreement but many neutral |
| Any | ≥ 0.3 | **DISPUTED** | Significant contradiction |
| < 0.3 | < 0.3 | **INSUFFICIENT EVIDENCE** | Most documents are neutral |

### 6.5 Evidence Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| Documents per target | 2 | 5+ |
| Evidence per document | 1 `EvidenceRecord` or `SemanticTriple` | 3+ independent sources |
| Minimum edge confidence | 0.1 | 0.5+ |
| Cross-doc coverage | 2 different documents | Documents from different author groups |

---

## 7. Contradiction Engine

### 7.1 Overview

The Contradiction Engine detects conflicts between claims, entities, and document findings using deterministic graph-structural and logical criteria.

### 7.2 Contradiction Types

```
Direct contradiction:
  Document A ─CONTRADICTS─→ Document B
    └─ Explicitly stated: "Contrary to Smith et al. (2020), we find..."

Indirect contradiction (same entity, opposite polarity):
  Document A ─EXTENDS─→ Entity X     (with claim "X improves accuracy")
  Document B ─EXTENDS─→ Entity X     (with claim "X reduces accuracy")
    └─ Same entity, opposite claim polarity

Indirect contradiction (negated triple):
  Triple: "Dropout" ─improves─→ "regularization"     (is_negated=False)
  Triple: "Dropout" ─improves─→ "regularization"     (is_negated=True)
    └─ Same triple, different negation flag

Indirect contradiction (competing claims):
  Claim A: "Method X achieves state-of-the-art on benchmark Y"
  Claim B: "Method Z outperforms all existing methods on benchmark Y"
    └─ Implicit contradiction about benchmark Y
```

### 7.3 `ContradictionResult` Model

```python
class ContradictionResult(BaseModel):
    """Result of contradiction analysis."""

    target_id: str
    """The node ID being analysed for contradictions."""
    target_label: str

    direct_contradictions: list[DirectContradiction] = Field(default_factory=list)
    """Explicit CONTRADICTS edges."""
    indirect_contradictions: list[IndirectContradiction] = Field(default_factory=list)
    """Logically inferred contradictions."""

    contradiction_count: int = Field(default=0, ge=0)
    aggregate_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DirectContradiction(BaseModel):
    source_document_id: str
    source_document_title: str
    target_document_id: str
    target_document_title: str
    edge_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    source_text: str | None = None


class IndirectContradiction(BaseModel):
    description: str
    """Human-readable description of the contradiction."""
    subject_id: str
    """Entity or claim at the centre of the contradiction."""
    subject_label: str
    claim_a: str
    """First claim."""
    claim_a_document: str
    """Document containing claim_a."""
    claim_b: str
    """Contradicting claim."""
    claim_b_document: str
    """Document containing claim_b."""
    confidence: float = Field(ge=0.0, le=1.0)
    """Confidence that this is a genuine contradiction."""
```

### 7.4 Direct Contradiction Detection

```
Input:
  graph          : CorpusGraphResult
  target_id      : str
  min_confidence : float

Algorithm:

  1. Query edges from target: edges = graph.query_edges(
       CorpusGraphQuery(source_id=target_id,
                        relation_types=[CONTRADICTS]))

  2. Also query edges TO target: incoming = graph.query_edges(
       CorpusGraphQuery(target_id=target_id,
                        relation_types=[CONTRADICTS]))

  3. Combine, deduplicate, filter by min_confidence.

  4. For each CONTRADICTS edge, resolve evidence_ids to
     EvidenceRecord objects and extract source_text.

  5. Return DirectContradiction list.

Confidence:
  contradiction_confidence = edge.confidence
  (The CONTRADICTS edge already encodes the detection confidence
   from the DocumentRelationEngine.)
```

### 7.5 Indirect Contradiction Detection

```
Input:
  graph          : CorpusGraphResult
  target_id      : str
  claims_index   : dict[str, list[RUOClaim]]  # claims by entity cluster ID
  triples_index  : dict[str, list[SemanticTriple]]

Algorithm:

  1. Identify all entity clusters connected to target_id via
     EXTENDS edges (i.e., documents sharing this entity).

  2. For each entity cluster, collect all claims and triples
     that reference it.

  3. Pairwise comparison:
     For each pair of claims (c1, c2) about the same entity:
       If claim_type(c1) == claim_type(c2) and
          polarity(c1) != polarity(c2):
         → IndirectContradiction detected

     For each pair of triples (t1, t2) with same subject_id
       and same predicate:
       If t1.is_negated != t2.is_negated:
         → IndirectContradiction detected

  4. Confidence computation:
     indirect_conf = min(claim_a.confidence, claim_b.confidence)

  5. Deduplicate: same (subject, claim_pair) should appear once.
```

### 7.6 Polarity Detection

Polarity is determined from:

| Source | Polarity Signal |
|---|---|
| `RUOClaim.is_contradicted` | `True` → negative |
| `SemanticTriple.is_negated` | `True` → negative |
| `RelationType.CONTRADICTS` edge | Always negative |
| `RUOClaim.claim_type` | `NEGATION` → negative |
| `RUOClaim.normalized_statement` | Contains negation keywords ("does not", "fails", "contradicts") → negative |

---

## 8. Research Gap Engine

### 8.1 Overview

The Research Gap Engine identifies missing or under-explored areas in the corpus using deterministic graph-structural criteria. No AI guessing — every gap is derived from measurable graph properties.

### 8.2 `GapAnalysisResult` Model

```python
class GapAnalysisResult(BaseModel):
    """Result of research gap analysis."""

    isolated_entities: list[GapItem] = Field(default_factory=list)
    """Entities appearing in only 1 document with no co-occurrence edges."""
    missing_comparisons: list[GapItem] = Field(default_factory=list)
    """Entity clusters with no COMPARES_WITH edges to other clusters."""
    weak_evidence_regions: list[GapItem] = Field(default_factory=list)
    """Claims or entities with below-threshold confidence."""
    under_studied_datasets: list[GapItem] = Field(default_factory=list)
    """Dataset-type entities appearing in fewer than N documents."""
    unconnected_documents: list[GapItem] = Field(default_factory=list)
    """Documents with degree below a threshold."""

    total_gaps: int = Field(default=0, ge=0)
    summary: str = ""
    """Human-readable summary of all gaps found."""


class GapItem(BaseModel):
    gap_type: GapType
    node_id: str
    label: str
    description: str
    """Why this is a gap (specific structural reason)."""
    confidence: float = Field(ge=0.0, le=1.0)
    """Confidence that this is a genuine gap (not an artifact)."""
    supporting_metrics: dict[str, Any] = Field(default_factory=dict)
    """Relevant metrics: degree, document_count, cluster_size, etc."""
    suggestion: str = ""
    """Actionable suggestion for addressing this gap."""
```

### 8.3 Gap Detection Algorithms

#### 8.3.1 Isolated Entities

```
Criteria:
  - Entity cluster appears in exactly 1 document
  - Entity cluster has degree == document_count (only EXTENDS edges, no COMPARES_WITH)
  - OR: degree == 0 (cluster exists but no edges)

Algorithm:
  For each entity_cluster node in graph:
    doc_count = number of document nodes connected via EXTENDS edges
    compares_with_count = number of COMPARES_WITH edges incident to this node
    total_degree = node degree (from graph)

    if doc_count == 1 and compares_with_count == 0:
      → Isolated entity gap
      confidence = 1.0 - max(0.5, entity_cluster.weight)
                   (lower entity confidence = more confident it's a gap)

    suggestion = f"Entity '{label}' appears only in document {doc_id} "
                 f"with no cross-document co-occurrence edges. Consider "
                 f"whether this entity is comparable to entities in other "
                 f"documents."

Metrics stored:
  - degree, doc_count, compares_with_count, cluster_size
```

#### 8.3.2 Missing Comparisons

```
Criteria:
  - Entity cluster has low COMPARES_WITH degree relative to cluster size
  - Entity cluster with label type METHOD or DATASET has 0 cross-cluster edges
    despite appearing in multiple documents

Algorithm:
  For each entity_cluster node in graph:
    if node.entity_label in {METHOD, DATASET, METRIC}:
      ec_degree = number of COMPARES_WITH edges to other entity clusters
      doc_count = number of EXTENDS edges from documents

      if ec_degree == 0 and doc_count >= 2:
        → Missing comparison gap
        confidence = 1.0 - (1.0 / max(doc_count, 2))
                     (more documents without comparisons = higher gap confidence)
        suggestion = f"Entity '{label}' appears in {doc_count} documents "
                     f"but has no COMPARES_WITH edges. Consider whether "
                     f"cross-document comparison is possible."

Metrics stored:
  - doc_count, ec_degree, entity_label
```

#### 8.3.3 Weak Evidence Regions

```
Criteria:
  - Claim with confidence below threshold
  - Entity mentioned only in low-confidence triples
  - Document with overall quality below threshold

Algorithm:
  For each claim:
    if claim.confidence < threshold (default: 0.3):
      → Weak evidence gap
      confidence = 1.0 - claim.confidence

  For each entity with evidence chains:
    if chain.aggregate_confidence < threshold:
      → Weak evidence gap
      confidence = 1.0 - chain.aggregate_confidence

Metrics stored:
  - claim/entity confidence, evidence count, document_id
```

#### 8.3.4 Under-Studied Datasets

```
Criteria:
  - Entity with entity_label == DATASET
  - Appears in fewer than N documents (default: 2)

Algorithm:
  For each entity_cluster with entity_label == DATASET:
    doc_count = number of documents connected via EXTENDS

    if doc_count < min_doc_threshold (default: 2):
      → Under-studied dataset gap
      confidence = 1.0 - (doc_count / min_doc_threshold)
      suggestion = f"Dataset '{label}' is studied in only {doc_count} "
                   f"document(s) in this corpus. Consider whether additional "
                   f"comparative studies exist."

Metrics stored:
  - doc_count, cluster_size, entity_confidence
```

#### 8.3.5 Unconnected Documents

```
Criteria:
  - Document node with degree below threshold (default: 1)
  - Or: document with no COMPARES_WITH or CITES edges to other documents

Algorithm:
  For each document node:
    doc_degree = node degree
    inter_doc_degree = count of edges to other document nodes

    if inter_doc_degree == 0:
      → Unconnected document gap
      confidence = 1.0 - (doc_entity_count / max_entity_count_in_corpus)

Metrics stored:
  - total_degree, inter_doc_degree, entity_count
```

### 8.4 Gap Confidence Philosophy

```
Gap confidence answers: "How confident are we that this IS a gap?"
- Higher gap confidence = more certain that something is missing
- Lower gap confidence = possibly an artifact (e.g., resolution merged
  unrelated entities, or the corpus legitimately focuses on one thing)

Formula: gap_confidence = 1.0 - P(not_a_gap)

Where P(not_a_gap) is estimated from:
  - Entity cluster weight (high weight → likely real entity → gap more real)
  - Document quality (well-extracted documents → gaps more reliable)
  - Edge count (more edges → more confident in connectivity assessment)
```

---

## 9. Failure Modes

### 9.1 Multi-Hop Reasoner

| Failure Mode | Description | Impact | Mitigation |
|---|---|---|---|
| **False positive connection** | Path found via semantically weak edges (e.g., COMPARES_WITH through unrelated entities) | Spurious connections inflate confidence | Confidence propagation via product model attenuates weak edges; min_confidence threshold |
| **False negative connection** | Path missed due to max_depth too low | Incomplete results | Default max_depth=3 with configurable upper bound |
| **Path explosion** | Dense graphs produce combinatorial path counts (k^d) | Performance degradation; result truncation | max_results cap; visited-set pruning; depth limit |
| **Semantic drift** | Long paths accumulate unrelated relation types | Meaningless connections | Relation-type filtering; path confidence decays |
| **Cycle loops** | Revisiting same nodes via different routes | Duplicate paths | Per-query visited set (strict) or per-path visited set (balanced) |

### 9.2 Evidence-Backed Answering

| Failure Mode | Description | Impact | Mitigation |
|---|---|---|---|
| **Orphan evidence IDs** | `evidence_ids` on edges reference non-existent `EvidenceRecord` | Broken traceability | Validation rule rejects unresolvable IDs |
| **Confidence inflation** | Multiple weak evidence items aggregated into high-confidence answer | Overconfident answers | Use `min` aggregation for independent evidence; cap at max individual confidence |
| **Evidence staleness** | Evidence from outdated document versions | Incorrect answers | Document update timestamps; warning on evidence age |
| **Duplicate evidence** | Same `EvidenceRecord` referenced from multiple edges | Inflated evidence count | Deduplicate by `evidence_id` in answer construction |

### 9.3 Consensus Engine

| Failure Mode | Description | Impact | Mitigation |
|---|---|---|---|
| **False consensus** | All documents cite same source → appear to agree | Spurious "strong consensus" | Track citation relationships between documents; discount derivative sources |
| **False contradiction** | Different entity resolution clusters for same concept produce contradictory stances | Apparent disagreement | Cross-check entity clusters; flag cluster-merge candidates |
| **Neutral imbalance** | Most documents are neutral (no explicit stance) | Consensus classified as insufficient | Differentiate "no evidence" from "equal evidence for both sides" |
| **Small-sample bias** | Few documents mention a target → ratios are unreliable | Statistical insignificance | Minimum document threshold (default: 3) before reporting consensus |

### 9.4 Contradiction Engine

| Failure Mode | Description | Impact | Mitigation |
|---|---|---|---|
| **False positive contradiction** | Different contexts produce superficially conflicting claims | Apparent contradiction | Require same claim_type; same entity; check section context |
| **False negative contradiction** | CONTRADICTS edge missing because DocumentRelationEngine didn't detect it | Missed conflicts | Indirect contradiction detection provides coverage |
| **Stance misclassification** | Negation detection fails on complex linguistic patterns | Wrong polarity | Combine is_negated, is_contradicted, and pattern matching |
| **Temporal contradiction** | Earlier paper contradicted by later paper (valid science progression) | Flagged as error | Track publication dates; distinguish replication from refutation |

### 9.5 Research Gap Engine

| Failure Mode | Description | Impact | Mitigation |
|---|---|---|---|
| **False positive gap** | Entity appears isolated due to incomplete entity resolution | Spurious gap flagged | Cross-check cluster membership; low gap confidence for small clusters |
| **False negative gap** | Genuinely isolated entity not flagged because it shares a cluster with another entity | Missed gap | Flag clusters with poor internal cohesion |
| **Gap confidence inflation** | Low graph density produces many "isolated" entities | Noise | Adjust thresholds per corpus density; normalize by graph statistics |
| **Meaningless gaps** | Non-research entities flagged as "under-studied" | User confusion | Restrict dataset/tool gaps to `EntityLabel.DATASET` and `EntityLabel.TOOL` |

### 9.6 Cross-System Failure Modes

| Failure Mode | Description | Impact | Mitigation |
|---|---|---|---|
| **Graph sparsity** | Few edges → little reasoning possible | Empty or low-confidence results | Surface sparsity as a warning; suggest gap analysis |
| **Graph density** | Many edges → path explosion, false connections | Performance and precision issues | Relation-type filtering, confidence thresholds, max results cap |
| **Entity resolution errors** | Merged unrelated entities → false connections across documents | Cascading reasoning failures | Propagate resolution confidence; surface entity cluster warnings |
| **Missing evidence chains** | Claims without evidence chains | Cannot construct evidence-backed answers | Fall back to edge-level evidence |
| **Corpus homogeneity** | All documents from same lab/group → artificial consensus | Biased consensus assessment | Track author affiliations; flag homogeneous corpora |

---

## 10. Integration Plan

### 10.1 Implementation Order

```
M4-1  Architecture Design        ← THIS DOCUMENT
       No code. Design complete.

       ┌─────────────────────────────────────────────────────┐
       │                                                     │
M4-2  Query Engine + Result Models                           │
       ├─── reasoning/models.py                              │
       │     QueryType (enum)                                │
       │     ReasoningQuery (model)                          │
       │     ReasoningResult (model)                         │
       │     AnswerEvidence (model)                          │
       │     ReasoningStep (model)                           │
       │     ConsensusResult, ContradictionResult,           │
       │     GapAnalysisResult, GapItem (models)             │
       │     GapType (enum)                                  │
       │                                                     │
       ├─── reasoning/engine.py                              │
       │     ReasoningEngine (class)                         │
       │       - dispatch_query(query) → ReasoningResult     │
       │       - _resolve_evidence(evidence_ids)             │
       │       - _build_answer(query, evidence, paths)       │
       │       - _compute_confidence(evidence_list)          │
       │       - _format_answer_text(query, metadata)        │
       │                                                     │
       │  Dependencies: CorpusGraphResult, EvidenceRecord,   │
       │                EvidenceChain, SemanticTriple        │
       │  Tests: M4-2 test suite (query dispatch, evidence   │
       │         resolution, confidence computation, answer  │
       │         formatting)                                 │
       └─────────────────────────────────────────────────────┘

       ┌─────────────────────────────────────────────────────┐
       │                                                     │
M4-3  Multi-Hop Reasoner                                     │
       ├─── reasoning/multi_hop.py                           │
       │     MultiHopReasoner (class)                        │
       │       - reason(source_id, target_id, query)         │
       │       - _find_paths(source, target, params)         │
       │       - _filter_paths(paths, min_conf, rel_types)   │
       │       - _propagate_confidence(path, method)         │
       │       - _aggregate_paths(paths)                     │
       │       - _resolve_evidence_for_path(path)            │
       │       - _build_reasoning_trace(paths)               │
       │       - _detect_cycles(paths, strategy)             │
       │                                                     │
       │  Dependencies: M4-2, CorpusGraphResult              │
       │  Tests: 1-hop, 2-hop, 3-hop paths; cycle handling;  │
       │         confidence propagation; edge cases           │
       └─────────────────────────────────────────────────────┘

       ┌─────────────────────────────────────────────────────┐
       │                                                     │
M4-4  Consensus Engine                                       │
       ├─── reasoning/consensus.py                           │
       │     ConsensusEngine (class)                         │
       │       - analyze(target_id, query)                   │
       │       - _determine_stance(doc_id, target_id)        │
       │       - _compute_ratios(stance_counts)              │
       │       - _compute_consensus_confidence(entries)      │
       │       - _classify_consensus(result)                 │
       │       - _check_min_docs(result, threshold)          │
       │                                                     │
       │  Dependencies: M4-2, CorpusGraphResult, RUOClaim,   │
       │                SemanticTriple index                  │
       │  Tests: strong/moderate/weak/disputed/insufficient  │
       │         consensus; per-document breakdown; edge cases│
       └─────────────────────────────────────────────────────┘

       ┌─────────────────────────────────────────────────────┐
       │                                                     │
M4-5  Contradiction Engine                                   │
       ├─── reasoning/contradiction.py                       │
       │     ContradictionEngine (class)                     │
       │       - analyze(target_id, query)                   │
       │       - _detect_direct(target_id, query)            │
       │       - _detect_indirect(target_id, claims, triples)│
       │       - _detect_polarity_mismatch(claims)           │
       │       - _detect_negated_triple_conflict(triples)    │
       │       - _deduplicate_contradictions(list)           │
       │       - _compute_contradiction_confidence(matches)  │
       │                                                     │
       │  Dependencies: M4-2, M4-3, RUOClaim, SemanticTriple │
       │  Tests: direct CONTRADICTS edges; indirect via      │
       │         polarity; negated triples; deduplication;   │
       │         confidence computation                      │
       └─────────────────────────────────────────────────────┘

       ┌─────────────────────────────────────────────────────┐
       │                                                     │
M4-6  Research Gap Engine                                    │
       ├─── reasoning/gaps.py                                │
       │     ResearchGapEngine (class)                       │
       │       - analyze(query) → GapAnalysisResult          │
       │       - _find_isolated_entities(graph)              │
       │       - _find_missing_comparisons(graph)            │
       │       - _find_weak_evidence_regions(graph, claims)  │
       │       - _find_under_studied_datasets(graph)         │
       │       - _find_unconnected_documents(graph)          │
       │       - _generate_suggestions(gap_items)            │
       │       - _compute_gap_confidence(gap_type, metrics)  │
       │       - _deduplicate_gaps(all_gaps)                 │
       │                                                     │
       │  Dependencies: M4-2, CorpusGraphResult, Resolution- │
       │                Result, RUOClaim                     │
       │  Tests: each gap type; corpus with known gaps;      │
       │         threshold sensitivity; deduplication        │
       └─────────────────────────────────────────────────────┘

       ┌─────────────────────────────────────────────────────┐
       │                                                     │
M4-7  Corpus Synthesis Engine                                │
       ├─── reasoning/synthesis.py                           │
       │     CorpusSynthesisEngine (class)                   │
       │       - synthesize(query) → ReasoningResult         │
       │       - _select_engines(query_type)                 │
       │       - _merge_results(sub_results)                 │
       │       - _resolve_conflicts(sub_results)             │
       │       - _rank_evidence(all_evidence)                │
       │       - _synthesize_answer(merged)                  │
       │       - _compute_overall_confidence(merged)         │
       │                                                     │
       │  Dependencies: M4-2, M4-3, M4-4, M4-5, M4-6        │
       │  Tests: end-to-end queries; cross-engine conflict   │
       │         resolution; answer synthesis                │
       └─────────────────────────────────────────────────────┘

M4-8  Evaluation
       ├─── Evaluate each sub-engine on 8-paper corpus
       ├─── End-to-end reasoning scenarios
       ├─── Performance benchmarks
       ├─── Coverage analysis
       └─── Report: eval_output/module4_evaluation.md
```

### 10.2 Dependency Graph

```
M4-1 (design)
  │
  ▼
M4-2 (query engine + models)
  │
  ├─────────────┬──────────────┬──────────────┐
  ▼             ▼              ▼              ▼
M4-3          M4-4           M4-5          M4-6
(Reasoner)   (Consensus)    (Contradict)  (Gaps)
  │             │              │              │
  └─────────────┴──────────────┴──────────────┘
                        │
                        ▼
                     M4-7
                  (Synthesis)
                        │
                        ▼
                     M4-8
                  (Evaluation)
```

### 10.3 File Layout

```
src/researchmind/
├── reasoning/                    # NEW — Module 4 package
│   ├── __init__.py
│   ├── models.py                 # QueryType, ReasoningQuery, ReasoningResult,
│   │                             #   AnswerEvidence, ReasoningStep,
│   │                             #   ConsensusResult, ContradictionResult,
│   │                             #   GapAnalysisResult, GapItem, GapType
│   ├── engine.py                 # ReasoningEngine (dispatcher)
│   ├── multi_hop.py              # MultiHopReasoner
│   ├── consensus.py              # ConsensusEngine
│   ├── contradiction.py          # ContradictionEngine
│   ├── gaps.py                   # ResearchGapEngine
│   ├── synthesis.py              # CorpusSynthesisEngine
│   └── evidence.py               # EvidenceResolver (shared utility)
│
tests/
├── test_reasoning_models.py      # M4-2 model tests
├── test_reasoning_engine.py      # M4-2 query dispatch tests
├── test_multi_hop.py             # M4-3 tests
├── test_consensus.py             # M4-4 tests
├── test_contradiction.py         # M4-5 tests
├── test_gaps.py                  # M4-6 tests
├── test_synthesis.py             # M4-7 tests
└── test_reasoning_e2e.py         # M4-8 end-to-end tests
```

### 10.4 Reuse Strategy

| Existing Component | How M4 Reuses It |
|---|---|
| `CorpusGraphResult.get_neighbors()` | Multi-hop BFS expansion |
| `CorpusGraphResult.find_paths()` | Exhaustive path enumeration for multi-hop reasoning |
| `CorpusGraphResult.shortest_path()` | Shortest-path queries |
| `CorpusGraphResult.query_nodes()` | Entity/document lookup |
| `CorpusGraphResult.query_edges()` | Relation-type filtering |
| `CorpusGraphResult.connected_components()` | Graph connectivity analysis for gaps |
| `CorpusGraphResult.subgraph()` | Neighborhood extraction for evidence trace |
| `CorpusGraphEdge.evidence_ids` | Link from graph edges to evidence records |
| `CorpusGraphNode.metadata` | Node-level attributes (entity_count, confidence, etc.) |
| `EvidenceRecord` | Atomic evidence units backing answers |
| `EvidenceChain` | Aggregated evidence for claims |
| `SemanticTriple` | Structured facts for contradiction detection |
| `RUOClaim` | Claim stance, polarity, and evidence chain ID |
| `ResolutionResult` | Entity cluster metadata for gap analysis |
| `DocumentRelation` | Relation-level evidence and confidence |

### 10.5 Interface Contract

```
Module 4 ReasoningEngine API:

    def reason(self, query: ReasoningQuery) -> ReasoningResult:
        """Main entry point. Dispatches to the appropriate sub-engine
        based on query.query_type, collects results, and constructs
        a unified ReasoningResult."""
        ...

    def reason_batch(self, queries: list[ReasoningQuery]) -> list[ReasoningResult]:
        """Batch version of reason()."""
        ...

    def register_evidence_provider(
        self,
        evidence_resolver: Callable[[list[str]], list[EvidenceRecord]]
    ) -> None:
        """Register a callable that resolves evidence_ids to EvidenceRecords."""
        ...
```

---

## Appendix A: Confidence Formula Cheat Sheet

| Context | Formula | Notes |
|---|---|---|
| Single-edge path | `C = edge.confidence` | Direct traversal |
| Multi-edge path (product) | `C = Π(ci)` | Independent edges |
| Multi-edge path (min) | `C = min(ci)` | Worst-case bound |
| Multiple paths aggregate | `C = 1 - Π(1 - Cj)` | Noisy-OR combination |
| Consensus: per-document | `c = max(support_edges.conf)` | Best supporting evidence |
| Consensus: overall | `C = Σ(w_i * c_i) / Σ(w_i)` | Weighted by stance ratio |
| Contradiction: direct | `C = edge.confidence` | From CONTRADICTS edge |
| Contradiction: indirect | `C = min(c1, c2)` | Both claims' confidence |
| Gap: isolated entity | `C = 1 - max(0.5, entity_weight)` | Low entity weight = less certain gap |
| Gap: missing comparison | `C = 1 - (1 / max(doc_count, 2))` | More docs without comparisons = higher |
| Gap: weak evidence | `C = 1 - claim.confidence` | Inverse of claim confidence |
| Gap: under-studied | `C = 1 - (doc_count / threshold)` | Linear with doc count |
| Answer aggregate | `C = min(all_evidence.confidence)` | Weakest evidence bounds answer |
| No evidence | `C = 0.0` | No answer without evidence |

## Appendix B: Index Requirements

For efficient operation, Module 4 requires the following indexes (built during initialization from existing data):

| Index | Key | Value | Used By |
|---|---|---|---|
| Entity → document map | entity_cluster_id | `list[doc_id]` | Consensus, Gaps |
| Document → entity map | doc_id | `list[entity_cluster_id]` | Document lookup |
| Claim → entity map | claim_id | `list[entity_cluster_id]` | Contradiction |
| Evidence chain → document | evidence_chain_id | `list[doc_id]` | Answer building |
| Triple → entity | entity_cluster_id | `list[SemanticTriple]` | Contradiction |
| Claim by entity | entity_cluster_id | `list[RUOClaim]` | Consensus, Contradiction |

All indexes are buildable via a single pass over `CorpusGraphResult.nodes`, `CorpusGraphResult.edges`, and the document-level claim/triple lists. No schema changes required.
