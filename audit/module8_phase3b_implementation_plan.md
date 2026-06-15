# Module 8 Phase 3B — Implementation Plan

## Objective
Implement the FastAPI endpoints for Dashboard, Corpus Manager, Graph Explorer, and Monitoring, effectively replacing the `501 Not Implemented` stubs. Wire the frontend services (`dashboard.ts`, `corpus.ts`, `mock-graph.ts`, `mock-monitoring.ts`) to these endpoints, entirely eliminating `mock-data.ts`.

## Step 1: Pydantic Schema Definition
1. Audit the frontend types in `frontend/types/` (`document.ts`, `graph.ts`, `monitoring.ts`).
2. Define exact equivalent Pydantic models in `backend/api/models/` for Requests and Responses.
3. Ensure no schema validation errors occur by matching field names (using aliases if converting between `snake_case` and `camelCase`).

## Step 2: Backend Route Implementation
1. **`dashboard.py`**: Implement `/api/v1/dashboard/summary`, `/api/v1/dashboard/recent`, and `/api/v1/dashboard/status` using core aggregate data.
2. **`documents.py`**: Implement `/api/v1/documents` (list) and `/api/v1/documents/{id}` mapping to the M1 Extraction and Storage layers.
3. **`graph.py`**: Implement `/api/v1/graph/data` mapping to the M3 NetworkX architecture.
4. **`monitoring.py`**: Implement `/api/v1/monitoring/metrics` mapping to the M4 Telemetry/Monitoring aggregates.
5. Retain deterministic outputs in all route handlers.

## Step 3: Frontend Service Wiring
1. Refactor `frontend/services/dashboard.ts` to use `apiClient.post/get`.
2. Refactor `frontend/services/corpus.ts` to use `apiClient.post/get`.
3. Refactor `frontend/services/mock-graph.ts` (rename to `graph.ts`) to use `apiClient.post/get`.
4. Refactor `frontend/services/mock-monitoring.ts` (rename to `monitoring.ts`) to use `apiClient.post/get`.
5. Implement error bounds/timeout protections inherited from Phase 3A.

## Step 4: Cleanup & Verification
1. Safely delete `frontend/services/mock-data.ts`.
2. Clean up any stale imports.
3. Run `npm run build`, `npm run test`, and `python -m pytest` to verify contract integrity.
4. Confirm no `Date.now()`, `Math.random()`, or UUID invocations violate the deterministic requirements.

## Go/No-Go Decision
All precursor conditions have been met. The architecture is sound, risks are mitigated, and Phase 3A stabilization provides a robust API client foundation.

**Recommendation:** GO FOR PHASE 3B IMPLEMENTATION.
