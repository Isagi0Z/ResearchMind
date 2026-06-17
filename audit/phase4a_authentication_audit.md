# Phase 4A Authentication Audit

## Current State
- ackend/api/routes/auth.py contains basic schema mapping for /login, /register, /refresh, and /logout, but exclusively raises 501 Not Implemented.
- No active JWT issuance exists.
- The astapi.security modules are not utilized.

## Missing Capabilities Identified
1. **Login Flow:** No credential validation. Needs to connect to the impending PostgreSQL User table and verify Argon2id/Bcrypt password hashes.
2. **Refresh Token Strategy:** Lacks long-lived refresh tokens. Without this, users will face abrupt logouts when short-lived access tokens expire.
3. **Token Rotation:** Missing automatic invalidation of old refresh tokens upon issuance of a new pair (Refresh Token Rotation).
4. **Logout Invalidation:** Stateless JWTs cannot be trivially logged out. A Redis-backed token denylist (blocklist) architecture is missing.
5. **Session Management:** No concept of "active devices" or session limiting.

## Production Requirements
- Utilize PyJWT or python-jose for JWT signing.
- Access Tokens: 15-minute lifespan.
- Refresh Tokens: 7-day lifespan, opaque string stored in DB/Redis or signed JWT.
- Provide OAuth2-compatible Password Bearer flow for Swagger/Redoc UI compatibility.
