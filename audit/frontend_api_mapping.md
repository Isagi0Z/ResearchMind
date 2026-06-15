# Frontend to API Mapping

## 1. Dashboard
- **Frontend Service:** `services/dashboard.ts` (or similar mock)
- **Backend Endpoint:** `GET /api/v1/dashboard`
- **Request Schema:** None (GET request)
- **Response Schema:** TBD (Currently 501)
- **Compatibility Status:** **Missing** (Backend returns 501 Not Implemented)

## 2. Corpus Manager
- **Frontend Service:** `services/corpus.ts`
- **Backend Endpoints:** 
  - `GET /api/v1/documents` (Search/Pagination)
  - `GET /api/v1/document/{id}` (Metadata retrieval)
- **Request Schema:** Query parameters (TBD)
- **Response Schema:** TBD
- **Compatibility Status:** **Missing** (Backend returns 501 Not Implemented)

## 3. Graph Explorer
- **Frontend Service:** `services/mock-graph.ts`
- **Backend Endpoints:** 
  - `GET /api/v1/graph` (Summary, Edges)
  - `GET /api/v1/graph/node/{id}` (Nodes)
- **Request Schema:** Query parameters (TBD)
- **Response Schema:** TBD
- **Compatibility Status:** **Missing** (Backend returns 501 Not Implemented)

## 4. Query Interface
- **Frontend Service:** `services/mock-query.ts`
- **Backend Endpoints:**
  - `POST /api/v1/query/parse`
    - Request: `ParseRequest` (`{ raw_query: str }`)
    - Response: `{ "parsed_query": ParsedQuery }`
  - `POST /api/v1/query/plan`
    - Request: `ParsedQuery`
    - Response: `{ "execution_plan": ExecutionPlan }`
  - `POST /api/v1/query/route`
    - Request: `ExecutionPlan`
    - Response: `{ "step_routes": list[StepRoute] }`
  - `POST /api/v1/query/answer`
    - Request: `AnswerRequest` (`{ query_id: str, raw_query: str }`)
    - Response: `{ parsed_query, execution_plan, step_route, evidence, answer }`
- **Compatibility Status:** **Minor Changes Required** (Frontend mock generates `ResearchAnswer` deterministically. The frontend API client will need to wrap the `raw_query` string in the `ParseRequest`/`AnswerRequest` schema envelopes expected by FastAPI.)

## 5. Review Generator
- **Frontend Service:** `services/mock-review.ts`
- **Backend Endpoints:**
  - `POST /api/v1/reviews/generate`
    - Request: `ReviewRequest`
    - Response: `{ "review_result": ReviewResult }`
  - `POST /api/v1/reviews/validate`
    - Request: `ReviewResult`
    - Response: `{ "traceability_report": { "is_valid": bool, "errors": list } }`
- **Compatibility Status:** **Compatible** (Payload shapes map tightly to the Python Pydantic models. Frontend types in `types/review.ts` generally match `ReviewRequest` and `ReviewResult` fields.)

## 6. Monitoring
- **Frontend Service:** `services/mock-monitoring.ts`
- **Backend Endpoint:** `GET /api/v1/monitoring`
- **Request Schema:** None
- **Response Schema:** TBD
- **Compatibility Status:** **Missing** (Backend returns 501 Not Implemented)
