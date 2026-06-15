# Module 8 Phase 3A — Implementation Report

## Objective
Wire the Query Interface and Review Generator frontend screens to their real FastAPI backend endpoints, replacing the deterministic mock services.

## Scope
- **In Scope:** Query Interface, Review Generator
- **Out of Scope (unchanged):** Dashboard, Corpus Manager, Graph Explorer, Monitoring

## Changes Summary

### Files Modified (6)
| File | Change |
|------|--------|
| `frontend/lib/api-client.ts` | Implemented real `fetch`-based HTTP client with `ApiError` class and typed `post<T>()` method targeting `http://localhost:8000` |
| `frontend/features/query/query-workspace.tsx` | Replaced mock `generateMockAnswer()` with async `generateAnswer()` + try/catch error handling |
| `frontend/features/query/query-suggestions.tsx` | Updated import from `mock-query` → `query` |
| `frontend/features/review/review-generator-form.tsx` | Replaced sync `generateMockReview()` with async `generateReview()` + try/catch error handling |
| `frontend/features/review/review-export-panel.tsx` | Updated import from `mock-review` → `review` |
| `frontend/tests/query/query-suggestions.test.tsx` | Updated import from `mock-query` → `query` |

### Files Added (3)
| File | Purpose |
|------|---------|
| `frontend/services/query.ts` | Real API service: `generateAnswer()` calls `POST /api/v1/query/answer`, `determineQueryType()` and `MOCK_QUERY_SUGGESTIONS` preserved |
| `frontend/services/review.ts` | Real API service: `generateReview()` calls `POST /api/v1/reviews/generate`, `exportReviewToMarkdown()` preserved |
| `frontend/tests/query/query.test.ts` | Updated test suite mocking `apiClient.post` to validate service layer |

### Files Deleted (3)
| File | Reason |
|------|--------|
| `frontend/services/mock-query.ts` | Replaced by `query.ts` |
| `frontend/services/mock-review.ts` | Replaced by `review.ts` |
| `frontend/tests/query/mock-query.test.ts` | Replaced by `query.test.ts` |

## Architecture Decisions

1. **Single `/answer` endpoint:** Rather than orchestrating 4 sequential calls (`/parse` → `/plan` → `/route` → `/answer`), the frontend calls the composite `/answer` endpoint which internally executes the full pipeline and returns the merged result. This minimizes latency and simplifies the UI state machine.

2. **Response mapping layer:** The `query.ts` and `review.ts` services contain thin mapping functions that translate backend snake_case Pydantic response shapes into the frontend's camelCase TypeScript interfaces. No backend contracts were modified.

3. **Error handling:** Both `query-workspace.tsx` and `review-generator-form.tsx` now wrap API calls in try/catch blocks and transition to a `failed` execution state on error, rather than silently succeeding.

4. **Mock services preserved for M1-M4:** Dashboard, Corpus, Graph, and Monitoring continue using their existing deterministic mock services since their backend endpoints return `501 Not Implemented`.

## Commit
```
40d6b5c feat(m8-phase3a): wire Query and Review frontend to FastAPI backend
```
