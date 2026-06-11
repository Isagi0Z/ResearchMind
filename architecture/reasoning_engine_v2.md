# Module 4 — Reasoning Engine Architecture v2

**Status:** Design Document (Remediated)  
**Date:** 2026-06-11  
**Version:** 2.0  
**Audit Verdict:** READY  

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
| **Multi-hop reasoning** | Traverse the corpus graph along relation edges to connect indirectly related entities, documents, and claims. |
| **Evidence-backed answering** | Construct answers from `EvidenceRecord`, `EvidenceChain`, `SemanticTriple`, and `DocumentRelation` objects. Every answer traceable to source evidence. |
| **Cross-document synthesis** | Aggregate information about the same entity, claim, or method across documents. |
| **Consensus analysis** | Measure cross-document agreement. Compute support/contradiction/neutral ratios with deterministic confidence. |
| **Contradiction analysis** | Detect direct and indirect contradictions using `RelationType.CONTRADICTS`, claim polarity, and negated triples. |
| **Research gap identification** | Discover isolated entities, missing comparisons, weak-evidence claims, and under-studied datasets using deterministic graph-structural criteria. |
| **Graph exploration** | Expose the corpus graph through entity lookup, document lookup, path finding, neighbor traversal, and filtered edge/node queries. |

### 1.3 What Module 4 Is NOT Responsible For

| Out of Scope | Rationale |
|---|---|
| Fact extraction | Module 2 |
| Triple extraction | Module 2 |
| Evidence building | Module 2 (`EvidenceBuilder`) |
| Knowledge Graph construction | Module 2 (`KnowledgeGraphBuilder`) |
| Entity resolution | Module 3 (`EntityResolver`) |
| Document relation detection | Module 3 (`DocumentRelationEngine`) |
| Corpus graph construction | Module 3 (`CorpusGraphBuilder`) |
| LLM-based reasoning | Deterministic-only constraint |
| Embedding generation | Out of scope |
| External knowledge retrieval | No external APIs |
| Document ingestion | Module 1 |
| Schema modifications | Must reuse existing RUO/CorpusGraph structures |

### 1.4 Inputs Consumed

| Input | Source Module | Type | Usage in M4 |
|---|---|---|---|
| `CorpusGraphResult` | M3 | `CorpusGraphResult` | Primary reasoning substrate |
| `ResolutionResult` | M3 | `ResolutionResult` | Entity cluster metadata |
| `DocumentRelationResult` | M3 | `DocumentRelationResult` | Relation evidence metadata; `evidence` field provides `RelationEvidence` with description, source_ids, target_ids for evidence-backed answers |
| `EvidenceChain` list | M2 | `list[EvidenceChain]` | Per-claim evidence chains |
| `EvidenceRecord` list | M2 | `list[EvidenceRecord]` | Atomic evidence units |
| `SemanticTriple` list | M2 | `list[SemanticTriple]` | Structured facts with `is_negated` |
| `RUOClaim` list | M2 | `list[RUOClaim]` | Per-document claims with `claim_type`, `is_contradicted` |

### 1.5 System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      MODULE 4 — REASONING ENGINE                     │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              ReasoningEngine (M4-2 dispatcher)               │  │
│  │  - dispatch_query(query) → routes to sub-engine              │  │
│  │  - _resolve_evidence(evidence_ids) → AnswerEvidence list     │  │
│  │  - _build_answer(query, evidence) → ReasoningResult          │  │
│  └──────────┬──────────┬──────────┬──────────┬──────────────────┘  │
│             │          │          │          │                       │
│             ▼          ▼          ▼          ▼                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐               │
│  │Multi-Hop │ │Consensus │ │Contradict│ │  Gap     │               │
│  │(M4-3)    │ │(M4-4)    │ │(M4-5)    │ │(M4-6)    │               │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘               │
│       │            │            │            │                       │
│       └────────────┴────────────┴────────────┘                       │
│                            │                                         │
│                            ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │            Corpus Synthesis Engine (M4-7)                    │  │
│  │  Merges sub-engine results, resolves cross-engine conflicts, │  │
│  │  ranks evidence, computes overall confidence                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                            │                                         │
│                            ▼                                         │
│                     ReasoningResult                                  │
└─────────────────────────────────────────────────────────────────────┘
```

The M4-2 dispatcher routes queries to sub-engines. Each sub-engine produces a `ReasoningResult`. M4-7 merges results from multiple sub-engines when a query spans capabilities (e.g., consensus + contradiction on the same target). M4-2's internal `_build_answer` handles per-engine answer construction (evidence resolution → confidence aggregation → answer text). M4-7 handles cross-engine merging (conflict resolution → evidence ranking → unified confidence).

---

## 2. Query Model

### 2.1 `QueryType` Enum

```python
class QueryType(StrEnum):
    ENTITY_LOOKUP            = "entity_lookup"
    """Retrieve all graph information about a specific entity cluster."""
    DOCUMENT_LOOKUP          = "document_lookup"
    """Retrieve all graph information about a specific document."""
    PATH_REASONING           = "path_reasoning"
    """Multi-hop traversal to find indirect connections."""
    CONSENSUS_ANALYSIS       = "consensus_analysis"
    """Measure cross-document agreement about a claim, entity, or relationship."""
    CONTRADICTION_ANALYSIS   = "contradiction_analysis"
    """Detect contradictions involving a claim, entity, or document pair."""
    GAP_ANALYSIS             = "gap_analysis"
    """Identify research gaps: isolated entities, missing comparisons, weaknesses."""
    GRAPH_EXPLORATION        = "graph_exploration"
    """Open-ended traversal: neighbors, paths, connected components."""
