# Architecture Audit: Module 4 Reasoning Engine

**Auditor:** Senior Principal Engineer  
**Date:** 2026-06-11  
**Document Reviewed:** `architecture/reasoning_engine.md` (v1.0, 1368 lines)  

---

## Executive Summary

The architecture document is thorough, well-structured, and demonstrates a clear understanding of the existing codebase and constraints. The scope is appropriate, the reuse strategy is sound, and the integration plan follows a logical dependency order.

**However, the document contains one critical mathematical error and several high-severity design ambiguities that must be resolved before implementation.**

The primary concern is **Noisy-OR for multi-path confidence aggregation** — this formula will systematically overestimate confidence when paths share edges, producing arbitrarily high confidence in dense graphs. This is mathematically incorrect for the stated use case.

Secondary concerns include **contradictory consensus formulas** between the cheat sheet and detailed specification, a **backwards gap confidence formula** that contradicts its own stated philosophy, and **undefined stance priority** when documents simultaneously support and contradict the same target.

**Verdict: READY WITH FIXES**

Seven issues must be resolved before M4-2 implementation begins. All are well-scoped corrections to the design document (no code, no schema changes, no architectural redesign).

---

## Architecture Readiness Score

| Dimension | Score (1-5) | Notes |
|---|---|---|
| Scope clarity | 5 | Clearly defined boundaries, inputs, and exclusions |
| Query model completeness | 4 | Minor ambiguity on GAP_ANALYSIS asymmetry |
| Result model correctness | 4 | Conflicting confidence formulas need reconciliation |
| Multi-hop algorithm soundness | 2 | **Noisy-OR is incorrect for overlapping paths** |
| Evidence validation | 5 | Well-defined rules, no-answer-without-evidence is solid |
| Consensus algorithm | 3 | Undefined stance priority, missing `claim_type` signal |
| Contradiction detection | 4 | Sound logic, O(n²) scaling noted but acceptable |
| Gap detection determinism | 3 | Inverted confidence formula, missing corpus-size guard |
| Failure mode coverage | 5 | Comprehensive across all subsystems |
| Integration plan | 5 | Clear dependency order, file layout, test plan |

**Overall: 3.8 / 5.0 — READY WITH FIXES**

---

## Critical Findings

### C-1: Noisy-OR causes confidence inflation on overlapping paths

**Location:** Section 4.4 (confidence propagation), Section 4.7 (worked example)

**Description:** The document uses Noisy-OR (`P = 1 - Π(1 - Pi)`) to aggregate confidence across multiple paths between the same source and target. This formula computes the probability that "at least one path is correct" **only if paths are independent**. In a graph, paths routinely share edges — making them **dependent, not independent**.

**Proof from the document's own example:**

```
Path 1: Attention ─0.95→ BERT ─0.75→ ResNet ─0.92→ ImageNet   (product: 0.656)
Path 2: Attention ─0.80→ ResNet ─0.92→ ImageNet                  (product: 0.736)
```

These paths **share the edge** `ResNet ─0.92→ ImageNet`. Noisy-OR computes `1 - (1-0.656)*(1-0.736) = 0.909`. But the shared edge (0.92) appears in BOTH paths and is double-counted. The true aggregate should be lower.

**Catastrophic case:** If source and target are connected by a single edge with confidence 0.5, and there are 10 redundant (overlapping) paths each with product confidence ~0.5, Noisy-OR yields `1 - (0.5)^10 ≈ 0.999` — near certainty from moderate evidence.

**Severity:** CRITICAL — systematically overestimates confidence; the inflation grows with graph density.

**Fix:** Replace Noisy-OR with a formula that accounts for edge overlap:
- **OPTION A (correct but conservative):** `P_aggregate = max(P_path_i)` — the best path's confidence bounds the answer. No overcounting.
- **OPTION B (approximate but better):** `P_aggregate = 1 - Π(1 - P_edge_j)` where `P_edge_j` is each unique edge's confidence, computed once regardless of how many paths use it. This avoids double-counting.
- **OPTION C (graph-theoretic):** `P_aggregate = min_cut_product(source, target)` — find the minimum cut between source and target, multiply confidences along the cut. Represents the weakest independent evidence set.

**Recommendation:** Use Option A (max confidence) for the product model and Option B (unique-edge Noisy-OR) for an aggregate upper bound, documented with clear caveats.

---

### C-2: Contradictory consensus confidence formulas

