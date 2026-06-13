# Module 8 Phase 2 Determinism Remediation Plan

This plan analyzes the two identified determinism violations within the M5 codebase and recommends safe strategies for remediating them to unblock Phase 2 integration without modifying any code yet.

## Finding A: `QueryEngine.answer()` Timestamp

### 1. Location
**File:** `src/researchmind/query/engine.py`
**Line:** 134

### 2. Why it is non-deterministic
The codebase instantiates a `ResearchQuery` using:
```python
created_at=datetime.now(timezone.utc)
```
This timestamp changes at runtime, producing a distinct output value for every API invocation.

### 3. Execution Impact
- **API Output:** **AFFECTED**. The `created_at` timestamp is persistently attached to the `ResearchQuery` model and subsequently propagated to the `ResearchAnswer.generated_at` property. This means every API response will vary based on execution time.
- **Internal Processing Only:** **FALSE**. It is deeply visible in the final response.
- **Test Reproducibility:** **AFFECTED**. Snapshot tests or exact JSON string comparisons will fail across subsequent test runs.

### 4. Recommended Fix
Replace dynamic instantiation with a static, deterministic epoch or derive a timestamp deterministically from the query hash. 
**Proposed Fix:** Hardcode a standard deterministic epoch:
```python
created_at=datetime(2025, 1, 1, tzinfo=timezone.utc)
```

### 5. Impact Analysis
By freezing this timestamp, the M5 engine will return 100% byte-for-byte identical output for the exact same input string, satisfying our strict pipeline determinism constraints. 

### 6. Regression Risk
**Very Low.** A review of the M5/M6 architectures indicates that `created_at` is purely descriptive metadata. It does not actively drive any routing logic, time-to-live expiration, or graph algorithm branching.

### Final Recommendation
**SAFE TO REMEDIATE**

---

## Finding B: `QueryParser` "Recent" Constraint

### 1. Location
**File:** `src/researchmind/query/parser.py`
**Line:** 132

### 2. Why it is non-deterministic
The constraint parser maps the keyword "recent" using runtime execution:
```python
lambda _: datetime.now().year - 5
```
As the system clock advances, the resolved cutoff year changes (e.g., returning 2021 in 2026, but 2025 in 2030).

### 3. Execution Impact
- **API Output:** **AFFECTED**. This logic directly populates the `value` field of the extracted `QueryConstraint`.
- **Internal Processing Only:** **FALSE**. The `ParsedQuery` is returned publicly and impacts downstream execution.
- **Test Reproducibility:** **AFFECTED**. A test written today expecting ">= 2021" will break next year.
- **Routing / Planning Behavior:** **AFFECTED (Indirectly)**. While it doesn't alter the `PlanStep` engine routing, it radically alters the M4 parameter constraints sent to the search indexes.
- **Should a fixed configuration replace it?:** **YES**.

### 4. Recommended Fix
Replace the dynamic evaluation with a fixed configuration constant or a hardcoded baseline year to ensure "recent" always means the exact same cutoff boundary in this pipeline.
**Proposed Fix:** 
```python
_SYSTEM_BASELINE_YEAR = 2025
...
lambda _: _SYSTEM_BASELINE_YEAR - 5
```

### 5. Impact Analysis
Ensures the parser executes as a pure, referentially transparent function. "Recent" will deterministically map to the same mathematical cutoff regardless of server execution time.

### 6. Regression Risk
**Low.** The only side-effect is that "recent" is now a static concept within the system. Since this application favors strict mathematical determinism over real-world semantic drift, this tradeoff is actively desired.

### Final Recommendation
**SAFE TO REMEDIATE**
