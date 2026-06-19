# Phase 6 — Architecture Review

**Date:** 2026-06-19
**Branch:** module5-development
**Type:** Read-only architecture and scope definition (no modifications)

---

## Completed Architecture (Phases 4A–5E)

### Backend (FastAPI / Python)

| Layer | Technology | Status | Notes |
|-------|-----------|--------|-------|
| Framework | FastAPI + Uvicorn | ✅ Production | 10 route modules, 5 exception handlers |
| Config | pydantic-settings v2 | ✅ Production | Env validation, production guard |
| Auth | JWT (python-jose, HS256) | ✅ Production | iss/type claims, dual-mode (cookie + Bearer) |
| DB | SQLAlchemy 2.0 async | ✅ Production | AsyncSession, PG connection pooling |
| Migrations | Alembic | ✅ Production | 2 migrations (init + token_hash_sha256) |
| Rate Limiting | In-memory + Redis fallback | ✅ Production | MemoryCounterStore + RedisCounterStore |
| Middleware | RequestContext, SecurityHeaders, RateLimit, RequestSize | ✅ Production | Full stack |
| Docs/Graph Services | DocumentService, GraphService | ✅ Production | SQL-backed with CorpusManager seeding |
| Admin | AdminService + 4 endpoints | ✅ Production | require_role("admin") |
| Monitoring | MonitoringService + 2 endpoints | ✅ Production | Admin-only, SQL aggregation |
| Diagnostics | GET /diagnostics | ✅ Present | **Unauthenticated** — flagged for Phase 6 |

### Frontend (Next.js 15 / React 19)

| Layer | Technology | Status | Notes |
|-------|-----------|--------|-------|
| Framework | Next.js 15.1.6 App Router | ✅ Production | 11 routes |
| State (Server) | TanStack Query v5 | ✅ Production | 8 query hooks across features |
| State (Client) | Zustand v5 | ✅ Production | 6 stores (no persistence) |
| UI | shadcn/ui + Radix + Tailwind v4 | ✅ Production | 18 UI components |
| Auth | Bearer token + cookie | ✅ Production | `credentials: 'include'`, `postForm()` |
| Graph | @xyflow/react (ReactFlow) | ✅ Production | Read-only, 4 custom node types |
| Virtualization | @tanstack/react-virtual | ✅ Production | Corpus document list |
| API Client | Custom fetch wrapper | ✅ Production | Token refresh queue, 30s timeout |

### Engines (src/researchmind — UNCHANGED)

| Module | Purpose | Status |
|--------|---------|--------|
| M1 — Intake | PDF fingerprinting, route classification | ✅ Completed |
| M2 — Extraction | GROBID, PyMuPDF, OCR, TEI parsing | ✅ Completed |
| M3 — Structuring | Section normalization, chunking, citation linking | ✅ Completed |
| M4 — Enrichment | NER, claim detection, LLM fallback | ✅ Completed |
| M5 — Understanding | Fact extraction, triple extraction, KG construction | ✅ Completed |
| M6 — Synthesis | Evidence collection, finding gen, confidence, traceability | ✅ Completed |
| Query | Parser, planner, router, aggregator, synthesizer | ✅ Completed |
| Reasoning | Multi-hop, consensus, contradiction, gaps | ✅ Completed |
| Corpus | Entity resolution, document relations, graph | ✅ Completed |
| Storage | SQLite registry, document store (file-based) | ✅ Completed |
| Quality | Confidence scoring, validation | ✅ Completed |

### Testing

| Category | Count | Status |
|----------|-------|--------|
| Backend unit + integration | 187 | ✅ Passing (4 pre-existing stub failures excluded) |
| Frontend unit + component | 309 | ✅ Passing (2 pre-existing timeouts excluded) |
| E2E | 22 | ✅ Added Phase 5E |
| Performance | 17 | ✅ Added Phase 5E |
| Build (npm run build) | — | ✅ Compiled, linted, typed, 11 routes |