**Location:** Section 3.4 (cheat sheet) vs Section 6.3 (detailed algorithm)

**Cheat sheet (Section 3.4):**
```
Consensus confidence = (support_ratio * avg(support_conf) + contradiction_ratio * avg(contradict_conf))
```
Note: **omits** the neutral term.

**Detailed algorithm (Section 6.3):**
```
consensus_confidence = (
    support_ratio * avg_support_conf
    + contradiction_ratio * avg_contradict_conf
    + neutral_ratio * 0.5   # neutral default confidence
)
```
Note: **includes** the neutral term weighted at 0.5.

These formulas produce different results whenever `neutral_ratio > 0`. The cheat sheet will under-report confidence when a significant fraction of documents are neutral.

**Severity:** CRITICAL — implementors cannot determine which formula is correct.

**Fix:** Make the cheat sheet match the detailed algorithm (include the neutral term). Also justify why neutral confidence defaults to 0.5 (it represents maximum uncertainty — neither support nor contradiction).

---

### C-3: Mixed-stance documents silently ignore contradicting evidence

**Location:** Section 6.3, step 2a (stance determination)

**Description:** When a document has both supporting edges (SUPPORTS, EXTENDS) and contradicting edges (CONTRADICTS) to the same target, the algorithm checks rules in order and picks the **first match**. Since "supports" is checked first, any document with a supporting edge will be classified as "supports" even if it also has a CONTRADICTS edge. The contradicting evidence is silently discarded.

**Example:** Document A says "Method X improves accuracy on benchmark Y" (SUPPORTS edge) and also says "Contrary to Smith et al., we find Method X degrades performance on benchmark Z" (CONTRADICTS edge). The algorithm sees the SUPPORTS edge first and classifies the document as "supports" for target "Method X". The contradicting evidence about benchmark Z is invisible.

**Severity:** CRITICAL — produces false consensus by ignoring contradictory evidence within a single document.

**Fix:** The algorithm must handle mixed stance:
1. Check for CONTRADICTS edges FIRST (stronger signal)
2. OR classify as "mixed" and track both support and contradict confidence separately
3. OR require multi-document majority rule when both signals exist

**Recommendation:** Separate the entity- and claim-level stance. Use edge-level stance per relation type (a document can simultaneously support entity X while contradicting claim Y about entity X). Only aggregate at the answer level.

---

## High Findings

### H-1: Per-query visited set breaks all-paths enumeration

**Location:** Section 4.2 (algorithm) vs Section 4.5 (cycle handling)

**Description:** Section 4.2 calls for DFS-based all-paths enumeration via `graph.find_paths()`. Section 4.5 says the **default** cycle handling is "per-query visited set" which skips nodes already visited during the entire query. This is fundamentally incompatible with all-paths enumeration: once a node is visited, it can never be visited again, meaning at most ONE path to any target can be found.

The existing `CorpusGraphResult.find_paths()` already uses per-path visited sets (tracking nodes within the current path). Adding an external per-query visited set breaks its semantics.

**Severity:** HIGH — the default configuration would silently degrade to single-path search, defeating the multi-hop reasoner's purpose.

**Fix:** Change the default cycle handling to **per-path visited set** for all path-finding queries. Reserve per-query visited set for `GRAPH_EXPLORATION` (where you want BFS expansion without revisiting).

---

### H-2: Gap isolated-entity confidence formula contradicts stated philosophy

**Location:** Section 8.3.1 (algorithm) vs Section 8.4 (philosophy)

**Phiilosophy (Section 8.4):**
> "Entity cluster weight (high weight → likely real entity → gap more real)"

Interpretation: Higher entity weight → more confident it's a real entity → more confident its isolation is a genuine gap → **higher gap confidence**.

**Algorithm (Section 8.3.1):**
```
confidence = 1.0 - max(0.5, entity_cluster.weight)
```

Interpretation: If weight = 0.9, gap confidence = `1.0 - 0.9 = 0.1` (LOW).
If weight = 0.5, gap confidence = `1.0 - 0.5 = 0.5` (MODERATE).

**This is the inverse of the stated philosophy.** High-weight entities (most likely real) get LOW gap confidence. Low-weight entities (possibly artifact) get HIGH gap confidence.

**Severity:** HIGH — produces counterintuitive results that contradict the design rationale.

**Fix:** Invert the formula to match the philosophy:
```
confidence = entity_cluster.weight    # high weight → high gap confidence
```
Or, if clamped:
```
confidence = max(0.1, entity_cluster.weight)
```