```

### 2.2 `ReasoningQuery` Model

```python
class ReasoningQuery(BaseModel):
    """A complete reasoning query accepted by the ReasoningEngine."""

    query_type: QueryType

    # --- Node selection ---
    source_id: str | None = None
    """Primary node ID (document, entity_cluster, or claim)."""
    target_id: str | None = None
    """Secondary node ID (for pair-wise queries like path_reasoning)."""
    node_ids: list[str] | None = None
    """Multiple node IDs for batch operations."""

    # --- Entity / claim filters ---
    entity_label: EntityLabel | None = None
    claim_type: ClaimType | None = None
    relation_types: list[RelationType] | None = None

    # --- Traversal parameters ---
    max_depth: int = Field(default=3, ge=1, le=100)
    min_confidence: float = Field(default=0.3, ge=0.0, le=1.0)
    """Minimum confidence threshold (default 0.3 filters low-quality edges)."""

    # --- Result control ---
    max_results: int = Field(default=100, ge=1, le=10000)
    include_evidence: bool = Field(default=True)
    include_trace: bool = Field(default=True)
    include_graph_paths: bool = Field(default=True)

    # --- Gap analysis specific ---
    gap_types: list[GapType] | None = None
```

**Validation:** A `@model_validator` should enforce per-query-type required fields:
- `ENTITY_LOOKUP`, `DOCUMENT_LOOKUP`, `CONSENSUS_ANALYSIS`, `CONTRADICTION_ANALYSIS`, `GRAPH_EXPLORATION`: `source_id` required
- `PATH_REASONING`: both `source_id` and `target_id` required
- `GAP_ANALYSIS`: no required fields (runs on full corpus)

### 2.3 Per-QueryType Requirements Matrix

| QueryType | Required Inputs | Optional Inputs | Expected Output |
|---|---|---|---|
| `ENTITY_LOOKUP` | `source_id` (entity cluster ID) | `min_confidence`, `include_evidence`, `include_trace` | Entity cluster metadata, all connecting documents and entity clusters, all claims mentioning entity, evidence chains |
| `DOCUMENT_LOOKUP` | `source_id` (document ID) | `min_confidence`, `include_evidence`, `include_trace` | Document metadata, all entity clusters in doc, all relations, all claims, citation network neighbors |
| `PATH_REASONING` | `source_id`, `target_id` | `max_depth`, `relation_types`, `min_confidence`, `include_graph_paths` | List of `CorpusGraphPath` objects with confidence per path, intermediate node labels |
| `CONSENSUS_ANALYSIS` | `source_id` (claim or entity cluster ID) | `relation_types`, `min_confidence`, `include_evidence` | `ConsensusResult` with ratios, per-document breakdown, aggregate confidence |
| `CONTRADICTION_ANALYSIS` | `source_id` | `target_id`, `relation_types`, `min_confidence` | `ContradictionResult` with direct and indirect contradictions |
| `GAP_ANALYSIS` | (none) | `gap_types`, `entity_label`, `min_confidence` | `GapAnalysisResult` with categorized gaps |
| `GRAPH_EXPLORATION` | `source_id` | `max_depth`, `relation_types`, `min_confidence`, `max_results` | Neighborhood subgraph, path list, statistics |

### 2.4 `GapType` Enum

```python
class GapType(StrEnum):
    ISOLATED_ENTITY         = "isolated_entity"
    """Entity appearing in only one document with no inter-cluster edges."""
    MISSING_COMPARISON      = "missing_comparison"
    """Entity cluster with no COMPARES_WITH edges to other clusters."""
    LOW_CONFIDENCE_CLAIM    = "low_confidence_claim"
    """Individual claims or entities with below-threshold confidence."""
    UNDER_STUDIED_DATASET   = "under_studied_dataset"
    """Dataset-type entity appearing in fewer than N documents."""
    UNCONNECTED_DOCUMENT    = "unconnected_document"
    """Document node with degree below a threshold (few relations)."""
```

---

## 3. Reasoning Result Model

### 3.1 `ReasoningResult` Model

```python
class ReasoningResult(BaseModel):
    """Top-level result from any ReasoningEngine query."""

    query: ReasoningQuery
    answer: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    supporting_evidence: list[AnswerEvidence] = Field(default_factory=list)
    supporting_documents: list[str] = Field(default_factory=list)
    graph_paths: list[CorpusGraphPath] = Field(default_factory=list)
    reasoning_trace: list[ReasoningStep] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    @field_serializer("confidence")
    def _round_confidence(self, v: float) -> float:
        return round(v, 6)
