# Document Relation Engine — Architecture & Design

> **Version:** 1.0  
> **Module:** M3-3  
> **Date:** 2026-06-09  

---

## 1. Overview

The Document Relation Engine detects semantic relationships between pairs of `RUODocument` objects within a corpus. It uses five deterministic stages — citation links, shared entities, shared methods, triple comparison, and claim comparison — each contributing weighted evidence toward a final confidence score.

**Deterministic only** — no LLMs, embeddings, vector databases, or external APIs.

---

## 2. Detection Pipeline

```
Input: List[RUODocument] + optional ResolutionResult
   │
   ├── Stage 1: Citation Relations
   │   - DOI match, target_ruo_id match, corpus reference lookup
   │   - Relation: CITES / CITED_BY
   │   - Confidence: 1.0
   │   - Weight: 0.40
   │
   ├── Stage 2: Shared Canonical Entities
   │   - Cross-document entity overlap using M3-2 clusters
   │   - Relation: COMPARES_WITH / UNKNOWN
   │   - Confidence: overlap_ratio
   │   - Weight: 0.20
   │
   ├── Stage 3: Shared Methods
   │   - METHOD-typed entity overlap
   │   - Relation: USES_METHOD / EXTENDS
   │   - Confidence: method_overlap_ratio
   │   - Weight: 0.15
   │
   ├── Stage 4: Triple Comparison
   │   - Same subject/predicate/object → SUPPORTS
   │   - Same subject/predicate, conflicting object → CONTRADICTS
   │   - Confidence: average triple confidence
   │   - Weight: 0.15
   │
   └── Stage 5: Claim Comparison
       - Same claim_type + similar normalized statements
       - Negation mismatch → CONTRADICTS
       - Supporting claims → SUPPORTS
       - Confidence: average claim confidence
       - Weight: 0.10
```

### 2.1 Stage 1 — Citation Relations

Detects bibliographic citation links between documents.

**Sources:**
1. **`target_ruo_id` match**: A document A's reference has `target_ruo_id` set to document B's `ruo_id`
2. **DOI match**: A document A's reference has a DOI that matches document B's `header.doi`
3. **Fuzzy title match**: A document A's reference title matches document B's title above a similarity threshold (default: 85 using RapidFuzz `token_sort_ratio`)

**Direction:** If A references B → `CITES` (source=A, target=B). Inverse `CITED_BY` is derived.

**Confidence:** 1.0 for all citation detections (deterministic lookup).

---

### 2.2 Stage 2 — Shared Canonical Entities

Uses entity-resolution output (M3-2) to find semantically related documents via shared entities.

**Input:** `ResolutionResult.clusters` — each `EntityCluster` contains `canonical_entity.entity_ids` listing all entity references resolved to the same concept.

**Algorithm:**
1. For each cluster, collect the set of document IDs (extracted from entity_id prefixes) that contain members of that cluster
2. For each document pair that co-occurs in at least one cluster, compute:
   ```
   overlap = |shared_clusters| / min(|clusters_in_A|, |clusters_in_B|)
   ```
3. **Thresholds:**
   - `overlap >= 0.5` → `COMPARES_WITH` 
   - `overlap >= 0.2` → `COMPARES_WITH` (lower confidence)
   - `overlap < 0.2` → no relation

**Confidence:** `overlap_ratio` (clamped to [0, 1])

**Without resolution:** Falls back to raw entity text matching (lowercased).

---

### 2.3 Stage 3 — Shared Methods

Specialization of entity overlap for `METHOD`-labeled entities.

