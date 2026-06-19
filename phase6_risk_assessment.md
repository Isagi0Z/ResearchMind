# Phase 6 — Pre-Implementation Risk Assessment

**Date:** 2026-06-19  
**Methodology:** Read-only audit of Phase 5E claim accuracy, code review of modified files, live test execution

---

## Risk Register

### R1 — Session-level DB fixture lacks test isolation

| Attribute | Detail |
|-----------|--------|
| **Severity** | MEDIUM |
| **Likelihood** | HIGH |
| **Description** | `conftest.py`'s `setup_database` fixture is session-scoped — it creates tables once before ALL tests and drops them after ALL tests. There is no per-test rollback or truncation. Data created by one test class persists for subsequent test classes. |
| **Evidence** | `backend/api/tests/conftest.py` lines 17-22: `scope="session", autouse=True` — no truncation or rollback logic anywhere. |
| **Risk to Phase 6** | Any Phase 6 feature that creates test data with predictable identifiers must use unique names per class. Tests that assert exact row counts will be brittle. |
| **Mitigation** | Phase 6 test classes should use per-test unique identifiers or implement their own cleanup via `@pytest.fixture(autouse=True)` that truncates relevant tables. |

### R2 — No stale refresh token cleanup

| Attribute | Detail |
|-----------|--------|
| **Severity** | LOW |
| **Likelihood** | MEDIUM |
| **Description** | Refresh tokens are rotated on use (old revoked, new created) but there is NO background task to purge expired/revoked tokens from the `refresh_tokens` table. Over time, the table will accumulate stale rows. |
| **Evidence** | `backend/api/routes/auth.py` lines 122-158: new tokens created, old revoked, but no delete/purge logic. No scheduled task or cron job exists. |
| **Risk to Phase 6** | If Phase 6 adds long-running features or batch operations, the accumulating token table could cause minor storage bloat. Not a functional risk. |
| **Mitigation** | Phase 6 could add a lightweight periodic cleanup (e.g., on app startup or via apscheduler). Not blocking. |

### R3 — No self-protection in admin endpoints

| Attribute | Detail |
|-----------|--------|
| **Severity** | LOW |
| **Likelihood** | LOW |
| **Description** | The admin `PATCH /users/{id}/role` and `PATCH /users/{id}/status` endpoints do not prevent an admin from self-demoting (`role: "user"`) or self-deactivating (`is_active: false`). |
| **Evidence** | `backend/api/routes/admin.py` lines 71-96: no check comparing `current_user.id` to the target `id`. |
| **Risk to Phase 6** | If Phase 6 adds multi-admin workflows, this could allow accidental lockout. Low risk because deactivation still allows re-activation by another admin, and self-demotion to `user` loses admin access but the account still exists. |
| **Mitigation** | Phase 6 could add a guard: `if current_user.id == target_id: raise HTTPException(400, "Cannot modify yourself")`. Non-blocking for Phase 6 entry. |

### R4 — Diagnostics endpoint is unauthenticated

| Attribute | Detail |
|-----------|--------|
| **Severity** | LOW |
| **Likelihood** | LOW (for dev) / MEDIUM (for production) |
| **Description** | `GET /api/v1/diagnostics` exposes config metadata, runtime info, and system state without authentication. In production, this reveals environment details. |
| **Evidence** | `backend/api/routes/diagnostics.py` line 14-15: `@router.get("/diagnostics")` — no `Depends(get_current_user)` or other auth guard. |
| **Risk to Phase 6** | The endpoint intentionally exposes non-secret config (rate limits, token expiry, CORS origins, cookie settings). It does NOT expose SECRET_KEY, DATABASE_URL, passwords, or tokens. Acceptable risk for an internal observability tool. |
| **Mitigation** | Phase 6 should add admin-only auth guard to diagnostics endpoint OR document it as internal-only with a note to restrict in production via reverse proxy (e.g., nginx deny rule). |

