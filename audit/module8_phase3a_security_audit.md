# Module 8 Phase 3A Security Audit

## Review Criteria

| Check | Status | Details |
|---|---|---|
| **Exposed Stack Traces** | Warning | `frontend/lib/api-client.ts` propagates `errData.detail`. If FastAPI returns a stack trace in a 500 internal server error, it will be surfaced in the frontend UI or console. |
| **Unsafe Fetch Usage** | Acceptable | `api-client.ts` correctly uses `JSON.stringify(data)` and defines the `'Content-Type': 'application/json'` header. |
| **Hardcoded Credentials** | Acceptable | None found in the frontend source code. |
| **Localhost Assumptions** | Blocker | `api-client.ts` hardcodes `http://localhost:8000` directly in the `fetch` call string interpolation. This breaks portability and will fail in staging/production environments. It should use `process.env.NEXT_PUBLIC_API_URL`. |
| **CORS Issues** | Acceptable | The backend is assumed to run CORS middleware properly; frontend correctly uses standard POST requests without preflight-violating headers. |
| **Unsafe JSON Parsing** | Acceptable | Native `res.json()` is used appropriately. Non-JSON server responses (like 502 HTML pages) are caught via a `try/catch` and gracefully fall back to `res.statusText`. |

## Conclusion
A critical blocker exists regarding the hardcoded API base URL which must be externalized to environment configuration before production deployment.
