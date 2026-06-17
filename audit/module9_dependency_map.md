# Module 9 Phase 4 Dependency Map

## Dependency Graph
`mermaid
graph TD
    INF02[INF-02: Dockerfiles] --> INF01[INF-01: Reverse Proxy]
    PERS02[PERS-02: Alembic Migrations] --> PERS01[PERS-01: Postgres SQLAlchemy]
    PERS01 --> AUTH01[AUTH-01: JWT Authentication]
    AUTH01 --> AUTHZ01[AUTHZ-01: RBAC]
    INF02 --> BG01[BG-01: Celery/Redis Workers]
    BG01 --> SCL01[SCL-01: Scalable Query/Graph APIs]
    SEC02[SEC-02: Secrets Management] --> AUTH01
    SEC01[SEC-01: CORS Middleware] --> INF01
    OBS01[OBS-01: Observability] --> INF02
    INF01 --> DEP01[DEP-01: CI/CD Pipelines]
`

## System Impacts
- **Frontend Impact:** SEC-01 (CORS) required for browser cross-origin fetching. AUTH-01 requires the frontend to store and attach JWTs in an Authorization header via piClient. SCL-01 requires the frontend graph to implement pagination/LOD logic.
- **Backend Impact:** PERS-01 touches all dependencies in ackend/api/dependencies.py to inject DB sessions instead of memory instances. BG-01 forces ackend/api/routes/query.py and eview.py to become asynchronous task publishers instead of synchronous executors.
- **Deployment Impact:** INF-02 forms the basis of all future environment deployments. Without it, PostgreSQL and Redis cannot be safely networked.
