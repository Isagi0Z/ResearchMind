# Phase 5C Verification Report

## Verification Checklist

### 1. `python -m pytest`
```
189 passed in 86.07s (0:01:26)
```
Result: ✅ All 189 backend tests pass.

### 2. `npm test`
```
290 passed in 66.41s
```
Result: ✅ All 290 frontend tests pass.

### 3. `npm run build`
```
✓ Compiled successfully
✓ Generating static pages (12/12)
```
Result: ✅ Frontend build succeeds. Corpus page: 18.1 kB.

### 4. `alembic current`
```
3a1b2c3d4e5f (head)
```
Result: ✅ Database migrations are current.

## Deliverable Reports

- ✅ `reports/phase5c_implementation_report.md` — Architecture, files changed, data flow
- ✅ `reports/phase5c_documents_audit.md` — Endpoint audit, data correctness, issues fixed
- ✅ `reports/phase5c_test_report.md` — Backend (21 new) + frontend (5 new) test coverage
- ✅ `reports/phase5c_verification_report.md` — This file

## Phase 5C Scope

| Requirement | Status |
|---|---|
| Real document listing (SQLAlchemy) | ✅ Complete |
| Real document detail | ✅ Complete |
| Real search | ✅ ILIKE on title |
| Real sorting | ✅ title, year, status, entity_count — asc/desc |
| Real pagination | ✅ offset/limit via pageIndex/pageSize |
| Real metadata exposure | ✅ typed DocumentListItem/DocumentDetail schemas |
| Frontend loading state | ✅ Skeleton loader (pre-existing) |
| Frontend empty state | ✅ "No documents found" (pre-existing) |
| Frontend error state | ✅ ErrorState with retry (pre-existing) |
| Frontend pagination | ✅ pageIndex/pageSize passed to API |
| Frontend filtering | ✅ searchQuery + sort params sent to API |
| Frontend detail navigation | ✅ `/documents/{ruo_id}` endpoint |
| Backend document tests | ✅ 21 tests |
| Frontend document tests | ✅ 5 tests |
| All existing tests pass | ✅ 189 backend + 290 frontend |
| Build passes | ✅ npm run build |
| Alembic current | ✅ Head |
| Graph unaffected | ✅ Graph tests still pass |
| Monitoring unaffected | ✅ Monitoring tests still pass |
| Auth unaffected | ✅ Auth tests still pass |
| RBAC unaffected | ✅ No RBAC changes |
| Determinism preserved | ✅ Graph node determinism test passes |

## Critical Bug Fixes

1. **`list_all()` called on `DocumentStore` ABC** — This method never existed in the abstract interface. Previous code caught `AttributeError` with a bare `except` and returned empty data. Documents have effectively been returning empty results for all CRUD operations since the ABC was defined. Now they query SQLAlchemy directly.

2. **Frontend search/sort params silently dropped** — `frontend/services/corpus.ts` only serialized `pageIndex` and `pageSize`; `searchQuery`, `sortBy`, and `sortDirection` were defined in the TS interface but never sent to the API. Fixed.

3. **Empty `DocumentService` placeholder** — Was `class DocumentService: pass`. Now implements full document CRUD with DB seeding, search, sort, pagination, and detail merging.
