# Frontend ↔ FastAPI Integration Audit

## 1. Executive Summary
This audit evaluates the current state of the ResearchMind frontend (Module 7) and backend FastAPI layer (Module 8) to prepare for Phase 3 integration. The goal is to safely replace the frontend's deterministic mock services with real network calls to the FastAPI backend, which is wired to the M5 (Query) and M6 (Synthesis) engines.

## 2. Current Architecture State
**Frontend (Next.js App Router):**
- UI components fetch data through local service files (`services/mock-query.ts`, `services/mock-review.ts`, etc.).
- The services use deterministic algorithms (e.g., LCG and CRC32) to generate fake responses on the fly.
- TanStack Query is used (or will be) for state management and caching.

**Backend (FastAPI):**
- Base API routes are defined under `/api/v1/`.
- M5 Query and M6 Synthesis engines are fully wired to `/query/*` and `/review/*` endpoints.
- M1-M4 (Dashboard, Corpus, Graph, Monitoring) endpoints exist as placeholders returning `501 Not Implemented`.

## 3. Target Architecture
**Frontend → FastAPI → Core Engines**
- The `services/*.ts` files will be rewritten to perform `fetch()` requests to `http://localhost:8000/api/v1/...`.
- Mocks will be fully removed.
- State management will handle real asynchronous network latency, loading states, and error boundaries.

## 4. Gap Analysis Overview
| Area | Frontend Mock | Backend API | Status |
|---|---|---|---|
| Query | `mock-query.ts` | `/query/parse`, `/plan`, `/route`, `/answer` | Endpoints exist, schema mapping required |
| Review | `mock-review.ts` | `/reviews/generate`, `/validate` | Endpoints exist, schema mapping required |
| Dashboard | `dashboard.ts` | `/dashboard` | `501 Not Implemented` |
| Corpus | `corpus.ts` | `/documents` | `501 Not Implemented` |
| Graph | `mock-graph.ts` | `/graph` | `501 Not Implemented` |
| Monitoring | `mock-monitoring.ts` | `/monitoring` | `501 Not Implemented` |

## 5. Next Steps
The integration must be phased. Phase 3a should focus strictly on Query and Review endpoints (which are fully implemented in the backend), while Phase 3b will require implementing the M1-M4 backend adapters before frontend wiring can occur.