```

### 3.2 `AnswerEvidence` Model

```python
class AnswerEvidence(BaseModel):
    evidence_id: str
    source_text: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    document_id: str
    evidence_type: EvidenceType
    location: EvidenceSpan | None = None
    relation_type: RelationType | None = None
    chain_id: str | None = None
    triple_id: str | None = None
```

### 3.3 `ReasoningStep` Model

```python
class ReasoningStep(BaseModel):
    step_number: int = Field(ge=1)
    description: str
    source_node_id: str
    target_node_id: str
    relation_type: RelationType | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
```

### 3.4 Deterministic Confidence Computation

All confidence computation in Module 4 is deterministic. The following formulas apply throughout:

| Operation | Formula | Use Case |
|---|---|---|
| **Path confidence (product)** | `Π(ci)` for edges `e1...en` | Per-path likelihood; assumes conditional independence of edges given intermediate nodes (valid for ≤3 hops) |
| **Path confidence (min)** | `min(c1...cn)` | Worst-case bound on reliability (independence-free) |
| **Evidence aggregate (min)** | `min(c1...cn)` | Chain strength = weakest link |
| **Evidence aggregate (avg)** | `(Σ ci) / n` | Balanced per-document confidence |
| **Evidence aggregate (weighted)** | `Σ(wi * ci) / Σ wi` | Weighted by evidence quality or source reliability |
| **Consensus confidence** | `support_ratio * avg(support_conf) + contradiction_ratio * avg(contradict_conf) + neutral_ratio * 0.5` | Blended by proportion, includes neutral default (0.5 = maximum uncertainty) |
| **Gap: isolated entity** | `entity_cluster.weight` | Higher entity weight = more notable gap |
| **Gap: missing comparison** | `1.0 - (1.0 / max(doc_count, 2))` | More docs without comparison = more notable |
| **Gap: low confidence** | `1.0 - claim.confidence` | Inverse of claim confidence |
| **Gap: under-studied dataset** | `1.0 - (doc_count / threshold)` | Linear with doc count |
| **Gap: unconnected document** | `min(1.0, doc_entity_count / max_entity_count)` | More entities in unconnected doc = more notable |

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
  min_conf      : float         # Min edge confidence (default: 0.3)

Output:
  paths         : list[CorpusGraphPath]

Algorithm:

  1. If target_id is None (exploration mode):
     a. Return graph.get_neighbors(source_id, depth=max_depth)
        filtered by relation_types and min_confidence.

  2. If target_id is set (path-finding mode):
     a. Leverage graph.find_paths(source_id, target_id, max_depth).
        This is the existing DFS-based all-paths enumeration.
        Cycle handling uses per-path visited set by default.

     b. Apply post-filtering:
        - Remove paths containing edges with confidence < min_conf
        - Remove paths using non-allowed relation types
        - Remove paths that revisit nodes (only if cycle_handling == strict)

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

  Rationale: Each edge detection is an independent measurement process.
             If edge 1 has 0.9 and edge 2 has 0.8, the combined
             probability both detections are correct is 0.9 * 0.8 = 0.72.

  Assumption: Edges are conditionally independent given the intermediate
             node. This is a reasonable approximation for short paths
             (≤3 hops). For longer paths the independence assumption
             weakens — use the min model for a conservative bound.

Path confidence (minimum model):
  P_path_min = min(edge.confidence for edge in path)

  Rationale: Worst-case bound — the path is only as reliable as its
             weakest edge. Does not rely on the independence assumption.
             Used as the primary lower bound for reporting.

Aggregate across multiple paths (primary):
  P_aggregate = max(P_path_i for i in 1..n)

  Rationale: The best single path bounds the answer confidence.
             This avoids overcounting shared edges across paths.
             Multiple overlapping paths do not increase confidence —
             they only corroborate the best evidence.

Aggregate across multiple paths (optional upper bound):
  P_upper = 1 - Π(1 - e_j) for each unique edge j in all paths

  Rationale: Noisy-OR over unique edges (counting each edge once)
             provides an upper-bound estimate. Unlike path-level
             Noisy-OR, this does not double-count shared edges.
             Caveat: edges are not truly independent; this is an
             approximation. Must be reported with the caveat:
             "Upper-bound estimate assuming independent edge evidence."
```

### 4.5 Cycle Handling

| Strategy | Implementation | When Used |
|---|---|---|
| **Per-path visited set** | Each path tracks its own `node_ids`; skip if node already in current path | **Default for path-finding** |
| **Per-query visited set** | `visited: set[str] = {source_id}`; skip nodes already visited | Exploration mode only (GRAPH_EXPLORATION) |
| **Allow cycles (max_depth cap)** | Allow revisiting nodes but cap at `max_depth` | Exploration mode only |
| **Cycle detection in output** | Deduplicate paths with identical node-ID sequences | Post-processing |

### 4.6 Stopping Criteria

| Criterion | Condition | Behaviour |
|---|---|---|
| Target found | `current_node == target_id` | Record path and continue searching (DFS) or stop (BFS) |
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

