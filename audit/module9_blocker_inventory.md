# Module 9 Phase 4 Blocker Inventory

| ID | Category | Severity | Impact | Root Cause | Remediation Strategy | Est. Complexity |
|---|---|---|---|---|---|---|
| AUTH-01 | Authentication | Critical | No user verification. APIs open to all. | Only 501 stubs exist in uth.py. | Implement JWT lifecycle (login, refresh, verify) in FastAPI. | Medium |
| AUTHZ-01 | Authorization | High | No data segregation. | RBAC logic not implemented. | Add role scopes to JWT and validate in Depends hooks. | Low |
| PERS-01 | Persistence | Critical | Data loss on restart. | Uses InMemoryDocumentStore. | Implement SQLAlchemy + PostgreSQL repositories. | High |
| PERS-02 | Persistence | High | Cannot deploy schema changes. | No Alembic configured. | Initialize Alembic and define migration env. | Low |
| BG-01 | Background Processing | Critical | Request timeouts on real LLM calls. | Async endpoints await LLM synchronously. | Add Celery worker pool and Redis broker. | High |
| SEC-01 | Security | High | UI cannot securely talk to API cross-origin. | CORSMiddleware absent in pp.py. | Add configured middleware. | Low |
| SEC-02 | Security | Medium | Key leakage risk. | Missing secrets vault/rotation plan. | Integrate BaseSettings with a secure vault (e.g. Hashicorp or AWS Secrets). | Medium |
| INF-01 | Infrastructure | Critical | No TLS, static asset handling, or gateway. | Relying on raw Uvicorn/Node processes. | Configure Nginx/Traefik reverse proxy. | Medium |
| INF-02 | Infrastructure | High | Cannot deploy reproducibly. | Missing Dockerfiles / compose. | Write Dockerfiles and docker-compose.yml. | Medium |
| SCL-01 | Scalability | High | Browser / Memory crashes on large graphs. | /api/v1/graph sends entire dump. | Implement Graph LOD / bounding box queries. | High |
| OBS-01 | Observability | Medium | Blind to production issues. | Standard print/logger only. | Add Structlog and OpenTelemetry tracking. | Medium |
| DEP-01 | Deployment | High | No automated validation. | Missing CI/CD pipelines. | Build GitHub Actions for tests/lint/build. | Low |
