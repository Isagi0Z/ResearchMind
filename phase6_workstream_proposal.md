# Phase 6 — Workstream Proposal

**Date:** 2026-06-19
**Branch:** module5-development
**Type:** Proposed workstreams for Phase 6 implementation

---

## Summary

**Phase 6** proposes **7 workstreams** organized into **2 delivery waves** (Foundation + Feature). Each workstream addresses gaps identified in `phase6_gap_analysis.md`.

| Wave | Workstream | Gaps | Effort | Risk | Business Value |
|------|-----------|------|--------|------|----------------|
| **Foundation** | WS1 — Production Infrastructure | G1, G9 | XL | Medium | Operational |
| | WS2 — Background Jobs | G2, G4 | L | Low | User experience |
| | WS3 — Frontend Production Readiness | G6 | M | Low | Security, UX |
| **Feature** | WS4 — Data Persistence & Search | G3, G10 | XL | High | Core capability |
| | WS5 — Collaboration & Multi-User | G5 | XL | High | Platform value |
| | WS6 — Caching & Performance | G8 | M | Low | Efficiency |
| | WS7 — Observability & Monitoring | G7 | M | Low | Operational |

---

## WS1 — Production Infrastructure

**Gaps:** G1.1–G1.6, G9.1–G9.4

**Goals:**
1. Containerize the full application stack
2. Implement CI/CD pipeline with test gates
3. Deployable to a single host (Docker Compose) or cluster (K8s)
4. TLS termination via nginx reverse proxy

**Scope:**

| Task | Description | Effort |
|------|-------------|--------|
| 1.1 | Dockerfile for backend: multi-stage, Python 3.11 slim, gunicorn + uvicorn workers | S |
| 1.2 | Dockerfile for frontend: multi-stage, Node → Nginx static build | S |
| 1.3 | docker-compose.yml: API + frontend + nginx + Redis + PostgreSQL | M |
| 1.4 | nginx.conf: TLS termination, static serving, API proxy, rate limiting | M |
| 1.5 | .dockerignore for backend + frontend | S |
| 1.6 | CI/CD (GitHub Actions): lint → test → build → push → deploy | L |
| 1.7 | K8s manifests: Deployments, Services, Ingress, ConfigMap (non-sensitive) | L |
| 1.8 | K8s Secrets management for SECRET_KEY, DB credentials | S |
| 1.9 | K8s Health probes (liveness + readiness) | S |
| 1.10 | Makefile: build, test, migrate, seed, deploy commands | S |
| 1.11 | Database backup script (pg_dump → S3/volume) | S |

**Dependencies:** None (can run in parallel with WS2, WS3)
**Risk:** Medium — Docker/K8s learning curve, CI/CD setup debug time
**Test Strategy:** CI pipeline runs all existing tests before image build

---

## WS2 — Background Jobs

**Gaps:** G2.1–G2.4, G4.1–G4.2

**Goals:**
1. Async task execution for long-running operations (review generation, pipeline execution)
2. Job lifecycle: submit → queued → running → completed/failed
3. Real-time progress updates via SSE or WebSocket

**Scope:**

| Task | Description | Effort |
|------|-------------|--------|
| 2.1 | Celery app setup with Redis broker + result backend | M |
| 2.2 | Queue configuration (default + high + low priority) | S |
| 2.3 | Job model + DB table + Alembic migration | S |
| 2.4 | Job submission endpoint: `POST /api/v1/jobs` | S |
| 2.5 | Job status endpoint: `GET /api/v1/jobs/{id}` | S |
| 2.6 | Job cancellation endpoint: `DELETE /api/v1/jobs/{id}` | S |
| 2.7 | SSE endpoint for job progress stream: `GET /api/v1/jobs/{id}/stream` | M |
| 2.8 | Migrate review generation to async Celery task | M |
| 2.9 | Celery periodic tasks: expired token cleanup, temp file cleanup | S |
| 2.10 | Dockerfile for Celery worker (uses same base as API) | S |
| 2.11 | Frontend: useJobStatus() hook with SSE or polling fallback | M |
| 2.12 | Frontend: job progress UI component (progress bar, stage indicators) | M |
| 2.13 | Integration tests: submit, poll, cancel, error scenarios | M |

**Dependencies:** None (runs alongside WS1)
**Risk:** Low — well-understood pattern, but adds infrastructure dependency (Redis + Celery worker)
**Test Strategy:** Mock Celery in unit tests, integration test with real Redis in CI

---

## WS3 — Frontend Production Readiness

**Gaps:** G6.1–G6.6, G11.2

**Goals:**
1. Route-level auth middleware to protect admin/monitoring routes
2. Error boundaries at page and layout level
3. Persist critical user state across refreshes
4. Fix pre-existing test timeouts

**Scope:**

| Task | Description | Effort |
|------|-------------|--------|
| 3.1 | `middleware.ts` — check access_token cookie, redirect to /login if missing | M |
| 3.2 | `middleware.ts` — role check for admin routes, 403 redirect | M |
| 3.3 | Error boundary component + wrap in root layout and each protected page | S |
| 3.4 | Zustand persist middleware for sidebar collapse, query history (capped) | M |
| 3.5 | Configure `next.config.ts` — CSP headers, API rewrites, redirect rules | S |
| 3.6 | Fix `query-provider.tsx` "use shell" typo | S |
| 3.7 | Fix filters-panel test timeouts (async rendering, act()) | S |
| 3.8 | Optional: basic PWA manifest + service worker for offline fallback | S |

**Dependencies:** None
**Risk:** Low — focused on configuration and component wrapping
**Test Strategy:** Existing tests should pass; add middleware test

