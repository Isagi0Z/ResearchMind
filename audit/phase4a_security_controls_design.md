# Phase 4A Security Controls Design

## Security Headers
- X-Content-Type-Options: nosniff
- Strict-Transport-Security: max-age=31536000; includeSubDomains
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Will be implemented via a custom Starlette BaseHTTPMiddleware class.

## CORS Configuration
- Handled natively via FastAPI's CORSMiddleware.
- Configured by a comma-separated CORS_ORIGINS environment variable validated by Pydantic.

## Rate Limiting
- Built using a lightweight token bucket algorithm inside a custom middleware.
- State is held in a Python dict keyed by IP or request signature (pending Redis migration).
- Strict bounds: Default bucket capacity and replenish rate to prevent infinite loops from malicious scripts while keeping development unobstructed.

## Request Size Controls
- Middleware to intercept Content-Length headers and throw 413 Payload Too Large if requests exceed safe limits (e.g., 5MB for queries).