Aggregate confidence (max-path, primary):
  P = max(0.656, 0.736) = 0.736
  Rationale: Path 2 is the best single path. Path 1 shares the
  ResNet → ImageNet edge and would double-count it in Noisy-OR.

Aggregate confidence (unique-edge upper bound, optional):
  Unique edges: Attention→BERT (0.95), BERT→ResNet (0.75),
                ResNet→ImageNet (0.92), Attention→ResNet (0.80)
  P_upper = 1 − (1−0.95)(1−0.75)(1−0.92)(1−0.80)
         = 1 − (0.05)(0.25)(0.08)(0.20)
         = 1 − 0.0002 = 0.9998
  Note: Upper bound only; actual confidence is bounded by the
  best single path (0.736) due to shared edge dependencies.

Result: "Attention Is All You Need" is indirectly related to ImageNet
        via ResNet (confidence: 0.736, best-path aggregate).
```

---

## 5. Evidence-Backed Answering

[No changes needed — Section 5 is sound as-designed]

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
    if not evidence_list:
        return ReasoningResult(
            query=query,
            answer="Insufficient evidence to answer this query.",
            confidence=0.0,
            supporting_evidence=[],
            supporting_documents=[],
            warnings=["No supporting evidence found."],
        )
```

---

## 6. Consensus Engine

### 6.1 Overview

The Consensus Engine measures the degree of cross-document agreement about a specific claim, entity, or relationship. It operates over the corpus graph by examining edges from documents to the target node, combined with claim-level polarity information from `RUOClaim` and `SemanticTriple`.

### 6.2 `ConsensusResult` Model

```python
class ConsensusResult(BaseModel):
    target_id: str
    target_label: str

    total_documents: int = Field(ge=0)
    supporting_documents: int = Field(ge=0)
    contradicting_documents: int = Field(ge=0)
    neutral_documents: int = Field(ge=0)

    support_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    contradiction_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    neutral_ratio: float = Field(default=0.0, ge=0.0, le=1.0)

    consensus_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    per_document: list[DocumentConsensusEntry] = Field(default_factory=list)


class DocumentConsensusEntry(BaseModel):
    document_id: str
    document_title: str
    stance: str  # "supports" | "contradicts" | "neutral"
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    mixed_evidence: bool = False
    """True if document has both supporting and contradicting edges for
    this target. The stronger signal (contradicts) determines stance."""
```

### 6.3 Aggregation Method

```
For a given claim or entity C:

1. Find all documents D = {d1...dn} that are connected to C via:
   - An EXTENDS edge (document contains entity cluster C)
   - A SUPPORTS edge (document contains claim C)
   - A CONTRADICTS edge (document contradicts claim C)

2. For each document di in D:

   a. Determine stance (priority order — first match wins):

      - "contradicts" if:
          - Edge from di to C has relation_type CONTRADICTS
          - OR claim C has is_contradicted = True
          - OR claim C has claim_type == NEGATION
          - OR SemanticTriple mentioning C has is_negated = True

      - "supports" if (and no contradicting signal found above):
          - Edge from di to C has relation_type SUPPORTS, EXTENDS,
            USES_METHOD, USES_DATASET, REPRODUCES
          - OR claim C has is_supported_by containing di
          - OR SemanticTriple mentioning C has is_negated = False

      - "neutral" if:
          - No supporting or contradicting evidence found

      If di has BOTH contradicting edges AND supporting edges:
        - Set mixed_evidence = True in the DocumentConsensusEntry
        - The contradict stance takes priority (stronger signal)

   b. Compute stance confidence:
      - "contradicts": max(edge.confidence for contradicting edges,
                           claim.confidence for negated claims/triples)
      - "supports": max(edge.confidence for supporting edges)
      - "neutral": 0.5  # maximum uncertainty

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
       + neutral_ratio * 0.5   # neutral default = maximum uncertainty
   )
```

### 6.4 Consensus Classification

Decision tree (checked in order — first match wins):

| Condition | Classification | Interpretation |
|---|---|---|
| `contradiction_ratio ≥ 0.2` | **DISPUTED** | Significant contradictory evidence present |
| `support_ratio ≥ 0.8` | **STRONG CONSENSUS** | Overwhelming agreement across documents |
| `support_ratio ≥ 0.6` | **MODERATE CONSENSUS** | Majority agreement |
| `support_ratio ≥ 0.4` | **WEAK CONSENSUS** | Plurality agreement but many neutral |
| otherwise | **INSUFFICIENT EVIDENCE** | Too few documents take a position |

This ensures every possible (support_ratio, contradiction_ratio) pair maps to exactly one classification. Contradiction is the dominant signal — any ratio ≥ 0.2 triggers DISPUTED regardless of support level.

### 6.5 Evidence Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| Documents per target | 2 | 5+ |
| Evidence per document | 1 `EvidenceRecord` or `SemanticTriple` | 3+ independent sources |
| Minimum edge confidence | 0.3 | 0.5+ |
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
    target_id: str
    target_label: str
    direct_contradictions: list[DirectContradiction] = Field(default_factory=list)
    indirect_contradictions: list[IndirectContradiction] = Field(default_factory=list)
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
    subject_id: str
    subject_label: str
    claim_a: str
    claim_a_document: str
    claim_b: str
    claim_b_document: str
    confidence: float = Field(ge=0.0, le=1.0)
