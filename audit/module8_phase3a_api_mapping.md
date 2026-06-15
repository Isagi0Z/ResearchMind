# Module 8 Phase 3A — API Mapping

## Query Interface

| Frontend Function | HTTP Method | Backend Endpoint | Request Schema | Response Mapping |
|---|---|---|---|---|
| `generateAnswer(queryText)` | POST | `/api/v1/query/answer` | `{ "query_id": string, "raw_query": string }` | Maps `response.answer` → `ResearchAnswer`, `response.evidence` → `AggregatedEvidence[]`, `response.step_route.steps` → `ReasoningStep[]` |
| `determineQueryType(text)` | N/A (local) | — | — | Pure client-side heuristic classification; no backend call |
| `MOCK_QUERY_SUGGESTIONS` | N/A (local) | — | — | Static array of `ParsedQuery` objects; no backend call |

### Query Response Field Mapping

| Backend Field (snake_case) | Frontend Field (camelCase) | Type |
|---|---|---|
| `response.answer.query_id` | `queryId` | string |
| `response.answer.text` | `text` | string |
| `response.answer.confidence` | `confidence` | number |
| `response.answer.metrics.execution_time_ms` | `metrics.executionTimeMs` | number |
| `response.evidence[].evidence_id` | `evidence[].id` | string |
| `response.evidence[].source_doc_id` | `evidence[].sourceDocId` | string |
| `response.evidence[].source_title` | `evidence[].sourceTitle` | string |
| `response.evidence[].excerpt` | `evidence[].excerpt` | string |
| `response.evidence[].confidence` | `evidence[].confidence` | number |
| `response.step_route.steps[].step_id` | `traces[].id` | string |
| `response.step_route.steps[].order` | `traces[].order` | number |
| `response.step_route.steps[].description` | `traces[].description` | string |
| `response.step_route.steps[].confidence` | `traces[].confidence` | number |
| `response.step_route.steps[].path_id` | `traces[].pathId` | string |

---

## Review Generator

| Frontend Function | HTTP Method | Backend Endpoint | Request Schema | Response Mapping |
|---|---|---|---|---|
| `generateReview(request)` | POST | `/api/v1/reviews/generate` | `{ "review_id": string, "topic": string, "review_type": string, "target_entities": string[], "document_scope": string[] }` | Maps `response.review_result` → `ReviewResult` |
| `exportReviewToMarkdown(result)` | N/A (local) | — | — | Pure client-side markdown serializer; no backend call |

### Review Response Field Mapping

| Backend Field (snake_case) | Frontend Field (camelCase) | Type |
|---|---|---|
| `review_result.review_id` | `id` | string |
| `review_result.abstract` | `abstract` | string |
| `review_result.confidence` | `metadata.confidence` | number |
| `review_result.total_findings` | `metadata.findingsCount` | number |
| `review_result.total_evidence_items` | `metadata.evidenceCount` | number |
| `review_result.sections[].section_id` | `sections[].id` | string |
| `review_result.sections[].title` | `sections[].title` | string |
| `review_result.sections[].content` | `sections[].content` | string |
| `review_result.findings[].finding_id` | `findings[].id` | string |
| `review_result.findings[].finding_type` | `findings[].type` | string |
| `review_result.findings[].statement` | `findings[].statement` | string |
| `review_result.findings[].confidence` | `findings[].confidence` | number |

---

## Unchanged Services (Mock Retained)

| Service | Reason |
|---|---|
| `frontend/services/mock-dashboard.ts` | Backend `/api/v1/dashboard` returns 501 |
| `frontend/services/mock-corpus.ts` | Backend `/api/v1/documents` returns 501 |
| `frontend/services/mock-graph.ts` | Backend `/api/v1/graph` returns 501 |
| `frontend/services/mock-monitoring.ts` | Backend `/api/v1/monitoring` returns 501 |
