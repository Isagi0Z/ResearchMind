# Module 9 Phase 4 Remediation Strategy

## Strategic Overview
The remediation strategy is built upon a sequential progression that prioritizes data integrity and security before attempting architectural scaling. The strategy ensures that frontend components remain oblivious to backend structural shifts through strict adherence to Pydantic contracts established in Phase 3B.

## Security & Secrets
All raw configurations will be moved to a Vault or AWS Secrets Manager mock, exposed internally through Pydantic BaseSettings. JWT implementation will secure all endpoints, transitioning piClient to a bearer token approach. CORS will be locked to the production domain.

## Persistence First
Because background workers require a durable state to read/write from, PostgreSQL and Alembic must be implemented *before* Celery. The repository layer will be refactored to abstract SQLAlchemy sessions, replacing the InMemoryDocumentStore.

## Asynchronous Delegation
Heavy synchronous blocks (Query execution, Synthesis generation) will be refactored to dispatch tasks to a Redis-backed Celery pool. Endpoints will return 202 Accepted with a Job ID, moving the frontend to a polling or WebSocket pattern.

## Orchestration
A unified docker-compose environment will orchestrate the Next.js container, FastAPI web workers, Celery background workers, Redis, and PostgreSQL to ensure absolute parity between local development, CI, and Production.
