# Phase A: Frontend ↔ Backend Integration Audit

## 1. Goal
Audit the current M7 frontend implementation against the M1-M6 Python backend modules to identify the integration gap, missing DTOs, missing endpoints, and architectural mismatches.

## 2. Screen Integration Matrix

| Screen           | Mock Service | Real Backend Exists? | Integration Status |
| ---------------- | ------------ | -------------------- | ------------------ |
| Dashboard        | Yes          | Partial (M1-M3)      | **NOT READY**      |
| Corpus Manager   | Yes          | Yes (M1, M3)         | **NOT READY**      |
| Graph Explorer   | Yes          | Yes (M3, M4)         | **NOT READY**      |
| Query Interface  | Yes          | Yes (M5)             | **NOT READY**      |
| Review Generator | Yes          | Yes (M6)             | **NOT READY**      |
| Monitoring       | Yes          | Partial (Logging)    | **NOT READY**      |

*Note: While the backend modules exist (M1-M6), they are standalone Python modules without a unified API layer. No REST/GraphQL API exists to serve the frontend.*

## 3. Detailed Findings

### A. Missing APIs [CRITICAL]
- The backend currently consists of Python classes and functions.
- There is no web server (e.g., FastAPI, Flask) bridging the Python logic to HTTP requests.
- All frontend data fetching relies on client-side mocks (`mock-query.ts`, `mock-review.ts`, etc.).

### B. Missing DTOs & Serializers [HIGH]
- Python dataclasses/Pydantic models in M1-M6 do not currently have explicit serializers that match the TypeScript interfaces defined in M7 (e.g., `ReviewResult`, `MonitoringSnapshot`, `NodeWrapper`).
- Graph payload serialization (M3 -> React Flow) needs a dedicated adapter to avoid sending 50MB of raw graph data over the wire.

### C. Missing Backend Adapters [HIGH]
- The M5 (Query System) and M6 (Synthesis Engine) produce deterministic outputs, but they do not have async wrappers for long-running HTTP requests (e.g., Celery/Redis task queues).
- Attempting to run a 60-second synthesis via a blocking HTTP request will result in browser timeouts.

### D. Missing Streaming Support [MEDIUM]
- The frontend `ReviewProgressTracker` and `TraceViewer` rely on `setTimeout` polling.
- The backend requires Server-Sent Events (SSE) or WebSockets to push pipeline stage transitions in real-time.

### E. Missing Authentication Hooks [CRITICAL]
- M7-3 Foundation contains Auth layout, but the backend has no `users` table, no JWT generation, and no RBAC (Role-Based Access Control).

## 4. Conclusion
The frontend and backend are completely decoupled. A dedicated **Production API Layer** (FastAPI) is strictly required to bridge the Python modules to the Next.js client.
