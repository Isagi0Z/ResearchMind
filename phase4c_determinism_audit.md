# Phase 4C — Determinism Audit

## Audit Scope

Searched for banned non-deterministic calls across all code paths introduced or modified during Phase 4C implementation.

## Banned Patterns

| Pattern | Status |
|---|---|
| `uuid4` | ❌ Banned in M1–M6 engine paths |
| `datetime.now` | ❌ Banned in M1–M6 engine paths |
| `datetime.utcnow` | ❌ Banned in M1–M6 engine paths |
| `random.` | ❌ Banned in M1–M6 engine paths |
| `Math.random` | ❌ Banned in M1–M6 engine paths |
| `crypto.randomUUID` | ❌ Banned in M1–M6 engine paths |

## Results

### M1–M6 Engine Paths (`src/researchmind/query/`, `src/researchmind/synthesis/`)

**ZERO violations.** All engine paths remain deterministic.

| Directory | `uuid4` | `datetime.now` | `random.` | Verdict |
|---|---|---|---|---|
| `src/researchmind/query/` | 0 | 0 | 0 | ✅ Clean |
| `src/researchmind/synthesis/` | 0 | 0 | 0 | ✅ Clean |

### Non-Engine Paths (Allowed)

The following paths use `datetime.now`, `uuid4`, or `time.time()` for legitimate non-deterministic purposes (auth, persistence, metadata, rate limiting):

| File | Pattern | Purpose | Justification |
|---|---|---|---|
| `backend/api/auth/security.py` | `datetime.now(timezone.utc)` | Token expiration | Auth — explicitly excluded |
| `backend/api/routes/auth.py` | `datetime.now(timezone.utc)` | Refresh token expiry check | Auth — explicitly excluded |
| `backend/db/models/*.py` | `uuid.uuid4` | Primary key generation | Persistence — explicitly excluded |
| `backend/api/rate_limiter.py` | `time.time()` | Window boundary calculation | Rate limiting — uses fixed-window `floor division`, deterministic within window |

### New Code Determinism Check

All new Phase 4C code was audited for accidental determinism violations:

| New/Modified File | Lines Changed | Violations | Verdict |
|---|---|---|---|
| `backend/api/rate_limiter.py` | 34 (new) | 0 | ✅ Uses `time.time() // window_seconds` (fixed-window, deterministic per request) |
| `backend/api/middleware.py` | +18 | 0 | ✅ No new non-deterministic calls |
| `backend/api/config.py` | +3 | 0 | ✅ Config only |
| `backend/api/routes/documents.py` | +27 | 0 | ✅ Pure string matching and list sorting |
| `backend/api/routes/query.py` | +29 | 0 | ✅ Added `/history` endpoint — pure DB query |
| `backend/api/routes/review.py` | +23 | 0 | ✅ Added `/history` endpoint — pure DB query |
| `backend/api/routes/graph.py` | +8 | 0 | ✅ Uses existing deterministic mock graph |
| `backend/api/routes/monitoring.py` | +12 | 0 | ✅ Passes through timeRange string to existing deterministic generator |
| `backend/api/routes/dashboard.py` | +28 | 0 | ✅ DB `COUNT(*)` queries only |

## Pre-Existing Non-Deterministic Code (Outside Scope)

The following files in data management layer contain `uuid4`/`datetime.now` calls — these are **outside M1–M6 engine paths** and are explicitly allowed:

- `src/researchmind/corpus/document_relations.py` — 18 calls (relation/evidence ID generation, timestamps)
- `src/researchmind/corpus/entity_resolution.py` — 4 calls (entity cluster ID generation)
- `src/researchmind/corpus/graph.py` — 4 calls (edge ID generation)

These are in the **data management/pipeline layer** and do not affect M1–M6 query/synthesis determinism.

## Verdict

**DETERMINISM MAINTAINED.** No new violations introduced. All Phase 4C changes respect the determinism boundary.