---

### H-3: Stance determination ignores `claim_type=NEGATION` in consensus engine

**Location:** Section 6.3, step 2a

**Description:** The consensus stance logic uses edge relation types, `is_supported_by`, `is_contradicted`, and `is_negated` to determine stance. However, it **does not use** `RUOClaim.claim_type`. The contradiction engine (Section 7.6) correctly lists `RUOClaim.claim_type` = `NEGATION` as a negative polarity signal, but the consensus engine doesn't leverage this.

A claim with `claim_type=NEGATION` (e.g., "Method X does not improve accuracy") attached to an entity via an EXTENDS edge would be classified as "supports" by the consensus engine because EXTENDS is in the support list. The negation is invisible.

**Severity:** HIGH — produces false consensus for negated claims.

**Fix:** In the consensus stance algorithm, add a check for `RUOClaim.claim_type == NEGATION` that overrides the edge-based stance to "contradicts" when negated claims are involved.

---

### H-4: Unconnected document gap formula rewards fewer entities

**Location:** Section 8.3.5

**Formula:**
```
confidence = 1.0 - (doc_entity_count / max_entity_count_in_corpus)
```

A document with 50 entities (corpus max = 60) → `1.0 - 50/60 = 0.167` — LOW confidence.
A document with 3 entities (corpus max = 60) → `1.0 - 3/60 = 0.95` — HIGH confidence.

**Problem:** A document with rich content (many entities) that is disconnected from the corpus is MORE noteworthy as a gap, not less. The formula penalizes rich documents and rewards sparse ones.

**Severity:** HIGH — inverts the gap significance signal.

**Fix:** Use a formula that increases with entity count:
```
confidence = min(1.0, doc_entity_count / max_entity_count_in_corpus)
```
Or make it proportional to the fraction of entity types unique to this document.

---

### H-5: Consensus classification has uncovered regions

**Location:** Section 6.4

**Current table:**

| Support Ratio | Contradiction Ratio | Classification |
|---|---|---|
| ≥ 0.8 | < 0.2 | STRONG CONSENSUS |
| ≥ 0.6 | < 0.2 | MODERATE CONSENSUS |
| ≥ 0.4 | < 0.2 | WEAK CONSENSUS |
| Any | ≥ 0.3 | DISPUTED |
| < 0.3 | < 0.3 | INSUFFICIENT EVIDENCE |

**Uncovered cases:**
- `support_ratio = 0.7, contradiction_ratio = 0.25`: Support qualifies for MODERATE (≥0.6) but contradiction disqualifies (< 0.2 required). Contradiction is 0.25 (≥ 0.2, < 0.3) — falls in the gap between < 0.2 and ≥ 0.3.
- `support_ratio = 0.35, contradiction_ratio = 0.25`: Support < 0.4 (not WEAK), contradiction < 0.3 (not DISPUTED). Falls through completely.
- `support_ratio = 0.9, contradiction_ratio = 0.1`: STRONG CONSENSUS despite 10% contradiction.

**Severity:** HIGH — can produce unclassified states or misleadingly strong consensus labels.

**Fix:** Make the classification exhaustive with a decision tree:
1. If `contradiction_ratio ≥ 0.2`: classify as DISPUTED regardless of support ratio
2. If `support_ratio ≥ 0.8`: STRONG CONSENSUS
3. If `support_ratio ≥ 0.6`: MODERATE CONSENSUS
4. If `support_ratio ≥ 0.4`: WEAK CONSENSUS
5. Otherwise: INSUFFICIENT EVIDENCE

This ensures (a) no uncovered regions, and (b) contradiction is dominant (even 20% contradiction triggers DISPUTED).

---

### H-6: `min_confidence` default of 0.0 includes zero-confidence edges

**Location:** Section 2.2, `ReasoningQuery`

```python
min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
```

The default of 0.0 means edges with confidence = 0.0 (or near-zero) are included in results. From the M3 evaluation, edge confidence ranges from ~0.047 to 1.0. A threshold of 0.0 will include the lowest-quality edges.

This is particularly dangerous for consensus analysis, where a single low-confidence CONTRADICTS edge could flip the classification from STRONG CONSENSUS to DISPUTED.

**Severity:** HIGH — default configuration produces lowest-quality results.

**Fix:** Change default to `0.3`:
```python
min_confidence: float = Field(default=0.3, ge=0.0, le=1.0)
```

