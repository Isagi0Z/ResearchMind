# Module 8 Phase 3A API Resilience Audit

## Evaluation Criteria

| Capability | Status | Assessment |
|---|---|---|
| **Backend Offline Behavior** | Acceptable | `fetch` natively throws a `TypeError: Failed to fetch` when the server is entirely unreachable. This triggers the `catch` blocks in `query-workspace.tsx` and `review-generator-form.tsx`, transitioning the UI to a `failed` state. No infinite loading occurs. |
| **Malformed Payload Handling** | Acceptable | Handled robustly by `api-client.ts`. The error handler wraps `res.json()` in a `try/catch`. If the server returns a malformed or non-JSON body (e.g. Nginx 502 Bad Gateway HTML), the parser falls back gracefully to `res.statusText`. |
| **HTTP 422 Handling** | Acceptable | FastAPI natively returns `422 Unprocessable Entity` with a detailed schema validation error object. The `api-client.ts` parses this, extracts `errData.detail`, and wraps it in an `ApiError`. |
| **HTTP 500 Handling** | Acceptable | `res.ok` safely catches 500 statuses. |
| **Timeout Behavior** | Blocker | No default timeout is configured on `fetch()` calls. Complex, deeply nested research queries sent to `/api/v1/query/answer` could theoretically hang indefinitely if the backend blocks. This must be remediated with an `AbortController`. |
| **Empty Response Behavior** | Warning | If the backend returns a `200 OK` with an empty response body or missing nested keys, `res.json()` succeeds but the mapping functions (e.g. `response.answer.text`) will throw a `TypeError`. This forces the UI into a `failed` state, which is safe, but prevents detailed error communication. |

## Conclusion
The API resilience is fundamentally sound but contains one blocker: missing `AbortController` timeouts in `api-client.ts` to prevent infinite hangs.
