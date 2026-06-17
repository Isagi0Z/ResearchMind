# Phase 4C — Risk Register

## Risk Scoring
- **Likelihood:** 1 (Rare) → 5 (Almost Certain)
- **Impact:** 1 (Negligible) → 5 (Catastrophic)
- **Severity:** Likelihood × Impact (1–25)
- **Mitigation Status:** 🟢 Active / 🟡 Monitored / 🔴 Unmitigated

---

| # | Risk Description | Workstream | L | I | S | Mitigation | Status |
|---|---|---|---|---|---|---|---|
| R01 | **Rate limiter introduces non-determinism**: Using wall-clock time in rate limit counters breaks M1–M6 determinism contract. | W1 | 3 | 4 | 12 | Use fixed-window boundaries (floor division by window_seconds), never `time.monotonic()` as primary key. Store counter in `request.state` — no global mutable state. | 🟢 Active |
| R02 | **Rate limiter memory leak**: In-memory per-IP counter map grows unbounded under high load. | W1 | 2 | 3 | 6 | Use LRU cache (e.g., `@lru_cache` or `cachetools.TTLCache`) with max size + TTL eviction. | 🟢 Active |
| R03 | **W2 search/filter on documents causes performance degradation**: `InMemoryDocumentStore.list_all()` returns all 1000 docs, but client-side filtering is O(n) for each request. | W2 | 2 | 2 | 4 | Acceptable at current scale (1000 docs). Document as known limitation; future PostgreSQL migration will move filtering to SQL. | 🟡 Monitored |
| R04 | **W3 history endpoints expose sensitive query/review content**: Users can see other users' data. | W3 | 1 | 5 | 5 | `get_current_active_user` dependency + FK `WHERE user_id = current_user.id` scopes queries. Add test verifying cross-user isolation. | 🟢 Active |
| R05 | **W3 history pagination not implemented server-side**: If W2 also lacks server-side pagination, both workstreams have same pattern gap. | W3 | 1 | 2 | 2 | In-memory pagination is acceptable at current scale. Both use same pattern as W2. | 🟡 Monitored |
| R06 | **W4 RBAC breaks existing optional-auth routes**: Monitoring endpoints currently allow anonymous access; adding `require_role("admin")` makes them 401/403 without login. | W4 | 3 | 3 | 9 | **Breaking change by design** — monitoring is sensitive. Must coordinate with frontend to handle auth errors gracefully (login prompt). | 🟢 Active |
| R07 | **W4 RBAC on query/review write routes breaks anonymous querying**: The entire query flow is currently optional-auth. Making write routes role-protected forces login for querying. | W4 | 4 | 3 | 12 | **Do NOT apply RBAC to query/review write routes.** Keep optional-auth for querying; apply RBAC only to monitoring and future admin routes. | 🟢 Active |
| R08 | **W5 monitoring filter timeRange change breaks frontend**: If timeRange query param is not URL-encoded properly, CRC32 seed derivation may produce unexpected results. | W5 | 1 | 2 | 2 | Frontend already URL-encodes via `URLSearchParams`. Backend seed uses `zlib.crc32(seed_str.encode())`. | 🟡 Monitored |
| R09 | **W6 graph node detail endpoint same ID across requests**: `generate_mock_graph()` uses fixed seed 12345, so the same query always returns the same data — correct by design. | W6 | 1 | 1 | 1 | Determinism is a feature, not a risk here. | 🟡 Monitored |
| R10 | **W7 dashboard real counts from empty DB**: Before any documents/reviews are ingested, SELECT COUNT(*) returns 0 — dashboard shows zero states. | W7 | 2 | 1 | 2 | Frontend already handles zero/loading states via `<EmptyState>`, `<Skeleton>`, `<ErrorState>` components. | 🟡 Monitored |
| R11 | **W8 cookie migration breaks refresh token rotation**: httpOnly cookies cannot be read by JS, so the current subscriber-pattern refresh model must change. | W8 | 4 | 4 | 16 | **Deferred to Phase 5.** Document the cookie-based refresh flow design now; implement only after Phase 4C stabilizes. | 🟢 Active |
| R12 | **Frontend not updated for backend changes**: W2 new query params, W4 RBAC errors, W5 filter support all require frontend changes. | ALL | 4 | 3 | 12 | All frontend services use `apiClient.get<T>()` — backend schema changes propagate naturally. RBAC 401/403 errors already handled by `sanitizeErrorMessage()`. | 🟡 Monitored |
| R13 | **Backend test suite (122 tests) fails after changes**: New functionality breaks existing endpoint behavior. | ALL | 3 | 4 | 12 | Run full `pytest` suite before every commit. Phase 4B remediation confirmed tests pass at baseline `5c0aa94`. | 🟢 Active |
| R14 | **Determinism regression**: A change introduces `uuid4` or `datetime.now()` into an M1–M6 engine path. | ALL | 2 | 5 | 10 | Determinism gate in CI (grep for `uuid4|datetime\.now` in `src/researchmind/query/`, `src/researchmind/synthesis/`). Manual audit before each Phase 4C commit. | 🟢 Active |
| R15 | **Migration conflicts**: If W3 adds queries/reviews tables, but the existing migration (`02cc7a4980ec`) already creates them. | W3 | 1 | 4 | 4 | Tables already exist — W3 only adds **new routes**, not new tables. No migration needed for Phase 4C. | 🟢 Active |

---

## Risk Heatmap

```
Impact →
 5 | R04*  R11*                R14
 4 | R15   R10         R13   R01
 3 | R09        R02  R05  R12
 2 | R08  R03  R07
 1 |      R06
   +───────────────────────────
     1    2    3    4    5  Likelihood →
```

*R04 is low-likelihood because `get_current_active_user` + FK scoping prevents it.
*R11 is high-severity but deferred — no immediate action.

---

## Key Decisions
1. **R07 (RBAC on query routes):** DO NOT apply RBAC to query/review write routes — keep optional-auth. RBAC only on monitoring/admin routes.
2. **R11 (Cookie migration):** DEFERRED to Phase 5. Document design only.
3. **R14 (Determinism):** Add CI grep gate. Non-deterministic calls in `corpus/`, `conversion/` are acceptable (data management layer).
4. **R15 (Migrations):** No new migrations needed for Phase 4C — all tables already exist.

---

## Residual Risk After Mitigation
- **High:** R07 (changing optional-auth to mandatory on wrong routes) — mitigated by design decision to NOT change query/review auth.
- **Medium:** R01 (rate limiter determinism) — mitigated by fixed-window approach.
- **Low:** All other risks are low after mitigation.
- **Deferred:** R11 (cookie security) — carried forward to Phase 5.
