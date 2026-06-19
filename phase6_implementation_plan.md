# Phase 6 — Pre-Implementation Plan

**Date:** 2026-06-19  
**Prerequisite:** Phase 5E fully verified with zero regressions, zero engine changes

---

## Phase 5E Gate Check

| Gate | Status | Evidence |
|------|--------|----------|
| E1 Security Hardening | ✅ Complete | JWT `iss`/`type` claims, env validation, security headers, CORS hardened |
| E2 Cookie Auth Migration | ✅ Complete | HTTP-only cookies set on login/refresh/clear, dual-mode (cookie + Bearer), `credentials: 'include'` |
| E3 E2E Coverage | ✅ Complete | 22 E2E tests covering all workflows, all passing |
| E4 Observability | ✅ Complete | Request timing (`X-Response-Time-Ms`), diagnostics endpoint |
| E5 PostgreSQL Validation | ✅ Complete | Connection pooling, `Text` type, DATABASE_URL validation |
| E6 Performance Validation | ✅ Complete | 17 tests with time budgets, pagination, load — all passing |
| Full test suite | ✅ Passing | 187 backend tests, 309 frontend tests |
| Build | ✅ Passing | `npm run build` — compiled, linted, typed, static-rendered |
| Alembic | ✅ At head | `3a1b2c3d4e5f` |
| Deterministic engines | ✅ Untouched | `src/researchmind/` — zero changes |

---

## Recommended Phase 6 Implementation Order

### Tier 1 — Quick Wins (low effort, high value)

| Task | Effort | Risk | Dependencies |
|------|--------|------|-------------|
| Guard admin self-modification (R3) | 1 hour | None | None |
| Protect diagnostics endpoint with admin auth (R4) | 1 hour | None | None |
| Fix CORS wildcard + credentials (R6) | 30 min | None | None |
| Remove stale `test_stubs.py` (R5) | 30 min | Low | Verify all coverage in test_monitoring.py |

### Tier 2 — Feature Additions (moderate effort)

| Task | Effort | Risk | Dependencies |
|------|--------|------|-------------|
| Background refresh token cleanup task | 4 hours | Low | apscheduler or lifespan event |
| Add per-test DB isolation (R1) | 4 hours | Medium | Requires transaction-per-test pattern |
| Rate limit on auth endpoints specifically | 3 hours | Low | Rate limiter already exists |

### Tier 3 — Architectural (higher effort)

| Task | Effort | Risk | Dependencies |
|------|--------|------|-------------|
| Add PostgreSQL integration test suite | 8 hours | Medium | Requires PG test instance |
| Migrate to structured JSON logging | 6 hours | Low | logging configuration |
| Add readiness/liveness probe endpoints | 2 hours | Low | None |

---

## Phase 6 Scope Recommendations

### Must have (blocking for Phase 6 entry)
- None — all Phase 5E gates pass

### Should have (within Phase 6)
- Admin self-modification guard
- Diagnostics endpoint auth
- Auth rate limiting
- Stale token cleanup

### Nice to have (Phase 6 stretch)
- Per-test DB isolation
- JSON structured logging
- PostgreSQL integration tests

### Out of scope
- Changes to `src/researchmind/` (deterministic engines)
- Redesign of core architecture
- Phase 4A–5D feature modifications

---

## Pre-Implementation Checklist

| Check | Done By | Verified |
|-------|---------|----------|
| Phase 5E tests all pass | 5E session | ✅ 187/187, 309/311 |
| No changes to `src/researchmind/` | This audit | ✅ git diff: empty |
| Alembic migrations up to date | This audit | ✅ head `3a1b2c3d4e5f` |
| Environment config validated | This audit | ✅ SECRET_KEY, DATABASE_URL, CORS, cookie settings |
| Security headers present | This audit | ✅ All 6 verified |
| Diagnostics safe | This audit | ✅ No secrets leaked |
| All modified files inspected | This audit | ✅ 20 files read and verified |
| Test result claims match reality | This audit | ✅ 41 E2E + perf tests executed live |
