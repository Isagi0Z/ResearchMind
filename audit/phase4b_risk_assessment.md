# Phase 4B Risk Assessment

## High Risk
- **Database Coupling**: Tightly coupling the M1-M6 engines to SQLAlchemy models risks destroying the determinism built during Phase 1-3. 
  - *Mitigation*: The reasoning engines must remain pure functions; the persistence layer only acts as a wrapper around the inputs/outputs.
- **Migration Failures**: State drift between the mock JSON databases and the active PostgreSQL instance.
  - *Mitigation*: Ensure robust test coverage for Alembic scripts and fallback gracefully.

## Medium Risk
- **Frontend Session State**: Infinite refresh loops if the token logic is buggy.
  - *Mitigation*: Use a standard, battle-tested library or strict interceptor timeout policies.
- **Ownership**: Accidentally returning another user's queries or reviews.
  - *Mitigation*: Row-level ownership checks at the API boundary on all fetching.

## Low Risk
- **Admin Tooling**: Lack of interfaces for managing users initially. 
  - *Mitigation*: Can be done via direct SQL or simple scripts initially.
