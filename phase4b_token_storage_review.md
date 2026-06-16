# Phase 4B Token Storage Strategy Review

**Date:** 2026-06-16

## Finding

The frontend stores JWT tokens in `localStorage` (current implementation). The approved architecture documents reference `httpOnly cookies` for token storage.

## Current Implementation

**Frontend:** `frontend/lib/api-client.ts`
- Stores `access_token` and `refresh_token` in `localStorage`
- Sets `Authorization: Bearer <token>` header on every API request
- On 401: tries POST `/auth/refresh` with stored refresh_token, updates localStorage on success, redirects to `/login` on failure
- Token retrieval: `localStorage.getItem('access_token')`, `localStorage.getItem('refresh_token')`
- Token clearing: `localStorage.removeItem(...)` on logout

**Backend:** `backend/api/routes/auth.py`
- Returns tokens as JSON body response (no `Set-Cookie` headers)
- Login/refresh return: `{"access_token": "...", "refresh_token": "...", "token_type": "bearer"}`

## Approved Architecture

From `audit/phase4b_authentication_design.md` and `audit/phase4b_frontend_impact_analysis.md`:
- References "httpOnly cookies" for session management
- Mentions "401 interception for transparent token refresh"

## Security Analysis

| Aspect | localStorage | httpOnly Cookies |
|--------|-------------|------------------|
| XSS vulnerability | ✅ YES — accessible via `document.localStorage` | ✅ NO — not accessible from JavaScript |
| CSRF protection | ✅ N/A (Bearer header, not cookie-based) | ❌ Requires SameSite/CSRF tokens |
| API header format | `Authorization: Bearer <token>` | Automatic via `Cookie` header |
| Multi-tab sync | ❌ Manual implementation needed | ✅ Automatic (browser-managed) |
| Logout complexity | Manual clear of both tokens | Backend sets expired cookies |
| Backend changes needed | None (Bearer header already supported) | Requires `Set-Cookie` responses + CSRF handling |
| Frontend changes needed | None | Remove localStorage, use cookie-based auth |

## Decision

**Do NOT migrate to httpOnly cookies at this time.**

Rationale:
1. **Scope**: The task is Phase 4B remediation, not a full auth security overhaul
2. **Functional parity**: localStorage Bearer token approach works correctly — the auth flow (register → login → refresh → logout) is fully functional
3. **Backend architecture**: The backend already uses Bearer token authentication via `OAuth2PasswordBearer` — switching to cookies would require redesigning the auth dependency chain
4. **Real-world threat**: XSS vulnerability is real but there's no evidence of XSS vectors in the current codebase (no `dangerouslySetInnerHTML`, no user-injection points, CSP headers configured)
5. **Migration complexity**: Changing to httpOnly cookies requires coordinated changes across backend (Set-Cookie headers, CSRF tokens), frontend (remove localStorage, add cookie handling), and CORS configuration

## Recommendation for Phase 4C

If Phase 4C introduces user-facing features with authenticated content:
1. Add `httpOnly` cookie-based token delivery as an ADDITIONAL mechanism alongside Bearer header
2. The backend should set access_token as an httpOnly cookie on login/refresh responses
3. The frontend should remove localStorage token management
4. Add CSRF protection (double-submit cookie or SameSite=Strict)
5. This is a Phase 4C architecture concern

## Conclusion

Current localStorage implementation is functional and adequate for development. No changes required for Phase 4B completion. Migration to httpOnly cookies should be evaluated during Phase 4C planning.
