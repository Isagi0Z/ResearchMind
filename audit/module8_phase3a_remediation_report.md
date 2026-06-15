# Module 8 Phase 3A — Remediation Report

## Remediations Implemented

### Remediation A — Externalize API Base URL
**Status:** ✅ Complete

**Changes:**
- `frontend/lib/api-client.ts`: Replaced hardcoded `http://localhost:8000` with `process.env.NEXT_PUBLIC_API_URL`.
- Added `getBaseUrl()` helper that throws a clear `ApiError(0, ...)` if the env var is missing.
- Created `frontend/.env.example` documenting the required variable.
- Created `frontend/.env.local` with the development default.
- Added `.env.local` and `.env*.local` to `.gitignore` to prevent committing secrets.

**Verification:** `npm run build` output confirms: `- Environments: .env.local`.

---

### Remediation B — AbortController Timeout Protection
**Status:** ✅ Complete

**Changes:**
- `frontend/lib/api-client.ts`: Added `AbortController` with `API_TIMEOUT_MS = 30_000` (30 seconds).
- `AbortError` from browser is caught and re-thrown as `ApiError(408, 'Request timed out')`.
- Generic network failures (server offline) throw `ApiError(0, 'Network error: unable to reach the server.')`.
- `clearTimeout()` called in both `catch` and `finally` to prevent timer leaks.

---

### Remediation C — Empty Response Hardening
**Status:** ✅ Complete

**Changes:**
- `frontend/services/query.ts`: Added 3 validation guards before field mapping:
  - `response.answer` must exist and `answer.text` must be a string.
  - `response.evidence` must be an array.
  - `response.step_route.steps` must be an array.
  - Violations throw `ApiError(502, 'Invalid response: ...')`.
- `frontend/services/review.ts`: Added 3 validation guards:
  - `response.review_result` must exist.
  - `review_result.abstract` must be a string.
  - `review_result.sections` and `review_result.findings` must be arrays.
  - Sub-arrays (`sec.findings`, `f.evidence_ids`) use `Array.isArray()` with empty-array fallbacks.

---

### Remediation D — Stack Trace Exposure Review
**Status:** ✅ Complete

**Changes:**
- `frontend/lib/api-client.ts`: Added `sanitizeErrorMessage()` function.
  - For `status >= 500`: Returns generic `'An internal server error occurred. Please try again later.'`
  - For `status < 500`: Preserves the backend `detail` string (e.g., 422 validation errors).
  - Fallback to `res.statusText` if detail is empty or non-string.

---

## Verification Results

| Gate | Result |
|---|---|
| `npm run build` | ✅ Passed — 10/10 pages, `.env.local` loaded |
| Frontend tests | ✅ 345 passed, 3 failed (pre-existing) |
| Backend pytest | ✅ 3054 passed |
| `git status` | ✅ Clean |

## Commit
```
851605f fix(m8-phase3a): remediation A-D — env config, timeout, response hardening, error sanitization
```
