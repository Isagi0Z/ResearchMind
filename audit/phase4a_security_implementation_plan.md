# Phase 4A Security Implementation Plan

## Step 1: JWT & Password Hashing Core
1. Introduce PyJWT and passlib[bcrypt] to the backend environment.
2. Replace mock implementations in ackend/api/routes/auth.py with true payload validation and JWT signing using a deterministic secret (or fallback dummy key for test compatibility).

## Step 2: Route Protection & RBAC
1. Define get_current_user in dependencies.py to extract and decode the JWT from the Authorization header.
2. Annotate /api/v1/query, /api/v1/reviews, and /api/v1/graph with Depends(get_current_user).
3. Introduce a ole claim to the token. Define get_admin_user and apply it to /api/v1/monitoring.

## Step 3: FastAPI Security Hardening
1. Inject CORSMiddleware in pp.py, mapping llow_origins to the frontend's configured host.
2. Implement a SecurityHeadersMiddleware to output HSTS and XSS-Protection headers on all HTTP responses.
3. Stub rate-limiting wrappers around LLM generation endpoints, falling back to a simplistic dict-based token bucket until Redis is available in Phase 4C.

## Step 4: Frontend Proxying & Auth State
1. Update Next.js to expose an API route (/api/auth/login) that proxies credentials to FastAPI, intercepts the JWT response, and issues a Set-Cookie header configuring an HTTP-Only cookie.
2. Modify pi-client.ts to automatically extract the cookie (if running server-side) and attach it as a Bearer token to backend requests.

## Determinism Integrity Check
- Ensure that the random salt generator for JWT signing defaults to LCG deterministic strings during testing, ensuring that backend test suites (3000+ tests) do not intermittently fail due to token expiration clock-skew or random padding differences.
