# Module 9 Phase 4 Phase Rollout Plan

## Phase 4A — Security Foundation
*   **JWT Completion:** Implement login/refresh endpoints in uth.py. Secure existing endpoints via Depends(get_current_user).
*   **Secret Management:** Hook BaseSettings into a secrets manager. Validate critical environment configurations at runtime.
*   **CORS Review:** Implement and configure CORSMiddleware in pp.py for strictly allowed origins.

## Phase 4B — Persistence Layer
*   **PostgreSQL:** Spin up PostgreSQL infrastructure.
*   **Migrations:** Introduce Alembic. Generate base migrations mapping Pydantic schemas to SQLAlchemy tables.
*   **Repository Layer:** Replace InMemoryDocumentStore with database-backed repositories within ackend/api/dependencies.py.

## Phase 4C — Background Execution
*   **Redis:** Deploy Redis for session caching and message brokering.
*   **Celery:** Implement Celery worker configurations.
*   **Long-running Jobs:** Offload query.py and eview.py endpoints to Celery. Refactor frontend to poll for task completion.

## Phase 4D — Observability
*   **Logging:** Integrate structlog for structured JSON logging.
*   **Metrics:** Expose Prometheus /metrics endpoint.
*   **Health Checks:** Expand /api/v1/system/health to verify Redis and PostgreSQL connectivity.

## Phase 4E — Deployment Infrastructure
*   **Docker:** Write Dockerfile.backend, Dockerfile.frontend, and Dockerfile.worker.
*   **Reverse Proxy:** Configure Nginx for TLS termination and path routing.
*   **Environment Configuration:** Build docker-compose.yml and establish GitHub Actions for CI testing.
