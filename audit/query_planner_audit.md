# Architecture Audit: Module 5 Research Assistant Layer

**Auditor:** Senior Principal Engineer  
**Date:** 2026-06-11  
**Document Reviewed:** `architecture/query_planner.md` (v1.0, 1678 lines)

---

## Executive Summary

The architecture document is comprehensive, professionally written, and demonstrates a clear understanding of the M4 engine layer and the constraints of deterministic execution. The scope boundaries are well-defined, the query taxonomy is sensible, the template-driven synthesis approach is sound, and the integration plan follows a logical dependency order.

**However, the document contains one critical mathematical error in the confidence formula, and several high-severity design inconsistencies that must be resolved before Phase 1 implementation.**

The primary concern is the **EXPLANATION confidence formula** (`product(path.confidence for path in paths)`), which penalizes the presence of multiple evidence paths — more evidence produces lower confidence. This is the inverse of the desired behavior.

Secondary concerns include a **target_id mismatch between planner and router** (cluster_id vs node_id), a **direct contradiction on index lifecycle** ("built once at startup" vs "rebuild on each query"), a **traceability verifier whose chunk-chain check is a no-op**, and a **regex overdass** that will misclassify FACTUAL queries as EXPLANATION.

**Verdict: READY WITH FIXES**

Twelve issues must be resolved before Phase 1 implementation begins. All are well-scoped corrections to the design document (no code, no schema changes, no architectural redesign).

---

## Architecture Readiness Score

| Dimension | Score (1-5) | Notes |
|---|---|---|
| Scope clarity | 5 | Clearly defined boundaries, inputs, exclusions, and consumption boundary |
| Query taxonomy completeness | 5 | 8 types well-defined with matrix, routing targets, and templates |
| Query model correctness | 4 | Minor redundancies (answer_type vs query_type, reasoning_trace vs reasoning_steps) |
| Parsing architecture soundness | 3 | **EXPLANATION regex overcaptures; entity ambiguity method undefined** |
| Query planner design | 3 | **Planner/router target_id mismatch; query_id never set; helper methods undefined** |
| Routing engine correctness | 3 | **Secondary engines documented but missing from routing code; enrichment gap** |
| Evidence aggregation | 4 | Sound dedup and anomaly detection; penalty vs multiplicative downgrade conflict |
| Answer synthesis | 3 | **EXPLANATION confidence formula is self-defeating; all templates are 1-element tuples** |
| Traceability enforcement | 3 | **`_verify_trace_chain` always returns True; consensus/gap evidence exempt** |
| Failure mode coverage | 4 | Comprehensive (30 items) but F-25 contradicts non-negotiable no-evidence policy |
| Integration plan | 4 | Dependency graph could better reflect execution order |
| Index design | 2 | **Appendix C structure disagrees with entity extraction code; lifecycle contradiction** |

**Overall: 3.5 / 5.0 — READY WITH FIXES**

---

## Critical Findings

### C-1: EXPLANATION confidence product penalizes more evidence

**Location:** Section 2.2 (comparison matrix), Section 8.4 (confidence formula)

**Description:** The EXPLANATION confidence formula is:
```
product(path.confidence for path in paths)
```

This computes the product of *all path confidences*. Since path confidences are in [0, 1], multiplying them always produces a value ≤ the minimum path confidence. **More evidence paths produce lower confidence.**

**Example:**
- Path A confidence = 0.8 (one explanatory claim), Path B confidence = 0.7 (second explanatory claim)
- Product = 0.8 × 0.7 = **0.56** — lower than either individual path
- Adding a third path at 0.9 → 0.8 × 0.7 × 0.9 = **0.504** — even lower

More explanatory evidence should increase confidence, not decrease it. Every other aggregate formula in Section 8.4 uses `max()` or `min()`, which produce sensible monotonic behavior. EXPLANATION is the only formula that is anti-monotonic with respect to evidence count.

This is distinct from the M4 multi-edge path confidence (product within a path), which is correct under conditional independence. This is product *across paths*, which is wrong.

**Severity:** CRITICAL — systematically produces lower confidence as more evidence is gathered; directly contradicts the principle that more evidence should strengthen an answer.

**Fix:** Replace with a formula that aggregates paths sensibly:
- **OPTION A:** `max(path.confidence for path in paths)` — the best explanatory path bounds the answer (conservative, monotonic)
- **OPTION B:** `1 - Π(1 - path.confidence for path in paths)` — Noisy-OR over paths (probabilistic upper bound, but note edge-sharing caveat from M4 C-1)
- **OPTION C:** `mean(path.confidence for path in paths)` — average confidence across all paths

**Recommendation:** Use Option A (max) for v1 to be consistent with MULTI_HOP and FACTUAL formulas. Document that a path's confidence is itself the product of its edge confidences, and the answer uses the strongest explanatory path.

---

## High Findings

