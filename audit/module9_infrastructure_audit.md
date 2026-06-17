# Module 9 Phase 4 Infrastructure Audit

## Requirements Assessment

- **PostgreSQL:** REQUIRED. InMemoryDocumentStore will not survive process restarts. A robust relational database is necessary for User Auth, RBAC, and Document Metadata persistence.
- **Redis:** REQUIRED. Essential for distributed rate limiting, session management, and serving as a message broker for background tasks.
- **Celery / Background Execution:** REQUIRED. Heavy LLM synthesis and long-running queries currently block the event loop or run inline. They must be offloaded to distributed workers.
- **Object Storage (S3-compatible):** RECOMMENDED. Necessary if raw files (PDFs, images) belonging to the corpus need to be durably stored outside of PostgreSQL.
- **Reverse Proxy (Nginx/Traefik):** REQUIRED. Critical for routing traffic between the Next.js frontend and FastAPI backend, and handling static assets efficiently.
- **HTTPS Termination:** REQUIRED. API and Frontend must be served securely. Uvicorn should not terminate SSL; this must happen at the reverse proxy or load balancer.
- **Deployment Environment:** REQUIRED. Need Dockerfiles and a docker-compose.yml to orchestrate Next.js, FastAPI, PostgreSQL, and Redis in unison.
