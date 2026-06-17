# Phase 4D — Determinism Audit Report

**Generated:** 2026-06-16

---

## Audit Scope

Verify that Phase 4D code changes do NOT introduce non-deterministic calls (`uuid4`, `datetime.now()`, `datetime.utcnow()`, `random.*`, `Math.random()`, `crypto.randomUUID()`) into M1–M6 deterministic engine paths.

**Engine paths (strictly monitored):**
- `src/researchmind/query/` (M1–M4)
- `src/researchmind/synthesis/` (M5–M6)

**Non-engine paths (allowed):**
- `backend/api/auth/` — JWT expiry, token creation
- `backend/db/models/` — ORM default UUIDs
- `src/researchmind/corpus/` — data management layer
- `frontend/` — all frontend code (client-side randomness is acceptable)
- Monitoring infrastructure code

---

## Audit Results

### M1–M6 Engine Paths: CLEAN

```
Scan: src/researchmind/query/*.py, src/researchmind/synthesis/*.py
Patterns: uuid4, datetime.now, datetime.utcnow, random.
Result: ZERO violations
```

No Phase 4D changes touch any file in `src/researchmind/query/` or `src/researchmind/synthesis/`.

### Frontend: CLEAN

```
Scan: frontend/app/**/*.tsx, frontend/features/**/*.{ts,tsx}, frontend/lib/*.ts, frontend/services/*.ts
Patterns: Math.random, crypto.randomUUID
Result: ZERO violations
```

### New Phase 4D Files

| File | Non-Deterministic Calls? | Notes |
|------|-------------------------|-------|
| `frontend/features/auth/use-auth.ts` | No | API call hook — no randomness |
| `frontend/features/monitoring/monitoring-dashboard.tsx` | No | Conditional rendering only |
| `frontend/features/monitoring/monitoring-hooks.ts` | No | React Query wrapper |
| `migrations/versions/3a1b2c3d4e5f_add_token_hash_sha256.py` | No | Alembic DDL only |

### Modified Phase 4D Files

| File | Non-Deterministic Calls? | Notes |
|------|-------------------------|-------|
| `backend/db/models/refresh_token.py` | No | ORM column definition |
| `backend/api/auth/security.py` | No | SHA256 is deterministic |
| `backend/api/routes/auth.py` | No | SHA256 lookup replaces bcrypt iteration |
| `backend/api/rate_limiter.py` | No | Pure algorithmic logic |
| `backend/api/middleware.py` | No | Store parameter pass-through |
| `backend/api/config.py` | No | Settings class |
| `backend/api/app.py` | No | Conditional import |
| `backend/api/routes/query.py` | No | Pagination params |
| `backend/api/routes/review.py` | No | Pagination params |
| `frontend/components/layout/app-shell.tsx` | No | Conditional rendering |

---

## Determinism Boundary Map

```
┌───────────────────────────────────────────────────┐
│                   DETERMINISTIC                     │
│  src/researchmind/query/   (M1–M4)                 │
│  src/researchmind/synthesis/ (M5–M6)               │
│                                                     │
│  Phase 4D touches: NONE                             │
└───────────────────────────────────────────────────┘
                        ▲
                        │ (API calls)
                        ▼
┌───────────────────────────────────────────────────┐
│                 NON-DETERMINISTIC                    │
│  (Acceptable / Allowed)                             │
│                                                     │
│  backend/api/auth/     — token expiry timestamps    │
│  backend/db/models/    — ORM UUID defaults          │
│  backend/api/routes/   — request handling           │
│  frontend/             — client-side rendering      │
│  src/researchmind/corpus/ — data management         │
│                                                     │
│  Phase 4D touches: auth routes, rate limiter,       │
│  history pagination, monitoring dashboard, sidebar  │
└───────────────────────────────────────────────────┘
```

---

## Conclusion

**Phase 4D introduces zero determinism violations.** All changes are confined to non-engine paths (auth, API routing, frontend rendering). The M1–M6 engine boundary is fully preserved.
