# Phase 6A — WS2 Job Architecture

**Date:** 2026-06-19
**Branch:** module5-development
**Phase:** 6A WS2 — Background Jobs & Real-time Progress

---

## Architecture Overview

```
┌─────────────────┐     HTTP (REST)      ┌──────────────────────────┐
│   Frontend      │ ◄────────────────── │   FastAPI (uvicorn)      │
│  (Next.js)      │                     │                          │
│                 │ ◄── SSE stream ──── │  GET /jobs/{id}/events   │
└────────┬────────┘                     │  POST /documents/process │
         │                              │  POST /reviews/generate  │
         │ EventSource                  │    -async                │
         │ (withCredentials)            │  GET /jobs               │
         │                              │  GET /jobs/{id}          │
         ▼                              └──────────┬───────────────┘
┌─────────────────┐                                │
│  Redis Broker   │ ◄──── Celery task ─────────────┘
│  (pub/sub)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Celery Worker   │
│  (separate       │
│   process)       │
└────────┬────────┘
         │
         ├── → PostgreSQL (job status updates via sync SQLAlchemy)
         ├── → ReviewOrchestrator.generate() (sync)
         └── → Document pipeline (sync)
```

---

## Data Flow

### Job Submission (e.g., review generation)

```
1. Client POST /reviews/generate-async { title, type, ... }
2. FastAPI creates Job record (status=queued, progress=0)
3. FastAPI returns { job_id: "uuid", status: "queued" }
4. FastAPI calls generate_review.delay(job_id, payload_json)
5. Celery worker receives task from Redis broker
6. Worker updates Job: status=running, started_at=now
7. Worker executes ReviewOrchestrator.generate()
8. Worker updates progress (0% → 10% → 90% → 100%)
9. Worker updates Job: status=completed, result_reference=result_json
```

### SSE Progress Streaming

```
1. Client opens GET /jobs/{id}/events (with cookie auth)
2. Server verifies job ownership (user_id match or admin)
3. Server polls jobs table every 1 second
4. On status/progress change → emits "progress" event
5. On terminal status (completed/failed) → closes stream
6. Frontend EventSource receives events via "progress" listener
7. Frontend updates JobProgressPanel in real-time
```

---

## Job Model Schema

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `Uuid(as_uuid=True)` | PK, default uuid4 |
| `user_id` | `Uuid(as_uuid=True)` | FK → users.id, CASCADE delete, indexed |
| `job_type` | `String(100)` | NOT NULL (e.g., "review_generation", "document_processing") |
| `status` | `String(20)` | NOT NULL, default "queued", indexed |
| `progress` | `Integer` | default 0 |
| `error_message` | `Text` | nullable |
| `result_reference` | `Text` | nullable (JSON string) |
| `created_at` | `DateTime(tz)` | server_default now() |
| `updated_at` | `DateTime(tz)` | onupdate now() |
| `started_at` | `DateTime(tz)` | nullable |
| `completed_at` | `DateTime(tz)` | nullable |

### Job Status Transitions

```
queued ──→ running ──→ completed
              │
              └──────→ failed
```

---

## Celery Configuration

| Setting | Value |
|---------|-------|
| Broker | Redis (`REDIS_URL` or `CELERY_BROKER_URL`) |
| Result Backend | Redis (`REDIS_URL` or `CELERY_RESULT_BACKEND`) |
| Serializer | JSON |
| Task Acks Late | True |
| Worker Prefetch | 1 |
| Result Expiry | 86400s (24h) |

---

## Auth Enforcement

| Endpoint | Auth | Scoping |
|----------|------|---------|
| `GET /jobs` | `get_current_active_user` | User sees own jobs; admin sees all |
| `GET /jobs/{id}` | `get_current_active_user` | User sees own; admin sees all; 403 for others |
| `GET /jobs/{id}/events` | `get_current_active_user` | Same as above |
| `POST /documents/process` | `get_current_user_optional` | Falls back to ephemeral UUID if unauthenticated |
| `POST /reviews/generate-async` | `get_current_user_optional` | Same fallback |

---

## SSE Event Format

```
event: progress
data: {"status": "running", "progress": 50, "error_message": null}

event: progress
data: {"status": "completed", "progress": 100, "error_message": null}
```

Terminal events: `completed` or `failed` status triggers stream close.
