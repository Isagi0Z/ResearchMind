# Phase 4A Auth Framework Design

## JWT Utility Layer
- Uses Python JWT libraries for HMAC (HS256) signature generation and verification.
- Functions create_access_token, create_refresh_token, and decode_token explicitly defined in security.py.
- Tokens will include standard claims: sub (username/ID), exp, iat, and a custom scopes claim for RBAC.

## Security Dependency Framework
- **oauth2_scheme**: Configured as OAuth2PasswordBearer pointing to /api/v1/auth/login.
- **get_current_user**: A dependency that reads the token from oauth2_scheme, validates it against the SECRET_KEY, and extracts the sub and scopes.
- **equire_role(role_name)**: A dependency factory that validates if the get_current_user output contains the required scope.

## Endpoint State
- The actual implementation of POST /api/v1/auth/login, egister, efresh, and logout will remain hardcoded to throw a 501 Not Implemented HTTPException.
- This ensures no temporary or mock users bypass the architecture before Phase 4B database integration.
