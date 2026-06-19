# Phase 5E — Cookie Auth Migration Audit

**Date:** 2026-06-19  

---

## Migration Summary

The authentication system now supports **dual-mode** token delivery:
1. **`Authorization: Bearer` header** (existing) — for API clients, mobile apps, CLI tools
2. **HTTP-only cookies** (new) — for browser-based frontend sessions

## Architecture

```
                    Browser                          API Client
┌─────────────────────────────┐          ┌──────────────────────┐
│   fetch(url, {credentials:  │          │  fetch(url, {headers: │
│   'include'})               │          │  {Authorization:      │
│         │                   │          │   'Bearer <token>'}}) │
│         ▼                   │          │         ▼             │
│   Cookie Jar ──► Request    │          │   Header ──► Request  │
│   (HTTP-only)   cookies     │          │   (explicit)  token   │
└─────────────┬───────────────┘          └──────────┬───────────┘
              │                                     │
              ▼                                     ▼
        ┌──────────────────────────────────────────┐
        │         FastAPI Backend                    │
        │  - Reads Authorization header first        │
        │  - Falls back to access_token cookie       │
        │  - Sets cookies on login/refresh           │
        │  - Clears cookies on logout                │
        └──────────────────────────────────────────┘
```

## Cookie Flow

### Login
```
POST /api/v1/auth/login
  → Set-Cookie: access_token=<JWT>; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=1800
  → Set-Cookie: refresh_token=<JWT>; HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth; Max-Age=604800
  → Response body: { access_token, refresh_token, token_type }
```

### Authenticated Request
```
GET /api/v1/graph/data
  Cookie: access_token=<JWT>
  → If valid → 200
  → If expired → 401 → Client POSTs to /auth/refresh
```

### Token Refresh
```
POST /api/v1/auth/refresh (no body, or empty JSON)
  Cookie: refresh_token=<JWT>
  → Set-Cookie: access_token=<new JWT>
  → Set-Cookie: refresh_token=<new JWT>
  → Response body: { access_token, refresh_token, token_type }
```

### Logout
```
POST /api/v1/auth/logout
  Cookie: refresh_token=<JWT>
  → Revokes refresh token in DB
  → Set-Cookie: access_token=; Expires=Thu, 01 Jan 1970
  → Set-Cookie: refresh_token=; Expires=Thu, 01 Jan 1970
```

## Frontend Changes

| File | Change | Rationale |
|------|--------|-----------|
| `api-client.ts` | Added `credentials: 'include'` to all requests | Ensures cookies are sent cross-origin |
| `api-client.ts` | Added `postForm()` method | Supports OAuth2 form-encoded login |
| `api-client.ts` | Token refresh sends `{}` body when no localStorage token | Cookie provides the refresh token |
| `login/page.tsx` | Uses `apiClient.postForm()` instead of raw fetch | Ensures credentials are included |

## Backward Compatibility

| Client type | Before | After |
|-------------|--------|-------|
| Browser (existing) | localStorage token, Bearer header | Cookie-based (fallback to Bearer) |
| Browser (new) | N/A | Cookie-based |
| API client (curl) | Bearer header | Bearer header (unchanged) |
| Mobile app | Bearer header | Bearer header (unchanged) |
| Test client | Bearer header | Bearer header (unchanged) |

## Security Improvements

| Threat | Mitigation | Status |
|--------|-----------|--------|
| XSS token theft | HTTP-only cookies prevent JS access | ✅ |
| CSRF | SameSite=Lax prevents cross-site requests | ✅ |
| Man-in-the-middle | Secure flag ensures cookie sent over HTTPS only | ✅ (production) |
| Session fixation | New cookies set on every login/refresh | ✅ |
| Token replay (refresh) | Token rotation revokes old token | ✅ |

## Configuration

```env
# In .env
AUTH_COOKIE_SECURE=false        # true in production
AUTH_COOKIE_SAMESITE=lax        # strict, lax, or none
AUTH_COOKIE_DOMAIN=             # set for subdomain sharing
CORS_ALLOW_CREDENTIALS=true     # must be true for cookie auth
```
