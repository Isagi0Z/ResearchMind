# Phase 6 — Gap Analysis

**Date:** 2026-06-19
**Branch:** module5-development
**Type:** Read-only gap identification for Phase 6 scope definition

---

## Gap Categories

### 1. Production Infrastructure (CRITICAL)

| # | Gap | Current State | Required State | Impact |
|---|-----|---------------|---------------|--------|
| G1.1 | **No application Dockerfiles** | Only GROBID in docker-compose.yml | Dockerfiles for API, frontend, worker, nginx | Cannot deploy or orchestrate |
| G1.2 | **No CI/CD pipeline** | Zero CI/CD config | GitHub Actions or equivalent for test → build → deploy | Manual deployments, no quality gates |
| G1.3 | **No Kubernetes manifests** | Zero k8s config | Deployments, Services, Ingress, ConfigMaps, Secrets | No horizontal scaling, no self-healing |
| G1.4 | **No reverse proxy / nginx** | No proxy config | nginx or Traefik for TLS termination, static serving, routing | No TLS, no static asset offload |
| G1.5 | **No TLS/HTTPS** | No cert config, no HSTS middleware active | Auto TLS (Let's Encrypt via nginx or cloud LB) | Plaintext in production |
| G1.6 | **No .dockerignore** | Not present | Exclude node_modules, __pycache__, .git, .env | Bloated images, secret leakage risk |

### 2. Background Processing (CRITICAL)

| # | Gap | Current State | Required State | Impact |
|---|-----|---------------|---------------|--------|
| G2.1 | **No task queue** | No Celery, RQ, APScheduler | Celery + Redis/RabbitMQ broker | All processing is synchronous in HTTP requests |
| G2.2 | **No scheduled jobs** | No cron, no periodic tasks | Periodic cleanup (expired tokens, temp files), health reports | Stale data accumulates |
| G2.3 | **No async pipeline execution** | Review generation is synchronous | Pipeline runs as background job with status polling | Long operations block or timeout |
| G2.4 | **No long-running job API** | No job submission/status/cancel | POST /jobs, GET /jobs/{id}, SSE status stream | No user feedback for >30s operations |

### 3. Data & Search (HIGH)

| # | Gap | Current State | Required State | Impact |
|---|-----|---------------|---------------|--------|
| G3.1 | **No full-text search** | SQL ILIKE only on title | Full-text search (PostgreSQL FTS, Elasticsearch, or MeiliSearch) | Cannot search document content |
| G3.2 | **No vector embeddings** | No embeddings, no vector DB | Embedding service + pgvector or Qdrant | No semantic search, no RAG |
| G3.3 | **No RAG (Retrieval-Augmented Generation)** | No chunk retrieval for answers | Retrieve relevant chunks → LLM synthesis with citations | Answers not grounded on actual corpus text |
| G3.4 | **No search relevance ranking** | No ranking, just pagination | BM25/vector hybrid ranking with boosting | Poor search result quality |
| G3.5 | **No document content storage** | Only metadata in corpus_documents | Full text/chunks stored and searchable | Cannot retrieve document content via API |

### 4. Real-time Communication (HIGH)

| # | Gap | Current State | Required State | Impact |
|---|-----|---------------|---------------|--------|
| G4.1 | **No WebSocket support** | No WebSocket in backend | WebSocket endpoint for job progress, monitoring | No live updates, only polling |
| G4.2 | **No Server-Sent Events** | No SSE in backend | SSE stream for job status, notifications | No push mechanism |
| G4.3 | **Frontend polling only** | 10s refetchInterval on monitoring | Real-time updates via WebSocket or SSE | Stale dashboards, unnecessary load |
| G4.4 | **No notification system** | No in-app notifications | Bell icon, notification center, unread count | Users never alerted on completion |

### 5. Collaboration & Multi-User (HIGH)

| # | Gap | Current State | Required State | Impact |
|---|-----|---------------|---------------|--------|
| G5.1 | **No workspace/team model** | Users are isolated | Workspace → Team → Member with roles | No multi-user collaboration |
| G5.2 | **No resource sharing** | Each user sees own data only | Workspace-scoped queries, reviews, documents | No collaborative research |
| G5.3 | **No RBAC beyond admin/user** | Only admin/user roles | Role hierarchy: owner → admin → editor → viewer | No granular permissions |
| G5.4 | **No invite flow** | Admin manually sets roles | Email invitation, accept/decline, token expiry | No self-service onboarding |
| G5.5 | **No audit logging** | Only request-level middleware | per-action audit trail (who, what, when, target) | No compliance, no forensics |

### 6. Frontend Production Readiness (HIGH)

| # | Gap | Current State | Required State | Impact |
|---|-----|---------------|---------------|--------|
| G6.1 | **No route-level auth middleware** | Protected routes accessible by URL | Next.js middleware.ts checks auth, redirects to /login | Any user can navigate to /admin, /monitoring |
| G6.2 | **No SSR/SSG** | All pages client-rendered | Server components where beneficial (public pages, SEO) | Poor initial load, no SEO |
| G6.3 | **No error boundaries** | React errors crash the page | Error boundaries at route/layout level | Brittle UX |
| G6.4 | **No state persistence** | All Zustand stores in-memory | Persist sidebar, filters, auth state (localStorage/indexedDB) | UX resets on every refresh |
| G6.5 | **Empty next.config.ts** | No custom headers, rewrites, redirects | CSP headers, API rewrites, redirect rules | No server-side protection |
| G6.6 | **No PWA capabilities** | No manifest, no service worker | Basic PWA for offline, installable | No offline support |

### 7. Observability (MEDIUM)

| # | Gap | Current State | Required State | Impact |
|---|-----|---------------|---------------|--------|
| G7.1 | **No Prometheus metrics** | No metrics endpoint | /metrics with request count, latency, error rate | No production monitoring |
| G7.2 | **No structured logging** | print() logging | JSON logging with correlation IDs | Cannot aggregate logs |
| G7.3 | **No Sentry/APM** | No error tracking | Sentry for crash reporting, performance tracing | Blind to production errors |
| G7.4 | **No health check endpoint** | /health returns {"status":"healthy"} | Liveness + readiness + dependency probes | No K8s health checks |
| G7.5 | **Diagnostics is unauthenticated** | GET /diagnostics is public | Require admin auth | Data leakage risk |

### 8. Caching & Performance (MEDIUM)

| # | Gap | Current State | Required State | Impact |
|---|-----|---------------|---------------|--------|
| G8.1 | **No Redis data caching** | Redis only for rate limiting | Redis cache for graph, documents, dashboard | Repeated queries hit DB |
| G8.2 | **No HTTP response caching** | No ETags, no Cache-Control | ETag + Cache-Control headers for GET endpoints | Unnecessary data transfer |
| G8.3 | **No query result caching** | Each query re-executes | Cache for identical queries (configurable TTL) | Wasteful for repeated research |
| G8.4 | **No DB query optimization** | No query analysis, no indexes beyond FKs | Missing indexes for monitoring/admin queries | Slow on large datasets |

### 9. Deployment Automation (MEDIUM)

| # | Gap | Current State | Required State | Impact |
|---|-----|---------------|---------------|--------|
| G9.1 | **No init/startup scripts** | Manual uvicorn + npm commands | Start, stop, migrate, seed scripts | Error-prone manual setup |
| G9.2 | **No database backup** | No backup config | Automated PG dump to S3/volume | Data loss risk |
| G9.3 | **No environment promotion** | One .env for everything | Dev/staging/production config separation | Configuration drift |
| G9.4 | **No build automation** | No Makefile or task runner | Unified build/test/deploy commands | Inconsistent local workflows |

### 10. Data Persistence (MEDIUM)

| # | Gap | Current State | Required State | Impact |
|---|-----|---------------|---------------|--------|
| G10.1 | **Corpus is in-memory** | CorpusManager loaded from mock at import | Persist to SQL, lazy-load on demand | Lost on restart |
| G10.2 | **Graph is in-memory** | Grapher builds from in-memory corpus | Graph nodes/edges persisted to SQL tables | Lost on restart |
| G10.3 | **Mock data seed** | generate_mock_documents() at startup | Real PDF ingestion pipeline or DB persistence | No real research data |

### 11. Testing Gaps (LOW)

| # | Gap | Current State | Required State | Impact |
|---|-----|---------------|---------------|--------|
| G11.1 | **4 pre-existing backend test failures** | test_stubs.py event loop issues | Fix or stub correctly | Test CI gate failure |
| G11.2 | **2 pre-existing frontend test timeouts** | filters-panel timeouts | Fix async rendering in tests | Test CI gate failure |
| G11.3 | **No integration test for background jobs** | No async job tests | Test job submission, status, completion | Gap when WS2 is implemented |

---

## Gap Severity Matrix

```
                    PRODUCTION IMPACT
                    Low     Med     High    Critical
EFFORT  Critical    ──      ──      ──      G1.1, G1.2, G1.3
  TO    High        ──      ──      G3.1-5, ──
 IMPL   Medium      G11     G8, G9  G5, G7   G2
        Low         ──      ──      G4, G6  ──
```

## Gap Dependency Graph

```
G1 (Infra) ──→ G9 (Deploy automation)
G2 (Jobs)  ──→ G4 (Real-time) ──→ G6.1 (Frontend middleware)
G3 (Search) ──→ G10 (Persistence)
G5 (Collaboration) ──→ G6.1 (Frontend auth)
G7 (Observability) ──→ G6 (UI polish)
G8 (Caching) ──→ G1.3 (K8s Redis)
```

## Pre-existing Issues (Carried Forward)

| Ref | Description | Since | Impact |
|-----|-------------|-------|--------|
| I1 | test_stubs.py: 4 failures (event loop) | Pre-Phase 4 | Blocks test CI gate |
| I2 | filters-panel timeout: 2 failures (3000ms) | Phase 5C | Blocks test CI gate |
| I3 | next.config.ts empty | Phase 4A | No server-side security headers |
| I4 | No frontend auth middleware | Phase 4D | Unauthenticated users can browse admin/monitoring routes |
| I5 | Diagnostics unauthenticated | Phase 5E | Information disclosure risk |
| I6 | query-provider.tsx has "use shell" typo | Phase 4A | Non-functional (overridden by "use client") |