---

## Medium Findings

### M-1: Path independence assumption undocumented

**Location:** Section 4.4

The product formula `Π(ci)` assumes edge confidences are independent. However, consecutive edges in a path are not independent — reaching the intermediate node is a prerequisite for traversing the next edge. For 2-hop paths this is approximately correct, but for longer paths the assumption weakens.

**Recommendation:** Add an explicit note that the product model assumes conditional independence of edges given the intermediate node, which is a simplification valid for short paths (≤3 hops).

---

### M-2: No cross-field validation on `ReasoningQuery`

**Location:** Section 2.2

The model defines `source_id: str | None = None`, but most query types require it. Validation is deferred to the dispatch logic. Adding Pydantic `@model_validator` would catch invalid query configurations earlier and provide better error messages.

**Recommendation:** Add a model validator that checks:

| QueryType | Required fields |
|---|---|
| ENTITY_LOOKUP | `source_id` |
| DOCUMENT_LOOKUP | `source_id` |
| PATH_REASONING | `source_id`, `target_id` |
| CONSENSUS_ANALYSIS | `source_id` |
| CONTRADICTION_ANALYSIS | `source_id` |
| GAP_ANALYSIS | (none) |
| GRAPH_EXPLORATION | `source_id` |

---

### M-3: Missing minimum corpus size guard for gap analysis

**Location:** Section 8.3

On a corpus of 2-3 documents, every entity appears in "only 1 document" and every dataset is "under-studied". These are artifacts of corpus size, not genuine research gaps.

**Recommendation:** Add a minimum document count threshold (e.g., 5 docs) below which gap analysis returns all results with a warning "Corpus too small for reliable gap analysis." Additionally, surface corpus size in each GapItem's `supporting_metrics`.

---

### M-4: Answer Builder (M4-2) vs Synthesis Engine (M4-7) responsibility overlap

**Location:** System context diagram (Section 1.5), Integration Plan (Section 10.1)

M4-2 includes an "Answer Builder" internal component. M4-7 is the "Corpus Synthesis Engine" that also builds answers. The relationship between these two is unclear — does M4-2's Answer Builder produce interim answers that M4-7 merges? Or does each sub-engine produce its own answer and M4-7 simply selects?

**Recommendation:** Clarify the layering:
- M4-2's Answer Builder = **per-engine answer construction** (takes sub-engine output + evidence → `ReasoningResult`)
- M4-7's Synthesis Engine = **cross-engine merging** (takes multiple `ReasoningResult` objects → unified `ReasoningResult`)

Update the diagram to show M4-3/4/5/6 feeding into M4-7, not M4-2.

---

### M-5: Indirect contradiction O(n²) scaling

**Location:** Section 7.5, step 3

For each entity cluster, all pairs of claims are compared: O(k²) for k claims. With 100 claims about a single entity, this is 4,950 comparisons. The doc mentions deduplication but not algorithmic complexity.

**Recommendation:** Add a bounding strategy: group claims by `claim_type` before pairwise comparison (contradictions between STATISTICAL and COMPARATIVE claims about the same entity are unlikely). Document worst-case complexity.

---

### M-6: Gap analysis thresholds should be configurable parameters, not hardcoded

**Location:** Section 8.3

Thresholds hardcoded in the algorithms:
- Isolated entity: `doc_count == 1` (line 916)
- Missing comparison: `doc_count >= 2` (line 944), entity label filter = {METHOD, DATASET, METRIC}
- Weak evidence: `threshold = 0.3` (line 966)
- Under-studied dataset: `min_doc_threshold = 2` (line 990)
- Unconnected document: implicit threshold = 0 (line 1013)

**Recommendation:** Define all thresholds as class-level constants or constructor parameters, documented with rationale.

---

## Low Findings

### L-1: `_validate_confidence` rounds but doesn't validate

**Location:** Section 3.1

```python
@field_validator("confidence")
@classmethod
def _validate_confidence(cls, v: float) -> float:
    return round(v, 6)
```

Pydantic already enforces `ge=0.0, le=1.0` from the field definition. The validator only rounds. Consider renaming to `_round_confidence` for clarity, or removing it and using `@field_serializer`.

### L-2: `register_evidence_provider` signature missing import

**Location:** Section 10.5

```python
from collections.abc import Callable  # missing import
```

The interface contract correctly uses `Callable` but doesn't show the import.

