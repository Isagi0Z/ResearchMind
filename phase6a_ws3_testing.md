# WS3 — Testing & Verification Report

## Test Results

| Suite | Tests | Pass | Fail | Pre-existing |
|---|---|---|---|---|
| Entire Frontend | 311 | 309 | 2 | 2 filters-panel |
| Graph (affected) | 4 | 4 | 0 | 0 |
| Corpus Manager (affected) | 9 | 9 | 0 | 0 |
| Filters Panel (affected) | 8 | 8 | 0 | 0 |
| All other test files (27) | — | 288 | 0 | 0 |

## Graph Explorer Test Updates

**File**: `frontend/tests/graph/graph-explorer.test.tsx`

| Test | Before | After | Reason |
|---|---|---|---|
| "shows loading state" | `getByText('Loading graph data...')` | `getByText('Loading...')` | Shared LoadingState uses `sr-only` text |
| "shows error state" | `getByText('Failed to load graph data')` | `getByText('Something went wrong')` | Shared ErrorState uses default title |
| "shows error state" | `getByText('Retry')` | `getByText('Try Again')` | Shared ErrorState uses "Try Again" label |

## Corpus Manager Test Updates

**File**: `frontend/tests/corpus/corpus-manager.test.tsx`

- Added mock for `@/services/jobs` (getJob, listJobs)
- Added mock for `@/features/jobs/use-jobs` (useJobStatus, useJobEvents, useJobList)
- Required because `CorpusManager` now imports `JobProgressPanel`

## Build Verification

```
Route (app)                              Size
┌ ○ /                                    136 B
├ ○ /admin                               5.56 kB
├ ○ /corpus                              17.2 kB
├ ○ /dashboard                           6.46 kB
├ ○ /graph                               60.8 kB
├ ○ /login                               3.58 kB
├ ○ /monitoring                          8.73 kB
├ ○ /query                               8.98 kB
├ ○ /register                            3.54 kB
└ ○ /reviews                             5.81 kB
+ Middleware                             32.2 kB

All 13 routes compiled successfully.
Linting and type checking passed.
```

## Manual Test Scenarios

### Auth Middleware
1. Visit `/dashboard` without auth cookie → redirect to `/login?redirect=/dashboard`
2. Visit `/admin` without auth cookie → redirect to `/login?redirect=/admin`
3. Visit `/admin` with non-admin cookie → redirect to `/dashboard`
4. Visit `/login` with any cookie → pass through
5. Visit `/` → pass through

### Session Restoration
1. Log in → profile persisted to localStorage
2. Refresh page → `useAuth` fetches `/auth/me`, populates store
3. Close and reopen tab → persisted profile loads immediately

### API Error Handling
1. 401 on data fetch → token refresh attempted
2. Refresh fails → redirect to `/login`
3. 403 on admin page → "Access Restricted" shown
4. 429 → specific rate-limit message displayed

### Persistence
1. Collapse sidebar → refresh → sidebar stays collapsed
2. Set corpus filters → navigate away → return → filters preserved
3. Set graph node type filter → refresh → filter preserved
