# M7-6 Query Interface Architecture

## 1. Scope
**In Scope:**
- Providing a primary UI for user queries targeting the ResearchMind intelligence pipeline.
- Visualizing responses, evidence extraction traces, and reasoning pathways.
- Categorizing and formatting outputs based on 8 explicit query types.
- Deterministic interaction modeling and mock integrations bridging the frontend to M4 (Reasoning) and M5 (Query System).

**Out of Scope:**
- General chatbot/conversational interfaces (non-deterministic).
- Direct mutation of the underlying corpus/graph.
- Backend prompt execution or LLM integration.

## 2. Query Types
All M5 query types are strictly supported. UX varies based on the type:
- **FACTUAL:** Direct answer prioritized. Small evidence panel.
- **EXPLANATION:** Multi-paragraph answer. Deep reasoning trace heavily featured.
- **COMPARISON:** Side-by-side or tabular result view. Dual evidence chains.
- **CONSENSUS:** High-level summary with weighted source distributions.
- **CONTRADICTION:** Side-by-side conflicting evidence panels. Distinct red/amber highlights.
- **RESEARCH_GAP:** Future-work focused. Low confidence scores highlighted as "unknowns".
- **MULTI_HOP:** Complex reasoning trace viewer prioritized over direct answers.
- **EXPLORATION:** Heavily integrated with Graph Explorer hooks. Suggests related queries.

## 3. UI Screens
### Query Workspace
- **Layout:** Centered or split-pane.
- **Components:** Large `<textarea>`, Query History sidebar, dynamic Query Suggestions based on corpus state.
- **State:** Displays the active M5 `ParsedQuery.type`.

### Results View
- **Layout:** Main content area post-execution.
- **Components:** Answer text block, global confidence dial, execution time metrics, reasoning chain summary.

### Evidence Explorer
- **Layout:** Collapsible side or bottom drawer, or tabbed view.
- **Components:** Source document cards, text excerpts, specific confidence scores, traceability links.

### Reasoning Trace Viewer
- **Layout:** Vertical stepper or tree view.
- **Components:** Step-by-step logic chains from M4.

## 4. Data Model Mapping
- **`ResearchAnswer`**: Core response payload mapped to Results View.
- **`AggregatedEvidence`**: Source arrays mapped to Evidence Explorer.
- **`ReasoningStep`**: Ordered graph mapped to Trace Viewer.
- **`ExecutionPlan`**: Rendered in loading/planning states.
- **`ParsedQuery`**: Defines UI context mode.

## 5. State Management
- **Zustand (`useQueryStore`)**: Manages UI state (`activeQuery`, `selectedEvidence`, `selectedReasoningStep`, `queryHistory`).
- **TanStack Query**: Handles API execution, caching identical queries, and retry logic.

## 6. Loading States
UI features progressive disclosure during loading:
1. *Parsing...* (Analyzing query type)
2. *Planning...* (Building execution graph)
3. *Reasoning...* (Extracting evidence)
4. *Synthesis...* (Formulating response)

## 7. Accessibility
- **WCAG 2.1 AA:** High contrast elements for consensus/contradiction markers.
- **Keyboard Navigation:** Tab-indexing ensures users can jump from Query Input to Results to Evidence easily.
- **Focus Management:** Focus shifts to Results upon execution completion.
- **ARIA:** Live regions announce progressive loading state transitions.

## 8. Performance
- **Targets:** `<250 KB` First-load JS for the route.
- **Virtualization:** Applied to Evidence Panel if evidence count `> 20`.
