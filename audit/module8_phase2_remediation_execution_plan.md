# Module 8 Phase 2 Determinism Remediation Execution Plan

This execution plan details the exact remediation steps required to eliminate the two determinism violations identified in the pre-implementation audit for Phase 2.

## 1. QueryEngine Determinism Remediation

### 1.1 Exact Code Location
- **File**: `src/researchmind/query/engine.py`
- **Class**: `QueryEngine`
- **Method**: `answer()`
- **Line number(s)**: 134

### 1.2 Proposed Code Changes
**Before:**
```python
        query = ResearchQuery.model_construct(
            query_id=query_id,
            raw_query=raw,
            created_at=datetime.now(timezone.utc),
        )
```

**After:**
```python
# Defined globally at the top of engine.py
_REFERENCE_TIMESTAMP = datetime(2025, 1, 1, tzinfo=timezone.utc)

...

        query = ResearchQuery.model_construct(
            query_id=query_id,
            raw_query=raw,
            created_at=_REFERENCE_TIMESTAMP,
        )
```

### 1.3 Deterministic Reference Strategy
We will define a private module-level constant `_REFERENCE_TIMESTAMP = datetime(2025, 1, 1, tzinfo=timezone.utc)`. This effectively mocks the clock, ensuring that identical textual inputs map perfectly to identical JSON API outputs forever.

### 1.4 Impact Analysis
- **Affected Models**: `ResearchQuery` (its `created_at` field) and `ResearchAnswer` (its `generated_at` field).
- **Affected Outputs**: The JSON output of any M5 query will now use `"2025-01-01T00:00:00Z"` instead of the wall-clock time.
- **Affected Evaluations**: None structurally, as timestamps are ignored by relevance/confidence metrics.
- **Affected Tests**: Snapshot tests requiring byte-for-byte reproducibility will now pass deterministically.

### 1.5 Final Recommendation
**SAFE TO IMPLEMENT**

---

## 2. QueryParser Determinism Remediation

### 2.1 Exact Code Location
- **File**: `src/researchmind/query/parser.py`
- **Class**: N/A (Module level global `_CONSTRAINT_PATTERNS`)
- **Line number(s)**: 132

### 2.2 Proposed Code Changes
**Before:**
```python
    (re.compile(r"\brecent\b", re.IGNORECASE), "year", "gte", lambda _: datetime.now().year - 5),
```

**After:**
```python
# Defined globally before _CONSTRAINT_PATTERNS
_REFERENCE_YEAR = 2025

...

    (re.compile(r"\brecent\b", re.IGNORECASE), "year", "gte", lambda _: _REFERENCE_YEAR - 5),
```

### 2.3 Deterministic Reference Strategy
We define `_REFERENCE_YEAR = 2025` as a private, documented constant near the top of the file. The concept of "recent" is hard-locked to `>= 2020` mathematically, permanently eliminating runtime context from query semantics.

### 2.4 Impact Analysis
- **Affected Models**: `QueryConstraint` (`value` property).
- **Affected Outputs**: `ParsedQuery.constraints` will now always resolve "recent" to `2020` natively.
- **Affected Evaluations**: Any M5 evaluation parsing "recent" will now fetch a strictly deterministic subset of papers (e.g. published after 2020).
- **Affected Tests**: Tests validating the parser rules for "recent" will stabilize instead of breaking on January 1, 2026.

### 2.5 Final Recommendation
**SAFE TO IMPLEMENT**

---

## 3. Global Regression Analysis
Because we are modifying foundational M5 (Query System) components, the effects could ripple upstream to M6 (Synthesis Engine).

- **M5 Tests Affected**: `test_query_parser.py` (specifically tests covering "recent" constraints), `test_query_engine.py` (any tests asserting output objects or running full pipeline flows).
- **M6 Tests Affected**: Negligible risk. M6 orchestration generally takes `ReviewRequest` which relies on `ReviewOrchestrator` internally, disconnected from `QueryEngine`.
- **Evaluation Scripts Affected**: `scripts/evaluate_m5.py` and `scripts/evaluate_m6.py` must run to prove outputs are completely identical / un-broken by this change.

## 4. Validation Plan
Once the remediation is applied, the exact sequence of commands to execute is:

```bash
# 1. Run full M5/M6 test suites
pytest tests/test_query_*
pytest tests/test_synthesis_*

# 2. Re-run M5 Evaluations to verify determinism
python scripts/evaluate_m5.py
# Verify diff on eval_output/module5_evaluation.md
# Verify diff on eval_output/module5_metrics.json

# 3. Re-run M6 Evaluations to verify stability
python scripts/evaluate_m6.py
# Verify diff on eval_output/module6_evaluation.md
# Verify diff on eval_output/module6_metrics.json
```
