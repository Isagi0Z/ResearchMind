# Final System Evaluation Plan

## 1. Goal
Validate the End-to-End (E2E) integration of the complete ResearchMind platform (M1 -> M8). Ensure data flows flawlessly from raw PDF extraction all the way to the Next.js Review Generator frontend.

## 2. Scope of Evaluation
- **Pipeline:** M1 -> M2 -> M3 -> M4 -> M5 -> M6 -> M8 (FastAPI) -> M7 (Next.js)
- **Infrastructure:** Redis queues, Postgres persistence, Docker network.

## 3. Test Scenarios

### A. Extraction & Resolution (M1, M2)
- **Action:** Upload 50 mixed PDFs (academic papers).
- **Target:** 100% extraction success. Entities must be resolved and deduplicated into deterministic canonical forms.

### B. Graph Generation (M3)
- **Action:** Build global corpus graph.
- **Target:** Graph completes generation in < 5 minutes. No orphaned nodes.

### C. Querying & Reasoning (M4, M5)
- **Action:** Execute 100 simultaneous simulated queries via the API.
- **Target:** 
  - 100% Celery task completion. 
  - Median query latency < 15 seconds.
  - Traceability mapping is preserved down to the specific `EvidenceBundle`.

### D. Synthesis (M6, M7)
- **Action:** Generate 20 full Review Results (mixed types: GENERAL, CONTRADICTION, COMPARATIVE).
- **Target:**
  - SSE streams correctly emit 7 pipeline stages.
  - Frontend renders findings and updates Traceability panel without hydration errors.
  - Export to MD matches JSON exact data structures.

### E. Failure Isolation
- **Action:** Manually kill the M4 Reasoning worker container during an active query.
- **Target:** API gracefully traps the timeout, logs the `critical` error to the M7 Monitoring dashboard, and informs the user rather than crashing the Next.js client.

## 4. Acceptance Gates
- **Gate 1:** Zero data loss between M1 and M3.
- **Gate 2:** Determinism verified (running the same query twice yields identical byte-for-byte JSON responses).
- **Gate 3:** API handles 50 concurrent users without 502 Bad Gateway drops.
- **Gate 4:** UI achieves >95 Lighthouse score in production build.
