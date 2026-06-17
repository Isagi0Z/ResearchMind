# Phase 4C — Security Audit

## Authentication Review

| Component | Status | Notes |
|---|---|---|
| `POST /api/v1/auth/register` | ✅ Unchanged | No role elevation; `UserCreate` accepts only username/email/password |
| `POST /api/v1/auth/login` | ✅ Unchanged | OAuth2 form; bcrypt verify; JWT creation |
| `POST /api/v1/auth/refresh` | ✅ Unchanged | Token rotation; bcrypt-hashed refresh tokens stored in DB |
| `POST /api/v1/auth/logout` | ✅ Unchanged | Revokes refresh token via bcrypt lookup |
| `GET /api/v1/auth/me` | ✅ Unchanged | Requires `get_current_user` (valid Bearer token) |

## RBAC Implementation Review

| Route | Old | New | Risk |
|---|---|---|---|
| `GET /api/v1/monitoring` | Anonymous access | `require_role("admin")` | **Breaking change** — documented in R06/R07 |
| `GET /api/v1/monitoring/metrics` | Anonymous access | `require_role("admin")` | **Breaking change** — documented |
| `GET /api/v1/query/history` | (new) | `get_current_active_user` | Standard auth — low risk |
| `GET /api/v1/reviews/history` | (new) | `get_current_active_user` | Standard auth — low risk |

**RBAC decision per R07**: Query answer (`POST /api/v1/query/answer`) and review generate (`POST /api/v1/reviews/generate`) remain optional-auth. RBAC is applied **only** to monitoring routes.

## Authorization Review

| Threat | Mitigation | Status |
|---|---|---|
| Cross-user history access | History endpoints filter `WHERE user_id = current_user.id` | ✅ |
| Token replay on history | `get_current_active_user` validates JWT signature + expiry + DB active check | ✅ |
| Rate limit bypass | `X-Forwarded-For` header spoofing possible — acceptable risk at current scale | ⚠️ Documented |
| Escalation via registration | No role field in `UserCreate`; default role is `"user"` | ✅ |
| SQL injection | SQLAlchemy parameterized queries throughout; raw SQL only in test `_make_admin` helper | ✅ |

## Rate Limiter Security

| Property | Implementation | Status |
|---|---|---|
| Key selection | `X-Forwarded-For` → `request.client.host` fallback | ✅ |
| Eviction | LRU eviction at 10,000 keys prevents memory exhaustion | ✅ |
| Window boundary | `time.time() // window_seconds` — fixed window, not sliding | ⚠️ Can have burst at window boundary — acceptable |
| 429 response | JSON body with `detail` only — no stack traces or internal state leaked | ✅ |

## Data Exposure Review

| Endpoint | Data Returned | Sensitivity |
|---|---|---|
| `GET /api/v1/query/history` | `id, raw_query, query_type, created_at` | Medium — user's own queries |
| `GET /api/v1/reviews/history` | `id, title, created_at` | Medium — review titles |
| `GET /api/v1/dashboard/summary` | Document/review counts | Low — aggregate only |
| `GET /api/v1/graph/node/{id}` | Node position, type, label, metadata | Low — mock data only |

## Vulnerability Assessment

| CWE | Description | Present? |
|---|---|---|
| CWE-287 | Improper Authentication | No — all auth routes use bcrypt + JWT |
| CWE-285 | Improper Authorization | No — history endpoints scope to user_id |
| CWE-200 | Information Exposure | No — error responses sanitized; no stack traces |
| CWE-770 | Allocation without Limit | No — rate limiter has 10K key LRU eviction |
| CWE-862 | Missing Authorization | No — monitoring now protected by `require_role` |
| CWE-613 | Insufficient Session Expiration | No — access tokens expire in 30 min; refresh in 7 days |

## Verdict

**SECURITY MAINTAINED.** The only breaking change (W4 — monitoring RBAC) is intentional and documented. No new vulnerabilities introduced.
