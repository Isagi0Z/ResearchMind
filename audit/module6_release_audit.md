# Module 6 — Release Audit Report

**Date:** 2026-06-12
**Auditor:** automated investigation
**Status:** NOT READY

---

## 1. Executive Summary

The Module 6 evaluation fails 2 of 6 acceptance gates (traceability at 0%, pipeline stability at 4/5 no-crash). Every downstream metric collapse (0 themes, 0 evidence, 0 findings) traces to a single root cause — an *evaluation harness* bug that prevents the theme detector from seeing any entity nodes. A secondary evaluation harness bug (Python lambda self-binding) breaks document lookups, causing all traceability checks to fail. A genuine implementation bug in the orchestrator causes a crash when `review_id` is `None`.

Of **4 distinct failures identified**, only **1** is an implementation bug. The other 3 are evaluation harness issues that do not reflect on the synthesis engine's correctness.

---

## 2. Acceptance Gate Analysis

| Gate | Required | Actual | Pass | Root Cause |
|------|----------|--------|------|------------|
| Determinism | 100% | 100% | PASS | — |
| Traceability | 100% | 0% | **FAIL** | Evaluation harness lambda bug (see §5) |
| Confidence bounds | 0 violations | 0 violations | PASS | — |
| Pipeline stability | 0 crashes | 1 crash | **FAIL** | Missing `review_id` sanitization in orchestrator (see §6) |
| Serialization | 100% | PASS | PASS | — |
| Review generation | >= 90% | 100% | PASS | — |

**Two gate failures:**
1. **Traceability** — false negative caused by eval harness, not implementation
2. **Pipeline stability** — genuine implementation bug: `ReviewOrchestrator.generate()` does not guard `ReviewResult(review_id=None, ...)`

---

## 3. Theme Detection Analysis (Audit B)

### Finding B1: 0 themes due to node_type mismatch — EVALUATION HARNESS BUG

**Reproduction path:**
```
run_m6_eval.py:_make_entity_node("e001", "method", 0.95)
  → node.node_type = "entity"

ThemeDetector.detect_themes(graph)
  → line 119: if node_type == "entity_cluster":
  → no nodes match → entity_nodes = {} → return []
```

**Evidence:**
- `theme_detector.py:119`: `if getattr(n, "node_type", None) == "entity_cluster"`
- `run_m6_eval.py:47` (`_make_entity_node`): `"node_type": "entity"`
- Unit tests use `CorpusGraphNode(node_type="entity_cluster", ...)` — all 119 pass
- Confirmed: changing `"entity"` → `"entity_cluster"` in mock produces 4 themes

**Classification:** EVALUATION HARNESS BUG — **Severity: CRITICAL** (blocker)

### Finding B2: Missing `label` attribute on mock nodes — EVALUATION HARNESS BUG

`_make_entity_node` does not set `node.label` as a direct attribute. The detector reads `cn.label` at line 180. When mock objects lack this attribute, `getattr(cn, "label", ...)` returns the `type("Node", ...)` default or raises. In the eval, `label` is set as a class attribute by `type("Node", (), {"node_id": ..., "label": label})`.

**Status:** NOT TRIGGERED (node_type check gates before label is accessed). Latent.

**Classification:** EVALUATION HARNESS BUG — **Severity: MEDIUM**

---

## 4. Evidence Pipeline Analysis (Audit C)

| Stage | Input | Expected Output | Actual Output | Collapse Point |
|-------|-------|-----------------|---------------|----------------|
| Themes | 8 entity nodes, 6 edges | >= 2 clusters | **0** | ThemeDetector: node_type mismatch |
| Bundles | 0 themes | ≥ 2 bundles | **0** | EvidenceCollector: `if not themes: return []` |
| Evidence | 0 bundles | ≥ 6 items | **0** | (never reached) |
| Findings | 0 evidence | ≥ 5 findings | **0** | (never reached) |

**First collapse:** Theme Detector (stage 1). All downstream zeros are a cascade from B1.

### Finding C1: Evidence collection lambda bug (latent) — EVALUATION HARNESS BUG

