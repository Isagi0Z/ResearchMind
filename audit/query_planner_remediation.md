# Remediation Report: Module 5 Research Assistant Layer

**Date:** 2026-06-11  
**Document:** `architecture/query_planner.md` (v1.0 → v1.1)  
**Audit Source:** `audit/query_planner_audit.md`

---

## Summary

| Category | Count | Fixed | Deferred |
|---|---|---|---|
| CRITICAL | 1 | 1 | 0 |
| HIGH | 6 | 6 | 0 |
| MEDIUM | 7 | 7 | 0 |
| LOW | 5 | 3 | 2 |
| **Total** | **19** | **17** | **2** |

---

## Fix Log

### C-1: EXPLANATION confidence product penalizes more evidence

**Action:** Replaced `product(path.confidence for path in paths)` with `max(path.confidence for path in paths)`

**Sections modified:**
- `Section 2.2` — comparison matrix confidence method: `product(path)` → `max(path)`
- `Section 8.4` — EXPLANATION formula row updated to `max(path.confidence for path in paths)` with inline justification
- `Section 8.5` — added EXPLANATION example answer demonstrating max-path confidence

**Rationale:** The product formula was anti-monotonic — more evidence paths produced lower confidence. Using `max()` aligns with MULTI_HOP and FACTUAL formulas, and is consistent with the principle that more evidence should strengthen (or at least not weaken) an answer. A path's confidence remains the product of its edge confidences (correct under conditional independence within a path).

---

### H-1: Planner uses cluster_id but router uses node_id

**Action:** Unified identifier strategy — `cluster_id` is the canonical identifier throughout both planner and router

**Sections modified:**
- `Section 6.2` — `router.route()` changed to use `parsed.primary_entity.cluster_id` and `e.cluster_id` instead of `node_id`

**Rationale:** `cluster_id` is the M3 entity cluster abstraction and supports the 1:N cluster-to-node relationship. The router internally resolves cluster_id to node_id when invoking M4 engines that require it. All plan examples already used cluster_id, so only the router needed updating.

---

### H-2: Index lifecycle contradiction

**Action:** Resolved the contradiction between "built once at startup" and "rebuild on each query" in favor of "built once at startup, invalidated on corpus mutation"

**Sections modified:**
- `Section 12.7 (F-28)` — updated from "Rebuild indexes on each query" to describe the correct lifecycle with rationale
- `Appendix C.4` — expanded lifecycle description with explicit note about M5 being read-only (Section 1.2), added normal-query path showing zero-overhead reuse

**Rationale:** M5 does not mutate the corpus (Section 1.2). Rebuilding indexes on every query is wasteful — indexes remain valid across all queries within a session. The once-at-startup design is correct; corpus mutation (a rare event) triggers a single rebuild on the next query.

---

### H-3: _verify_trace_chain is a no-op

**Action:** Implemented real chunk-chain verification in `_verify_trace_chain`

**Sections modified:**
- `Section 10.2` — replaced the always-return-True implementation with one that iterates `ev.trace` and calls `doc.get_chunk(trace_id)` for each ID
- Added explicit failure conditions documentation
- Required evidence types (`path_edge`, `contradiction`) fail when trace is empty; optional types (`consensus_entry`, `gap_item`) accept empty trace

**Rationale:** The traceability contract's final hop (evidence → document chunk) must be verified to prevent evidence referencing non-existent chunks from passing validation.

---

### H-4: EXPLANATION regex overcaptures FACTUAL queries

**Action:** Narrowed EXPLANATION patterns and added precedence documentation

**Sections modified:**
- `Section 4.2` — removed `r"what is (a|an|the) .*"` from EXPLANATION patterns (was causing all "what is X" questions to be classified as EXPLANATION)
- `Section 4.2` — added FACTUAL vs EXPLANATION precedence table with 8 examples showing correct classification

**Rationale:** The broad `.*` pattern captured all "what is" entity-lookup queries, misclassifying them as EXPLANATION. Removing it lets FACTUAL's `r"what (is|are|was|were)"` handle entity lookups naturally. EXPLANATION is now reserved for explicit explanation keywords (`explain`, `how does .* work`, `describe`, mechanism/concept questions).

---

### H-5: Secondary engines missing from routing code

**Action:** Added secondary engine entries for CONSENSUS and CONTRADICTION in the routing ROUTING_TABLE

