# Phase 4A Remediation Report

## Remediation Actions Performed

### A - Hardcoded SECRET_KEY
- **Issue**: ackend/api/config.py contained a hardcoded fallback value.
- **Fix**: Removed default value. SECRET_KEY: str now strictly requires an environment variable to boot the application. Verified determinism remains intact.

### B - Unreachable JWT Logic
- **Issue**: security.py had unreachable JWT encode/decode code after raising 501.
- **Fix**: Replaced implementation with strict 501 scaffold (Option A), removing all unreachable jwt.encode and jwt.decode code blocks.

### C - Authentication Framework Consistency
- **Issue**: dependencies.py's get_current_user was masking the 501 from decode_access_token and creating dead code.
- **Fix**: get_current_user now explicitly raises the 501 HTTPException directly. The dependency chain is completely deterministic and consistent for Phase 4A.

### D - Rate Limiter Determinism
- **Issue**: RateLimitMiddleware used an accumulating memory dictionary, violating determinism.
- **Fix**: Disabled active tracking. The middleware acts as a pure passthrough scaffold, preserving the architectural location without state side-effects (Option A).

### E - Duplicate Raise Statements
- **Issue**: Extraneous/duplicate HTTPExceptions in ackend/api/routes/auth.py.
- **Fix**: Completely rewrote the module ensuring only a single, authoritative HTTPException exists per route method.

### F - Security Header Review
- **Issue**: Strict-Transport-Security unconditionally emitted.
- **Fix**: Wrapped HSTS header insertion in an explicit if request.url.scheme == "https": condition to only activate on valid secure transport layers.