**Algorithm:**
1. Filter entities to `METHOD` label
2. Compute overlap ratio as in Stage 2
3. **Relation assignment:**
   - `overlap >= 0.4` → `USES_METHOD`
   - `overlap >= 0.2` → `EXTENDS` (one document builds on another's methodology)
   - `overlap < 0.2` → no relation

**Confidence:** `method_overlap_ratio`

---

### 2.4 Stage 4 — Triple Comparison

Compares `SemanticTriple` sets between documents.

**Matching rules:**
1. **Exact triple match**: Same `subject_id`, `predicate`, `object_id` → `SUPPORTS`
2. **Subject-predicate match, conflicting object**: Same `subject_id` and `predicate`, different `object_id` → `CONTRADICTS` candidate
3. **Subject-predicate match, one negated**: Same `subject_id` and `predicate`, same `object_id`, but different `is_negated` → `CONTRADICTS`

**Confidence:** Average confidence of the matching triples.

---

### 2.5 Stage 5 — Claim Comparison

Compares `RUOClaim` sets between documents.

**Matching rules:**
1. **Same claim_type + normalized statement match**: If two claims have the same `claim_type` and their `normalized_statement` fields are similar (fuzzy match above 80%) → potential match
2. **Negation check**: If one claim's statement contains negation ("does not", "isn't", "not", "never") and the other doesn't → `CONTRADICTS`
3. **Confirmation**: If both claims have similar positive statements → `SUPPORTS`

**Fallback without normalized_statement:** Compare `matched_patterns` intersection.

---

## 3. Confidence Model

### Per-Stage Weights

| Stage | Evidence Type | Weight | Max Confidence |
|-------|--------------|--------|----------------|
| 1 | Citation | 0.40 | 1.0 |
| 2 | Entity Overlap | 0.20 | `overlap_ratio` |
| 3 | Method Overlap | 0.15 | `method_overlap_ratio` |
| 4 | Triple Match | 0.15 | `avg_triple_confidence` |
| 5 | Claim Match | 0.10 | `avg_claim_confidence` |

### Aggregation

For each detected relation type, the final confidence is a weighted average of all evidence supporting that type:

```
final_conf = Σ(w_i · c_i) / Σ(w_i)
```

Where `w_i` is the stage weight and `c_i` is the max confidence from that stage for this relation type.

### Evidence Contribution

Each detection produces a `RelationEvidence` record with:
- `evidence_type`: Which stage produced it
- `description`: Human-readable explanation
- `confidence`: The confidence of this specific evidence item
- `source_ids`: Related IDs from the source document
- `target_ids`: Related IDs from the target document

---

## 4. Data Models

### 4.1 `RelationEvidence`

```python
class RelationEvidence(BaseModel):
    evidence_id: str
    evidence_type: str       # "citation" | "entity" | "method" | "triple" | "claim"
    description: str
    confidence: float        # [0, 1]
    source_ids: list[str]    # IDs in source document
    target_ids: list[str]    # IDs in target document
```

### 4.2 `RelationDetectionStats`

```python
class RelationDetectionStats(BaseModel):
    total_pairs: int                 # Document pairs evaluated
    relations_detected: int          # Total relations found
    relations_by_type: dict[str, int] # Count per RelationType
    stages_summary: dict[str, int]   # Evidence items per stage
```

### 4.3 `DocumentRelationResult`

```python
class DocumentRelationResult(BaseModel):
    relations: list[DocumentRelation]  # Detected relations
    evidence: list[RelationEvidence]   # All supporting evidence
    stats: RelationDetectionStats      # Summary statistics
```

---

## 5. Engine Class

```python
class DocumentRelationEngine:
    def __init__(
        self,
        resolution_result: ResolutionResult | None = None,
        entity_threshold: float = 0.2,
        method_threshold: float = 0.2,
        fuzzy_threshold: float = 85.0,
    ):
        ...
    
    def detect_relations(
        self,
        documents: list[RUODocument],
        corpus_manager: CorpusManager | None = None,
    ) -> DocumentRelationResult:
        """Run all 5 stages on all document pairs."""
        ...
    
    def detect_relations_between(
        self,
        doc_a: RUODocument,
        doc_b: RUODocument,
    ) -> list[tuple[RelationType, float, list[RelationEvidence]]]:
        """Run all 5 stages on a single pair."""
        ...
```

---

## 6. Performance Considerations

### Candidate Pair Generation

Instead of O(n²) pair evaluation, the engine uses index lookups:

1. **Citation candidates**: Documents that cite or are cited by each other
2. **Entity candidates**: Documents that share at least one entity cluster
3. **Method candidates**: Documents that share at least one METHOD entity

### Complexity

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| Citation detection | O(r) | r = total references |
| Entity overlap | O(c · d²) | c = clusters, d = docs per cluster |
| Method overlap | O(m · d²) | m = method clusters |
| Triple comparison | O(t²) | t = triples per doc (small) |
| Claim comparison | O(k²) | k = claims per doc (small) |
| **Total** | `O(n²)` worst-case | but typically much lower via candidate filtering |

---

## 7. Edge Cases

| Case | Handling |
|------|----------|
| No documents | Returns empty result |
| Single document | Returns empty result |
| Identical documents | Self-relation prevented by `DocumentRelation` validator |
| No shared entities | Entity stages produce no evidence |
| No resolution result | Fall back to raw entity text matching |
| Same DOI references | Citation deduplication |
| Conflicting evidence | Multiple relations generated (one per type) |
| Missing fields (null DOI, etc.) | Graceful skipping of that detection path |

---

## 8. Integration with CorpusManager

Relations detected by the engine can be added to a `CorpusManager`:

```python
engine = DocumentRelationEngine(resolution_result=result)
documents = corpus_manager.get_documents()
rel_result = engine.detect_relations(documents, corpus_manager)
for rel in rel_result.relations:
    corpus_manager.add_relation(rel)
```

The engine also reads from `CorpusManager.indexes` (citations_to, citations_from) to find candidate pairs efficiently.