```

### 7.4 Direct Contradiction Detection

```
Input:
  graph          : CorpusGraphResult
  target_id      : str
  min_confidence : float

Algorithm:

  1. Query outgoing edges: edges = graph.query_edges(
       CorpusGraphQuery(source_id=target_id,
                        relation_types=[CONTRADICTS]))

  2. Query incoming edges: incoming = graph.query_edges(
       CorpusGraphQuery(target_id=target_id,
                        relation_types=[CONTRADICTS]))

  3. Combine, deduplicate, filter by min_confidence.

  4. For each CONTRADICTS edge, resolve evidence_ids to
     EvidenceRecord objects and extract source_text.

  5. Return DirectContradiction list.

Confidence:
  contradiction_confidence = edge.confidence
```

### 7.5 Indirect Contradiction Detection

```
Input:
  graph          : CorpusGraphResult
  target_id      : str
  claims_index   : dict[str, list[RUOClaim]]
  triples_index  : dict[str, list[SemanticTriple]]

Algorithm:

  1. Identify all entity clusters connected to target_id via
     EXTENDS edges.

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

Complexity: O(k²) in the number of claims per entity cluster.
For entities with >50 claims, group by claim_type before pairwise
comparison — cross-type contradictions (STATISTICAL vs EXISTENCE)
are unlikely and can be skipped.
```

### 7.6 Polarity Detection

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
    isolated_entities: list[GapItem] = Field(default_factory=list)
    missing_comparisons: list[GapItem] = Field(default_factory=list)
    low_confidence_claims: list[GapItem] = Field(default_factory=list)
    under_studied_datasets: list[GapItem] = Field(default_factory=list)
    unconnected_documents: list[GapItem] = Field(default_factory=list)
    total_gaps: int = Field(default=0, ge=0)
    summary: str = ""


class GapItem(BaseModel):
    gap_type: GapType
    node_id: str
    label: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_metrics: dict[str, Any] = Field(default_factory=dict)
    suggestion: str = ""
```

### 8.3 Gap Detection Algorithms

**Corpus size guard:** If `total_documents < 5`, all gap results include a warning: "Corpus too small for reliable gap analysis — gaps may reflect corpus composition rather than genuine research gaps." The `GapAnalysisResult.summary` field includes this warning. Individual `GapItem` entries surface `supporting_metrics.corpus_size` for downstream filtering.

All thresholds below are configurable class-level constants:

| Constant | Default | Used By |
|---|---|---|
| `ISOLATED_DOC_THRESHOLD` | 1 | 8.3.1 |
| `MISSING_COMPARISON_DOC_MIN` | 2 | 8.3.2 |
| `MISSING_COMPARISON_LABELS` | {METHOD, DATASET, METRIC} | 8.3.2 |
| `LOW_CONFIDENCE_THRESHOLD` | 0.3 | 8.3.3 |
| `UNDER_STUDIED_DOC_THRESHOLD` | 2 | 8.3.4 |
| `CORPUS_SIZE_MIN` | 5 | §8.3 premise |

#### 8.3.1 Isolated Entities

```
Criteria:
  - Entity cluster appears in exactly 1 document
  - Entity cluster has degree == document_count (only EXTENDS edges,
    no COMPARES_WITH)
  - OR: degree == 0 (cluster exists but no edges)

Algorithm:
  For each entity_cluster node in graph:
    doc_count = number of document nodes connected via EXTENDS edges
    compares_with_count = number of COMPARES_WITH edges incident to node
    total_degree = node degree

    if doc_count == ISOLATED_DOC_THRESHOLD and compares_with_count == 0:
      → Isolated entity gap
      confidence = entity_cluster.weight
                   (higher entity weight = more likely real = more notable gap)

    suggestion = f"Entity '{label}' appears only in 1 document "
                 f"with no cross-document co-occurrence edges. Consider "
                 f"whether this entity is comparable to entities in other "
                 f"documents."

Metrics stored:
  - degree, doc_count, compares_with_count, cluster_size
```

#### 8.3.2 Missing Comparisons

```
Criteria:
  - Entity cluster with label type in MISSING_COMPARISON_LABELS
  - Has 0 COMPARES_WITH edges despite appearing in multiple documents

Algorithm:
  For each entity_cluster node in graph:
    if node.entity_label in MISSING_COMPARISON_LABELS:
      ec_degree = number of COMPARES_WITH edges to other clusters
      doc_count = number of EXTENDS edges from documents

      if ec_degree == 0 and doc_count >= MISSING_COMPARISON_DOC_MIN:
        → Missing comparison gap
        confidence = 1.0 - (1.0 / max(doc_count, 2))
                     (more docs without comparisons = higher gap confidence)

        suggestion = f"Entity '{label}' appears in {doc_count} documents "
                     f"but has no COMPARES_WITH edges. Consider whether "
                     f"cross-document comparison is possible."

Metrics stored:
  - doc_count, ec_degree, entity_label
```

