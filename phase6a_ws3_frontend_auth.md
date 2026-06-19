# WS3 — Frontend Auth Layer & User Experience — Implementation Report

## Summary

Implemented a defense-in-depth authentication and error handling layer for the ResearchMind frontend, covering route protection, session restoration, error boundaries, API error handling, persistent state, admin guards, jobs UI, and loading/empty state standardization.

## Work Items

### WS3-1 — Auth Middleware (`frontend/middleware.ts`)
- **File created**: `frontend/middleware.ts` (32.2 kB compiled)
- **Matcher**: `/((?!_next/static|favicon.ico).*)`
- **Public routes**: `/`, `/login`, `/register`
- **Protected routes**: `/dashboard`, `/query`, `/reviews`, `/graph`, `/corpus`
- **Admin-only routes**: `/admin`, `/monitoring`
- **Mechanism**: Decodes `access_token` cookie JWT payload (base64) to extract `sub` and `role` claims; redirects unauthenticated to `/login?redirect=<path>`; redirects non-admin to `/dashboard`
- **Defense-in-depth**: Middleware is the first gate; server-side API still enforces auth for all endpoints

### WS3-2 — Session Restoration (`frontend/stores/auth-store.ts`, `frontend/features/auth/use-auth.ts`)
- **Auth store**: New Zustand store with `persist` middleware for cross-tab user state
- **Auto-fetch**: `useAuth` hook calls `GET /auth/me` on mount if no cached profile exists
- **Hydration**: `partialize` limits persistence to `user` only (no transient loading state)
- **Dual-mode**: Compatible with existing cookie + Bearer token auth

### WS3-3 — Global Error Boundary (`frontend/components/errors/`)
- **ErrorBoundary**: `React.Component` class-based boundary wrapping `AppShell` in root layout
  - Catches unhandled render errors
  - Shows error reference ID + retry button
  - Accepts optional custom fallback
- **RouteError**: Status-aware error display for 401, 403, 404, 429, 500
  - Action links: "Log In" (401), "Go Back", "Try Again"
  - Used in integrated components

### WS3-4 — API Error Layer (`frontend/lib/api-client.ts`)
- **Centralized error handling**:
  - `ApiError` class with `status` and `message`
  - `ERROR_MESSAGES` map for HTTP status codes (401, 403, 404, 429)
  - Server-side 500 errors masked as generic message
- **Auto-refresh** on 401 (excluding login/refresh endpoints)
  - Queue mode: concurrent requests during refresh are buffered via `refreshSubscribers`
  - Redirects to `/login` on refresh failure
- **Timeout handling**: 30-second `AbortController` with `ApiError(408, ...)`
- **Network error**: Catches `TypeError` with descriptive message

### WS3-5 — Persistent UI State (Zustand persist middleware)
- **ui-store**: Persists `sidebarCollapsed` to `localStorage`
- **corpus-store**: Persists `searchQuery`, `filters`, `sort` across sessions
- **graph-store**: Persists `nodeTypeFilter`
- **auth-store**: Persists `user` profile across sessions
- All use `zustand/middleware/persist` with `partialize` to minimize stored data

### WS3-6 — Admin Route Guards (defense-in-depth)
- **Middleware layer**: `/admin` and `/monitoring` routes require `role === "admin"` (JWT claim)
- **Component layer**: `AdminUsers` and `MonitoringDashboard` check `useAuthStore().isAdmin()` and show access-denied UI when API returns 403
- Both layers handle 401 and 403 with appropriate user-facing messages

### WS3-7 — Jobs UI Integration
- **Dashboard**: Already had `JobHistoryTable` in grid layout (from WS2)
- **Review page**: Added `JobProgressPanel` shown alongside `ReviewProgressTracker` when `review-store.jobId` is set
- **Corpus manager**: Added `JobProgressPanel` wired to `processingJobId` state
- **Review store**: Extended with `jobId`/`setJobId` for async job tracking

### WS3-8 — Loading & Empty State Standardization
- **graph-explorer.tsx**: Replaced local `LoadingState`, `ErrorState`, `EmptyState` functions with shared components (`@/components/shared/`)
- **Graph explorer tests updated**: Assertions changed to match shared component text
- **Corpus-manager tests updated**: Mocked `@/services/jobs` for `JobProgressPanel` compatibility

## Verification Results

| Metric | Result |
|---|---|
| Build (frontend) | 13/13 static routes, middleware compiled (32.2 kB) |
| Frontend tests | 309/311 passing (2 pre-existing filters-panel flaky failures) |
| Backend tests | Not affected (no backend changes) |
| Test files | 30/31 passing |

## Files Changed/Created

| File | Status | Purpose |
|---|---|---|
| `frontend/middleware.ts` | **Created** | Auth middleware with JWT cookie decode |
| `frontend/stores/auth-store.ts` | **Created** | Persistent auth state with session hydration |
| `frontend/features/auth/use-auth.ts` | **Updated** | Auto-fetch profile on mount |
| `frontend/components/errors/ErrorBoundary.tsx` | **Created** | React error boundary |
| `frontend/components/errors/RouteError.tsx` | **Created** | Status-code-aware error display |
| `frontend/lib/api-client.ts` | **Updated** | Centralized error messages, auto-refresh, timeout |
| `frontend/stores/ui-store.ts` | **Updated** | Added persist middleware |
| `frontend/features/corpus/corpus-store.ts` | **Updated** | Added persist middleware |
| `frontend/features/graph/graph-store.ts` | **Updated** | Added persist middleware |
| `frontend/features/review/review-store.ts` | **Updated** | Added `jobId` field |
| `frontend/features/admin/admin-users.tsx` | **Updated** | Admin route guard |
| `frontend/features/monitoring/monitoring-dashboard.tsx` | **Updated** | Admin route guard |
| `frontend/features/corpus/corpus-manager.tsx` | **Updated** | JobProgressPanel integration |
| `frontend/features/review/review-page-client.tsx` | **Updated** | JobProgressPanel integration |
| `frontend/features/graph/graph-explorer.tsx` | **Updated** | Shared LoadingState/ErrorState/EmptyState |
| `frontend/tests/graph/graph-explorer.test.tsx` | **Updated** | Updated assertions for shared components |
| `frontend/tests/corpus/corpus-manager.test.tsx` | **Updated** | Mocked jobs services |

## Risk Assessment

- **Low**: All changes are frontend-only; no backend or engine modifications
- **Low**: Pre-existing test flakiness (filters-panel timeouts) unchanged
- **Low**: Middleware is additive — server-side auth enforcement unchanged
