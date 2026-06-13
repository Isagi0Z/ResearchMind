# M8 Production API Layer Architecture

## 1. Goal
Design a thin, high-performance, deterministic FastAPI web layer that exposes M1-M6 Python modules to the M7 Next.js frontend without duplicating business logic.

## 2. Stack
- **Framework:** FastAPI (Python 3.9+)
- **Validation:** Pydantic v2
- **Server:** Uvicorn
- **Task Queue:** Celery + Redis (for long-running M5/M6 tasks)
- **Auth:** OAuth2 with JWT (JSON Web Tokens)

## 3. Core Principles
- **Thin Wrappers:** FastAPI routes should ONLY handle HTTP validation, auth, and routing. Business logic remains strictly in M1-M6.
- **Determinism:** API routes must not inject random seeds. All timestamps or IDs must originate from the database or deterministic hashes.
- **Asynchronous Execution:** Heavy queries and syntheses MUST be offloaded to worker queues, returning a `job_id` for polling/SSE.

## 4. API Endpoints

### A. Authentication
- `POST /api/auth/login` -> Returns JWT.
- `POST /api/auth/register` -> Creates user.
- `POST /api/auth/refresh` -> Refreshes JWT.
- `POST /api/auth/logout` -> Invalidates session.

### B. Corpus & Documents (M1, M2)
- `GET /api/documents` -> Paginated list of ingested corpus files.
- `GET /api/document/{id}` -> Fetch specific document content and entities.
- `POST /api/documents/upload` -> Queue document for extraction.

### C. Graph Explorer (M3, M4)
- `GET /api/graph/snapshot` -> Returns bounded LCG/subgraph for React Flow (max 5000 nodes).
- `GET /api/graph/node/{id}` -> Returns localized neighborhood for expansion.
- `GET /api/graph/cluster` -> Returns aggregated high-level graph topology.

### D. Query System (M5)
- `POST /api/query` -> Triggers reasoning engine. Returns `job_id`.
- `GET /api/query/{job_id}/status` -> Returns SSE stream of execution stages.
- `GET /api/query/{job_id}/result` -> Returns final `QueryResult` DTO.

### E. Synthesis & Review (M6)
- `POST /api/review` -> Triggers review generation. Returns `job_id`.
- `GET /api/review/{job_id}/status` -> Returns SSE stream of synthesis stages.
- `GET /api/review/{job_id}/result` -> Returns final `ReviewResult` DTO.

### F. System Monitoring (M7-8)
- `GET /api/monitoring/health` -> Live status of M1-M6 processes.
- `GET /api/monitoring/metrics` -> Historical performance charts (cached).
- `GET /api/monitoring/queue` -> Live Celery task queue visibility.

## 5. DTO & Schema Design (Pydantic)
FastAPI Pydantic schemas will be generated to match `frontend/types/*.ts` exactly.
- `ReviewRequestSchema`
- `ReviewResultSchema`
- `EvidenceBundleSchema`
- `NodeWrapperSchema`

## 6. Rate Limiting & Versioning
- **Versioning:** All routes prefixed with `/v1/api/`.
- **Rate Limiting:** IP-based token bucket (e.g., 100 req/min for general API, 5 req/min for heavy M6 synthesis).