---

## WS4 — Data Persistence & Search

**Gaps:** G3.1–G3.5, G10.1–G10.3

**Goals:**
1. Persist corpus documents and graph to SQL tables (no more in-memory mock)
2. Full-text search on document titles and content
3. Vector embeddings for semantic search
4. RAG — retrieve relevant chunks to ground LLM answers

**Scope:**

| Task | Description | Effort |
|------|-------------|--------|
| 4.1 | Document content model + table + migration | M |
| 4.2 | Document chunk model + table + migration | M |
| 4.3 | Graph node/edge model + table + migration | XL |
| 4.4 | Rewrite `_ensure_seeded()` to load from DB instead of mock | M |
| 4.5 | Seed task: import mock corpus into DB (one-time migration) | S |
| 4.6 | Full-text search endpoint: `GET /api/v1/documents/search?q=` | M |
| 4.7 | Embedding service (via google-genai or sentence-transformers) | M |
| 4.8 | pgvector setup + vector column + index (HNSW) | M |
| 4.9 | Semantic search endpoint: `GET /api/v1/documents/semantic?q=` | M |
| 4.10 | RAG pipeline: chunk retrieval → context assembly → LLM synthesis | L |
| 4.11 | Frontend: search results UI (hybrid list, relevance badges, highlighting) | L |
| 4.12 | Frontend: document detail view with content rendering | M |

**Dependencies:** WS1 (Docker for pgvector), WS6 (caching for search)
**Risk:** High — largest scope, touches persistence layer, requires embedding model choices
**Test Strategy:** Test with SQLite for FTS, integration test with PG/pgvector in CI
**Critical Decision:** Choose between Elasticsearch (external dependency) vs PostgreSQL FTS + pgvector (fewer services)

---

## WS5 — Collaboration & Multi-User

**Gaps:** G5.1–G5.5

**Goals:**
1. Workspace/team model for multi-user collaboration
2. Granular RBAC (owner, admin, editor, viewer)
3. Shared resources (queries, reviews, documents within workspace)
4. Audit trail for all state-changing actions

**Scope:**

| Task | Description | Effort |
|------|-------------|--------|
| 5.1 | Workspace model + table + migration | M |
| 5.2 | Team membership model + role + migration | M |
| 5.3 | Workspace-scoped resource access (queries, reviews, documents) | L |
| 5.4 | Invite flow: generate + validate invite token, join workspace | M |
| 5.5 | Audit log model + table + migration | M |
| 5.6 | Audit middleware: log all state-changing requests | M |
| 5.7 | Frontend: workspace switcher + member list + role badges | M |
| 5.8 | Frontend: invite dialog (email, role selector, send) | M |
| 5.9 | Frontend: resource sharing indicators (workspace badges on items) | S |
| 5.10 | Migration: assign existing users to default personal workspace | S |

**Dependencies:** WS3 (frontend auth middleware), WS6 (caching for audit writes)
**Risk:** High — data model changes affect all services, permission checks added everywhere
**Test Strategy:** Comprehensive permission matrix tests (every role × every action)

---

## WS6 — Caching & Performance

**Gaps:** G8.1–G8.4

**Goals:**
1. Redis for data caching (graph, dashboard, documents)
2. HTTP caching (ETags, Cache-Control)
3. Query result caching with TTL
4. Missing DB indexes for monitoring/admin queries

**Scope:**

| Task | Description | Effort |
|------|-------------|--------|
| 6.1 | RedisCacheService: generic async cache with TTL | M |
| 6.2 | Cache decorators: `@cached(ttl=60)` for service methods | S |
| 6.3 | Apply caching to GraphService, DocumentService, MonitoringService, DashboardService | M |
| 6.4 | ETag support on GET endpoints + middleware | M |
| 6.5 | Query result cache: hash query → store/retrieve result | S |
| 6.6 | Cache invalidation on mutations (POST, PATCH, DELETE) | S |
| 6.7 | Add missing DB indexes for admin/monitoring queries | S |
| 6.8 | Performance test suite extension (verify cache reduces latency) | S |

**Dependencies:** WS1 (Docker for Redis)
**Risk:** Low — well-understood pattern, no data model changes
**Test Strategy:** Mock Redis in unit tests, integration test with real Redis in CI

---

## WS7 — Observability & Monitoring

**Gaps:** G7.1–G7.5

**Goals:**
1. Prometheus metrics endpoint for request rate, latency, errors
2. Structured JSON logging with correlation IDs
3. Sentry integration for error tracking and performance tracing
4. Proper health check endpoints (liveness + readiness + dependency status)
5. Secure diagnostics endpoint (admin auth)

**Scope:**

| Task | Description | Effort |
|------|-------------|--------|
| 7.1 | Prometheus metrics: request counter, latency histogram, error counter | M |
| 7.2 | `GET /metrics` endpoint (Prometheus scrape target) | S |
| 7.3 | Structured logging: JSON formatter with request_id, user_id, endpoint | M |
| 7.4 | Sentry SDK integration: FastAPI + Celery + frontend | M |
| 7.5 | Liveness probe: `GET /health/live` (always 200) | S |
| 7.6 | Readiness probe: `GET /health/ready` (DB, Redis, Celery checks) | S |
| 7.7 | Diagnotics: add `require_role("admin")` auth | S |
| 7.8 | Frontend: error tracking wrapper with user feedback | S |

**Dependencies:** WS2 (Celery integration for job tracing)
**Risk:** Low — well-understood libraries and patterns
**Test Strategy:** Integration test health endpoints, metrics endpoint
