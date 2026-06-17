# Phase 4B Migration Strategy

## Objectives
- Zero regression risk.
- Preserve all existing deterministic APIs.

## Rollout Sequence
1. **Schema Initialization (Backend)**: Introduce Alembic, SQLAlchemy, and PostgreSQL. Deploy the database schema without tying it to the active logic.
2. **Persistence Sinks (Backend)**: Connect the Query and Review endpoints to "fire-and-forget" persistence sinks. The outputs remain deterministic, but a copy of the results is asynchronously written to PostgreSQL.
3. **Authentication Activation (Backend)**: Activate the /login, /register, and /refresh endpoints. Keep the get_current_user dependencies *optional* on business routes initially to avoid breaking the frontend.
4. **Frontend Integration**: Implement the login flow, token management, and session context. Route unauthenticated users correctly.
5. **Enforcement Cut-over**: Switch the backend dependencies on business routes from optional to strictly enforced.