### R5 — `test_stubs.py` has 4 pre-existing failures

| Attribute | Detail |
|-----------|--------|
| **Severity** | LOW |
| **Likelihood** | CERTAIN |
| **Description** | 4 tests in `test_stubs.py` fail with `RuntimeError: No current event loop in thread 'MainThread'`. These tests create async event loops incorrectly. Pre-existing and not caused by Phase 5E. |
| **Evidence** | Previous pytest runs: `FAILED backend/api/tests/test_stubs.py::test_monitoring_admin_allowed` (and 3 others). |
| **Risk to Phase 6** | Low. These tests only affect monitoring stub scenarios. They do not block the 187 passing tests or the Phase 5E verification. However, the file was modified (git status shows `M backend/api/tests/test_stubs.py`) suggesting a prior attempt to fix them that didn't resolve the issue. |
| **Mitigation** | Phase 6 could remove or rewrite `test_stubs.py` since all monitoring functionality is now covered by `test_monitoring.py` (20 tests) and `test_integration_e2e_full.py`. |

### R6 — CORS `allow_credentials=True` when origins list contains wildcard

| Attribute | Detail |
|-----------|--------|
| **Severity** | LOW |
| **Likelihood** | LOW |
| **Description** | In `app.py` line 68-76: when `cors_origins_list` is empty, the code falls back to `["*"]`. With `allow_credentials=True`, the combination `*` + credentials is invalid per CORS spec and will be rejected by browsers. However, this fallback only triggers when CORS_ORIGINS is empty (local dev scenario), so the risk is limited. |
| **Evidence** | `backend/api/app.py` lines 68-76: `cors_origins = settings.cors_origins_list if settings.cors_origins_list else ["*"]; allow_credentials=settings.CORS_ALLOW_CREDENTIALS`. With `.env` having `CORS_ORIGINS=http://localhost:3000`, the production path uses explicit origins. |
| **Risk to Phase 6** | Low for dev (CORS_ORIGINS is set in `.env`). `validate_environment()` also warns when CORS_ORIGINS is empty in production. |
| **Mitigation** | Phase 6 could set `allow_credentials=False` when origins is `["*"]`. Non-blocking. |

### R7 — `RateLimitMiddleware` is outermost but reads `request.state` before `RequestContextMiddleware` sets it

| Attribute | Detail |
|-----------|--------|
| **Severity** | LOW |
| **Likelihood** | LOW |
| **Description** | Middleware are executed in reverse order of addition. `RequestContextMiddleware` is added first (innermost), `RateLimitMiddleware` is added after (outermost). When a request comes in, `RateLimitMiddleware` runs first — it reads `request.client.host` but NOT `request.state.request_id`. No actual bug exists because the rate limiter does not use `request.state`. |
| **Evidence** | `backend/api/app.py` lines 48, 58-62, `middleware.py` line 72-75. |
| **Risk to Phase 6** | If Phase 6 adds middleware that depends on `request.state.request_id`, it must be added AFTER `RequestContextMiddleware` (or be added before it but handle the missing state gracefully). |

---

## Overall Risk Summary

| Risk | Severity | Likelihood | Phase 6 Blocking? |
|------|----------|------------|-------------------|
| R1 — No test isolation | MEDIUM | HIGH | ⚠️ Workaround needed |
| R2 — No stale token cleanup | LOW | MEDIUM | ❌ Not blocking |
| R3 — No admin self-protection | LOW | LOW | ❌ Not blocking |
| R4 — Diagnostics unauthenticated | LOW | LOW (dev) | ❌ Not blocking (enhance later) |
| R5 — Pre-existing test failures | LOW | CERTAIN | ❌ Not blocking |
| R6 — CORS wildcard + credentials | LOW | LOW | ❌ Not blocking |
| R7 — Middleware ordering | LOW | LOW | ❌ Informational |

**No blocking risks identified.** Phase 6 may proceed with awareness of R1's workaround requirement.
