# Phase 6 — Implementation Roadmap

**Date:** 2026-06-19
**Branch:** module5-development
**Type:** Phased delivery plan for Phase 6 implementation

---

## Delivery Strategy

Phase 6 is organized into **2 waves** with **4 delivery phases** to manage risk and deliver value incrementally:

```
Wave 1 (Foundation) ──→ Wave 2 (Features)
  Phase 6A                Phase 6C
  Phase 6B                Phase 6D
```

| Phase | Workstreams | Duration | Risk | Production Value |
|-------|------------|----------|------|------------------|
| **6A** | WS1 + WS2 + WS3 | 3 weeks | Low | Deployable, background jobs, auth-protected UI |
| **6B** | WS6 + WS7 | 2 weeks | Low | Fast caching, monitoring, metrics |
| **6C** | WS4 | 4 weeks | High | Search, RAG, persistent data |
| **6D** | WS5 | 3 weeks | High | Multi-user collaboration |

**Total estimated duration:** 12 weeks

---

## Phase 6A — Foundation (Weeks 1–3)

**Workstreams:** WS1 (Infrastructure), WS2 (Background Jobs), WS3 (Frontend Readiness)

**Objective:** Make the application deployable, responsive, and secure.

### Week 1 — Containerization & CI/CD (WS1)

| Day | Tasks | Deliverable |
|-----|-------|-------------|
| 1–2 | Backend Dockerfile, .dockerignore | `Dockerfile.backend`, `.dockerignore` |
| 3 | Frontend Dockerfile | `Dockerfile.frontend`, nginx config |
| 4 | docker-compose.yml (API + frontend + nginx + Redis + PG) | `docker-compose.yml` |
| 5 | nginx TLS + reverse proxy | `nginx.conf`, self-signed cert for dev |

### Week 2 — Background Jobs (WS2) + CI/CD

| Day | Tasks | Deliverable |
|-----|-------|-------------|
| 1–2 | Celery app, Redis broker, worker Dockerfile | `celery_app.py`, `Dockerfile.worker` |
| 3 | Job model + migration + submit/status/cancel endpoints | `jobs` table, `routes/jobs.py` |
| 4 | SSE stream endpoint + migrate review gen to Celery | SSE endpoint, review task |
| 5 | GitHub Actions CI: test → build | `.github/workflows/ci.yml` |

### Week 3 — Frontend Readiness (WS3) + Polish

| Day | Tasks | Deliverable |
|-----|-------|-------------|
| 1 | `middleware.ts` auth guards + role checks | `frontend/middleware.ts` |
| 2 | Error boundaries + Zustand persist | Error boundary component, persist config |
| 3 | next.config.ts (CSP, rewrites) + fix typo | Updated config |
| 4 | Fix filter-panel timeout + add middleware test | Passing test suite |
| 5 | Makefile + integration test: full docker-compose up | `Makefile`, CI integration test |

### Phase 6A Exit Criteria

- [ ] `docker-compose up` starts API + frontend + nginx + Redis + PG
- [ ] `npm run build` passes
- [ ] All 187 backend tests + 309 frontend tests pass
- [ ] 22 E2E tests pass against docker-compose stack
- [ ] Celery processes a review generation task
- [ ] Unauthenticated users are redirected from /admin, /monitoring
- [ ] GitHub Actions CI passes

---

## Phase 6B — Performance & Observability (Weeks 4–5)

**Workstreams:** WS6 (Caching), WS7 (Observability)

**Objective:** Make the application observable, fast, and production-monitorable.

### Week 4 — Caching (WS6)

| Day | Tasks | Deliverable |
|-----|-------|-------------|
| 1 | RedisCacheService + `@cached` decorator | `services/cache_service.py` |
| 2 | Cache GraphService + DocumentService | ~50% fewer DB reads |
| 3 | Cache MonitoringService + DashboardService | ~60% fewer DB reads |
| 4 | ETag middleware + query result cache | ETag support, query_cache table |
| 5 | Missing indexes + cache invalidation + perf test update | Index migration, passing perf tests |

### Week 5 — Observability (WS7)

| Day | Tasks | Deliverable |
|-----|-------|-------------|
| 1 | Prometheus metrics middleware + `/metrics` endpoint | Prometheus metrics, prometheus.yml |
| 2 | Structured JSON logging + correlation ID | JSON log output |
| 3 | Sentry SDK (backend + frontend + Celery) | Error reports in Sentry |
| 4 | Health probes (liveness + readiness + dependencies) | `/health/live`, `/health/ready` |
| 5 | Secure diagnostics endpoint + Grafana dashboard (optional) | Admin-only diagnostics, dashboard JSON |

### Phase 6B Exit Criteria

- [ ] Prometheus scrapes `/metrics` successfully
- [ ] Logs are structured JSON with request_id
- [ ] Sentry captures unhandled backend + frontend errors
- [ ] Health probes correctly report DB/Redis/Celery status
- [ ] Diagnostics endpoint returns 401 for non-admin
- [ ] Performance tests show latency improvement from caching

---

## Phase 6C — Search & Persistence (Weeks 6–9)

**Workstreams:** WS4 (Data Persistence & Search)

**Objective:** Real data persistence, full-text search, vector search, and RAG.

### Week 6 — Data Models & Persistence

| Day | Tasks | Deliverable |
|-----|-------|-------------|
| 1–2 | Document content + chunk models + migration | `document_contents`, `document_chunks` tables |
| 3–4 | Graph node/edge models + migration | `graph_nodes`, `graph_edges` tables |
| 5 | Rewrite `_ensure_seeded()` to load from DB | No mock data at startup |

### Week 7 — Full-Text Search