Even if themes were detected, `_make_corpus` defines `get_documents` via `lambda: docs`. Python treats the lambda as a descriptor — when called as `corpus.get_documents()`, it passes `self` as the first argument, causing:

```
TypeError: <lambda>() takes 0 positional arguments but 1 was given
```

The collector's `_get_documents()` catches the exception and returns `[]`. Verified: `_get_documents()` returns 0 docs even when corpus has documents.

**Classification:** EVALUATION HARNESS BUG — **Severity: CRITICAL** (would block pipeline even after B1 fix)

---

## 5. Traceability Analysis (Audit E)

### Finding E1: All 4 findings fail traceability — EVALUATION HARNESS BUG

**Violations:**
```
Finding tf1 references unknown document doc_001
Finding tf2 references unknown document doc_001
Finding tf3 references unknown document doc_001
Finding tf5 references unknown document doc_001
```

**Root cause:** same lambda self-binding as C1. `_make_corpus([_make_doc("doc_001")])` creates a corpus whose `get_documents()` raises `TypeError`. `_build_doc_lookup` catches it and returns `{}` (empty lookup). Every `source_document_ids = ["doc_001"]` triggers "unknown document."

**Verification:**
```python
# traceability.py:18-23
def _get_documents(corpus):
    if hasattr(corpus, "get_documents"):
        try:
            return corpus.get_documents()  # ← TypeError: caught
        except Exception:
            return []  # ← empty result
    ...
```

Each of the 4 non-gap findings (tf1, tf2, tf3, tf5) references `doc_001` which is missing from the empty lookup. tf4 (gap) is correctly skipped by the gap exemption.

**Classification:** EVALUATION HARNESS BUG — **Severity: CRITICAL** (false negative on acceptance gate)

---

## 6. Failure Isolation Analysis (Audit F)

### Finding F1: Crash on None review_id — IMPLEMENTATION BUG

**Metrics:** `failures_injected=5, crashes=1, warnings_generated=0`

**Crashing test:** Test 6 (None request attributes)
```python
req6 = ReviewRequest.model_construct(review_id=None, review_type=None, title=None, ...)
r6 = o6.generate(req6)  # ← crashes
```

**Stack trace:**
```
pydantic.ValidationError: 1 validation error for ReviewResult
review_id
  Input should be a valid string [type=string_type, input_value=None, input_type=NoneType]
```

**Code path:**
```
orchestrator.py:272  →  ReviewResult(review_id=review_id, ...)
```

`getattr(request, "review_id", "")` returns `None` (attribute exists with value `None`, so default `""` is not used). Neither `_build_stub_review` nor the final `ReviewResult()` construction sanitizes this value.

`_build_stub_review` is wrapped in try/except (line 212, caught), but the final assembly is NOT (line 272, unguarded).

**This violates the architecture constraint "orchestrator never raises."**

**How the counting works:**
- 6 injection tests attempted
- 5 completed without crash → `failures_injected = 5`
- 1 crashed → `crashes = 1`
- No surviving test generated warnings (empty pipeline = silent)
- **Stability rate:** 4/5 = 80%

**Classification:** IMPLEMENTATION BUG — **Severity: CRITICAL**

### Non-crashing tests produce 0 warnings

The 5 surviving tests (broken graph, broken corpus, both broken, null everything, empty corpus/graph) all produce 0 warnings because the theme detector returns 0 themes (no `entity_cluster` nodes) and the pipeline continues silently with empty data. The warnings pipeline would only produce output if themes were detected but something failed mid-stage.

---

## 7. Metrics Validation (Audit G)

| Source | Themes | Evidence | Findings | Sections | Traceability | Crashes |
|--------|--------|----------|----------|----------|--------------|---------|
| Console | 0 | 0 | 0 | 51 | 0%/4 | 1 |
| `module6_evaluation.md` | 0 | 0 | 0 | 51 | 0%/4 | 1 |
| `module6_metrics.json` | 0 | 0 | 0 | 51 | 0%/4 | 1 |

**Finding G1: No discrepancies between sources** — ALL metrics are internally consistent.

**Finding G2: Metrics label "Injected: 5" is misleading**

The eval tracks "successful injections" (tests that ran without crashing), not "injection attempts." 6 tests are attempted; 5 complete without crash. The label should be "attempted: 6, succeeded: 5, crashed: 1."

