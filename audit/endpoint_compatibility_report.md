# Endpoint Compatibility Report

## Overview
This report details the schema and behavioral compatibility between the frontend UI layers and the backend FastAPI endpoints for the M5 (Query) and M6 (Review/Synthesis) engines. M1-M4 routes are deliberately excluded from detailed mapping as they currently yield `501 Not Implemented`.

## 1. Query Engine Compatibility
**Frontend Data Source:** `services/mock-query.ts`
**Backend Routes:** `backend/api/routes/query.py`

### Mismatches & Gaps:
- **Parse Schema Envelope:** The frontend currently expects to pass a raw string to the parser mock. The FastAPI `/api/v1/query/parse` endpoint expects a JSON payload matching the `ParseRequest` Pydantic model:
  ```json
  { "raw_query": "string" }
  ```
  *Action:* The frontend API client must wrap strings in this object.
- **Answer Schema Envelope:** The `/api/v1/query/answer` endpoint expects an `AnswerRequest` (`query_id`, `raw_query`). The frontend currently generates the mock response using just the string.
  *Action:* Frontend must generate a stable `query_id` (or receive it from the parse step) and pass it along with the raw text.
- **Response Shape Matching:** The backend `/answer` endpoint returns a composite object containing `parsed_query`, `execution_plan`, `step_route`, `evidence`, and `answer` keys. The frontend `mock-query.ts` returns a merged `ResearchAnswer` object.
  *Action:* The frontend API client will need a small adapter layer to extract the Pydantic `answer` sub-object and map the `evidence` and `traces` arrays to match the `ResearchAnswer` TS interface.

## 2. Review Engine Compatibility
**Frontend Data Source:** `services/mock-review.ts`
**Backend Routes:** `backend/api/routes/review.py`

### Mismatches & Gaps:
- **Schema Alignment:** The backend expects a `ReviewRequest` which strictly enforces non-empty `review_id` and `topic`, and validates `ReviewType` enumerations. The frontend currently mocks these structures successfully.
- **Validation Route Structure:** The `/api/v1/reviews/validate` endpoint receives a full `ReviewResult` object and returns a nested `traceability_report`. The frontend must match the `ReviewResult` schema exactly as returned by `/generate`.
- **Determinism Safety:** The backend's `ReviewResult` relies on deterministic operations (no UUIDs/timestamps) ensuring safety across requests.

## 3. General Architecture Deficits (M1-M4)
- **Missing Endpoints:** `/dashboard`, `/documents`, `/graph`, and `/monitoring` are entirely stubbed (`raise HTTPException(501)`). Attempting to wire these directly in Phase 3 without implementing the backend logic will result in immediate UI failures. 
- **Action Required:** Phase 3 must strictly scope frontend wiring to the Query and Review domains, deferring Dashboard/Corpus/Graph/Monitoring integration until their respective backend adapters are built.
