# M7-5 Graph Explorer Roadmap

## Phases

### Phase 1: Core Scaffolding & State
- **Goal:** Install React Flow, set up the base routing, and configure the Zustand graph store.
- **Tasks:**
  - Initialize `/app/graph/page.tsx` and register it in AppShell.
  - Build `graph-store.ts` handling selected nodes, viewport state, and expanded clusters.
  - Define strict TypeScript interfaces for deterministic graph payloads (`GraphNode`, `GraphEdge`).

### Phase 2: Deterministic Mock Data Generation
- **Goal:** Create a 5,000-node graph dataset without non-deterministic generation.
- **Tasks:**
  - Build `services/mock-graph.ts` utilizing an LCG algorithm.
  - Generate hierarchical clusters spanning Tier 1 (500 nodes) to Tier 2 (3000 nodes).
  - Pre-calculate deterministic `x,y` coordinates to bypass dynamic physics layout during hydration.

### Phase 3: Graph Visualization Engine
- **Goal:** Render the graph with custom React Flow nodes.
- **Tasks:**
  - Implement `<DocumentNode />`, `<EntityNode />`, `<ClusterNode />`.
  - Implement custom edge rendering (e.g., `<ContradictsEdge />` in red, `<SupportsEdge />` in green).
  - Add viewport controls (MiniMap, Zoom, Fit View).

### Phase 4: Interaction & Accessibility Layer
- **Goal:** Enable traversal and details inspection.
- **Tasks:**
  - Build `<GraphSidebar />` to show selected node/edge details.
  - Implement keyboard adjacency traversal (Arrow keys shifting focus across edges).
  - Build the screen-reader `aria-live` announcement system.

### Phase 5: Search & Filtering
- **Goal:** Cluster-aware client-side search.
- **Tasks:**
  - Implement the search toolbar.
  - Implement visual highlighting (dimming non-matching nodes, pulsing clusters containing matches).

## Dependencies
- `@xyflow/react` (React Flow)
- `d3-force` or `dagre` (Optional: only if offline deterministic layout calculation is needed prior to rendering).
- `zustand` (Already installed).
- `lucide-react` (Already installed).

## Risks
1. **Performance at 5k Nodes:** React Flow maps every node to a DOM element. If CSS complexity per node is high, panning framerate will drop.
   *Mitigation:* Keep custom node HTML extremely minimal. Use pure CSS shapes where possible.
2. **Determinism Violations:** Physics-based layout engines (like d3-force) are non-deterministic across different browser JS engines due to floating-point math.
   *Mitigation:* Coordinates must be pre-calculated in the mock service using fixed-point math or a strict deterministic algorithm, then fed statically to React Flow.

## Testing Targets
- **Unit:** Zustand state transitions, deterministic generation consistency.
- **Interaction:** Searching, Node selection, Sidebar population.
- **Total:** Target 40-50 Vitest assertions.

## Performance Checkpoints
- **Checkpoint 1 (Post-Phase 3):** Render 1,000 nodes. Verify `> 55 FPS` panning.
- **Checkpoint 2 (Post-Phase 5):** Render 5,000 nodes. Verify route bundle size `< 300KB`. Verify memory `< 150MB`.