#### 8.3.3 Low-Confidence Claims

```
Criteria:
  - Claim with confidence below LOW_CONFIDENCE_THRESHOLD
  - Entity with evidence chain aggregate confidence below threshold

Algorithm:
  For each claim:
    if claim.confidence < LOW_CONFIDENCE_THRESHOLD (default: 0.3):
      → Low-confidence claim gap
      confidence = 1.0 - claim.confidence

  For each entity with evidence chains:
    if chain.aggregate_confidence < LOW_CONFIDENCE_THRESHOLD:
      → Low-confidence claim gap
      confidence = 1.0 - chain.aggregate_confidence

Metrics stored:
  - claim/entity confidence, evidence count, document_id
```

#### 8.3.4 Under-Studied Datasets

```
Criteria:
  - Entity with entity_label == DATASET
  - Appears in fewer than UNDER_STUDIED_DOC_THRESHOLD documents

Algorithm:
  For each entity_cluster with entity_label == DATASET:
    doc_count = number of documents connected via EXTENDS

    if doc_count < UNDER_STUDIED_DOC_THRESHOLD (default: 2):
      → Under-studied dataset gap
      confidence = 1.0 - (doc_count / UNDER_STUDIED_DOC_THRESHOLD)
      suggestion = f"Dataset '{label}' is studied in only {doc_count} "
                   f"document(s) in this corpus. Consider whether additional "
                   f"comparative studies exist."

Metrics stored:
  - doc_count, cluster_size, entity_confidence
```

#### 8.3.5 Unconnected Documents

```
Criteria:
  - Document with no COMPARES_WITH or CITES edges to other documents

Algorithm:
  For each document node:
    inter_doc_degree = count of edges to other document nodes

    if inter_doc_degree == 0:
      → Unconnected document gap
      confidence = min(1.0, doc_entity_count / max_entity_count_in_corpus)
                   (more entities in an unconnected document = more content
                    not integrated with the corpus = more notable gap)

Metrics stored:
  - total_degree, inter_doc_degree, entity_count
```

### 8.4 Gap Confidence Philosophy

```
Gap confidence answers: "How confident are we that this IS a gap?"
- Higher gap confidence = more certain that something is missing
- Lower gap confidence = possibly an artifact

Gap confidence is proportional to the strength of the signal that
the gap exists:
  - Entity weight (high weight → real entity → gap is real)
  - Document quality (well-extracted → gaps more reliable)
  - Entity count (rich content in unconnected doc → more notable)
  - Document count (many docs without comparison → more notable)

Gap confidence is NOT a measure of how important the gap is.
"""
```

---

## 9. Failure Modes

[No changes needed — Section 9 was already comprehensive.]

### 9.1 Multi-Hop Reasoner

| Failure Mode | Description | Impact | Mitigation |
|---|---|---|---|
| **False positive connection** | Path via semantically weak edges | Spurious connections | Product model attenuates weak edges; min_confidence threshold |
| **False negative connection** | Path missed due to low max_depth | Incomplete results | Default max_depth=3, configurable upper bound |
| **Path explosion** | Dense graphs: combinatorial path counts (k^d) | Performance degradation | max_results cap; depth limit; relation-type filtering |
| **Semantic drift** | Long paths accumulate unrelated relation types | Meaningless connections | Path confidence decays via product; relation-type filters |
| **Cycle loops** | Revisiting nodes via different routes | Duplicate paths | Per-path visited set (default); per-query set (exploration) |

### 9.2 Evidence-Backed Answering

| Failure Mode | Description | Impact | Mitigation |
|---|---|---|---|
| **Orphan evidence IDs** | evidence_ids reference non-existent EvidenceRecord | Broken traceability | Validation rule rejects unresolvable IDs |
| **Confidence inflation** | Multiple weak evidence items → high confidence | Overconfident answers | min aggregation for independent evidence |
| **Evidence staleness** | Outdated document versions | Incorrect answers | Timestamps; warning on evidence age |
| **Duplicate evidence** | Same EvidenceRecord referenced from multiple edges | Inflated count | Deduplicate by evidence_id |

### 9.3 Consensus Engine

| Failure Mode | Description | Impact | Mitigation |
|---|---|---|---|
| **False consensus** | All documents cite same source → appear to agree | Spurious "strong consensus" | Track citation relationships between documents |
| **False contradiction** | Different resolution clusters for same concept | Apparent disagreement | Cross-check cluster membership |
| **Neutral imbalance** | Most documents neutral (no explicit stance) | Classified insufficient | Differentiate "no evidence" from "equal evidence for both sides" |
| **Small-sample bias** | Few documents mention target → ratios unreliable | Statistical insignificance | Minimum document threshold (default: 3) |

### 9.4 Contradiction Engine

| Failure Mode | Description | Impact | Mitigation |
|---|---|---|---|
| **False positive contradiction** | Different contexts → superficially conflicting claims | Apparent contradiction | Require same claim_type and entity; check section context |
| **False negative contradiction** | CONTRADICTS edge missing | Missed conflicts | Indirect contradiction detection provides coverage |
| **Stance misclassification** | Negation detection fails on complex patterns | Wrong polarity | Combine is_negated, is_contradicted, and pattern matching |
| **Temporal contradiction** | Earlier paper contradicted by later paper | Flagged as error | Track publication dates; distinguish replication from refutation |