### H-1: Planner uses `cluster_id` but router uses `node_id` as target_id

**Location:** Section 5.4 (plan examples) vs Section 6.2 (routing logic)

**Description:** In the planner example (Section 5.4, Example 1), the plan step sets `target_id: "clu_003"` (a cluster ID). In the router (Section 6.2), the `RoutingDirective` sets:
```python
target_id=(
    parsed.primary_entity.node_id
    if parsed.primary_entity else None
),
```
using `node_id` instead of `cluster_id`.

The planner creates steps that reference `cluster_id`, but when the router creates directives for execution, it uses `node_id`. If both components are used in a pipeline (planner → router → execution), the plan steps and routing directives will disagree on what entity to query.

**Example:** An ambiguous entity that maps to cluster "clu_005" and has node_id "node_042". The planner creates a step with `target_id: "clu_005"`. The router creates a directive with `target_id: "node_042"`. Which one does the engine execute against?

**Severity:** HIGH — causes undefined runtime behavior; some engines expect node_ids, others may expect cluster_ids; the mismatch will produce empty results or errors.

**Fix:** Choose a single identifier scheme:
- Use **cluster_id** throughout (consistent with M3 entity resolution), and have the router resolve cluster_id → node_id internally
- Or use **node_id** throughout, and have the planner resolve cluster_id → node_id during planning
- Update the plan examples and routing code to use the same scheme

**Recommendation:** Use `cluster_id` as the canonical identifier in both planner and router. Add a `cluster_id` field to `RoutingDirective`. Have the router resolve to node_id only when invoking M4 engines that require it. This matches the M3 entity cluster abstraction (one cluster may contain multiple nodes).

---

### H-2: Index lifecycle contradiction — "built once" vs "rebuild on each query"

**Location:** Appendix C.4 (line 1665) vs Section 12.7 F-28 (line 1360)

**Description:** Two sections of the document give directly contradictory instructions for index lifecycle:

**Appendix C.4 (line 1665):**
> All indexes are **built once at startup** and **invalidated only when the corpus changes** (add/remove document).

**F-28 (line 1360):**
> | F-28 | Corpus indexes stale | Entity/document indexes outdated | Entity extraction may miss targets | **Rebuild indexes on each query** (in-memory, < 50ms) |

"Built once at startup, invalidated only on corpus mutation" ≠ "Rebuild on each query." These are fundamentally different strategies with different performance and consistency characteristics.

- Once-at-startup: stale if corpus is modified between queries, but minimal overhead per query
- On-every-query: always fresh, but 50ms overhead per query (adds up at scale)

**Severity:** HIGH — implementors cannot determine which lifecycle to implement; building indexes on every query on a 57-node corpus is wasteful, but following the once-at-startup approach misses F-28's stated rationale.

**Fix:** Resolve the contradiction by choosing one strategy:
- **Preferred:** "Build once at startup, invalidate on corpus mutation" is the correct design for a read-only system (M5 does not mutate the corpus per Section 1.2). Update F-28 to reflect this.
- **Alternative:** If on-every-query is desired, update Appendix C.4 and remove the "invalidated only when corpus changes" language.

