# Module 8 Phase 3B — Frontend Integration Audit

## Screen to Backend Mapping

| Frontend Screen | Service File | Target Route | Current Status |
|---|---|---|---|
| **Query Interface** | `frontend/services/query.ts` | `/api/v1/query/answer` | 🟢 Live (FastAPI) |
| **Review Generator** | `frontend/services/review.ts` | `/api/v1/reviews/generate` | 🟢 Live (FastAPI) |
| **Dashboard** | `frontend/services/dashboard.ts` | `/api/v1/dashboard/*` | 🔴 Mocked (`setTimeout` / `MOCK_DATA`) |
| **Corpus Manager** | `frontend/services/corpus.ts` | `/api/v1/documents/*` | 🔴 Mocked (`setTimeout` / `MOCK_DATA`) |
| **Graph Explorer** | `frontend/services/mock-graph.ts` | `/api/v1/graph/*` | 🔴 Mocked (Offline simulation) |
| **Monitoring** | `frontend/services/mock-monitoring.ts` | `/api/v1/monitoring/*` | 🔴 Mocked (Offline simulation) |

## Remaining Mock Services
- `frontend/services/mock-data.ts`
- `frontend/services/mock-graph.ts`
- `frontend/services/mock-monitoring.ts`

Note: `corpus.ts` and `dashboard.ts` both import and resolve static arrays from `mock-data.ts` using simulated network delay wrappers (`setTimeout`).

## Contract Mismatches & Blockers
The primary blocker preventing the removal of these mock services is the `501 Not Implemented` state of the FastAPI endpoints in `documents.py`, `dashboard.py`, `graph.py`, and `monitoring.py`. 

Additionally, because the backend endpoints are entirely stubbed, there is a **frontend/backend contract mismatch**. The frontend types (e.g. `RUODocument`, `CorpusSummary`) do not have corresponding Pydantic schema contracts explicitly defined and bound to route handlers in the API layer.
