# Phase 4B Persistence Architecture Plan

## 1. Current Storage State (Phase 4A)
- **Documents & Corpora**: Relies on InMemoryDocumentStore and mock JSON (ackend/api/mock_data.py).
- **Query & Review State**: Transient. Executed via QueryEngine and ReviewOrchestrator but entirely lost when the API process terminates.
- **Graph State**: Currently using a DummyGraph or transient memory graph, meaning relationships between concepts are not saved.
- **Users**: Non-existent. Handled by a 501-deferred authentication scaffold.

## 2. Target Storage Architecture (Phase 4B)
- **Relational Data (PostgreSQL)**:
  - Users, roles, credentials.
  - Queries (raw inputs, parsed outputs, ownership).
  - Reviews (title, synthesized result, ownership).
  - Corpus/Document metadata (fingerprints, associations, titles).
- **In-Memory / Deterministic Processing**:
  - The actual extraction and reasoning loops (M1-M6 engines) will remain completely isolated and deterministic. They will consume data loaded from PostgreSQL but will not mutate it directly during the algorithmic trace.
  - LLM trace/step states should probably be saved to the database asynchronously or stored as a serialized JSON artifact depending on size.
