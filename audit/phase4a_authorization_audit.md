# Phase 4A Authorization Audit

## Endpoint Classification
- **Public (No token required):**
  - GET /api/v1/system/health
  - POST /api/v1/auth/login
  - POST /api/v1/auth/register
- **Authenticated (Standard User ole:user):**
  - POST /api/v1/query/answer
  - POST /api/v1/reviews/generate
  - GET /api/v1/dashboard/*
  - GET /api/v1/graph
  - GET /api/v1/documents/*
- **Admin-Only (ole:admin):**
  - GET /api/v1/monitoring
  - GET /api/v1/monitoring/metrics
  - *(Future)* User management endpoints.

## Permission Model Design
The JWT payload will include a scopes or ole claim. 
A FastAPI dependency, get_current_user, will decode the JWT and inject the user context into the route.
A secondary wrapper, equire_admin, will evaluate user.role == 'admin' and throw a 403 Forbidden if validation fails.

## Necessary Dependency Injections
1. ackend/api/dependencies.py requires:
   - get_token_from_header(request: Request) -> str
   - get_current_user(token: str = Depends(oauth2_scheme)) -> User
   - get_admin_user(user: User = Depends(get_current_user)) -> User
2. Update existing routers to include these dependencies in their function signatures or APIRouter inclusions.
