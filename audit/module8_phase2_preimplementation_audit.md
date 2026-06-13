# Module 8 Phase 2 Pre-Implementation Audit

This document audits the codebase before initiating Phase 2 FastAPI endpoint implementation to ensure strict adherence to deterministic design principles and structural constraints.

## 1. Constructor Signatures
The target classes expose the following signatures:
- **`QueryParser(corpus: Any | None = None)`**
- **`QueryPlanner()`**
- **`StepDispatcher()`**
- **`QueryEngine(parser=None, planner=None, dispatcher=None, aggregator=None, synthesizer=None, multi_hop=None, consensus=None, contradiction=None, gap=None)`**
- **`ReviewOrchestrator(corpus_manager: Any, graph: Any, consensus_engine: Any = None, contradiction_engine: Any = None, gap_engine: Any = None, multi_hop_reasoner: Any = None, document_store: Any = None)`**
- **`TraceabilityVerifier()`**

## 2. Dependency Analysis
- **Required Dependencies:** `ReviewOrchestrator` requires `corpus_manager` and `graph`. `TraceabilityVerifier` requires `corpus` to be passed into its `verify_review` method.
- **Optional Dependencies:** All M4 reasoning engines (`multi_hop`, `consensus`, `contradiction`, `gap`) are entirely optional in both `QueryEngine` and `ReviewOrchestrator`.
- **Is `None` Safe?:** Yes. Missing M4 engines gracefully return fallback responses or append failures to the `failed_steps` lists.
- **Are empty Corpus objects sufficient?:** Yes. A review of `ThemeDetector`, `EvidenceCollector`, and `TraceabilityVerifier` indicates that passing an empty list `[]` or a dummy `RUOCorpus()` will gracefully yield 0 themes/findings, producing an empty (but structurally valid) `ReviewResult` with warnings.

## 3. Execution-Path Audit
- **`QueryEngine.answer()`**: Dispatches to `parser.parse()`, `planner.create_plan()`, `dispatcher.route_plan()`, and the M4 engine registry. Unconfigured engines result in failed steps rather than runtime exceptions.
- **`ReviewOrchestrator.generate()`**: Progresses sequentially through `ThemeDetector`, `EvidenceCollector`, `FindingGenerator`, `SectionBuilder`, `TraceabilityVerifier`, and `ConfidenceComputer`. It intercepts all inner exceptions and populates the `warnings` array in `ReviewResult`.
- **`TraceabilityVerifier.verify_review()`**: Dereferences `corpus.get_documents()`. If none exist, it logs traceability warnings without crashing.

## 4. Determinism Audit
A strict regex search for `datetime.now`, `time.time`, `uuid`, etc., revealed two critical determinism violations within the newly merged M5 source code:

1. `src/researchmind/query/engine.py:134`
   - Code: `created_at=datetime.now(timezone.utc),`
   - Classification: **API BLOCKER / REQUIRES REMEDIATION**
2. `src/researchmind/query/parser.py:132`
   - Code: `lambda _: datetime.now().year - 5`
   - Classification: **API BLOCKER / REQUIRES REMEDIATION**

The M6 (Synthesis) module is completely clean of any non-deterministic timestamps or UUIDs.

## 5. API Contract Review
**Recommendation:** Expose the internal Pydantic models directly as API response schemas. 
The classes defined in `query.models` and `synthesis.models` (e.g., `ParsedQuery`, `ExecutionPlan`, `ReviewResult`) are pure, highly structured data transfer objects. They are entirely disconnected from any ORM or persistence layer. Returning them directly through FastAPI achieves a 1:1 parity with the core domain and eliminates redundant mapping layers. Errors should still adhere to the standard `{"error": {"code": "...", "message": "...", "request_id": "..."}}` envelope via global exception handlers.

## 6. Endpoint Readiness Table

| Planned Endpoint | Target Class | Readiness Status |
| :--- | :--- | :--- |
| `/api/v1/query/parse` | `QueryParser` | **REQUIRES REMEDIATION** |
| `/api/v1/query/plan` | `QueryPlanner` | **READY** |
| `/api/v1/query/route` | `StepDispatcher` | **READY** |
| `/api/v1/query/answer` | `QueryEngine` | **REQUIRES REMEDIATION** |
| `/api/v1/reviews/generate` | `ReviewOrchestrator` | **READY WITH DEPENDENCY INJECTION** |
| `/api/v1/reviews/validate` | `TraceabilityVerifier`| **READY WITH DEPENDENCY INJECTION** |

---

## Final Recommendation: NO-GO
**NO-GO for implementation.** Phase 2 API integration is strictly blocked until the two `datetime.now()` occurrences inside `query/engine.py` and `query/parser.py` are remediated to use stable, deterministic defaults (such as a constant epoch or CRC32 derivations).