**Sections modified:**
- `Section 6.1` — enriched the routing table documentation with descriptions of what enrichment means for each type
- `Section 6.2` — added `"secondary": ["multi_hop"]` to both CONSENSUS and CONTRADICTION entries in `ROUTING_TABLE`

**Rationale:** The routing table documented enrichment but the code didn't implement it. CONSENSUS enrichment uses MultiHop to find additional supporting/contradicting edges for cross-validation. CONTRADICTION enrichment uses MultiHop to find alternative contradictory paths beyond direct edges.

---

### H-6: Appendix C index structure incompatible with extraction code

**Action:** Aligned entity extraction code with Appendix C's `list[EntityCluster]` structure

**Sections modified:**
- `Section 4.3` — Pass 2 entity extraction now iterates over `list[EntityCluster]` (multiple clusters per label), extracting each cluster's `cluster_id` and `node_id`
- `Section 4.3` — added hasattr guard for `cluster.node_id` (clusters may not always carry a node_id)

**Rationale:** A single label (e.g., "attention") may map to multiple entity clusters. The old code assumed a 1:1 label→(cluster_id, node_id) mapping, which would crash with a TypeError when encountering multiple clusters. The fix matches the robust list-valued structure already documented in Appendix C.1.

---

### M-1: Template trailing comma tuple bug

**Action:** Fixed MULTI_HOP template trailing comma

**Sections modified:**
- `Section 8.2` — removed trailing comma after `"Best path confidence: {confidence:.2f}"` that was creating a 1-element tuple instead of a string

**Rationale:** Only MULTI_HOP had this issue (other templates were correctly formatted). The trailing comma caused `_TEMPLATES["MULTI_HOP"]["answer"]` to be a tuple `("...",)` instead of a string, which would raise `AttributeError` on `.format()`.

---

### M-2: F-25 violates non-negotiable no-evidence policy

**Action:** Replaced F-25 with a policy-compliant failure mode

**Sections modified:**
- `Section 12.6` — replaced `"Override to min(0.1, max_evidence_confidence)"` with `"the no-evidence policy (Section 10.5) prohibits fabricating a non-zero confidence"`

**Rationale:** The original F-25 directly contradicted the non-negotiable no-evidence policy by allowing a minimum 0.1 confidence override. The new F-25 describes the correct behavior: when all evidence is below threshold, return 0.0 with a warning.

---

### M-3: PlanDependency model unused

**Action:** Removed entire `PlanDependency` model section

**Sections modified:**
- `Section 5.5` (formerly) — removed `PlanDependency` class definition; renumbered `5.6 PlanResult` to `5.5 PlanResult`

**Rationale:** The model was defined but never referenced. `PlanStep` uses `dependencies: list[str]` (plain step_id strings), making `PlanDependency` dead code. If data-flow tracking is needed later, it can be added as an optional dict field on `PlanStep`.

---

### M-4: _detect_ambiguity undefined

**Action:** Defined the `_detect_ambiguity` method

**Sections modified:**
- `Section 4.3` — added full method implementation after the `extract()` method body

**Algorithm:**
1. Group entities by normalized (lowercased) text
2. Within each group, count unique `node_id` values
3. If a group has >1 unique node_id, mark all entities in that group as ambiguous and populate their `alternatives` list

**Rationale:** Without this definition, implementors would need to guess the ambiguity detection logic. The method is now deterministic and specified.

---

### M-5: Planner helper methods undefined

**Action:** Defined `_compute_parallel_groups` and `_estimate_complexity`

**Sections modified:**
- `Section 5.3` — added both method implementations after the `plan()` method body

**`_compute_parallel_groups`:** Uses topological layering to identify steps whose dependencies don't chain into each other. Steps in the same "ready" layer can execute in parallel.

**`_estimate_complexity`:** Uses step count thresholds (≤2 low, ≤5 medium, >5 high). Simple but sufficient for a v1 orchestrator.

**Rationale:** These methods were referenced in the `plan()` algorithm but had no specification, making parallel execution and complexity estimation unimplementable.

---

### M-6: Traceability exempts consensus_entry and gap_item

**Action:** Refined evidence type exemptions in source document checking

**Sections modified:**
- `Section 10.2` — changed exemption from `("consensus_entry", "gap_item")` to `("gap_item",)` only

