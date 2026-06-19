# WS3 — Architecture & Integration Report

## Auth Architecture

```
Browser Request
    │
    ▼
Next.js Middleware (middleware.ts)
    ├─ Static assets /_next → pass
    ├─ Public routes /, /login, /register → pass
    ├─ Protected routes → check access_token cookie
    │   ├─ Missing → redirect /login?redirect=<path>
    │   └─ Present → decode JWT payload (base64)
    │       ├─ Invalid → redirect /login
    │       ├─ Admin route + role=admin → pass
    │       └─ Admin route + role≠admin → redirect /dashboard
    │
    ▼
Client Component (useAuth → GET /auth/me)
    ├─ Success → store profile in Zustand (persisted)
    └─ Failure → clear store, render RouteError
```

### Defense-in-Depth Layers
1. **Next.js Middleware** — Route-level guard, decodes JWT cookie without crypto
2. **API Server** — Full JWT verification (iss, type, exp, signature) via `require_role`
3. **Component Guards** — `useAuthStore().isAdmin()` check in admin/monitoring components
4. **Error Boundary** — Catches unhandled render errors globally

## Error Handling Architecture

```
API Call
    │
    ▼
handleFetchWithAuth
    ├─ Has access_token? → add Authorization header
    ├─ Timeout (30s) → ApiError(408, "Request timed out")
    ├─ Network error → ApiError(0, "Network error")
    ├─ 401 response → attempt token refresh
    │   ├─ Success → retry original request
    │   └─ Failure → clear tokens, redirect /login
    └─ Non-OK response → ApiError(status, message)
        ├─ 500+ → "An internal server error occurred"
        └─ 401/403/404/429 → mapped message or server detail
```

### Token Refresh Queue
- Only one refresh attempt at a time via `isRefreshing` lock
- Concurrent 401 responses subscribe to `refreshSubscribers` array
- Once refreshed, all queued requests are replayed with new token

## State Persistence Architecture

```
Zustand Store
    │
    ├── use persist() middleware
    │       │
    │       ├── partialize → select fields to save
    │       └── name → localStorage key
    │
    ├── ui-store → "ui-store" → { sidebarCollapsed }
    ├── auth-store → "auth-store" → { user }
    ├── corpus-store → "corpus-store" → { searchQuery, filters, sort }
    └── graph-store → "graph-store" → { nodeTypeFilter }
```

## Data Flow for Jobs UI Integration

```
Review Generator Form          Corpus Manager
        │                           │
        ▼                           ▼
  POST /reviews/generate-async  POST /documents/process
        │                           │
        ▼                           ▼
  JobProgressPanel(jobId)      JobProgressPanel(processingJobId)
        │                           │
        ├── useJobStatus ── useQuery(refetchInterval=2s)
        └── useJobEvents ── EventSource SSE
                │
                ▼
        Dashboard: JobHistoryTable (useJobList, refetchInterval=10s)
```

## Component Dependencies

```
layout.tsx
  └─ ErrorBoundary
       └─ AppShell
            ├─ useAuth → auto-fetch /auth/me
            ├─ Sidebar → useUIStore (persisted collapsed state)
            ├─ Dashboard → JobHistoryTable
            ├─ Reviews → ReviewPageClient → JobProgressPanel
            ├─ Corpus → CorpusManager → JobProgressPanel
            ├─ Graph → GraphExplorer (shared Loading/Error/Empty states)
            ├─ Admin → AdminUsers (admin guard)
            └─ Monitoring → MonitoringDashboard (admin guard)
```
