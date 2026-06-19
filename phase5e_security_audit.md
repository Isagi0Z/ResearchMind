# Phase 5E — Security Hardening Audit

**Date:** 2026-06-19  
**Scope:** Authentication, JWT handling, refresh token lifecycle, CORS, security headers, error exposure

---

## 1. JWT Token Security

### Before
- JWT tokens contained only `sub` (user ID), `exp`, and `role` claims
- No issuer claim → tokens from any source would be accepted
- No token type claim → a refresh token could potentially be used as an access token
- `decode_token()` accepted any valid JWT regardless of purpose

### After
- ✅ `iss: "researchmind-api"` claim on all tokens — prevents token injection from external issuers
- ✅ `type: "access"` or `type: "refresh"` claim — prevents token type confusion
- ✅ `decode_access_token()` requires `type=access` — refresh tokens cannot be used for API access
- ✅ `get_current_user_optional()` validates `iss` claim
- 🔑 Secret key validation: ≥32 chars, rejects `testing_secret_key`, reads from env or `.env`

## 2. Refresh Token Lifecycle

| Aspect | Status | Detail |
|--------|--------|--------|
| Rotation on use | ✅ | Each refresh creates a new token and revokes the old one |
| SHA256 lookup | ✅ | O(1) lookup via `token_hash_sha256` column |
| bcrypt storage | ✅ | `hashed_token` column stores bcrypt hash for verification |
| Expiry enforcement | ✅ | Database query includes `expires_at > now()` check |
| Revocation on logout | ✅ | Token marked `is_revoked = True` |
| Stale cleanup | ⚠️ | No background task for expired token cleanup (deferred to Phase 6) |

## 3. CORS Configuration

| Aspect | Status | Detail |
|--------|--------|--------|
| Origin whitelist | ✅ | Configurable via `CORS_ORIGINS` env var (comma-separated) |
| Credentials | ✅ | `allow_credentials` configurable via `CORS_ALLOW_CREDENTIALS` |
| Exposed headers | ✅ | `X-Request-ID` exposed for client-side error correlation |
| Methods/Headers | ✅ | `*` allowed (standard for API) |
| Production validation | ✅ | Warns when CORS_ORIGINS is empty in production |

## 4. Security Headers

| Header | Status | Detail |
|--------|--------|--------|
| `X-Content-Type-Options: nosniff` | ✅ | Always set |
| `Strict-Transport-Security` | ✅ | HTTPS only: `max-age=31536000; includeSubDomains` |
| `X-Frame-Options: DENY` | ✅ | Always set |
| `X-XSS-Protection: 1; mode=block` | ✅ | Always set |
| `X-Request-ID` | ✅ | Always set (moves from `RequestContextMiddleware` to `SecurityHeadersMiddleware`) |
| `Referrer-Policy` | ✅ | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | ✅ | `camera=(), microphone=(), geolocation=()` |
| `Content-Security-Policy` | ✅ | HTTPS only: `default-src 'self'` |

## 5. Error Exposure

| Scenario | Before | After |
|----------|--------|-------|
| 500 Internal Server Error | Detail suppressed (no stack trace) | ✅ Unchanged — still suppressed |
| 422 Validation Error | Detail preserved | ✅ Unchanged — intentional for developer feedback |
| 401 Unauthorized | Generic message | ✅ Unchanged |
| 404 Not Found | Generic message | ✅ Unchanged |

## 6. Rate Limiting

| Aspect | Status | Detail |
|--------|--------|--------|
| In-memory store | ✅ | `MemoryCounterStore` — active by default |
| Redis store | ✅ | `RedisCounterStore` — conditional on `REDIS_URL` |
| Configurable limits | ✅ | `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS` |
| X-Forwarded-For support | ✅ | Respects proxy headers |
| Auth endpoint rate limiting | ⚠️ | Not specifically hardened beyond global limits (deferred) |

## 7. Cookie Security

| Aspect | Status | Detail |
|--------|--------|--------|
| HTTP-only | ✅ | Cookies not accessible via JavaScript |
| Secure flag | ✅ | Config-driven, auto-true in production |
| SameSite | ✅ | Configurable (default `lax`) |
| Path restriction | ✅ | Refresh cookie limited to `/api/v1/auth` path |
| Domain restriction | ✅ | Configurable via `AUTH_COOKIE_DOMAIN` |
| Max-Age | ✅ | Matches token expiry |
| CSRF protection | ✅ | SameSite=Lax prevents cross-site form submission |
| XSS mitigation | ✅ | HTTP-only cookie prevents token theft via XSS |

## 8. Environment Validation

The `validate_environment()` function checks at startup:
- ✅ CORS_ORIGINS non-empty in production
- ✅ AUTH_COOKIE_SECURE enabled in production
- ✅ SameSite=None requires Secure flag
- ✅ REFRESH_TOKEN_EXPIRE_DAYS ≤ 30
- ✅ DATABASE_URL set to PostgreSQL in production
- ✅ Non-empty DATABASE_URL (warns about SQLite default)