### 9.5 Research Gap Engine

| Failure Mode | Description | Impact | Mitigation |
|---|---|---|---|
| **False positive gap** | Entity isolated due to incomplete resolution | Spurious gap | Low gap confidence for small/uncertain clusters |
| **False negative gap** | Genuinely isolated entity not flagged | Missed gap | Flag clusters with poor internal cohesion |
| **Gap confidence inflation** | Low density → many "isolated" entities | Noise | Corpus size guard; normalize by graph statistics |
| **Meaningless gaps** | Non-research entities flagged | User confusion | Restrict dataset/tool gaps to EntityLabel.DATASET/TOOL |

### 9.6 Cross-System Failure Modes

| Failure Mode | Description | Impact | Mitigation |
|---|---|---|---|
| **Graph sparsity** | Few edges → little reasoning possible | Empty/low-confidence results | Surface sparsity as warning; suggest gap analysis |
| **Graph density** | Many edges → path explosion | Performance / precision issues | Relation-type filtering; confidence thresholds; max_results cap |
| **Entity resolution errors** | Merged unrelated entities → false connections | Cascading failures | Propagate resolution confidence; surface warnings |
| **Missing evidence chains** | Claims without evidence chains | Cannot construct evidence-backed answers | Fall back to edge-level evidence |
| **Corpus homogeneity** | All documents from same lab → artificial consensus | Biased assessment | Track author affiliations; flag homogeneous corpora |

---

## 10. Integration Plan

### 10.1 Implementation Order

```
M4-1  Architecture Design (v2 remediated)
       No code. Design complete.

M4-2  Query Engine + Result Models
       ├─── reasoning/models.py
       │     QueryType, ReasoningQuery, ReasoningResult,
       │     AnswerEvidence, ReasoningStep,
       │     ConsensusResult, ContradictionResult,
       │     GapAnalysisResult, GapItem, GapType
       │
       ├─── reasoning/engine.py
       │     ReasoningEngine (dispatcher)
       │       - dispatch_query(query) → ReasoningResult
       │       - _resolve_evidence(evidence_ids) → list[AnswerEvidence]
       │       - _build_answer(query, evidence, paths) → ReasoningResult
       │         (per-engine answer construction: evidence resolution →
       │          confidence aggregation → answer text formatting)
       │       - _compute_confidence(evidence_list, method)
       │       - _format_answer_text(query, metadata)
       │
       │  Dependencies: CorpusGraphResult, EvidenceRecord,
       │                EvidenceChain, SemanticTriple

M4-3  Multi-Hop Reasoner
       ├─── reasoning/multi_hop.py
       │     MultiHopReasoner
       │       - reason(source_id, target_id, query)
       │       - _find_paths(source, target, params)
       │       - _filter_paths(paths, min_conf, rel_types)
       │       - _propagate_confidence(path, method)
       │       - _aggregate_paths(paths)  # max-path primary, unique-edge upper bound
       │       - _resolve_evidence_for_path(path)
       │       - _build_reasoning_trace(paths)
       │       - _detect_cycles(paths, strategy)
       │
       │  Dependencies: M4-2, CorpusGraphResult

M4-4  Consensus Engine
       ├─── reasoning/consensus.py
       │     ConsensusEngine
       │       - analyze(target_id, query)
       │       - _determine_stance(doc_id, target_id)
       │         # Priority: CONTRADICTS > NEGATION > SUPPORTS > neutral
       │         # Tracks mixed_evidence flag
       │       - _compute_ratios(stance_counts)
       │       - _compute_consensus_confidence(entries)
       │       - _classify_consensus(result)
       │         # Decision tree: DISPUTED (≥0.2) > STRONG (≥0.8) > ...
       │       - _check_min_docs(result, threshold)
       │
       │  Dependencies: M4-2, CorpusGraphResult, RUOClaim,
       │                SemanticTriple index

M4-5  Contradiction Engine
       ├─── reasoning/contradiction.py
       │     ContradictionEngine
       │       - analyze(target_id, query)
       │       - _detect_direct(target_id, query)
       │       - _detect_indirect(target_id, claims, triples)
       │       - _detect_polarity_mismatch(claims)
       │       - _detect_negated_triple_conflict(triples)
       │       - _deduplicate_contradictions(list)
       │       - _compute_contradiction_confidence(matches)
       │
       │  Dependencies: M4-2, M4-3, RUOClaim, SemanticTriple

M4-6  Research Gap Engine
       ├─── reasoning/gaps.py
       │     ResearchGapEngine
       │       - analyze(query) → GapAnalysisResult
       │       - _find_isolated_entities(graph)
       │       - _find_missing_comparisons(graph)
       │       - _find_low_confidence_claims(graph, claims)
       │       - _find_under_studied_datasets(graph)
       │       - _find_unconnected_documents(graph)
       │       - _generate_suggestions(gap_items)
       │       - _compute_gap_confidence(gap_type, metrics)
       │       - _deduplicate_gaps(all_gaps)
       │       - _check_corpus_size(graph)  # returns warning if < 5 docs
       │
       │  Dependencies: M4-2, CorpusGraphResult, ResolutionResult, RUOClaim

M4-7  Corpus Synthesis Engine
       ├─── reasoning/synthesis.py
       │     CorpusSynthesisEngine
       │       - synthesize(query) → ReasoningResult
       │       - _select_engines(query_type)
       │       - _merge_results(sub_results)
       │         # Merges ReasoningResult objects from multiple engines
       │         # Handles cross-engine conflict resolution
       │       - _resolve_conflicts(sub_results)
       │       - _rank_evidence(all_evidence)
       │       - _synthesize_answer(merged)
       │       - _compute_overall_confidence(merged)
       │
       │  Dependencies: M4-2, M4-3, M4-4, M4-5, M4-6

M4-8  Evaluation
       ├─── Evaluate each sub-engine on 8-paper corpus
       ├─── End-to-end reasoning scenarios
       ├─── Performance benchmarks
       ├─── Coverage analysis
       └─── Report: eval_output/module4_evaluation.md
```

