# Module 9 Phase 4 Deployment Plan

## Current State Architecture
- Standalone Next.js Node server (
pm run dev/start)
- Standalone Uvicorn FastAPI server (uvicorn)
- In-memory data structures bridging mock LLM behaviors
- Zero security isolation or container orchestration

## Target Production Architecture
1. **Frontend Tier:** Next.js application served via Node.js container, with static assets accelerated by Nginx.
2. **API Tier:** FastAPI running via Gunicorn with Uvicorn workers in a Python container.
3. **Data Tier:** PostgreSQL container for durable state and documents. Redis container for rate limiting and Celery broker.
4. **Worker Tier:** Celery worker container(s) executing Python logic for background LLM processes.
5. **Gateway:** Nginx Reverse Proxy container handling SSL termination, CORS headers, and routing (/ to Frontend, /api/ to Backend).

## Deployment Steps
1. **Containerization:** Author Dockerfile.frontend, Dockerfile.backend, and Dockerfile.worker.
2. **Orchestration:** Create docker-compose.yml defining the network, volumes, and dependencies (Postgres -> Redis -> Backend -> Frontend -> Gateway).
3. **Database Migration:** Implement Alembic and map Pydantic schemas to SQLAlchemy models.
4. **Task Queue Integration:** Rewrite Query/Review endpoints to emit Celery tasks and return Polling IDs.
5. **Security Hardening:** Implement Auth0/JWT middleware and configure CORS inside FastAPI.
6. **CI/CD Pipeline:** Configure GitHub Actions for linting, testing, and Docker image pushing.
