# Phase 5 — Dependency & Coupling Analysis Report

**Generated:** 2026-06-16

---

## 1. Complete Dependency Map

### 1.1 Auth Dependency Chain
```
LoginPage ──POST──▶ /auth/login
                       │
                  security.py (bcrypt verify + JWT create)
                       │
                  RefreshToken model (INSERT + SHA256 hash)
                       │
                  Response: {access_token, refresh_token}
                       │
                  localStorage (frontend)
                       │
                  api-client.ts (Bearer header on every request)
                       │
                  401 → /auth/refresh → SHA256 lookup → new tokens
```

### 1.2 Query Dependency Chain
```
QueryPage
  ├──▶ POST /query/parse     → QueryParser
  ├──▶ POST /query/plan      → QueryPlanner
  ├──▶ POST /query/route     → StepDispatcher
  ├──▶ POST /query/answer    → QueryEngine → M1-M6 pipeline
  └──▶ GET  /query/history   → DB (Query model, paginated)
```

### 1.3 Review Dependency Chain
```
ReviewsPage
  ├──▶ POST /review/generate → ReviewOrchestrator → M5-M6 synthesis
  ├──▶ POST /review/validate → TraceabilityVerifier → CorpusManager
  └──▶ GET  /review/history  → DB (Review model, paginated)
```

### 1.4 Monitoring Dependency Chain
```
MonitoringDashboard
  ├──▶ useMonitoringData()
  │       └──▶ getMonitoringData() → apiClient.get('/monitoring/metrics')
  │               └──▶ require_role("admin") → mock_graph.generate_mock_monitoring()
  │
  ├──▶ MetricsOverview          (reads data.metrics)
  ├──▶ SystemHealthPanel        (reads data.health)
  ├──▶ PerformanceCharts        (reads data.charts)
  ├──▶ ProcessingQueue          (reads data.queue)
  ├──▶ RecentErrors             (reads data.recentErrors)
  ├──▶ CorpusStatistics         (reads data.corpus)
  └──▶ ModuleMetrics            (reads data.health + data.charts)
```

### 1.5 Graph Dependency Chain
```
GraphPage ──GET──▶ /graph/data  → mock_graph.generate_mock_graph()
                  /graph/node/{id} → DB lookup or 404
```

### 1.6 Document Dependency Chain
```
CorpusPage ──GET──▶ /documents  → CorpusManager.store.list_all()
                    (filter/sort in Python, not SQL)
```

### 1.7 Dashboard Dependency Chain
```
DashboardPage
  ├──▶ GET /dashboard/summary → SELECT COUNT(*) FROM documents, reviews
  ├──▶ GET /dashboard/status  → mock system status
  └──▶ GET /dashboard/recent  → recent docs/reviews from DB
```

---

## 2. Coupling Risk Matrix

| ID | Dependency | Risk Level | Description | Phase 5 Impact |
|----|-----------|------------|-------------|----------------|
| C01 | Monitoring → mock data | **HIGH** | 2 endpoints return `generate_mock_monitoring()` — no real pipeline integration | Blocking — cannot ship monitoring without real data |
| C02 | Graph → mock data | **HIGH** | `/graph/data` returns `generate_mock_graph()` with 1000 deterministic placeholder nodes | Blocking — graph explorer shows fake data |
| C03 | Documents → in-memory filter/sort | **MEDIUM** | All documents fetched then filtered/sorted in Python | Degrades at 10K+ docs |
| C04 | Auth → localStorage tokens | **HIGH** | XSS vulnerability (W8 deferred) | Security blocker for production |
| C05 | Rate limiter → in-memory | **MEDIUM** | Not shared across workers unless Redis configured | Multi-worker deployment requires Redis |
| C06 | Frontend → no error boundaries | **MEDIUM** | No React error boundaries in app-shell or monitoring | Uncaught exceptions could blank-screen |
| C07 | No admin UI → raw SQL only | **HIGH** | No way to promote users to admin without `_make_admin` test helper | Operational blocker |
| C08 | DB → SQLite default | **MEDIUM** | PostgreSQL supported but untested at scale | Production migration required |
| C09 | Refresh token → bcrypt fallback | **LOW** | Logout still iterates tokens for old NULL-hash tokens | Minor — existing tokens rotate on refresh |
| C10 | Monitoring frontend → 11 sub-components | **LOW** | All consume the same `useMonitoringData` hook | Acceptable — React Query deduplicates |

---

## 3. Scalability Bottlenecks

| Bottleneck | Location | Current Limit | Production Target |
|------------|----------|--------------|-------------------|
| DB connection | `db/session.py` | Single SQLite file (1 writer) | PostgreSQL pool (100+ concurrent) |
| Rate limiter | `rate_limiter.py` | Single-process memory | Redis-backed shared counters |
| Documents filter | `routes/documents.py` | In-memory Python sort | SQL WHERE/ORDER BY push-down |
| Refresh token | `routes/auth.py` | SHA256 O(1) lookup | Already optimized in Phase 4D |
| Monitoring data | `mock_graph.py` | Deterministic mock only | Real pipeline metrics |
| Graph data | `mock_graph.py` | Deterministic mock only | Real graph from CorpusManager |
| History | `routes/query.py`, `routes/review.py` | Paginated (200 max) | Acceptable for current scale |

---

## 4. Circular Dependency Check

```
frontend → api ──HTTP──▶ backend
                            ↓
                    researchmind (engine)
                            ↓
                    database (models)
```

No circular dependencies detected. All dependency arrows point in one direction: Frontend → Backend API → ResearchMind Engines → Database. The frontend has no direct dependency on database or engine code.

---

## 5. Third-Party Dependency Summary

| Dependency | Version | Purpose | Risk |
|-----------|---------|---------|------|
| Python 3.9+ | 3.9.13 | Runtime | Low |
| FastAPI | latest | Web framework | Low |
| SQLAlchemy 2.x | latest | ORM | Low |
| Alembic | latest | Migrations | Low |
| PyJWT | latest | JWT | Low |
| passlib[bcrypt] | latest | Password hashing | Low |
| aiosqlite | latest | Async SQLite | Low |
| asyncpg | latest | Async PostgreSQL | Low (unused default) |
| Node.js 18+ | - | Frontend runtime | Low |
| Next.js 15 | 15.1.6 | React framework | Low |
| React Query | latest | Data fetching | Low |
| Zustand | latest | State management | Low |
| Tailwind CSS | latest | Styling | Low |
| Vitest | latest | Testing | Low |
| Playwright ❌ | NOT INSTALLED | E2E testing | **Missing** |

**Critical missing dep:** Playwright/Cypress for E2E tests. No E2E coverage exists.
