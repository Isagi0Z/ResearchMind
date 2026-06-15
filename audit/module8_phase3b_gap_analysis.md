# Module 8 Phase 3B — Gap Analysis

## Current State vs Target State

| Capability | Current State | Target State | Gap |
|---|---|---|---|
| **Query Engine (M5)** | Live on API, Integrated | Live on API, Integrated | None |
| **Synthesis Engine (M6)** | Live on API, Integrated | Live on API, Integrated | None |
| **Corpus Management (M1)** | Mocked Frontend, 501 Backend | Live on API, Integrated | Missing Pydantic Schemas, Missing FastAPI Route Logic |
| **Entity Resolution (M2)** | Implicitly Mocked | Live on API, Integrated | Missing API translation layer for entity operations |
| **Corpus Graph (M3)** | Mocked Frontend (`mock-graph.ts`), 501 Backend | Live on API, Integrated | Missing `graph.py` implementation mapping to NetworkX/Graph core |
| **Monitoring (M4)** | Mocked Frontend (`mock-monitoring.ts`), 501 Backend | Live on API, Integrated | Missing `monitoring.py` implementation mapping to core metrics |

## Structural Gaps
1. **Schema Definitions:** The FastAPI backend does not yet define the specific Pydantic `Request` and `Response` models required to bridge the frontend's TypeScript interfaces (e.g. `CorpusSummary`, `SystemStatus`) to the backend Python domain models.
2. **Service Architecture:** The frontend currently relies on file-level mock services (`mock-data.ts`). These need to be safely migrated to real asynchronous REST calls via `api-client.ts`.
3. **Paging & Filtering:** The mocked `corpus.ts` supports pseudo-pagination and filtering on `MOCK_DOCUMENTS`. The backend FastAPI layer will need to correctly pass and handle pagination tokens/offsets to the M1 underlying core without degrading determinism.
