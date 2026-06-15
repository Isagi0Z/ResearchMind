# Module 8 Phase 3B — Risk Assessment

## Implementation Risks

### 1. Determinism Degradation (High Risk)
The core ResearchMind architecture strictly enforces deterministic behavior. When removing the static `MOCK_DATA` arrays and bridging the frontend to real M1/M2/M3 operations via FastAPI, there is a severe risk of introducing non-deterministic timestamps (e.g., `updatedAt`, `createdAt`) or UUIDs at the API integration layer.
- **Mitigation:** Rely exclusively on `crc32` hashing in the frontend, and verify that FastAPI Pydantic models leverage the established `datetime` mocking scaffolding and fixed UUID injection from earlier modules.

### 2. Contract Breakage (Medium Risk)
The frontend `mock-data.ts` shapes are intimately bound to the UI components. The backend core logic might yield different shapes (e.g. `source_doc_id` vs `sourceDocId`).
- **Mitigation:** The FastAPI models MUST act as strict adapters, adhering to the frontend's expected REST JSON shape, or the frontend mapping logic must translate the shapes reliably without breaking the React components.

### 3. Asynchronous Waterfall Latency (Low Risk)
The Dashboard aggregates `getCorpusSummary`, `getRecentDocuments`, and `getSystemStatus`. When transitioned from mocked `setTimeout` to real API calls, sequential fetching could severely degrade performance.
- **Mitigation:** Ensure the frontend uses `Promise.all` or TanStack Query parallel fetching.

### 4. Build Environment Contamination (Medium Risk)
Work on the backend API layer often generates `.pytest_cache`, `__pycache__`, or temp `.db` artifacts. The rigid containment rules (`D:\RM\.tmp`) must be preserved.
- **Mitigation:** Strict enforcement of `pytest` environment variables and `.gitignore` compliance.