### L-3: `DocumentRelationResult` input usage unclear

**Location:** Section 1.4, Inputs Consumed

`DocumentRelationResult` is listed as an input but the document doesn't specify how it's used differently from `CorpusGraphEdge.evidence_ids`. The `DocumentRelationResult.evidence` field contains `RelationEvidence` objects that could provide richer evidence than edge-level `evidence_ids`.

**Recommendation:** Clarify that `DocumentRelationResult` provides relation-level evidence metadata for evidence-backed answers, while `CorpusGraphEdge` provides the graph traversal structure.

### L-4: Gap analysis `WEAK_EVIDENCE_REGION` definition is vague

**Location:** Section 2.4

```python
WEAK_EVIDENCE_REGION = "weak_evidence_region"
"""Group of entities/claims with below-threshold confidence."""
```

What constitutes a "group"? Are individual low-confidence entities flagged, or only clusters of them? The algorithm (Section 8.3.3) checks individual claims, which is inconsistent with the "region" concept in the enum documentation.

**Recommendation:** Either rename to `LOW_CONFIDENCE_CLAIM` or define a spatial clustering criterion (e.g., ≥3 low-confidence claims within the same section).

---

## Confidence Formula Review

| Formula | Correct? | Notes |
|---|---|---|
| Single-edge path: `C = edge.confidence` | ✅ | Direct reuse of M3 edge confidence |
| Multi-edge path (product): `C = Π(ci)` | ✅ | Valid under conditional independence assumption; document the assumption |
| Multi-edge path (min): `C = min(ci)` | ✅ | Conservative lower bound |
| **Multi-path aggregate (Noisy-OR): `C = 1 - Π(1 - Cj)`** | **❌** | **CRITICAL — overcounts shared edges** |
| Consensus per-document: `c = max(support_edges.conf)` | ✅ | Best evidence represents stance |
| **Consensus overall** | **❌** | **CRITICAL — two contradictory formulas in same document** |
| Contradiction direct: `C = edge.confidence` | ✅ | Direct reuse |
| Contradiction indirect: `C = min(c1, c2)` | ✅ | Weakest claim bounds detection |
| **Gap isolated entity: `C = 1 - max(0.5, weight)`** | **❌** | **HIGH — inverted vs. philosophy** |
| Gap missing comparison: `C = 1 - (1/max(doc_count,2))` | ✅ | Sensible — more docs without comparison = more notable |
| Gap weak evidence: `C = 1 - claim.confidence` | ✅ | Inverse relationship is correct (low claim conf = high gap conf) |
| **Gap under-studied: `C = 1 - (doc_count/threshold)`** | ⚠️ | MEDIUM — linear degradation is ad-hoc; consider logarithmic scaling |
| **Unconnected document: `C = 1 - (entity_count/max_count)`** | **❌** | **HIGH — inverted vs. significance** |
| Answer aggregate: `C = min(all_evidence.confidence)` | ✅ | Conservative lower bound |
| No evidence: `C = 0.0` | ✅ | Forces evidence-backed answers |

**Formulas with issues: 5 out of 15** (1 CRITICAL, 3 HIGH, 1 MEDIUM)

---

## Scalability Review

| Component | Scalability Concern | Mitigation in Design |
|---|---|---|
| Multi-hop path enumeration | DFS in dense graphs: O(k^d) paths | max_results cap (100), max_depth limit (3-100), visited-set pruning |
| Consensus per-document stance | Linear in documents × edges per doc | None needed — bounded by corpus size |
| Indirect contradiction | O(n²) pairwise claim comparison | None specified — add grouping by claim_type |
| Gap analysis | Full graph scan | Linear in nodes/edges — acceptable for 10k-node corpora |
| Index building | Single pass over nodes + edges | Already specified |
| Evidence resolution | Random access by evidence_id | O(1) dict lookup — already specified in engine design |

**Overall: Acceptable.** The design has reasonable caps for the explosion-prone multi-hop search. The indirect contradiction O(n²) should be noted with a grouping strategy.

---

## Determinism Review

| Requirement | Status | Evidence |
|---|---|---|
| No LLMs | ✅ | Explicitly stated in scope |
| No embeddings | ✅ | Explicitly stated |
| No vector databases | ✅ | Explicitly stated |
| No external APIs | ✅ | Explicitly stated |
| All confidence deterministic | ✅ | All formulas are arithmetic; no stochastic components |
| All traversal deterministic | ✅ | BFS/DFS are deterministic given same graph and parameters |
| Stance determination deterministic | ⚠️ | **Current algorithm depends on rule-checking order** — must fix to handle mixed-stance deterministically (see C-3) |
| Gap detection deterministic | ✅ | All criteria are graph-structural (degree, doc count, etc.) |

