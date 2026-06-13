# M7-5 Graph Explorer Architecture

## 1. Scope
**In Scope:**
- Interactive visualization of the ResearchMind corpus graph.
- Display of Entities, Documents, Themes, and Clusters.
- Support for complex hierarchical graphs (clustering above 5,000 nodes).
- Keyboard-accessible node traversal and edge inspections.
- Deterministic layout generation utilizing `React Flow`.
- Scalable rendering using client-side sub-graph slicing and server-side semantic clustering.

**Out of Scope:**
- General purpose network analysis algorithms (e.g., executing PageRank on the client).
- Mutation of the graph (read-only visualization only).
- Query formulation or reasoning generation (handled by M5 and M6).

## 2. Graph Data Model
The frontend strictly adheres to the SRO/RUO schemas and maps them into a unified node/edge structure.

**Node Types:**
- `document`: Research paper or publication.
- `entity`: Extracted concepts (Methods, Metrics, Datasets, etc.).
- `theme`: Semantic grouping of concepts.
- `cluster`: Aggregated super-nodes used to collapse complex sub-graphs.

**Edge Types:**
- `USES_METHOD`
- `COMPARES_WITH`
- `SUPPORTS`
- `CONTRADICTS`
- `REFERENCES`
- `CO_OCCURS`

## 3. Rendering Strategy
Rendering large graphs requires dynamic scaling strategies. Maximum raw nodes rendered into the DOM at any given time is capped at **5,000**.

| Tier | Dataset Size | Rendering Mode | Clustering Mode | Search Behavior |
|------|--------------|----------------|-----------------|-----------------|
| Tier 1 | 0 - 1,000 nodes | Native `React Flow` | None (Flat rendering) | Client-side exact/fuzzy match |
| Tier 2 | 1,000 - 5,000 nodes | Canvas/Webgl-assisted `React Flow` | Selective semantic grouping | Client-side exact/fuzzy match |
| Tier 3 | 5,000 - 50,000 nodes | Hierarchical Clustering | Mandatory Cluster nodes (collapsing sub-graphs) | Server-side API search with Client-side highlighting |
| Tier 4 | 50,000+ nodes | Drill-down Sub-graphs | Hardcap: Only cluster summaries rendered initially | Server-side strictly |

## 4. Interaction Model
- **Node Selection:** Click or `Enter` to focus a node. Opens a details side-panel.
- **Edge Selection:** Click or `Enter` on edge lines to view extraction confidence and evidence source.
- **Expand Cluster:** Double-click or `Space` on a `cluster` node to unpack its children (if within 5k limit) or navigate to a sub-graph view.
- **Collapse Cluster:** Context menu or `Escape` while focused on an unpacked cluster.
- **Multi-select:** `Shift + Click` or `Cmd/Ctrl + Drag` for batch actions or combined context views.
- **Keyboard Navigation:** `Tab` cycles clusters/high-degree nodes. Arrow keys traverse adjacent nodes along edges.
- **Focus Management:** Selecting a node triggers a `focus-trap` inside the details panel to maintain WCAG standards, pressing `Esc` returns focus to the node on the canvas.

## 5. Search
- **Client-side (Tier 1 & 2):** Uses a pre-computed deterministic index (e.g., mapping node IDs to strings) maintained via Zustand.
- **Server-side (Tier 3 & 4):** Defers to backend search endpoints to locate hidden/clustered nodes.
- **Cluster-aware Search:** If a searched node exists inside a collapsed cluster, the cluster pulses or highlights to indicate hidden contents.
- **Result Highlighting:** Grey out non-matching nodes (opacity 0.2) and highlight matching nodes/edges.

## 6. Accessibility
- **WCAG 2.1 AA Compliance:** High contrast mode support, strict ARIA labeling on SVG elements.
- **Keyboard Navigation:** Full arrow-key adjacency traversal.
- **Screen Reader Support:** Live-regions announce node connections and edge types upon focus. Hidden canvas elements are exposed as a structured nested list to `aria-hidden="false"` screen readers.
- **Reduced Motion:** Respects `prefers-reduced-motion` media query by disabling physics-based layout animations (e.g., d3-force) and instantly snapping nodes to their deterministic coordinates.

## 7. Performance
- **Node/Edge Limits:** Max 5,000 nodes rendered. Target < 10,000 edges.
- **Bundle Budget:** `< 300KB` first-load JS for the `/graph` route (incorporating `React Flow` and `d3-force`).
- **Memory Budget:** `< 150MB` heap size for graph data structures.
- **FPS Targets:** 60 FPS for panning/zooming. `requestAnimationFrame` debouncing applied to heavy layout recalculations.

## 8. Testing Strategy
- **Unit Tests:** Vitest assertions for deterministic layout algorithms, node aggregations, and Zustand store reducers.
- **Interaction Tests:** React Testing Library verifying keyboard traversal, node expansion, and search filtering logic.
- **Performance Tests:** Mocking a 5,000 node dataset and asserting render times `< 500ms`.
- **Accessibility Tests:** `axe-core` integrated into RTL to verify ARIA compliant canvas navigation.