**Recommendation:** Keep "built once at startup" as the canonical design (the corpus is read-only from M5's perspective per Section 1.2). Update F-28 to match. The 50ms rebuild cost is not justified when the corpus never changes during a session.

---

### H-3: `_verify_trace_chain` is a no-op — chunk-level verification never executes

**Location:** Section 10.2, lines 1148-1152

**Description:** The traceability contract mandates a 3-hop chain:
```
Answer → AggregatedEvidence → CorpusGraphEdge/Entry → RUODocument
```

The `verify()` method correctly checks Hops 1-3 (evidence ID exists, source document ID exists, document exists in corpus). However, the final Hop — verifying the evidence can be located within the document — is implemented as:

```python
def _verify_trace_chain(self, ev: AggregatedEvidence, doc: Any) -> bool:
    if not ev.trace:
        return True  # Consensus and gap evidence may not have direct chunk traces
    return True
```

This **always returns True**. When `ev.trace` is non-empty (meaning a trace chain IS provided), the method still returns True without checking whether the trace IDs actually resolve to chunks within the document. The `"no chunk found matching evidence"` failure in the `verify()` method is dead code — it can never be reached.

**Severity:** HIGH — the traceability contract's final and most important hop (evidence → document chunk) is unenforced. An answer with evidence referencing a non-existent chunk would pass verification.

**Fix:** Implement the chunk-chain verification:
```python
def _verify_trace_chain(self, ev: AggregatedEvidence, doc: Any) -> bool:
    if not ev.trace:
        return True  # No trace chain provided — skip (consensus/gap evidence)
    for trace_id in ev.trace:
        chunk = doc.get_chunk(trace_id)
        if chunk is None:
            return False  # Trace reference does not resolve to a document chunk
    return True
```
This requires `RUODocument` to support chunk lookup by ID (which should exist from M2 processing).

Additionally, remove the exemption for `consensus_entry` and `gap_item` from source document checking (Hop 2). If these evidence types claim to represent consensus or gap findings, they must trace to at least one source document.

---

### H-4: EXPLANATION regex overcaptures FACTUAL queries

**Location:** Section 4.2, pattern for EXPLANATION (line 330)

**Description:** The EXPLANATION type detection includes the pattern:
```python
r"what is (a|an|the) .*"
```

This is priority 5 out of 8 (applied before FACTUAL at priority 7). The pattern `r"what is (a|an|the) .*"` matches nearly any "what is X" question, including clear FACTUAL queries:

| Query | Correct Type | Matched Type | Reason |
|---|---|---|---|
| "What is the Adam optimizer?" | FACTUAL | **EXPLANATION** | `what is the` + `.*` |
| "What is the ResNet architecture?" | FACTUAL | **EXPLANATION** | `what is the` + `.*` |
| "What is the attention mechanism?" | EXPLANATION | EXPLANATION | Acceptable match |
| "What is a GAN?" | FACTUAL | **EXPLANATION** | `what is a` + `.*` |

The broad `.*` at the end makes this pattern capture ALL "what is" questions regardless of whether they ask for a definition (EXPLANATION) or a fact (FACTUAL).

**Severity:** HIGH — systematically misclassifies entity-lookup questions as explanation questions, which triggers different routing (path-finding instead of entity exploration), different template selection, and different confidence computation.

**Fix:** Narrow the EXPLANATION pattern to distinguish explanations from factual lookups:
- Use `r"explain\b"` and `r"how does .* work"` — these are unambiguous explanation triggers
- Remove `r"what is (a|an|the) .*"` from EXPLANATION or restrict it to pattern fragments that clearly indicate explanation (e.g., `r"what is the (mechanism|principle|idea|concept)"`)
- Let `r"what (is|are|was|were)"` under FACTUAL (priority 7) handle entity lookup queries naturally
- Alternatively, implement a two-pass: if EXPLANATION matches via `what is`, check whether the entity can be found; if found as a single entity, downgrade to FACTUAL

**Recommendation:** Remove `r"what is (a|an|the) .*"` from EXPLANATION. Move it to FACTUAL or drop it entirely (FACTUAL's `r"what (is|are|was|were|does|do|did)"` already covers it). Reserve EXPLANATION for explicit explanation keywords: `explain`, `how does .* work`, `describe`.

---

### H-5: Consensus and Contradiction secondary engines defined but not implemented in routing code

**Location:** Section 6.1 (routing table) vs Section 6.2 (routing code)

**Description:** The routing table (Section 6.1) documents secondary engines:

| Query Type | Secondary Engine(s) |
|---|---|
| CONSENSUS | MultiHopReasoner (enrich) |
| CONTRADICTION | MultiHopReasoner (paths) |

However, the routing code (Section 6.2) only defines secondary engines for COMPARISON:
```python
"COMPARISON": {"primary": "multi_hop", ..., "secondary": ["consensus"]},
"CONSENSUS": {"primary": "consensus", ...},  # No secondary
"CONTRADICTION": {"primary": "contradiction", ...},  # No secondary
```

This means the enrichment paths for CONSENSUS (e.g., using MultiHop to find additional supporting documents) and CONTRADICTION (e.g., using MultiHop to find contradictory paths) are never executed. The routing table describes a richer interaction than the routing code implements.

**Severity:** HIGH — the stated design includes multi-engine orchestration for consensus and contradiction, but the implementation code does not deliver it. Answers for these query types will be less complete than the design promises.

**Fix:** Add secondary engine entries for CONSENSUS and CONTRADICTION in the routing code, or remove them from the routing table if enrichment is deferred to a later phase. If enrichment is intentionally deferred, document it explicitly.

**Recommendation:** Add secondary enrichment to the routing code:
```python
"CONSENSUS": {"primary": "consensus", "m4_type": "CONSENSUS_ANALYSIS",
               "params": {"min_confidence": 0.3},
               "secondary": ["multi_hop"]},
"CONTRADICTION": {"primary": "contradiction", "m4_type": "CONTRADICTION_ANALYSIS",
                   "params": {"min_confidence": 0.3},
                   "secondary": ["multi_hop"]},
```
Document what enrichment means for each type (CONSENSUS: find additional supporting/contradicting edges; CONTRADICTION: find alternative contradictory paths).

---

### H-6: Appendix C index structure disagrees with entity extraction code

**Location:** Section 4.3 (entity extraction Pass 2) vs Appendix C.1 (entity label index)

**Description:** The entity extraction code (Section 4.3, Pass 2) uses a flat dictionary:
```python
cluster_index = self._build_cluster_index(corpus)  # label → (cluster_id, node_id)
```

This maps a single label to a single `(cluster_id, node_id)` pair — implying a 1:1 label-to-entity mapping.

Appendix C.1 defines a different structure:
```
entity_label_to_cluster: Entity label (lowercase) → list[EntityCluster]
entity_label_to_node: Entity label (lowercase) → CorpusGraphNode
```

The appendix returns `list[EntityCluster]` (0:many labels-to-clusters) while the code assumes `(cluster_id, node_id)` (1:1). These are incompatible data structures. If a label maps to multiple clusters (e.g., "attention" maps to both an "Attention Mechanism" cluster and an "Attention in Vision" cluster), the entity extraction code would fail because it expects a single tuple.

**Severity:** HIGH — the mismatch will cause runtime errors (TypeError: cannot unpack multiple values) when a label maps to multiple clusters, which is expected in any realistic corpus.

**Fix:** Make the entity extraction code handle list-valued index lookups:
```python
# Pass 2: Entity cluster label matching (handle multiple matches)
for label, clusters in cluster_index.items():
    if label.lower() in query.lower():
        for cluster in clusters:
            entities.append(QueryEntity(
                text=label,
                entity_type="concept",
                cluster_id=cluster.cluster_id,
                node_id=cluster.node_id,
                confidence=0.9,
            ))
```
Update the expected data structure in Appendix C to match the implementation.

---

## Medium Findings

### M-1: All template `answer` values are 1-element tuples, not strings

**Location:** Section 8.2, lines 879-953

**Description:** Every template's `"answer"` value uses the pattern:
```python
"answer": (
    "multi-line "
    "string"
),
```

The trailing comma inside the parentheses creates a **1-element tuple** instead of a string. For example:
```python
_TEMPLATES["FACTUAL"]["answer"]
# Returns: ("{entity_label} is associated with ...",) ← tuple, not string
```

Only FACTUAL's `"no_evidence"` key is correctly a plain string:
```python
"no_evidence": "No evidence found for {entity_label}.",
```

If the synthesizer calls `template["answer"].format(...)`, it will raise an `AttributeError` because tuples don't have `.format()`. The `"no_evidence"` fallback would work, but the primary answer template for all 8 query types would crash.

**Severity:** MEDIUM — causes immediate runtime crash on first non-trivial query. However, this is trivially caught by unit testing (CP-1 or CP-6).

**Fix:** Remove the trailing comma from each `"answer"` value:
```python
"answer": (
    "multi-line "
    "string"
),  →  "answer": (
               "multi-line "
               "string"
           ),
```

(Keep the parentheses for implicit string concatenation; remove only the comma after the closing quote.)

Note: MULTI_HOP has an additional trailing comma within the string tuple itself (line 941-942). Fix both.

---

### M-2: F-25 violates non-negotiable no-evidence policy

**Location:** Section 10.5 (no-evidence policy) vs Section 12.6 F-25

**Description:** Section 10.5 states:
> This policy is **non-negotiable** — it prevents hallucination by design.

The policy says zero evidence → confidence 0.0 → "Insufficient evidence" response.

However, F-25 (line 1352) defines:
> | F-25 | Final confidence = 0 despite evidence | Conflict between evidence and formula | Answer marked as no-confidence | Override to `min(0.1, max_evidence_confidence)` |

F-25 directly contradicts the non-negotiable policy. If the confidence formula produces 0.0 despite evidence being present, F-25 overrides to at least 0.1. This means there IS a case where evidence can be bypassed and non-zero confidence returned — exactly what the policy claims to prevent.

**Scenario:** All evidence items have confidence below a threshold that causes the formula to return 0.0 (e.g., a pathological consensus where all docs contradict). F-25 overrides to 0.1 and returns an answer with fabricated confidence, violating the non-negotiable policy.

**Severity:** MEDIUM — internal design contradiction that undermines the hallucination-prevention guarantee.

**Fix:** Resolve the contradiction:
- If the policy is truly non-negotiable: Remove F-25 entirely. When the formula gives 0.0, return "Insufficient evidence" regardless of whether evidence objects exist.
- If F-25 is desired: Amend the policy in Section 10.5 to allow this carve-out. Document the specific conditions (formula returns 0.0 despite non-empty evidence list).

**Recommendation:** Remove F-25. The confidence formula should already produce non-zero values when evidence exists. If a pathological case arises, the answer should honestly report 0.0 confidence rather than fabricating a minimum threshold.

---

### M-3: `PlanDependency` model defined but never used

**Location:** Section 5.5 (line 678) vs Section 5.1 (PlanStep definition)

**Description:** Section 5.5 defines a `PlanDependency` model:
```python
class PlanDependency(BaseModel):
    source_step_id: str
    target_step_id: str
    data_required: list[str] = Field(default_factory=list)
```

However, `PlanStep` uses `dependencies: list[str]` (a flat list of step_id strings), not `list[PlanDependency]`. The `PlanDependency` model is never referenced anywhere else in the document — no plan example uses it, no algorithm consumes it, and plan steps use plain strings instead.

**Severity:** MEDIUM — dead code that creates confusion about whether dependency tracking includes data requirements.

**Fix:** Either:
- Remove `PlanDependency` and rely on `PlanStep.dependencies: list[str]` (the simpler approach, matching the plan examples)
- Or update `PlanStep` to use `dependencies: list[PlanDependency]` and add data requirements to the plan examples

**Recommendation:** Remove `PlanDependency` as an independent model. If data-flow tracking is needed, add it as an optional dict field on `PlanStep`.

---

### M-4: Entity extraction `_detect_ambiguity` undefined

**Location:** Section 4.3, line 421

**Description:** The entity extraction algorithm calls:
```python
self._detect_ambiguity(entities)
```

This method is referenced but never defined. The ambiguity handling table (Section 4.5) describes what should happen (set `is_ambiguous`, include alternatives), but the detection logic itself is unspecified:
- What threshold constitutes ambiguity? (2+ matches? 3+?)
- Is it based on overlapping text, overlapping node_ids, or overlapping clusters?
- Does it use the `alternatives` list from the index or compute it separately?

**Severity:** MEDIUM — implementors cannot correctly implement ambiguity detection without specifying the algorithm.

**Fix:** Define `_detect_ambiguity`:
```python
def _detect_ambiguity(self, entities: list[QueryEntity]) -> None:
    """Detect ambiguous entity matches where multiple entities share text."""
    # Group entities by normalized text
    text_groups: dict[str, list[QueryEntity]] = {}
    for ent in entities:
        key = ent.text.lower()
        text_groups.setdefault(key, []).append(ent)

    # Mark groups with >1 unique node_id as ambiguous
    for key, group in text_groups.items():
        unique_nodes = {e.node_id for e in group if e.node_id}
        if len(unique_nodes) > 1:
            for ent in group:
                ent.is_ambiguous = True
                ent.alternatives = [
                    e.node_id for e in group if e.node_id != ent.node_id
                ]
```

---

### M-5: Planner helper methods referenced but undefined

**Location:** Section 5.3, lines 532-535

**Description:** The `QueryPlanner.plan()` method calls two helper methods:
```python
parallel = self._compute_parallel_groups(steps)
complexity = self._estimate_complexity(steps)
```

Neither method is defined or described anywhere in the document. The execution plan examples all show `parallel_groups: []` (empty), making parallel execution unusable.

Specific issues:
- `_compute_parallel_groups` must analyze step dependencies and identify independent execution paths. How? By mutual exclusion of dependency chains? By timestamp estimation? It's unspecified.
- `_estimate_complexity` uses "low" | "medium" | "high". What criteria distinguish them? Step count? Expected execution time? Graph density? It's unspecified.

**Severity:** MEDIUM — parallel execution and complexity estimation are design features that cannot be implemented from the document as-is.

**Fix:** Define both methods with concrete algorithms. For example:
```python
def _compute_parallel_groups(self, steps: list[PlanStep]) -> list[list[str]]:
    """Identify sets of steps with no dependency chains between them."""
    # Build dependency graph
    deps = {s.step_id: set(s.dependencies) for s in steps}
    # Use topological analysis to identify independent layers
    groups = []
    remaining = set(deps.keys())
    while remaining:
        # Find steps with no unresolved dependencies
        ready = {
            sid for sid in remaining
            if not deps[sid] & remaining
        }
        if not ready:
            break  # Cycle detected
        groups.append(sorted(ready))
        remaining -= ready
    return groups

def _estimate_complexity(self, steps: list[PlanStep]) -> str:
    """Estimate execution complexity based on step count and types."""
    engine_types = {s.engine for s in steps}
    if len(steps) <= 2:
        return "low"
    elif len(steps) <= 5:
        return "medium"
    else:
        return "high"
```

---

### M-6: Traceability verifier exempts consensus_entry and gap_item from document checking

**Location:** Section 10.2, lines 1121-1125

**Description:** The `verify()` method skips the source document check for consensus and gap evidence:
```python
if not ev.source_document_id:
    if ev.evidence_type not in ("consensus_entry", "gap_item"):
        failures.append(...)
    continue
```

This means consensus entries and gap items can lack a source document entirely without being flagged. This creates a traceability blind spot for 2 of the 5 evidence types:

- **Consensus entries:** If a `ConsensusResult` has per-document breakdowns, those documents should be traced. The exemption silently drops the traceability requirement.
- **Gap items:** A gap finding (e.g., "no comparison between X and Y") is an *absence* of evidence — it's reasonable that it may not trace to a positive document. But the document chain should still verify that the entities involved exist.

**Severity:** MEDIUM — creates a traceability gap for 40% of evidence types, reducing the contract's coverage.

**Fix:** Refine the exemption:
- For `consensus_entry`: Require at least one source document ID. Consensus is inherently document-based; every entry should trace.
- For `gap_item`: Allow empty source_document_id but require all referenced node_ids to exist in the corpus. Add a separate check for entity existence.

---

### M-7: `reasoning_trace` and `reasoning_steps` overlap

**Location:** Section 9.1, lines 1049-1050

**Description:** The `ResearchAnswer` model has two reasoning fields:
```python
reasoning_trace: list[ReasoningStep] = Field(default_factory=list)
reasoning_steps: list[dict] = Field(default_factory=list)
```

- `reasoning_trace` uses `ReasoningStep` — a model that is never defined in the document
- `reasoning_steps` is `list[dict]` — untyped, duplicates the concept
- The difference between them is not explained. Are they different views of the same data? Is one a summary of the other?

**Severity:** MEDIUM — confusing design that forces implementors to guess which field to populate and how they differ.

**Fix:** Consolidate to a single reasoning field:
- Define `ReasoningStep` as a Pydantic model with fields: `step_id`, `engine`, `description`, `confidence`, `evidence_ids`
- Remove `reasoning_steps: list[dict]` (replace with the typed model)
- Or, if both are needed, document explicitly: `reasoning_trace` = M4-level engine trace, `reasoning_steps` = M5-level plan step trace

**Recommendation:** Keep only `reasoning_trace: list[ReasoningStep]` with a clearly defined `ReasoningStep` model. Remove `reasoning_steps`.

---

## Low Findings

### L-1: `query_type` and `classification` use `str` instead of enum/Literal

**Location:** Section 3.3 (`ParsedQuery.query_type`), Section 9.1 (`ResearchAnswer.classification`)

`ParsedQuery.query_type: str` accepts any string, not just the 8 defined types. Same for `ResearchAnswer.classification: str | None`. Using `Literal["FACTUAL", "COMPARISON", ...]` would catch typos at validation time.

### L-2: `answer_type` field duplicates `query_type`

**Location:** Section 9.1, line 1058

```python
query_type: str = ""
answer_type: str = ""  # "factual" | "comparison" | ...
```

`answer_type` is `query_type` in lowercase. Remove it or define it as a derived property.

### L-3: Evidence ranking can produce negative scores

**Location:** Section 7.3, lines 820-830

The ranker applies penalties of -0.2 for missing source text and -0.3 for missing trace. Combined with low base confidence (e.g., 0.1), the score can go negative. While this doesn't break sorting, it produces "scores" that are not interpretable as confidence. Clamp scores to [0, ∞) or use multiplicative penalties.

### L-4: No ground truth defined for 105 test queries

**Location:** Section 14.3

The evaluation plan lists 105 queries with types and examples but provides no ground truth answers. Gate 4 (correctness ≥ 80%) depends on manual review, which is subjective and labor-intensive. For a deterministic v1, define expected answer patterns (template slots filled with specific values) for at least the 25 FACTUAL queries.

### L-5: `query_id` never populated in `ExecutionPlan`

**Location:** Section 5.3, lines 522-545

Both code paths set `query_id=""`. The planner should propagate the parsed query's identifier. This is a minor oversight — it would make correlating plans with queries more difficult during debugging.

---

## Confidence Formula Review

| Formula | Correct? | Notes |
|---|---|---|
| **FACTUAL**: `max(e.confidence for e in evidence)` | ✅ | Correct — best evidence bounds the answer |
| **COMPARISON**: `min(conf_a, conf_b, consensus_conf)` | ✅ | Conservative — weakest link bounds comparison |
| **EXPLANATION**: `product(path.confidence for path in paths)` | **❌** | **CRITICAL — penalizes more evidence; use `max()` instead (consistent with MULTI_HOP)** |
| **CONSENSUS**: `sr*avg(sup) + cr*avg(con) + nr*0.5` | ✅ | Correct — weighted by document ratios |
| **CONTRADICTION**: `max(c.confidence for c in contradictions)` | ✅ | Correct — strongest contradiction bounds answer |
| **RESEARCH_GAP**: `min(g.confidence for g in gaps)` | ✅ | Conservative — weakest gap signal |
| **MULTI_HOP**: `max(path.confidence for path in paths)` | ✅ | Correct — best path bounds answer |
| **EXPLORATION**: `max(e.confidence for e in edges)` | ✅ | Correct — best edge bounds answer |
| **No evidence default**: `0.0` | ✅ | Forces evidence-backed answers |

**Formulas with issues: 1 out of 9** (1 CRITICAL)

Note: The EXPLANATION issue is distinct from the M4 Noisy-OR issue (which was about multi-edge within a single path). M5's EXPLANATION formula aggregates across paths, and the product is self-defeating.

---

## Scalability Review

| Component | Scalability Concern | Mitigation in Design |
|---|---|---|
| Query parsing (regex cascade) | Linear in rules (8) × patterns (~5 each) | Trivial — 40 total patterns, each O(n) |
| Entity extraction (3-pass index) | Linear in index size × query length | Acceptable — index is < 100 entries for 57-node corpus; O(n) in query words |
| Query planning (dispatch) | Single dictionary lookup + builder | O(1) dispatch |
| Evidence aggregation | Linear in evidence count | Acceptable for corpus-bound results |
| Evidence dedup | O(n²) in worst case (text normalization) | 5-key strategy limits scope; typically O(n) per key |
| Answer synthesis | Template selection + string formatting | O(1) |
| Traceability verification | Linear in evidence items | O(n) document lookups (O(1) each via dict) |
| Index building | O(nodes + edges) | < 50ms for 57-node corpus |

**Overall: Acceptable.** M5 is fundamentally a orchestrator layer with low computational complexity. The most expensive operation is entity extraction (substring matching against the index), which is trivial for the target corpus sizes. No component has super-linear scaling that would be problematic at up to 200-node corpora.

The design correctly avoids all NLP, embedding, and API call overhead. The 50ms index rebuild budget (F-28) is achievable even for larger corpora.

---

## Determinism Review

| Requirement | Status | Evidence |
|---|---|---|
| No LLMs | ✅ | Explicitly stated in Section 1.2 |
| No embeddings | ✅ | Explicitly stated |
| No vector databases | ✅ | Explicitly stated |
| No external APIs | ✅ | Explicitly stated |
| All regex deterministic | ✅ | Same patterns, same input → same match |
| All entity extraction deterministic | ⚠️ | **Ambiguity detection undefined (M-4)** — may produce non-deterministic entity ordering if not specified |
| All planning deterministic | ✅ | Switch/builder dispatch is fully deterministic |
| All routing deterministic | ✅ | Dictionary lookup is deterministic |
| All evidence aggregation deterministic | ✅ | Sort with deterministic key, dedup with deterministic rules |
| All template synthesis deterministic | ✅ | Same evidence → same template output |
| Traceability verification deterministic | ✅ | All checks are deterministic |

**Verdict:** Deterministic by design. One minor risk: undefined `_detect_ambiguity` could produce non-deterministic entity ordering if defaults to Python set iteration order.

---

## Implementation Risk Assessment

| Topic | Risk Level | Explanation |
|---|---|---|
| EXPLANATION confidence formula | **HIGH** | Implementors will likely ship the product-of-paths formula as written, producing systematically wrong confidence for explanation queries. Must fix before Phase 1. |
| Planner-router target_id mismatch | **HIGH** | Runtime failures will occur when planner steps reference cluster_ids but router produces node_ids. Caught during integration testing but costly to fix post-hoc. |
| Index lifecycle ambiguity | **MEDIUM** | Implementors will pick one strategy arbitrarily. If they pick "rebuild on each query", performance degrades. If they pick "once at startup", they're inconsistent with F-28. Fix before Phase 1. |
| Template tuple bug | **LOW** | Caught immediately during CP-1 model validation or CP-6 template test. Easy to fix. |
| EXPLANATION regex overcapture | **MEDIUM** | Misclassification won't crash, but FACTUAL queries will produce EXPLANATION-quality answers (vague multi-sentence explanations instead of precise facts). Hard to detect without manual review. |
| Missing secondary engines | **MEDIUM** | CONSENSUS and CONTRADICTION will work but without enrichment. User-facing quality is lower than documented. Caught during Gate 5 evaluation. |
| Trace verifier no-op | **HIGH** | The traceability contract is a marquee feature. A no-op verification means the contract is unenforceable. Will pass all tests but provide false assurance. Fix before Phase 7. |

---

## Recommended Changes Before Phase 1

### Must Fix (Prevents Correct Answers)

| # | Severity | Section | Change |
|---|---|---|---|
| 1 | CRITICAL | 8.4 | Replace EXPLANATION `product(path.confidence)` with `max(path.confidence)` — more evidence must not decrease confidence |
| 2 | HIGH | 5.4 / 6.2 | Align planner and router on a single target ID scheme (recommend: cluster_id throughout) |
| 3 | HIGH | C.4 / 12.7 | Resolve index lifecycle contradiction — choose "built once at startup" (recommended) or "rebuild on each query" |
| 4 | HIGH | 10.2 | Implement `_verify_trace_chain` to actually verify chunk resolution, not just return True |
| 5 | HIGH | 4.2 | Narrow EXPLANATION regex to prevent FACTUAL overcapture — remove `what is (a\|an\|the) .*` |
| 6 | HIGH | 6.1 / 6.2 | Add secondary engine entries for CONSENSUS and CONTRADICTION in routing code, or remove from table |
| 7 | HIGH | 4.3 / C.1 | Fix entity extraction code to handle list-valued index entries (multiple clusters per label) |

### Should Fix (Prevents Confusing or Incomplete Results)

| # | Severity | Section | Change |
|---|---|---|---|
| 8 | MEDIUM | 8.2 | Fix all template `"answer"` values — remove trailing commas converting strings to tuples |
| 9 | MEDIUM | 10.5 / 12.6 | Resolve F-25 vs no-evidence policy contradiction — recommend removing F-25 |
| 10 | MEDIUM | 5.5 | Remove unused `PlanDependency` model or integrate it with `PlanStep` |
| 11 | MEDIUM | 4.3 | Define `_detect_ambiguity` algorithm |
| 12 | MEDIUM | 5.3 | Define `_compute_parallel_groups` and `_estimate_complexity` |
| 13 | MEDIUM | 10.2 | Remove or refine consensus_entry / gap_item exemption from document checking |
| 14 | MEDIUM | 9.1 | Consolidate `reasoning_trace` and `reasoning_steps` into a single typed field |

### Nice to Have

| # | Severity | Section | Change |
|---|---|---|---|
| 15 | LOW | 3.3 / 9.1 | Use `Literal` type for `query_type` and `classification` instead of `str` |
| 16 | LOW | 9.1 | Remove `answer_type` (duplicates `query_type`) |
| 17 | LOW | 7.3 | Clamp evidence ranking scores to `[0, ∞)` |
| 18 | LOW | 14.3 | Define ground truth for at least 25 of 105 test queries |
| 19 | LOW | 5.3 | Populate `query_id` in `ExecutionPlan` from parsed query |

---

## Dependency Chain Impact

| Fix # | Affected Phases | Breaks Downstream |
|---|---|---|
| 1 (EXPLANATION formula) | Phase 6 (Synthesizer) | No — fixes correctness |
| 2 (target_id mismatch) | Phase 3 (Planner), Phase 4 (Router) | **Yes** — must fix both in lockstep |
| 3 (index lifecycle) | Phase 2 (Parser), Appendix C | No — clarifies existing text |
| 4 (trace verifier) | Phase 7 (Traceability) | No — fixes broken implementation |
| 5 (EXPLANATION regex) | Phase 2 (Parser) | No — narrows existing pattern |
| 6 (secondary engines) | Phase 4 (Router) | No — adds missing entries |
| 7 (entity index structure) | Phase 2 (Parser), Appendix C | **Yes** — data structure change affects both |
| 8 (template tuples) | Phase 6 (Synthesizer) | No — fixes literal bug |
| 9 (F-25 policy) | Phase 6 (Synthesizer) | No — removes conflicting rule |
| 10 (PlanDependency) | Phase 3 (Planner) | No — removes dead code |
| 11 (ambiguity detection) | Phase 2 (Parser) | No — adds missing spec |
| 12 (planner helpers) | Phase 3 (Planner) | No — adds missing spec |
| 13 (trace exemptions) | Phase 7 (Traceability) | No — tightens existing rules |
| 14 (reasoning fields) | Phase 1 (Models) | **Yes** — model change affects Phases 2-8 |

**Recommendation:** Apply fixes in this order:
1. Phase 1 fixes first: #8 (template types), #14 (reasoning fields), #15 (Literal types), #16 (answer_type)
2. Phase 2 fixes: #5 (regex), #7 (index structure), #11 (ambiguity), #2 (target_id — part 1 from entity side)
3. Phase 3 fixes: #2 (target_id — part 2 from planner side), #10 (PlanDependency), #12 (helper methods)
4. Phase 4 fixes: #6 (secondary engines), #2 (target_id — part 3 from router side)
5. Phase 6 fixes: #1 (EXPLANATION formula), #8 (ensure templates are strings), #9 (F-25)
6. Phase 7 fixes: #4 (trace verifier), #13 (exemptions)
7. Cross-cutting: #3 (index lifecycle)

---

## Final Verdict

# READY WITH FIXES

The architecture is fundamentally sound. The scope, layering, reuse strategy, and integration plan are well-conceived. The document is thorough, professionally written, and correctly identifies most design concerns (30 failure modes across 7 categories).

**Seven high-severity and one critical issue must be resolved before Phase 1 implementation begins.** All are well-scoped corrections to the design document (no code, no schema changes, no architectural redesign). The most critical is the EXPLANATION confidence formula, which produces lower confidence with more evidence — the inverse of the correct behavior.

Three implementation-phase risks are notable:
1. **Planner-router target_id mismatch** (H-1) requires coordinated fixes across Phases 2, 3, and 4 — the highest integration risk.
2. **Traceability verifier no-op** (H-3) is a marquee feature that must be implemented correctly before Phase 7.
3. **Index lifecycle contradiction** (H-2) is a quick editorial fix but affects how implementors approach index management from day one.

**Estimated impact of fixes:** ~2-4 hours of document editing. No architectural changes, no schema changes, no new components required.