**Verdict:** Deterministic by design. One fix needed for stance determination order-dependence.

---

## Implementation Risk Assessment

| Topic | Risk Level | Explanation |
|---|---|---|
| Noisy-OR confidence model | **HIGH** | Implementors will ship mathematically incorrect confidence if they follow the current document. Fix must be applied before M4-2. |
| Consensus ambiguity | **HIGH** | Two contradictory formulas (cheat sheet vs algorithm) will cause implementation drift — one engineer follows Section 3.4, another follows Section 6.3, results disagree. Fix before M4-4. |
| Gap formula inversion | **MEDIUM** | Implementors may notice the backwards formula and "correct" it to match the philosophy, but without the fix explicitly in the document, this becomes tribal knowledge. Fix before M4-6. |
| Stance priority undefined | **MEDIUM** | Implementors will pick an arbitrary order (likely the order listed in the algorithm), producing silently wrong results for mixed-stance documents. Fix before M4-4. |
| Cycle handling default | **LOW** | Likely caught during M4-3 unit testing when all-paths test returns fewer paths than expected. Easy to fix during implementation. |
| min_confidence default | **LOW** | Caught during first integration test on real data. Easy to fix. |
| O(n²) contradiction | **LOW** | Not a problem for the 8-paper evaluation corpus. Becomes a problem at 100+ papers. Add grouping optimization during M4-5. |

---

## Recommended Changes Before M4-2

### Must Fix (Prevents Correct Implementation)

| # | Severity | Section | Change |
|---|---|---|---|
| 1 | CRITICAL | 4.4 | Replace Noisy-OR multi-path aggregation with max-path or unique-edge Noisy-OR |
| 2 | CRITICAL | 3.4 | Align confidence cheat sheet with Section 6.3 consensus formula |
| 3 | CRITICAL | 6.3 | Define mixed-stance priority (CONTRADICTS > SUPPORTS, or "mixed" classification) |
| 4 | HIGH | 4.5 | Change default cycle handling from per-query to per-path visited set |
| 5 | HIGH | 8.3.1 | Invert gap isolated-entity formula to match philosophy: `C = entity_cluster.weight` |
| 6 | HIGH | 2.2 | Change `min_confidence` default from `0.0` to `0.3` |
| 7 | HIGH | 6.4 | Fix consensus classification table to be exhaustive with no gaps |

### Should Fix (Prevents Confusing Results)

| # | Severity | Section | Change |
|---|---|---|---|
| 8 | HIGH | 6.3 | Add `claim_type=NEGATION` as a "contradicts" signal in consensus stance |
| 9 | HIGH | 8.3.5 | Invert unconnected document gap formula |
| 10 | MEDIUM | 2.2 | Add cross-field validator for required fields per QueryType |
| 11 | MEDIUM | 4.4 | Document edge independence assumption |
| 12 | MEDIUM | 8.3 | Add minimum corpus size guard for gap analysis |
| 13 | MEDIUM | 1.5 | Clarify M4-2 Answer Builder vs M4-7 Synthesis Engine boundary |

### Nice to Have

| # | Severity | Section | Change |
|---|---|---|---|
| 14 | LOW | 3.1 | Rename validator or use serializer |
| 15 | LOW | 10.5 | Add missing Callable import |
| 16 | LOW | 1.4 | Clarify DocumentRelationResult usage |
| 17 | LOW | 2.4 | Rename WEAK_EVIDENCE_REGION or define spatial criterion |

---

## Final Verdict

# READY WITH FIXES

The architecture is fundamentally sound. The scope, layering, reuse strategy, and integration plan are all well-conceived. The document is thorough and professionally written.

**Seven specific fixes are required before M4-2 implementation begins**, all of which are scoped corrections to the design document (no code, no schema changes, no architectural redesign). The most critical is replacing the Noisy-OR confidence aggregation with a formula that doesn't overcount shared edges.

The document correctly identifies most failure modes in Section 9, which gives confidence that the design thinking is mature even where specific formulas need adjustment.

**Estimated impact of fixes:** ~1-2 hours of document editing. No architectural changes required.
