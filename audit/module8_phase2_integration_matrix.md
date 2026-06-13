# Integration Matrix

| Endpoint          | Backend Class      | Status    |
| ----------------- | ------------------ | --------- |
| /query/parse      | QueryParser        | NOT FOUND |
| /query/plan       | QueryPlanner       | NOT FOUND |
| /query/route      | StepDispatcher     | NOT FOUND |
| /query/answer     | QueryEngine        | NOT FOUND |
| /reviews/generate | ReviewOrchestrator | NOT FOUND |
| /reviews/validate | TraceabilityVerifier| NOT FOUND |
| /graph/summary    | CorpusGraphResult  | NOT FOUND |
| /documents        | CorpusManager      | NOT FOUND |

## Gap Analysis

### Missing Files
- Entire Python packages are absent: `researchmind.query`, `researchmind.reasoning`, `researchmind.synthesis`.

### Missing Classes
- `QueryParser`, `QueryPlanner`, `StepDispatcher`, `QueryEngine`, `ReviewOrchestrator`, `TraceabilityVerifier`, `CorpusGraphResult`, `CorpusManager`.

### Missing Imports
- `from researchmind.query import QueryParser`
- `from researchmind.synthesis import ReviewOrchestrator`
- `from researchmind.corpus import CorpusManager` (the existing corpus module contains `graph.py` and `document_relations.py`, but not `CorpusManager` or `CorpusGraphResult`).

### Required Remediation
- The backend implementation for M4 (Reasoning), M5 (Query), and M6 (Synthesis) must be fully developed or restored into `src/researchmind` before the FastAPI API Contract layer can be built. 
- Furthermore, classes mapped for M3 (Graph) and M1 (Documents) like `CorpusGraphResult` and `CorpusManager` do not exist in the source code.
- **Proceed Status:** DO NOT PROCEED. The implementation condition ("At least one of M1–M6 implementations are present / Existing implementation locations are identified") is violated because the exact mapping targets do not exist. Per constraints, we cannot build mock adapters.