**Classification:** EVALUATION HARNESS BUG (cosmetic) — **Severity: LOW**

---

## 8. Findings Table

| ID | Finding | Classification | Severity | Evidence |
|----|---------|----------------|----------|----------|
| B1 | `_make_entity_node` uses `node_type="entity"`; ThemeDetector expects `"entity_cluster"` | EVALUATION HARNESS BUG | CRITICAL | Confirmed: changing `"entity"` → `"entity_cluster"` produces 4 themes |
| B2 | Mock entity nodes lack direct `label` attribute (latent) | EVALUATION HARNESS BUG | MEDIUM | Unit tests use `CorpusGraphNode` with explicit `.label` |
| C1 | `_make_corpus` lambda `lambda: docs` raises TypeError on call due to Python self-binding | EVALUATION HARNESS BUG | CRITICAL | `_get_documents()` catches exception, returns `[]` |
| E1 | Same lambda bug causes all 4 traceability checks to fail | EVALUATION HARNESS BUG | CRITICAL | 4 warnings all "references unknown document" |
| F1 | `review_id=None` crashes orchestrator at `ReviewResult()` construction | IMPLEMENTATION BUG | CRITICAL | Pydantic ValidationError, no try/except wrapping final assembly |
| G2 | "Injected: 5" mislabels "succeeded without crash" as "injected" | EVALUATION HARNESS BUG | LOW | 6 tests attempted, 5 survived, 1 crashed |

---

## 9. Recommended Fixes

### Fixes required before tagging (in priority order):

1. **[IMPLEMENTATION BUG - F1]** Guard `review_id` in `orchestrator.py`
   - File: `src/researchmind/synthesis/orchestrator.py`
   - Location: after line 87 (`review_id = getattr(request, "review_id", "")`)
   - Fix:
     ```python
     if not isinstance(review_id, str):
         review_id = ""
     ```
   - Rationale: mirrors existing `review_type` and `title` sanitization patterns

2. **[EVALUATION HARNESS]** Fix `_make_entity_node` node_type
   - File: `audit/run_m6_eval.py`
   - Location: line 47-50
   - Fix: change `"node_type": "entity"` to `"node_type": "entity_cluster"` and add `"label": label` direct attribute
   - Also add `"label": label` to the `type("Node", ...)` dict

3. **[EVALUATION HARNESS]** Fix `_make_corpus` and `_make_doc` lambda self-binding
   - File: `audit/run_m6_eval.py`
   - Location: lines 80-83 and 67-73
   - Fix: change `lambda: docs` to `lambda self: docs` and `lambda: claims` to `lambda self: claims`

4. **[EVALUATION HARNESS - G2]** Rename failure isolation counter
   - Change `failures_injected` tracking to count attempts, not just survivors
   - Or re-label the metric to clarify semantics

### Optional improvements:

5. **[EVALUATION HARNESS]** Add a `review_id` guard similar to the orchestrator fix, so `model_construct` edge cases don't produce misleading crash counts
6. **[IMPLEMENTATION — defensive]** Wrap final `ReviewResult()` construction in try/except in orchestrator for belt-and-suspenders resilience

---

## 10. Release Verdict

> **Can Module 6 legitimately be tagged `git tag module6-complete`?**

### NO.

**Justification:**

The answer must be NO because **1 genuine implementation bug** (F1) causes the orchestrator to violate its core architectural contract: `"Never raises — failures are captured in ReviewResult.warnings / errors"`. When `review_id=None` reaches `ReviewResult()`, a `ValidationError` propagates uncaught.

The 3 evaluation harness bugs (B1, C1, E1) are not implementation defects — they are test infrastructure issues. However, F1 is real, reproducible, and architectural.

**Conditions for YES:**
- Fix F1: add `review_id` type guard in orchestrator → all 6 injection tests survive with 0 crashes → acceptance gate pass rate goes from 4/6 to 5/6
- Fix B1, C1, E1 in eval harness → themes > 0, evidence flows, traceability rate rises to expected → traceability gate passes → 6/6 gates pass

### Verdict: NOT READY — one implementation bug (F1) blocks release.
