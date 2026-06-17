# Phase 4A API Security Audit

## Current Middleware & Routing Vulnerabilities
- **Rate Limiting:** Missing. The system is vulnerable to DoS through excessive LLM queries or graph pulls. A malicious actor could exhaust the API budget or memory limits easily.
- **Throttling:** Missing. Concurrency limits are absent.
- **Abuse Protection:** Missing. No IP-level bans, CAPTCHAs on authentication routes, or anomalous request flagging.
- **Request Size Controls:** Missing explicit payload limits for POST routes (e.g. POST /api/v1/query/answer).
- **Security Headers:** Missing. pp.py does not append HSTS (Strict-Transport-Security), X-Frame-Options, or Content-Security-Policy headers.
- **CORS Configuration:** Missing CORSMiddleware. The API cannot currently be consumed by a browser from a different origin domain.

## Recommended Implementations
- Add slowapi or custom Redis-based Token Bucket middleware to enforce strict limits (e.g., 10 RPM for LLM queries, 100 RPM for general API).
- Implement CORSMiddleware in pp.py restricting llow_origins strictly to the frontend's deployment URL.
- Implement a SecurityHeadersMiddleware to append OWASP-recommended headers to every outbound response.
