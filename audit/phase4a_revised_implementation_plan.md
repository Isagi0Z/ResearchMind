# Phase 4A Revised Implementation Plan

## Objective
Establish the backend security foundation without breaking existing open routes. Defer actual enforcement and user management to Phase 4B.

## Work Items
1. **Secrets & Configuration:**
   - Update config.py with strict Pydantic validation for SECRET_KEY, ALGORITHM, and CORS_ORIGINS.
   - Prevent application boot if secrets are missing. Provide .env.example.

2. **Authentication Infrastructure:**
   - Implement ackend/api/auth/jwt.py containing robust JWT encoding, decoding, and verification functions using PyJWT or python-jose.
   - Ensure the exp logic and secret key usage respect determinism constraints during testing.
   - Retain 501 Not Implemented for /api/v1/auth/* endpoints. Document Phase 4B dependency.

3. **Authorization Infrastructure:**
   - Extend ackend/api/dependencies.py to define role-based dependencies (e.g., get_current_user, equire_role("admin")), but do **not** inject them into the actual routers yet.
   - Document the future classification of all endpoints.

4. **API Security Hardening:**
   - Integrate CORSMiddleware in pp.py.
   - Implement SecurityHeadersMiddleware to append HSTS, X-Content-Type-Options, etc.
   - Add a deterministic, dict-backed token-bucket rate limiter middleware as a placeholder for Redis.