**Rationale:** Consensus entries are inherently document-derived (they summarize document stances) — they must trace to at least one source document. Gap items represent absence of evidence, so they may legitimately lack a source document. Consensus is now held to the same traceability standard as path edges and contradictions.

---

### M-7: reasoning_trace and reasoning_steps overlap

**Action:** Consolidated to a single `reasoning_trace` field with a properly defined `ReasoningStep` model

**Sections modified:**
- `Section 9.1` — removed `reasoning_steps: list[dict]`; replaced comment on `reasoning_trace` to clarify it's one entry per plan step
- `Section 8.6` — added `ReasoningStep` Pydantic model with fields: `step_id`, `engine`, `description`, `confidence`, `evidence_ids`, `metadata`

**Rationale:** Having two reasoning fields (one typed, one untyped) with no documented distinction was confusing. The single typed `reasoning_trace: list[ReasoningStep]` provides both type safety and clear semantics.

---

### L-2: answer_type duplicates query_type

**Action:** Removed `answer_type` field from `ResearchAnswer`

**Rationale:** `answer_type` was `query_type` in lowercase — pure duplication. Clients should use `query_type` directly.

### L-3: Evidence ranking can produce negative scores

**Action:** Added `max(s, 0.0)` clamp to ranking score function

**Rationale:** Base confidence + penalties could drive the ranking score below zero. Clamping to `[0, ∞)` keeps the score interpretable.

### L-5: query_id never populated in ExecutionPlan

**Action:** Changed `query_id=""` to `query_id=parsed.query_id if hasattr(parsed, 'query_id') else ""`

**Rationale:** Plans were created with empty query_id, making plan-to-query correlation difficult during debugging. The fix propagates the identifier from the parsed query when available.

---

### Deferred Items

| Finding | Reason for Deferral |
|---|---|
| L-1: `query_type`/`classification` as `str` instead of `Literal` | Cosmetic; str works at runtime. Adding Literal would require importing `typing.Literal` across multiple files. Defer to implementation phase. |
| L-4: No ground truth for 105 test queries | Requires domain expert to author 25+ expected answers. Out of scope for architecture remediation. |

---

## Files Modified

`architecture/query_planner.md` — 22 edits across the following sections:
- Section 2.2 (comparison matrix)
- Section 4.2 (EXPLANATION regex, precedence table)
- Section 4.3 (entity extraction Pass 2, _detect_ambiguity)
- Section 5.3 (helper methods _compute_parallel_groups, _estimate_complexity; query_id fix)
- Section 5.5 (removed PlanDependency, renumbered)
- Section 6.1 (enrichment documentation)
- Section 6.2 (cluster_id unification, secondary engines)
- Section 7.3 (ranking score clamping)
- Section 8.2 (MULTI_HOP template comma fix)
- Section 8.4 (EXPLANATION confidence formula)
- Section 8.5 (EXPLANATION example answer)
- Section 8.6 (new: ReasoningStep model)
- Section 9.1 (consolidated reasoning fields, removed answer_type)
- Section 10.2 (real _verify_trace_chain, refined exemptions)
- Section 12.6 (F-25 replacement)
- Section 12.7 (F-28 lifecycle fix)
- Appendix C.4 (lifecycle clarification)
- Document header (version 1.1)

---

## Validation Status

- [x] Re-read entire architecture document — all sections consistent
- [x] Internal contradictions resolved (index lifecycle, F-25 policy)
- [x] All formulas verified (EXPLANATION uses max, all others unchanged)
- [x] Routing table fully aligned with routing code (secondary engines for all 3 types)
- [x] Target ID consistent (cluster_id in both planner examples and router)
- [x] Traceability rules enforced (chunk-level check no longer a no-op)
- [x] Query taxonomy precedence documented (FACTUAL vs EXPLANATION table)

**Remaining LOW items deferred (2):** L-1 (Literal types), L-4 (ground truth queries)

## Final Readiness Statement

**The architecture document is now READY for Phase 1 implementation.**

All CRITICAL, HIGH, and MEDIUM findings from the audit have been resolved. The document is internally consistent, all formulas are correct, routing is aligned, traceability is enforceable, and the query classification rules are properly documented with precedence. Two LOW items (Literal types, ground truth queries) are deferred to the implementation phase.
