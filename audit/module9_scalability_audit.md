# Module 9 Phase 4 Scalability Audit

## Execution Flow Analysis

### Query & Review Execution Flow
- **Bottleneck:** LLM generation workflows (Query/Review) execute inline during the HTTP request lifecycle.
- **Scaling Risk:** High. In a production scenario with real LLM delays, requests will easily exceed typical load balancer timeouts (e.g., 30-60 seconds). This will lead to dropped connections and orphaned backend processes consuming worker threads.
- **Solution:** Asynchronous task queue (Celery + Redis) returning Job IDs, polled by the frontend or pushed via WebSockets.

### Graph Loading Flow
- **Bottleneck:** The /api/v1/graph endpoint currently returns the entire graph payload in a single synchronous response.
- **Scaling Risk:** Critical. Attempting to transmit and render 89,000 nodes and 215,000 edges will exhaust memory on both the backend serializer and the frontend browser (React Flow limits). 
- **Solution:** Implement bounding-box graph queries, Level of Detail (LOD) aggregation, and pagination.

### Monitoring Architecture
- **Bottleneck:** Frontend relies on periodic polling via piClient.get.
- **Scaling Risk:** Medium. With many active users, heavy polling translates to thousands of unnecessary requests.
- **Solution:** Migrate to WebSockets (e.g., FastAPI WebSockets) or Server-Sent Events (SSE) for real-time telemetry updates.