### 10.2 Dependency Graph

```
M4-1 (design v2)
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
├── reasoning/
│   ├── __init__.py
│   ├── models.py
│   ├── engine.py            # ReasoningEngine (dispatcher)
│   ├── multi_hop.py         # MultiHopReasoner
│   ├── consensus.py         # ConsensusEngine
│   ├── contradiction.py     # ContradictionEngine
│   ├── gaps.py              # ResearchGapEngine
│   ├── synthesis.py         # CorpusSynthesisEngine
│   └── evidence.py          # EvidenceResolver (shared utility)

tests/
├── test_reasoning_models.py
├── test_reasoning_engine.py
├── test_multi_hop.py
├── test_consensus.py
├── test_contradiction.py
├── test_gaps.py
├── test_synthesis.py
└── test_reasoning_e2e.py
```

### 10.4 Reuse Strategy

| Existing Component | How M4 Reuses It |
|---|---|
| `CorpusGraphResult.get_neighbors()` | Multi-hop BFS expansion |
| `CorpusGraphResult.find_paths()` | Exhaustive path enumeration (per-path cycle handling) |
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
| `RUOClaim` | Claim stance, polarity, claim_type, evidence chain ID |
| `ResolutionResult` | Entity cluster metadata for gap analysis |
| `DocumentRelation` | Relation-level evidence and confidence |

### 10.5 Interface Contract

```python
from collections.abc import Callable

class ReasoningEngine:
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
| Multi-edge path (product) | `C = Π(ci)` | Assumes conditional independence of edges (valid ≤3 hops) |
| Multi-edge path (min) | `C = min(ci)` | Worst-case bound; does not require independence |
| Multiple paths aggregate (primary) | `C = max(Cj)` | Best path bounds answer; avoids overcounting shared edges |
| Multiple paths aggregate (upper bound) | `C = 1 - Π(1 - e_j)` | Noisy-OR over unique edges only; caveat: edges not truly independent |
| Consensus: per-document | `c = max(support_edges.conf)` | Best supporting evidence for the assigned stance |
| Consensus: overall | `C = sr * avg(support_conf) + cr * avg(contradict_conf) + nr * 0.5` | Blended by stance ratio; neutral = 0.5 (maximum uncertainty) |
| Contradiction: direct | `C = edge.confidence` | From CONTRADICTS edge |
| Contradiction: indirect | `C = min(c1, c2)` | Both claims' confidence |
| Gap: isolated entity | `C = entity_cluster.weight` | High weight = real entity = more notable gap |
| Gap: missing comparison | `C = 1 - (1 / max(doc_count, 2))` | More docs without comparison = higher confidence |
| Gap: low confidence claim | `C = 1 - claim.confidence` | Inverse of claim confidence |
| Gap: under-studied dataset | `C = 1 - (doc_count / threshold)` | Linear with doc count below threshold |
| Gap: unconnected document | `C = min(1.0, entity_count / max_count)` | More entities in isolated doc = more notable |
| Answer aggregate | `C = min(all_evidence.confidence)` | Weakest evidence bounds answer |
| No evidence | `C = 0.0` | No answer without evidence |

## Appendix B: Index Requirements

| Index | Key | Value | Used By |
|---|---|---|---|
| Entity → document map | entity_cluster_id | `list[doc_id]` | Consensus, Gaps |
| Document → entity map | doc_id | `list[entity_cluster_id]` | Document lookup |
| Claim → entity map | claim_id | `list[entity_cluster_id]` | Contradiction |
| Evidence chain → document | evidence_chain_id | `list[doc_id]` | Answer building |
| Triple → entity | entity_cluster_id | `list[SemanticTriple]` | Contradiction |
| Claim by entity | entity_cluster_id | `list[RUOClaim]` | Consensus, Contradiction |

All indexes are buildable via a single pass over `CorpusGraphResult.nodes`, `CorpusGraphResult.edges`, and the document-level claim/triple lists. No schema changes required.