| Day | Tasks | Deliverable |
|-----|-------|-------------|
| 1 | PostgreSQL FTS index setup + GIN index | `fts_index` migration |
| 2 | Search endpoint: `GET /api/v1/documents/search?q=` | `routes/search.py` |
| 3 | Search ranking with ts_rank | Relevance-ordered results |
| 4 | Frontend: search bar + results list + highlighting | UI component |
| 5 | Integration tests + E2E tests | Passing search tests |

### Week 8 — Vector Search & Embeddings

| Day | Tasks | Deliverable |
|-----|-------|-------------|
| 1 | pgvector extension + vector column + HNSW index | Migration |
| 2 | Embedding service (google-genai or sentence-transformers) | `services/embedding_service.py` |
| 3 | Semantic search endpoint | `GET /api/v1/documents/semantic?q=` |
| 4 | Hybrid search (FTS + vector with RRF) | `GET /api/v1/documents/hybrid?q=` |
| 5 | Frontend: semantic search UI (relevance badges, source tabs) | UI component |

### Week 9 — RAG Pipeline

| Day | Tasks | Deliverable |
|-----|-------|-------------|
| 1 | Chunk retrieval service (hybrid search → top-k chunks) | `services/retrieval_service.py` |
| 2 | Context assembly + LLM prompt construction | RAG prompt template |
| 3 | LLM answer synthesis with citations | Grounded answers in `/query/answer` |
| 4 | Frontend: answer citations (chunk reference, highlights) | UI component |
| 5 | Integration tests + E2E tests for search + RAG | Passing tests |

### Phase 6C Exit Criteria

- [ ] All corpus documents persisted in DB (no mock at startup)
- [ ] Graph nodes/edges persisted in SQL tables
- [ ] Full-text search returns relevant results ordered by rank
- [ ] Semantic search returns semantically similar results
- [ ] Hybrid search combines both methods
- [ ] RAG pipeline retrieves chunks and generates cited answers
- [ ] Frontend shows search results with highlighting and citations
- [ ] All existing tests still pass

---

## Phase 6D — Collaboration (Weeks 10–12)

**Workstreams:** WS5 (Collaboration & Multi-User)

**Objective:** Multi-user workspaces, team management, audit trail.

### Week 10 — Workspace & Membership

| Day | Tasks | Deliverable |
|-----|-------|-------------|
| 1–2 | Workspace + team membership models + migration | `workspaces`, `workspace_members` tables |
| 3 | Workspace CRUD + member management endpoints | `routes/workspaces.py` |
| 4 | Migration: create personal workspace for existing users | Data migration |
| 5 | Permission checks on all existing endpoints (scope to workspace) | RBAC middleware update |

### Week 11 — Invite Flow & Audit

| Day | Tasks | Deliverable |
|-----|-------|-------------|
| 1–2 | Invite model + token generation + validate/accept | `routes/invites.py` |
| 3 | Audit log model + middleware | `audit_logs` table, audit middleware |
| 4 | Frontend: workspace switcher, member list, invite dialog | UI components |
| 5 | Frontend: resource sharing indicators, permission-aware UI | UI components |

### Week 12 — Integration & Test

| Day | Tasks | Deliverable |
|-----|-------|-------------|
| 1 | Permission matrix: comprehensive test (every role × action) | Permission test suite |
| 2 | Audit log query UI (frontend) | Audit browser |
| 3 | E2E tests: invite flow, workspace switching, permission denied | E2E test suite |
| 4 | Build + final test pass | Clean CI run |
| 5 | Documentation + rollout plan | ADRs, deployment guide |

### Phase 6D Exit Criteria

- [ ] Workspaces created with members and roles
- [ ] Users can create/join workspaces via invite
- [ ] All resources scoped to workspace (no cross-workspace access)
- [ ] Audit log captures all state-changing actions
- [ ] Permission tests pass for all role × action combinations
- [ ] All 187 backend + 309 frontend tests pass
- [ ] All E2E tests pass (existing + new)
- [ ] Build passes

---

## Rollback Plan (per Phase)

| Phase | Rollback Trigger | Rollback Action |
|-------|-----------------|-----------------|
| 6A | CI fails on Docker/CI changes | `git revert` 6A commits, continue with pre-6A deployment |
| 6B | Caching causes stale data | Disable cache decorators (env flag), revert config |
| 6C | Search degrades query performance | Revert migration, fall back to ILIKE search |
| 6D | Permission model breaks access | Revert workspace migration, restore pre-collab access |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Docker/K8s complexity | Medium | High | Start with docker-compose, defer K8s to post-Phase 6 |
| Embedding model cost/quality | Medium | High | Bench both google-genai and sentence-transformers; configurable |
| pgvector performance on large corpus | Low | High | Test with 10k+ documents; HNSW index; fallback to FTS only |
| Celery infrastructure overhead | Medium | Medium | One extra container; same Redis used for caching |
| Permission model scope creep | Medium | Medium | Focus on workspace isolation first; complex roles deferred |
| Pre-existing test failures block CI | High | Low | Fix or mark expected failures; don't gate CI on them |

---

## Post-Phase 6 Candidates (Deferred)

| Candidate | Reason for Deferral |
|-----------|---------------------|
| Kubernetes production manifests | Complexity; docker-compose sufficient for initial deployment |
| Helm charts | Post-K8s decision |
| Multi-region / HA deployment | Not needed until user base grows |
| SSO / OAuth providers | Auth already functional; defer to user demand |
| Mobile app | Frontend already responsive; native app is future phase |
| Real PDF ingestion pipeline connected to API | Requires M1–M6 integration; post-Phase 6 |
| Advanced analytics / ML insights | Depends on data accumulation |
