# Integration Risk Assessment: Phase 3 Frontend ↔ FastAPI

## Risk Factors

### 1. Schema Mismatches (High Risk)
- **Detail:** FastAPI Pydantic models are strictly validated. If the frontend sends additional fields, omits required ones, or uses wrong data types, a `422 Unprocessable Entity` is returned.
- **Impact:** Frontend integration fails completely. 
- **Mitigation:** Ensure the frontend API client strictly adheres to `ParseRequest`, `AnswerRequest`, `ReviewRequest`, and `ReviewResult` schemas. Typescript interfaces in `types/query.ts` and `types/review.ts` must be aligned with Pydantic exports.

### 2. Missing Endpoints (Critical Risk)
- **Detail:** Dashboard, Corpus, Graph, and Monitoring services point to backend stubs that currently return a hardcoded `501 Not Implemented`.
- **Impact:** UI components reliant on these endpoints will crash or infinitely load if mock services are replaced blindly.
- **Mitigation:** Only replace mocks for the `query` and `review` domains in this immediate phase. Maintain the deterministic mock services for M1-M4 until the backend counterparts are fully implemented.

### 3. TanStack Query Migration Risks (Medium Risk)
- **Detail:** The frontend is configured to use React Query. Shifting from instant, deterministic mock resolution to real network calls introduces latency, potential timeouts, and HTTP errors.
- **Impact:** Poor UX, unhandled loading states, or infinite retries.
- **Mitigation:** Implement proper `isLoading`, `isError`, and `errorBoundary` states in the Next.js components. Ensure API fetches have reasonable timeouts.

### 4. Determinism & Testability Risks (Low Risk)
- **Detail:** The backend has been remediated to ensure timestamps and random behaviors are mocked out via reference constants (M5/M6 determinism rules). However, network latency inherently introduces non-deterministic timing.
- **Impact:** E2E tests relying on exact millisecond execution times may flap.
- **Mitigation:** Frontend UI tests should mock the network layer, or execution time checks should use relaxed thresholds.

### 5. Frontend State Migration Risks (Medium Risk)
- **Detail:** Existing mocks synchronously return complete objects. Real API calls will require async handling and potentially breaking up single monolithic state updates into sequential ones (e.g., `parse` -> `plan` -> `route` -> `answer`).
- **Impact:** UI jitter or intermediate broken states if intermediate step data isn't handled gracefully.
- **Mitigation:** UI should render skeleton states or loading spinners while stepping through the `query` pipeline, mimicking the step-by-step nature of the backend.
