# ResearchMind Deployment Guide

## Local Development

### Prerequisites

- Python 3.9+
- Node.js 20+
- SQLite (default) or PostgreSQL

### Backend

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install ".[dev]"

# Set up environment
cp .env.example .env
# Edit .env with your SECRET_KEY and other settings

# Run migrations
alembic upgrade head

# Start server
uvicorn backend.api.app:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Set up environment
cp .env.example .env.local
# Edit .env.local with NEXT_PUBLIC_API_URL

# Start dev server
npm run dev
```

### Running Tests

```bash
# Backend
python -m pytest backend/api/tests/ -v

# Frontend
cd frontend && npm test

# Build
cd frontend && npm run build
```

---

## Docker Deployment

### Prerequisites

- Docker Engine 24+
- Docker Compose v2+

### Quick Start

```bash
# 1. Clone and enter the repository
cd researchmind

# 2. Create .env file with required secrets
cp .env.example .env
# Edit .env — set SECRET_KEY (min 32 chars)

# 3. Build and start all services
docker compose build
docker compose up -d

# 4. Run database migrations
docker compose exec backend alembic upgrade head

# 5. Verify
curl http://localhost/api/v1/health
# → {"status": "healthy"}
```

The application is now available at:

| Service | URL |
|---------|-----|
| Frontend | http://localhost |
| API | http://localhost/api/v1 |
| API Docs | http://localhost/api/v1/docs |
| GROBID | http://localhost:8070 |

### Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| nginx | nginx:alpine | 80 | Reverse proxy, TLS termination |
| backend | custom | 8000 | FastAPI application |
| frontend | custom | 3000 | Next.js application |
| postgres | postgres:16-alpine | 5432 | Primary database |
| redis | redis:7-alpine | 6379 | Caching, rate limiting, Celery broker |
| grobid | grobid/grobid:0.8.1 | 8070 | PDF extraction (optional) |

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | **Yes** | — | JWT signing key (min 32 chars, use `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `POSTGRES_PASSWORD` | No | `researchmind` | PostgreSQL password |
| `ENVIRONMENT` | No | `development` | `development`, `testing`, `staging`, `production` |
| `CORS_ORIGINS` | No | `http://localhost:3000,http://localhost` | Comma-separated allowed origins |
| `AUTH_COOKIE_SECURE` | No | `false` | Set `true` in production |
| `AUTH_COOKIE_SAMESITE` | No | `lax` | Cookie SameSite policy |
| `NEXT_PUBLIC_API_URL` | No | `http://localhost/api/v1` | Frontend API URL |
| `REDIS_URL` | No | `redis://redis:6379/0` | Redis connection string |
| `RATE_LIMIT_REQUESTS` | No | `1000` | Max requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | No | `60` | Rate limit window |

### Commands

```bash
# Build all images
docker compose build

# Start all services (detached)
docker compose up -d

# View logs
docker compose logs -f

# Stop all services
docker compose down

# Stop and remove volumes
docker compose down -v

# Run backend migrations
docker compose exec backend alembic upgrade head

# Check migration status
docker compose exec backend alembic current

# Access backend shell
docker compose exec backend /bin/bash

# View PostgreSQL logs
docker compose logs -f postgres
```

### Health Checks

| Endpoint | Purpose | Expected Status |
|----------|---------|-----------------|
| `GET /api/v1/health/live` | Liveness probe | `{"status": "alive"}` |
| `GET /api/v1/health/ready` | Readiness probe | `{"status": "ready", "checks": {"database": true, "redis": null, "migration": true}}` |

Docker Compose uses these endpoints for container health checks.

---

## Production Deployment

### Prerequisites

- Domain name with DNS pointing to server
- Docker & Docker Compose
- (Optional) Kubernetes cluster for horizontal scaling

### Steps

1. **Set environment to production**

```bash
ENVIRONMENT=production
```

2. **Configure secrets**

Generate a strong SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Set a strong PostgreSQL password:
```bash
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

3. **Configure TLS**

Add a `nginx-ssl.conf` or use a reverse proxy (Caddy, Traefik) in front of nginx for automatic Let's Encrypt certificates.

4. **Enable cookie security**

```bash
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=lax
```

5. **Set CORS origins**

```bash
CORS_ORIGINS=https://yourdomain.com
```

6. **Start services**

```bash
docker compose up -d
docker compose exec backend alembic upgrade head
```

---

## Upgrade Procedure

1. Pull latest code: `git pull`
2. Rebuild: `docker compose build`
3. Run migrations: `docker compose exec backend alembic upgrade head`
4. Restart: `docker compose up -d --force-recreate`

---

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| Backend won't start | Missing SECRET_KEY | Set `SECRET_KEY` in `.env` |
| Database connection refused | PostgreSQL not ready | Wait or check `docker compose logs postgres` |
| Migration fails | Alembic head mismatch | Run `alembic upgrade head` |
| Frontend shows blank page | `NEXT_PUBLIC_API_URL` wrong | Check frontend env config |
| CORS errors | `CORS_ORIGINS` mismatch | Match frontend URL in CORS_ORIGINS |
| 429 Too Many Requests | Rate limit exceeded | Increase `RATE_LIMIT_REQUESTS` or wait |
| Container exits immediately | Missing env var | Check logs: `docker compose logs <service>` |
