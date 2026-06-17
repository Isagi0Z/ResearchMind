# Phase 4B Authentication Architecture

## Foundation Reuse
- The JWT encoding/decoding scaffolding in ackend/api/auth/security.py can be fully reused, with the addition of a time-based expiration (exp claim) now that determinism constraints loosen for authentication tokens.
- The astapi.security.OAuth2PasswordBearer and router skeletons can be reused.

## Changes Required
- Implement bcrypt hashing via passlib for saving new users to the PostgreSQL database.
- Integrate active database session validation into get_current_user inside dependencies.py.
- Activate exp claims.

## Tokens
- **Access Tokens**: Short-lived (e.g., 15-60 minutes) JWTs.
- **Refresh Tokens**: Long-lived (e.g., 7 days) tokens stored hashed in PostgreSQL for explicit revocation ability.

## Role Model
- dmin: Full repository, user, and corpus access.
- user: Bound to self-owned queries, reviews, and general read corpus access.