---

## Current Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                           Browser                                  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Next.js App (11 routes)                                    │  │
│  │  ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌───────────────┐   │  │
│  │  │ /login  │ │/dashboard│ │ /query  │ │ /admin        │   │  │
│  │  │/register│ │ /corpus  │ │/reviews │ │ /monitoring   │   │  │
│  │  │         │ │ /graph   │ │         │ │               │   │  │
│  │  └─────────┘ └──────────┘ └─────────┘ └───────────────┘   │  │
│  │                                                              │  │
│  │  ┌────────────────────────────────────────────────────────┐  │  │
│  │  │  Zustand (6 stores)   │  TanStack Query (8 hooks)     │  │  │
│  │  └────────────────────────────────────────────────────────┘  │  │
│  │                                                              │  │
│  │  ┌────────────────────────────────────────────────────────┐  │  │
│  │  │  api-client.ts (cookie + Bearer, token refresh queue)  │  │  │
│  │  └────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┬──────────────────────────────────┘
                                  │ HTTP (REST JSON)
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│  FastAPI App (uvicorn)                                            │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Middleware (order): CORS → SecurityHeaders → RequestSize    │  │
│  │  → RateLimit → RequestContext                                │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌─────────┐ ┌──────┐ ┌───────┐ ┌────────┐ ┌─────────┐ ┌─────┐  │
│  │ /health │ │/auth │ │ /query│ │/reviews│ │ /graph  │ │/docs │  │
│  └─────────┘ └──────┘ └───────┘ └────────┘ └─────────┘ └─────┘  │
│              ┌────────┐ ┌────────────┐ ┌───────┐ ┌───────────┐  │
│              │/monitor│ │  /admin    │ │/dash  │ │/diagnostics│  │
│              └────────┘ └────────────┘ └───────┘ └───────────┘  │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Dependencies (module-level singletons)                      │  │
│  │  CorpusManager ─┐   ┌─ QueryEngine (Parser/Planner/Dispatcher)│ │
│  │                 ├──→┤─ ReviewOrchestrator                     │  │
│  │  Grapher ───────┘   └─ TraceabilityVerifier                  │  │
│  │  MockData ───→ CorpusManager.from_documents()                │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Services                                                    │  │
│  │  AdminService(db)  │  DocumentService(db, corpus)             │  │
│  │  GraphService(corpus)  │  MonitoringService(db)              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  DB Models: User, Query, Review, Document, RefreshToken,     │  │
│  │  CorpusDocument                                              │  │
│  │  Engine: AsyncSession (SQLite dev / PostgreSQL prod)         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────┐
│  src/researchmind (M1–M6 deterministic engines — READ-ONLY)        │
│  ┌───────┐ ┌────────┐ ┌─────────┐ ┌──────────┐ ┌──┐ ┌──────────┐ │
│  │ Intake│ │Extract │ │Structure│ │ Enrich   │ │...│ │ Synthesis│ │
│  │ (M1)  │ │ (M2)   │ │ (M3)    │ │ (M4)     │ │   │ │ (M6)     │ │
│  └───────┘ └────────┘ └─────────┘ └──────────┘ └──┘ └──────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────────┐  │
│  │Query     │ │Reasoning │ │Corpus    │ │Storage (file + SQL) │  │
│  └──────────┘ └──────────┘ └──────────┘ └─────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

---

## Architecture Constraints (Must Preserve)

1. **M1–M6 engines are immutable** — no modifications to `src/researchmind/`
2. **Deterministic pipeline** — all engines produce consistent output for same input
3. **Auth/RBAC intact** — JWT, cookie dual-mode, admin/user roles
4. **Testing baseline** — all existing tests must continue to pass
5. **Alembic at head** — no migration changes without migration
6. **No mock seeds in production** — CorpusManager mock data is dev-only
7. **API backward compatibility** — existing endpoints must not change signatures
