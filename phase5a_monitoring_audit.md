# Phase 5A Monitoring Audit — Mock Data Elimination

**Generated:** 2026-06-18

---

## 1. Mock Data Elimination Audit

### Before (Phase 4D)
```python
# backend/api/routes/monitoring.py
from backend.api.mock_graph import generate_mock_monitoring

@router.get("")
async def get_monitoring(...):
    return generate_mock_monitoring(timeRange)   # FAKE DATA
```

### After (Phase 5A)
```python
# backend/api/routes/monitoring.py
from backend.api.services.monitoring_service import MonitoringService

@router.get("")
async def get_monitoring(..., db: AsyncSession = Depends(get_db)):
    service = MonitoringService(db)
    return await service.get_snapshot(timeRange)  # REAL DATA FROM DB
```

## 2. Mock Function Status

| Function | File | Phase 5A Status | Notes |
|----------|------|----------------|-------|
| `generate_mock_monitoring()` | `backend/api/mock_graph.py` | ✅ No longer called from any monitoring route | Still exists for graph module (Phase 5B) |
| `generate_mock_graph()` | `backend/api/mock_graph.py` | ❌ Still used by graph routes | Phase 5B scope |

## 3. Data Source Audit

| Monitoring Field | Source | Deterministic | Real |
|-----------------|--------|---------------|------|
| `id` | `time.time()` | No (timestamp) | N/A (identifier) |
| `health[].status` | Hardcoded "Healthy" | Yes | Yes (API is running) |
| `health[].uptime` | "—" | Yes | Yes (no uptime tracking) |
| `health[].activeThreads` | 0 | Yes | Yes (no thread tracking) |
| `metrics.queriesExecuted` | `COUNT(queries)` | Yes | ✅ REAL |
| `metrics.queriesToday` | `COUNT(queries WHERE created_at >= cutoff)` | Yes | ✅ REAL |
| `metrics.querySuccessRate` | `COUNT(result IS NOT NULL) / COUNT(*)` | Yes | ✅ REAL |
| `metrics.reviewsGenerated` | `COUNT(reviews)` | Yes | ✅ REAL |
| `metrics.reviewsToday` | `COUNT(reviews WHERE created_at >= cutoff)` | Yes | ✅ REAL |
| `metrics.registeredUsers` | `COUNT(users)` | Yes | ✅ REAL |
| `metrics.activeUsers` | `COUNT(users WHERE is_active = true)` | Yes | ✅ REAL |
| `metrics.refreshTokensActive` | `COUNT(refresh_tokens WHERE is_revoked = false)` | Yes | ✅ REAL |
| `metrics.documentsProcessed` | `COUNT(documents)` | Yes | ✅ REAL |
| `charts[].throughput` | `COUNT(queries) per hour` | Yes | ✅ REAL |
| `charts[].latencyMs` | 0.0 | Yes | Yes (unavailable) |
| `charts[].successRate` | `ok/total per hour` | Yes | ✅ REAL |
| `queue` | `[]` | Yes | Yes (no job queue) |
| `recentErrors` | `[]` | Yes | Yes (no error tracking) |
| `corpus.documentCount` | `COUNT(documents)` | Yes | ✅ REAL |
| `corpus.reviewCount` | `COUNT(reviews)` | Yes | ✅ REAL |
| `corpus.authorCount` | 0 | Yes | Yes (unavailable) |
| `corpus.entityCount` | 0 | Yes | Yes (unavailable) |

## 4. Determinism Verification

All real data sources use SQL aggregate functions which are deterministic for identical database states. The only non-deterministic value is `id` (Unix timestamp), which is cosmetic.

M1-M6 engine paths: **NOT TOUCHED**. Determinism fully preserved.

## 5. Unavailable Metrics (Return 0 or Empty)

| Metric | Reason | Future Phase |
|--------|--------|-------------|
| Average response time | No per-query timing | Phase 6+ |
| Ingestion failures | No error tracking in document pipeline | Phase 5C+ |
| API request volume | No request log table | Phase 6+ |
| Rate-limit events | No rate limiter event logging | Phase 6+ |
| Endpoint usage stats | No per-endpoint counters | Phase 6+ |
| Entities resolved | M2 engine not instrumented | Phase 5B+ |
| Graph edges | Graph builder not instrumented | Phase 5B+ |
