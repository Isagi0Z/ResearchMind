# Deployment Architecture

## 1. Overview
The ResearchMind production deployment utilizes a containerized microservices architecture orchestrated via Docker Compose for single-node deployments, or Kubernetes for horizontal scaling.

## 2. Infrastructure Components

### A. Reverse Proxy (Nginx)
- **Role:** Handles SSL termination, static asset serving, and request routing.
- **Rules:** 
  - `/*` -> Next.js Frontend
  - `/api/*` -> FastAPI Backend

### B. Frontend (Next.js)
- **Tech:** Node 20 (Alpine)
- **Mode:** Standalone output mode for optimized Docker builds.
- **Scaling:** Stateless. Can be replicated infinitely behind a load balancer.

### C. Backend API (FastAPI)
- **Tech:** Python 3.9 (Uvicorn + Gunicorn)
- **Role:** Handles all web traffic, Auth, and DB reads. Pushes heavy tasks to Redis.
- **Scaling:** Stateless workers.

### D. Task Workers (Celery)
- **Tech:** Python 3.9 (Celery)
- **Role:** Executes M1-M6 logic. Extremely CPU and Memory intensive.
- **Scaling:** Horizontally scaled based on queue depth.

### E. Database (PostgreSQL)
- **Role:** Primary persistence for Corpus Metadata, User Accounts, and Job Statuses.
- **Strategy:** Scheduled pg_dump backups to cold storage (S3).

### F. Message Broker & Cache (Redis)
- **Role:** Celery task broker and high-speed cache for graph sub-queries.

## 3. Deployment Flow (CI/CD)
1. **GitHub Actions:** Triggered on merge to `main`.
2. **Test:** Run Vitest (Frontend) and PyTest (Backend).
3. **Build:** Compile Next.js and build Docker images.
4. **Push:** Images pushed to Docker Hub or AWS ECR.
5. **Deploy:** Webhook triggers `docker compose pull && docker compose up -d` on the production server.

## 4. Security & Monitoring
- **Internal Network:** Database and Redis ports are NOT exposed to the internet. Only Nginx (443) is exposed.
- **Logging:** Docker json-file logging aggregated via Vector or FluentBit.
- **Secrets:** Managed via `.env` files and Docker Swarm/K8s Secrets. Do not commit credentials.
