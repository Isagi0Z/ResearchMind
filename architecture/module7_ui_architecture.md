# Module 7 — ResearchMind Studio UI Architecture

**Status:** Architecture Document
**Date:** 2026-06-12
**Version:** 1.0

---

## Table of Contents

1. [UI Vision](#1-ui-vision)
2. [Design Principles](#2-design-principles)
3. [Technology Stack Decision](#3-technology-stack-decision)
4. [Information Architecture](#4-information-architecture)
5. [Navigation Model](#5-navigation-model)
6. [Page-by-Page Designs](#6-page-by-page-designs)
7. [Component Library](#7-component-library)
8. [State Management Architecture](#8-state-management-architecture)
9. [API Integration Strategy](#9-api-integration-strategy)
10. [Performance Strategy](#10-performance-strategy)
11. [Accessibility Strategy](#11-accessibility-strategy)
12. [Responsive Design Plan](#12-responsive-design-plan)
13. [Security Considerations](#13-security-considerations)
14. [Implementation Roadmap](#14-implementation-roadmap)
15. [Evaluation Criteria](#15-evaluation-criteria)

---

## 1. UI Vision

### 1.1 Personality

ResearchMind Studio presents as a professional research tool — serious, capable, and precise. The visual language communicates depth without complexity, power without noise.

Comp:
- **Perplexity** for the query experience — clean input, structured results, cited sources
- **Linear** for the workspace dashboard — clear metrics, task-oriented layout, dark mode done right
- **Notion** for the document viewer — sidebar navigation, rich content, collapsible sections
- **Cursor** for the graph explorer — developer-tool precision, keyboard-first interaction

### 1.2 Vibe

```
Professional  ·  Precise  ·  Fast  ·  Scholarly
```

Not playful (not Duolingo), not corporate (not Salesforce), not academic (no university portals).

Dark mode as primary design target. Light mode as secondary.

### 1.3 Key Differentiators

- Every action is deterministic and reproducible — reflect this in the UI (show IDs, confidence scores, traceability chains)
- No "AI loading" spinner hell — the pipeline is fast and deterministic, so show real progress with actual metrics
- Evidence is always one click away — every claim, every finding, every review section links back to source documents

---

## 2. Design Principles

### 2.1 Clarity Over Creativity

Every UI element has a single purpose. No decorative elements that don't carry information. Tooltips explain, not decorate.

### 2.2 Progressive Disclosure

Show the headline (confidence score, finding count). Reveal details on interaction (expand, hover, click). Never overwhelm with all data at once.

### 2.3 Keyboard-First

Every action available via keyboard. `/` for search, `n` for new project, `g` then `d` for dashboard, `Escape` to close. Power users never need the mouse.

### 2.4 Determinism Visible

The backend is deterministic. The UI should reflect this:
- Show CRC32 IDs (short, copyable)
- Show confidence as a precise number, not a vague bar
- Show traceability chains as interactive paths
- Version every generated review

### 2.5 Fast By Default

- Instant navigation (no full page loads)
- Skeleton screens for every loading state
- Optimistic updates for mutations
- Prefetch likely next actions

---

## 3. Technology Stack Decision

### 3.1 Final Stack

| Layer | Choice | Justification |
|-------|--------|---------------|
| Framework | **Next.js 14+ (App Router)** | Landing page (SSR/SSG) + dashboard (CSR) in one framework. File-based routing, React Server Components for marketing pages, client components for interactive dashboards. |
| Language | **TypeScript 5+** | Strict mode. Mandatory for maintainability at this scale. |
| Build Tool | **Turbopack** (via Next.js) | Faster than Webpack, zero-config with Next.js. |
| Styling | **Tailwind CSS v4 + shadcn/ui** | shadcn/ui provides accessible, unstyled primitives that we theme. Tailwind keeps CSS lean and consistent. No CSS-in-JS runtime. |
| State (Server) | **TanStack Query v5** | Caching, deduplication, background refetch, pagination, optimistic updates. Solves 90% of state problems. |
| State (Client) | **Zustand** | 1KB. No boilerplate. Persist middleware for theme/preferences. Subscribe with selectors for granular rerenders. |
| Forms | **React Hook Form + Zod** | Performant (uncontrolled). Zod for schema validation shared with API layer. |
| Graph | **React Flow v12** | Canvas-rendered, supports thousands of nodes, built-in minimap/controls, custom node types, edge animations. Best-in-class React graph library. |
| PDF | **react-pdf / canvas-based viewer** | Client-side PDF rendering. No server round-trips for document viewing. |
| Animation | **Framer Motion** | Layout animations, page transitions, micro-interactions. Best DX for React animation. |
| Virtualization | **TanStack Virtual** | Virtual scrolling for document lists, finding lists, evidence lists. Handles 100k+ rows. |
| Icons | **Lucide React** | Consistent, clean, tree-shakeable. Pairs naturally with shadcn/ui. |

### 3.2 Rejected Alternatives

| Alternative | Rejected Because |
|-------------|------------------|
| **Redux Toolkit** | Too much boilerplate for this scale. Zustand + TanStack Query covers everything with less code. |
| **Recoil / Jotai** | Atom-based state is powerful but adds cognitive overhead for a team. Zustand is simpler. |
| **Cytoscape.js** | Powerful but not React-native. React Flow has better React integration, custom node support, and comparable performance. |
| **D3 (direct)** | D3 is a rendering library, not a graph library. We'll use D3 for charts (metrics dashboard) but React Flow for graphs. |
| **Vite + React Router** | Loses SSR for landing page, SEO, and metadata. Next.js App Router gives us both. |
| **tRPC** | Our backend is Python (FastAPI). tRPC requires TypeScript backend. REST with TanStack Query is the right fit. |
| **Chakra / Mantine** | Good libraries but heavier than shadcn/ui. shadcn/ui gives us full control over styling and bundle size. |

### 3.3 Backend API Assumptions

The UI communicates with a Python backend:

```
REST API (FastAPI recommended)
  └── /api/v1/
       ├── /corpus/          — document management
       ├── /graph/           — knowledge graph
       ├── /query/           — M5 research queries
       ├── /review/          — M6 review generation
       ├── /pipeline/        — pipeline status & metrics
       └── /system/          — health & monitoring

WebSocket
  └── /ws/pipeline/          — real-time pipeline progress
  └── /ws/review/            — live review generation updates
```

---

## 4. Information Architecture

### 4.1 Site Structure

```
/                           → Landing page (public)
/app                        → Application root (authenticated)
  /app/dashboard            → Workspace dashboard
  /app/corpus               → Corpus manager (list)
  /app/corpus/[id]          → Corpus detail
  /app/corpus/[id]/doc/[doc_id]  → Document viewer
  /app/graph                → Knowledge graph explorer
  /app/query                → Research query interface
  /app/query/[id]           → Query result detail
  /app/reviews              → Review list
  /app/reviews/new          → Review generator
  /app/reviews/[id]         → Review viewer
  /app/settings             → User settings
  /app/system               → System monitoring
```

### 4.2 Object Model (Frontend)

```
Workspace
  ├── Corpus
  │    ├── Document (paper)
  │    │    ├── Metadata (title, authors, venue, year)
  │    │    ├── Claims
  │    │    ├── Entities
  │    │    └── References
  │    └── Graph
  │         ├── Nodes (entities, documents, claims)
  │         └── Edges (relations)
  ├── Query
  │    ├── Result
  │    │    ├── Evidence
  │    │    ├── Confidence
  │    │    └── TraceabilityChain
  │    └── History
  ├── Review
  │    ├── Sections
  │    │    └── Findings
  │    ├── Confidence
  │    └── Traceability
  └── Pipeline
       ├── Status
       ├── Metrics
       └── Logs
```

---

## 5. Navigation Model

### 5.1 Global Navigation

```
┌─────────────────────────────────────────────────────┐
│ Logo          Search (⌘K)        Theme  Profile     │
├────────┬────────────────────────────────────────────┤
│        │                                            │
│ Sidebar│  Main Content Area                         │
│        │                                            │
│  □ Dash│                                            │
│  □ Corp│                                            │
│  □ Grap│                                            │
│  □ Quer│                                            │
│  □ Revi│                                            │
│  □ Syst│                                            │
│        │                                            │
└────────┴────────────────────────────────────────────┘
```

- **Sidebar**: Collapsible (icon-only mode on narrow viewports). Primary navigation items with active indicator. Bottom section for settings and theme toggle.
- **Top bar**: Global search (command palette), breadcrumbs (context-aware), notification dot for pipeline events.
- **Command palette** (`⌘K`): Search across all corpora, documents, queries, and reviews. Recent items. Keyboard shortcuts reference.

### 5.2 Layout System

Three-level layout:

1. **Shell** — sidebar + topbar + content area (persistent across `/app/*`)
2. **Page** — page-specific layout (list/detail split, full-width graph, etc.)
3. **Panel** — slide-over panels for secondary content (document metadata, evidence details, traceability chain)

### 5.3 Navigation Conventions

| Action | Shortcut |
|--------|----------|
| Open command palette | `⌘K` |
| Search documents | `/` |
| New query | `n` then `q` |
| New review | `n` then `r` |
| Go to dashboard | `g` then `d` |
| Go to corpus | `g` then `c` |
| Go to graph | `g` then `g` |
| Go to queries | `g` then `q` |
| Go to reviews | `g` then `r` |
| Toggle sidebar | `⌘B` |
| Toggle dark mode | `⌘⇧D` |
| Close panel | `Esc` |
| Navigate back | `⌘[` |

---

## 6. Page-by-Page Designs

### 6.1 Landing Page

**Layout:** Full-bleed sections, centered content max-1200px.

**Sections:**
1. **Hero** — Large headline: "Deterministic Research Synthesis." Subtitle: "From papers to structured reviews — no LLMs, no hallucinations, full traceability." Animated graph visualization as background (lightweight, CSS/Canvas driven).
2. **How It Works** — Three-step visual: Upload → Analyze → Review. Each step shows a preview of the actual interface (screenshots or live embedded components).
3. **Architecture Overview** — Interactive architecture diagram showing M1–M6 pipeline. Hover over each module to see key metrics (documents processed, entities resolved, queries executed).
4. **Feature Grid** — Cards for each capability: PDF extraction, entity resolution, knowledge graph, research queries, literature reviews. Each card has a short description and a "Learn More" link.
5. **Demo Reviews** — Two or three example reviews users can explore without logging in. Click to see a read-only preview of a generated review with confidence scores and traceability.
6. **CTA** — "Start your research." Button leads to `/app/dashboard` or sign-in.

**State:**
- **Loading**: Skeleton blocks for hero animation, feature cards fade in
- **Error**: Static fallback with retry
- **Empty**: N/A (public page)

### 6.2 Workspace Dashboard

**Layout:** Two-column grid. Left (70%): main metrics. Right (30%): activity feed.

**Components:**
1. **Stats Bar** — Horizontal row of stat cards:
   - Total documents
   - Total entities
   - Total queries
   - Total reviews
   - Pipeline health (green/amber/red dot)
   Each card shows the number, a label, and a sparkline trend (optional).
2. **Recent Projects** — List of recently accessed corpora. Each item: name, document count, last modified, quick-action buttons (open, delete).
3. **Recent Reviews** — List of recently generated reviews. Each item: title, review type, confidence score (color-coded), word count, timestamp.
4. **Graph Summary** — Small preview of the knowledge graph (static SVG or mini React Flow instance showing top-level clusters).
5. **Activity Feed** — Chronological list of events: "Document processed: Attention Is All You Need", "Query completed: Transformer architectures", "Review generated: Method Landscape". Each item: icon, description, relative timestamp.
6. **Pipeline Status** — Mini pipeline visualization showing M1–M6. Each module shows status (idle, running, completed, error) with optional progress.

**State:**
- **Loading**: Skeleton stat cards + skeleton list items + pulse animation on pipeline
- **Empty (first run)**: "Welcome to ResearchMind — upload your first paper to get started." Illustration + CTA button to corpus manager.
- **Error**: Banner at top: "Failed to load dashboard data. Check backend connection." Retry button.

### 6.3 Corpus Manager

**Layout:** Full-width table view. Top toolbar + table + optional detail panel (slide-over).

**Components:**
1. **Toolbar**:
   - Upload button (opens file dialog or drag-drop zone)
    - Search input (server-side via `GET /api/v1/corpus/:id/documents?q=:query&cursor=:cursor&limit=:limit`). Minimum input length: 2 chars. Debounce: 300ms. Results paginated via cursor-based pagination.
   - Filter dropdowns: by status (processing/ready/error), by date range
   - Sort dropdown: by title, date, size, status
   - Batch action bar (appears when rows selected): "Delete selected", "Reprocess selected", "Export metadata"
2. **Document Table** (virtualized via TanStack Virtual):
   - Columns: Title, Authors, Year, Venue, Status (badge: Processing/Ready/Error), Entities count, Claims count, Date added
   - Row click → select (checkbox) or navigate to document viewer
   - Row hover → quick actions: "View", "Delete"
   - Column headers sortable (click to toggle asc/desc)
   - Sticky header, horizontal scroll for many columns
3. **Upload Zone** (drag-drop overlay):
   - Accepts PDF files
   - Shows upload progress per file (name, size, progress bar)
   - Handles errors (unsupported format, file too large)
   - Batch upload (multiple files at once)
4. **Detail Panel** (slide-over from right):
   - Shows selected document's metadata
   - Extracted entities (tag list)
   - Claims count
   - Processing logs
   - "Open in viewer" button

**State:**
- **Loading**: Skeleton table rows (10 rows of shimmer)
- **Empty**: "No documents yet." Illustration + upload CTA. Sample document import option.
- **Error**: Error banner + retry. Individual row error badge for failed processing.
- **Uploading**: Progress bar per file. Overall batch progress.

### 6.4 Document Viewer

**Layout:** Split view. Left (60%): PDF viewer. Right (40%): detail panel with tabs.

**Components:**
1. **PDF Viewer**:
   - Canvas-based rendering (react-pdf or custom)
   - Page navigation (prev/next, page number input)
   - Zoom controls (fit width, fit page, percentage slider)
   - Search within document (highlight matches)
   - Evidence highlights (claim sentences highlighted in the PDF, color-coded by entity type)
   - Source linking (click a highlighted claim → show metadata panel)
2. **Detail Panel** (tabbed):
   - **Metadata** tab: Title, Authors, Abstract, Venue, Year, DOI, Pages
   - **Entities** tab: List of extracted entities with type badges (method, dataset, metric, concept). Click → filter graph by entity.
   - **Claims** tab: List of extracted claims. Each claim shows: text, confidence badge, linked entities (clickable chips). Sort by confidence or page.
   - **References** tab: Citation list. Each reference: title, authors, year. "Open" button if reference is in corpus.
3. **Minimap** (optional): Small thumbnail strip showing document pages with highlight indicators for claim locations.

**State:**
- **Loading**: PDF skeleton (gray page outline with shimmer text lines). Tab skeletons.
- **Error**: "Failed to load document." Retry button. "Download original PDF" fallback.
- **Empty claims**: "No claims extracted." With explanation: "Claims are extracted during document processing."
- **Empty entities**: "No entities found in this document."

### 6.5 Knowledge Graph Explorer

**Layout:** Full-window graph. Sidebar (collapsible) + graph canvas.

**Components:**
1. **Graph Canvas** (React Flow):
   - Custom node types:
     - **Entity node**: Colored circle/badge by type (method=blue, dataset=green, metric=yellow, concept=purple). Shows entity label. Size scales with connected edge count.
     - **Document node**: Rounded rectangle, shows document title (truncated).
     - **Claim node**: Small pill shape, shows claim text snippet.
   - Custom edge types:
     - **Relation edge**: Arrow connecting entity→entity. Color and dash pattern by relation type (COMPARES_WITH, USES_METHOD, etc.).
     - **Document edge**: Thin line connecting entity→document. Click → show evidence.
   - Built-in controls: zoom, pan, fit view, lock/unlock
   - Minimap (bottom-right corner)
   - Background grid or dot pattern
   - Click node → show info panel (slide-over)
   - Click edge → show relation details (tooltip or panel)
   - Drag nodes (re-layout)
   - Lasso selection for batch operations
   - Smart layout: force-directed by default, hierarchical toggle, cluster collapse/expand
2. **Sidebar** (left, collapsible):
    - **Search** input: Search nodes by label or ID. For graphs ≤5k nodes, search is client-side (Fuse.js index). For larger graphs, search queries the server (`GET /api/v1/corpus/:id/graph/search?q=:query`) with 300ms debounce.
   - **Filter** section:
     - Node type toggles (entity, document, claim)
     - Entity type toggles (method, dataset, metric, concept)
     - Edge type toggles
     - Confidence range slider
   - **Legend**: Color and shape reference for all node/edge types
   - **Clusters** section: List of detected clusters with node count. Click → zoom to cluster, highlight members, dim rest.
   - **Statistics**: Total nodes, total edges, clusters, average confidence
3. **Path Visualization** (mode):
   - Two input fields: "From entity" and "To entity"
   - "Find Path" button highlights shortest path between them
   - Path shown with animated edges, dimmed non-path nodes
   - Step-by-step path description in sidebar

**State:**
- **Loading**: Full-screen skeleton with pulsing circles (simulating node positions)
- **Empty**: "No graph data. Upload documents to build the knowledge graph."
- **Large graph** (1000+ nodes): See Graph Scalability Strategy below.

#### 6.5.1 Graph Scalability Strategy

ResearchMind graphs may reach 1–50k+ nodes. React Flow is capable at 0–5k nodes. Beyond that, a cluster abstraction layer is required.

**Tiered rendering:**

| Tier | Node Count | Rendering Strategy | Details |
|------|------------|-------------------|---------|
| Small | 0–1k | React Flow (full) | All nodes rendered. Force-directed layout in main thread. |
| Medium | 1k–5k | React Flow (optimized) | Simplified node types (text-only, no shadows). `nodesDraggable: false`. Edge rendering via Canvas (not SVG). Force-directed layout in Web Worker. |
| Large | 5k–50k | Cluster mode | Backend computes clusters server-side. Graph loads as cluster nodes (aggregate nodes representing groups). Individual nodes are loaded on demand when user zooms into a cluster. Force layout disabled; pre-computed positions from server. |
| Extreme | 50k+ | Aggregated view | Only cluster-level view is shown. No individual node rendering. Cluster nodes show count badges. User must search or filter to drill into a specific subgraph. |

**Cluster mode mechanics:**

```
Server response for large graph:
{
  "mode": "clustered",
  "clusters": [
    { "id": "cluster_001", "label": "Transformer Methods", "node_count": 342,
      "centroid": { "x": 100, "y": 200 }, "color": "#3b82f6" },
    ...
  ],
  "edges": [  // inter-cluster edges only
    { "source_cluster": "cluster_001", "target_cluster": "cluster_002",
      "edge_count": 12, "relation_type": "compares_with" }
  ]
}
```

- **Expand on zoom:** When user zooms into a cluster node beyond a threshold (viewport zoom > 2x), the client requests `GET /api/v1/corpus/:id/graph?cluster=cluster_001` which returns the individual nodes and intra-cluster edges for that cluster.
- **Collapse on zoom out:** When zoom drops below threshold, sub-nodes are replaced by the cluster node.
- **Cluster layout:** Pre-computed by the server using force-directed placement at the cluster level. No client-side layout computation for large graphs.

**Node search at scale (C3 remediation):**

| Graph Size | Search Strategy | Implementation |
|------------|-----------------|----------------|
| 0–5k | Client-side | Load all node labels into a Fuse.js index on graph load. Search is instant (< 50ms). |
| 5k–50k | Server-side | `GET /api/v1/corpus/:id/graph/search?q=:query` with 300ms debounced input. Results highlight matching nodes. |
| 50k+ | Server-side | Same as 5k–50k but limited to top 50 results. User must refine query if too broad. |

**Hard limits:**
- Maximum nodes rendered as individual React Flow elements: **5,000**
- Maximum nodes stored in client-side Fuse.js index: **5,000** (above this, index building blocks UI)
- Maximum edges rendered as individual SVG elements: **5,000** (above this, switch to Canvas edge rendering)
- Cluster expand depth: **1 level** (expanding a sub-cluster within an expanded cluster is not supported)

**Layout computation:**

| Node Count | Location | Algorithm | Max Wait |
|------------|----------|-----------|----------|
| 0–500 | Main thread | d3-force (100 iterations) | 500ms |
| 500–5k | Web Worker | d3-force (50 iterations, simplified) | 3s |
| 5k+ | Server | Pre-computed positions via ForceAtlas2 | N/A (cached) |

If layout exceeds max wait, the graph renders with a fallback circular layout and the force simulation continues in the background. Nodes animate to their computed positions when the simulation completes.

**Memory management:**
- Graph data > 5k nodes is NOT held in JavaScript heap as React Flow elements. Only visible clusters are materialized.
- On cluster expand, the parent cluster node is removed from the React Flow instance and replaced with sub-nodes. Reverse on collapse.
- React Flow instance is disposed (`rfInstance.destroy()`) on unmount to prevent memory leaks.

**Layout:** Top: input bar. Below: result area.

**Inspiration:** ChatGPT + Perplexity combined.

**Components:**
1. **Query Input** (large, centered when empty, compact when results present):
   - Multi-line textarea (auto-resize)
   - Submit button (or Enter to submit)
   - Example queries shown as hints below input when empty
   - Keyboard shortcut: `/` to focus
   - History dropdown (previous queries, accessible via arrow keys)
2. **Query Processing View** (appears after submit):
   - Step indicator showing M5 pipeline stages: Parse → Classify → Plan → Route → Aggregate → Synthesize
   - Each step shows status (waiting, running, done, error) with timing
   - Real-time WebSocket updates for each stage
   - Estimated time remaining
3. **Result View**:
   - **Header**: Query text (editable → re-submit), confidence score (large, color-coded), execution time
   - **Classification badge**: "Method", "Dataset", "Comparative", etc.
   - **Plan visualization**: The query execution plan shown as a compact tree/dag with clickable nodes
   - **Evidence cards**: List of evidence supporting the answer. Each card:
     - Source document title (clickable → document viewer)
     - Extracted sentence/text
     - Confidence bar
     - Entity tags (clickable → filter graph)
     - Relationship type (supports, contradicts, relates)
   - **Traceability chain**: Expandable section at bottom. Shows the full chain from query → plan → evidence → documents. Each step clickable for details.
   - **Suggested follow-ups**: 2–3 suggested queries based on this result
4. **History Sidebar** (right, collapsible):
   - Chronological list of past queries
   - Each item: truncated query text, date, confidence indicator (color dot)
   - Click → re-load that query's result
   - Search within history

**State:**
- **Initial**: Empty input with example queries
- **Processing**: Step indicator with real-time WebSocket progress
- **Result**: Evidence cards with traceability
- **Empty result**: "No evidence found matching your query." Suggestions for broadening the query.
- **Error**: "Query processing failed." Error details + retry button.

### 6.7 Literature Review Generator

**Layout:** Stepped form → progress → preview.

**Components:**
1. **Step 1: Configure** (form):
   - **Review type** selector: Cards for each type (General, Method, Dataset, Consensus, Contradiction, Research Gap, Comparative, Landscape). Each card shows: title, description, typical section count.
   - **Parameters** panel (appears after type selected):
     - Min confidence slider (0.0–1.0)
     - Max themes (number input)
     - Max findings per section (number input)
     - Include contradictions (toggle)
     - Include gaps (toggle)
     - Target entities (multi-select, searchable, populated from graph)
   - **Preview** sidebar (right): Shows estimated section structure for selected review type
2. **Step 2: Generate** (progress):
   - Real-time pipeline visualization showing M6 stages: Theme Detection → Evidence Collection → Finding Generation → Section Building → Traceability → Confidence
   - Each stage shows status (waiting/running/done) with timing
   - Intermediate results appear as they become available (e.g., themes list appears after stage 1)
   - Cancel button (graceful pipeline stop)
3. **Step 3: Review** (preview):
   - The generated review shown in a layout identical to the Review Viewer (section 6.8)
   - "Regenerate" button (same parameters)
   - "Adjust" button (go back to step 1 with parameters preserved)
   - "Export" dropdown: PDF, Markdown, JSON, plain text
   - "Save Review" button

**State:**
- **Initial**: No type selected → show type cards
- **Configuring**: Parameters panel visible
- **Generating**: Real-time progress per stage
- **Complete**: Preview with export options
- **Error**: Stage that failed highlighted in red. Error message. Retry from failed stage.

### 6.8 Review Viewer

**Layout:** Sidebar (left, section navigation) + main content.

**Components:**
1. **Navigation Sidebar** (left, 250px):
   - Review title at top
   - Section list: All sections of the review. Current section highlighted. Each item shows section title, finding count badge, confidence dot.
   - Click section → smooth scroll to section
   - "Expand all" / "Collapse all" toggle for findings
2. **Main Content**:
   - **Header**: Review title, review type badge, overall confidence score (large, prominent), date generated, word count, traceability status (verified/unverified badge)
   - **Abstract**: Collapsible, shown expanded by default
   - **Sections**: Each section renders as:
     - Section title with anchor link
     - Section content (template text)
     - Finding list (each finding is a card):
       - Finding statement
       - Confidence badge (color-coded: green > 0.7, yellow > 0.4, red < 0.4)
       - Finding type badge (supporting, consensus, contradiction, gap, relation)
       - Expandable evidence: "Show sources" → reveals linked evidence items with document titles and excerpts
       - "View traceability" button → opens traceability panel
     - Section statistics: finding count, evidence count, document count
3. **Traceability Panel** (slide-over):
   - Shows the full trace chain for a finding
   - Finding → Evidence IDs → Source Documents
   - Each step clickable (evidence ID → show evidence detail, document → open document viewer)
   - Visual chain (linked nodes)
4. **Toolbar** (floating, bottom-right):
   - "Scroll to top"
   - "Table of contents" toggle
   - "Export" dropdown
   - "Print"

**State:**
- **Loading**: Skeleton sections (shimmer blocks for each section)
- **Loaded**: Full review with collapsible findings
- **Empty sections**: Sections with 0 findings show: "No findings for this section." (expected for abstract/conclusion with no findings)
- **Error**: "Failed to load review." Retry.

### 6.9 System Monitoring

**Layout:** Tabbed dashboard with metric cards and charts.

**Components:**
1. **Module Metrics** grid:
   - Card for each module (M1–M6): name, status indicator, documents processed, success rate, average processing time
   - Click → expand to detailed per-module view
2. **Processing Queue**:
   - Current queue depth
   - Items in queue (table: document name, queued at, estimated start)
   - Recently completed (table: document name, completed at, processing time, status)
3. **Error Logs**:
   - Filterable table (by module, severity, time range)
   - Columns: timestamp, module, severity (badge), message, document ID
   - Click row → expand to full error details and stack trace
   - "Clear" button, "Export logs" button
4. **Performance Charts** (D3-based):
   - Processing time over time (line chart, last 24h/7d/30d)
   - Documents processed per hour (bar chart)
   - Error rate over time (area chart)
   - Cache hit rate (gauge)
   - Memory / CPU usage (if available)
5. **Cache Metrics**:
   - Cache size
   - Hit rate percentage
   - Entry count
   - "Clear cache" button (with confirmation)

**State:**
- **Loading**: Skeleton metric cards + empty chart placeholders with pulse animation
- **Empty**: "No pipeline activity yet." (shown for fresh installs)
- **Error**: "Metrics unavailable." with reason.

---

## 7. Component Library

### 7.1 Component Hierarchy

```
<App>
  <Shell>
    <TopBar>
      <Logo />
      <GlobalSearch />        // ⌘K command palette
      <Breadcrumbs />
      <ThemeToggle />
      <UserMenu />
    </TopBar>
    <Sidebar>
      <NavItem />             // icon + label, active state
      <NavSection />           // group label + children
      <SidebarFooter />        // settings, theme
    </Sidebar>
    <Main>
      <Page />                // page content (routed)
    </Main>
  </Shell>
  <CommandPalette />           // ⌘K overlay
  <SlideOver />                // right panel
  <ConfirmDialog />
  <Toast />
```

### 7.2 Core Design System Tokens

**Colors:**

```
--color-bg:           #0a0a0b      (dark base)
--color-bg-subtle:    #141416      (card backgrounds)
--color-bg-elevated:  #1c1c1f      (hover, active)
--color-border:       #2a2a2e      (subtle borders)
--color-text:         #f4f4f5      (primary text)
--color-text-secondary: #a1a1aa    (secondary text)
--color-accent:       #3b82f6      (primary blue)
--color-accent-hover: #2563eb
--color-success:      #22c55e      (confidence > 0.7)
--color-warning:      #eab308      (confidence 0.4–0.7)
--color-danger:       #ef4444      (confidence < 0.4, errors)
--color-info:         #06b6d4

Entity type colors:
--entity-method:      #3b82f6      (blue)
--entity-dataset:     #22c55e      (green)
--entity-metric:      #eab308      (yellow)
--entity-concept:     #a855f7      (purple)
```

**Typography:**

```
Font family: Inter (sans-serif) + JetBrains Mono (monospace for IDs/code)

--font-sans:   'Inter', system-ui, sans-serif
--font-mono:   'JetBrains Mono', monospace

Scale:
--text-xs:     0.75rem   (12px)
--text-sm:     0.875rem  (14px)
--text-base:   1rem      (16px)
--text-lg:     1.125rem  (18px)
--text-xl:     1.25rem   (20px)
--text-2xl:    1.5rem    (24px)
--text-3xl:    1.875rem  (30px)
--text-4xl:    2.25rem   (36px)
```

**Spacing:**

```
4px base unit. Multiples:
--spacing-1: 0.25rem (4px)
--spacing-2: 0.5rem  (8px)
--spacing-3: 0.75rem (12px)
--spacing-4: 1rem    (16px)
--spacing-6: 1.5rem  (24px)
--spacing-8: 2rem    (32px)
--spacing-12: 3rem   (48px)
--spacing-16: 4rem   (64px)
```

**Shadows:**

```
--shadow-sm:   0 1px 2px rgba(0,0,0,0.3)
--shadow-md:   0 4px 6px rgba(0,0,0,0.3)
--shadow-lg:   0 10px 15px rgba(0,0,0,0.3)
--shadow-xl:   0 20px 25px rgba(0,0,0,0.4)
```

**Border radius:**

```
--radius-sm:   0.375rem (6px)
--radius-md:   0.5rem   (8px)
--radius-lg:   0.75rem  (12px)
--radius-xl:   1rem     (16px)
```

### 7.3 Shared Components (shadcn/ui primitives + custom)

| Component | Source | Notes |
|-----------|--------|-------|
| Button | shadcn/ui | Variants: default, secondary, ghost, outline, destructive. Sizes: sm, md, lg, icon. |
| Input | shadcn/ui | With icon support, error state, clearable. |
| Select | shadcn/ui | Searchable select for entity pickers. |
| Command | shadcn/ui | Base for command palette ⌘K. |
| Dialog | shadcn/ui | Confirmation dialogs, modals. |
| Sheet | shadcn/ui | Slide-over panels (evidence detail, traceability). |
| Table | shadcn/ui | Sortable columns, row selection. |
| Badge | shadcn/ui | Status badges, entity type badges, confidence badges. |
| Tabs | shadcn/ui | Document detail panel tabs. |
| Tooltip | shadcn/ui | Hover information for confidence scores, IDs. |
| Progress | shadcn/ui | Pipeline stage progress. |
| Skeleton | shadcn/ui | Loading skeletons. |
| Toast | shadcn/ui | Notifications for pipeline events, errors. |
| Dropdown | shadcn/ui | User menu, export options. |
| Card | Custom | Stat cards, entity cards, evidence cards. |
| StatCard | Custom | Dashboard metric cards with label, value, sparkline. |
| StepIndicator | Custom | Pipeline stage visualization (running/completed/failed). |
| ConfidenceBadge | Custom | Color-coded confidence display. |
| EntityChip | Custom | Entity type tag with color. |
| TraceChain | Custom | Interactive traceability path visualization. |
| GraphNode | Custom (React Flow) | Entity node, document node, claim node. |
| GraphEdge | Custom (React Flow) | Relation edge with label. |

### 7.4 Animation Philosophy

- **Micro-interactions**: 150ms ease-out. Button hover, card hover lift, toggle switches.
- **Layout transitions**: 300ms spring. Sidebar collapse, panel slide-in, list reordering.
- **Page transitions**: 200ms fade + slight slide. Avoid shared axis transitions (complex, error-prone).
- **Loading states**: Skeleton shimmer at 1.5s cycle. Pulse for pipeline progress indicators.
- **Graph**: No animation on initial load (instant layout). 500ms transitions for layout changes, node additions.
- **Never use**: Spinners for pipeline progress (use step indicators instead). Carousels. Auto-playing animations.

---

## 8. State Management Architecture

### 8.1 State Categories

| Category | Tool | Rationale |
|----------|------|-----------|
| **Server state** | TanStack Query | All API data: documents, queries, reviews, graph, metrics. Automatic caching, background refetch, pagination. |
| **UI state** | Zustand | Theme, sidebar open/close, active panel, panel width, command palette open. Persisted to localStorage. |
| **Form state** | React Hook Form | Review configuration, query input, corpus upload. Local to form, serialized on submit. |
| **URL state** | Next.js search params | Pagination cursor, active tab, selected entity ID. Shareable, bookmarkable. |
| **Graph state** | Zustand + React Flow state | Selected nodes, viewport position, active filter set. Graph is performance-critical; keep state minimal. |

### 8.2 TanStack Query Configuration

```typescript
// Global defaults
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,       // 30s before background refetch
      gcTime: 5 * 60_000,      // 5min in cache
      retry: 2,
      refetchOnWindowFocus: false,  // disable for data that rarely changes
    },
  },
});
```

**Query key conventions:**

```
["corpus"]                          → corpus list
["corpus", id]                      → single corpus
["corpus", id, "documents"]         → documents in corpus
["corpus", id, "documents", docId]  → single document
["corpus", id, "graph"]             → graph data
["query", id]                       → query result
["query", id, "traceability"]       → traceability chain
["review", id]                      → review detail
["review", id, "sections"]          → review sections
["pipeline", "status"]              → pipeline status
["pipeline", "metrics"]             → module metrics
["system", "health"]                → system health
```

### 8.3 Zustand Stores

```typescript
// Theme store
interface ThemeStore {
  mode: "dark" | "light";
  toggle: () => void;
}

// UI store
interface UIStore {
  sidebarOpen: boolean;
  sidebarWidth: number;
  commandPaletteOpen: boolean;
  activeSlideOver: string | null;
  toggleSidebar: () => void;
  openCommandPalette: () => void;
  closeCommandPalette: () => void;
  openSlideOver: (id: string) => void;
  closeSlideOver: () => void;
}

// Graph store
interface GraphStore {
  selectedNodes: string[];
  selectedEdges: string[];
  filters: {
    nodeTypes: Set<string>;
    entityTypes: Set<string>;
    edgeTypes: Set<string>;
    minConfidence: number;
  };
  layout: "force" | "hierarchical" | "cluster";
  selectNode: (id: string) => void;
  setFilter: (key: string, value: unknown) => void;
  setLayout: (layout: string) => void;
}
```

### 8.4 Real-Time Updates

#### 8.4.1 Connection Strategy

Two-tier strategy: **WebSocket primary** with **HTTP polling fallback**.

| Tier | Protocol | Use Case |
|------|----------|----------|
| Primary | WebSocket (`wss://`) | All real-time events when available |
| Fallback | HTTP polling (`GET /api/v1/pipeline/status`) | WebSocket blocked by firewall/proxy |

Detection: WebSocket connection attempt with 5s timeout. If it fails, or if the connection drops and cannot be re-established after 3 attempts, switch to polling.

#### 8.4.2 WebSocket State Machine

```
                    ┌─────────────┐
                    │   IDLE      │
                    └──────┬──────┘
                           │ connect()
                    ┌──────▼──────┐
              ┌─────│ CONNECTING  │─────┐
              │     └──────┬──────┘     │ timeout (5s)
              │            │ open       │
              │     ┌──────▼──────┐     │
              │     │  CONNECTED  │     │
              │     └──────┬──────┘     │
              │            │ close      │
              │     ┌──────▼──────┐     │
              │     │DISCONNECTED │     │
              │     └──────┬──────┘     │
              │            │ retry      │
              │     ┌──────▼──────┐     │
              └─────│RECONNECTING │─────┘
                    └──────┬──────┘
                           │ max retries exceeded
                    ┌──────▼──────┐
                    │   FAILED    │──── Switch to polling
                    └─────────────┘
```

**Reconnection backoff:**

| Attempt | Delay | Jitter |
|---------|-------|--------|
| 1 | 1s | ±500ms |
| 2 | 2s | ±500ms |
| 3 | 4s | ±1s |
| 4 | 8s | ±1s |
| 5 | 16s | ±2s |
| 6+ | 30s (cap) | ±5s |

- **Max retries:** 10 consecutive failures before transitioning to FAILED
- **Reset condition:** A successful connection resets the attempt counter to 0
- **Health monitoring:** Ping/pong messages every 30s. If no pong received within 10s, treat as DISCONNECTED.

#### 8.4.3 WebSocket Event Types

```typescript
type WSEvent =
  | { type: "pipeline:stage_start"; module: string; stage: string; sequence: number }
  | { type: "pipeline:stage_complete"; module: string; stage: string; duration: number; sequence: number }
  | { type: "pipeline:stage_error"; module: string; stage: string; error: string; sequence: number }
  | { type: "review:progress"; reviewId: string; stage: string; progress: number; sequence: number }
  | { type: "review:complete"; reviewId: string; sequence: number }
  | { type: "corpus:document_processed"; corpusId: string; documentId: string; sequence: number }
  | { type: "system:metric_update"; metrics: Record<string, number>; sequence: number }
```

Each event carries a `sequence` number (monotonically increasing server-side). The client tracks `lastProcessedSequence` on reconnect and ignores events with `sequence <= lastProcessedSequence`.

#### 8.4.4 TanStack Query Integration

On receiving events, call `queryClient.invalidateQueries()`:

| Event | Keys Invalidated |
|-------|-----------------|
| `review:complete` | `["review", reviewId]`, `["review"]` |
| `review:progress` | `["review", reviewId]` (only if detail page is mounted) |
| `corpus:document_processed` | `["corpus", corpusId, "documents"]`, `["corpus", corpusId]` |
| `pipeline:stage_*` | `["pipeline", "status"]` |
| `system:metric_update` | `["pipeline", "metrics"]` |

Invalidation is wrapped in a React ref check: if the component tree has no active observers for a key, invalidation is skipped (TanStack Query handles this internally via `gcTime`).

#### 8.4.5 Polling Fallback

When WebSocket is in FAILED state (or not supported), fall back to HTTP polling:

| Context | Interval | Endpoint | Condition |
|---------|----------|----------|-----------|
| Review generation active | 2s | `GET /api/v1/review/:id` | Only when review page is mounted and review is in "generating" status |
| Pipeline monitoring | 15s | `GET /api/v1/pipeline/status` | Dashboard or system page mounted |
| Document processing | 10s | `GET /api/v1/corpus/:id` | Corpus detail page mounted with processing documents |
| Idle (no relevant page) | Disabled | — | No polling when user is on unrelated pages |

**Transition logic:**
```
WebSocket state change:
  CONNECTING → CONNECTED : polling stops (if active), WebSocket takes over
  RECONNECTING → DISCONNECTED → FAILED : polling starts with appropriate interval
  FAILED → CONNECTING (manual retry or page refresh) : polling continues until CONNECTED
```

The polling is implemented via TanStack Query's `refetchInterval` option, which is standardized across the app and respects `staleTime`. No separate polling timer infrastructure needed.

#### 8.4.6 Connection Status UI

A persistent indicator in the top bar shows current connection state:

| State | Indicator | Behavior |
|-------|-----------|----------|
| CONNECTED | Green dot | Normal |
| CONNECTING | Yellow dot with pulse | Brief on initial load |
| RECONNECTING | Yellow dot with pulse | Network interruption; auto-recovering |
| DISCONNECTED | Red dot | Temporary; retrying |
| FAILED | Red dot with "!" | Polling active; click to retry WebSocket |

The indicator is implemented as a small (8px) dot in the top bar next to the theme toggle. Hover tooltip shows the current state and last event time.

---

## 9. API Integration Strategy

### 9.1 API Client Layer

```typescript
// Singleton fetch wrapper with:
// - Base URL from environment
// - Auth token injection
// - Error normalization
// - Request/response logging (dev only)

// src/lib/api/client.ts
class ApiClient {
  private baseUrl: string;
  private token: string | null;

  async get<T>(path: string, params?: Record<string, string>): Promise<T>;
  async post<T>(path: string, body: unknown): Promise<T>;
  async put<T>(path: string, body: unknown): Promise<T>;
  async delete(path: string): Promise<void>;
  async upload(path: string, file: File, onProgress?: (pct: number) => void): Promise<unknown>;
}
```

### 9.2 API Module Structure

```
src/lib/api/
  client.ts           — ApiClient singleton
  queries.ts          — TanStack Query hooks (useDocuments, useGraph, etc.)
  mutations.ts        — TanStack Mutation hooks (useUploadDocument, useGenerateReview, etc.)
  websocket.ts        — WebSocket manager (connect, reconnect, event emitter)
  types.ts            — Shared API types (Document, Review, QueryResult, etc.)
```

### 9.3 Key API Endpoints

| Method | Path | Purpose | Caching |
|--------|------|---------|---------|
| GET | `/api/v1/corpus` | List corpora | 30s stale |
| POST | `/api/v1/corpus` | Create corpus | — |
| GET | `/api/v1/corpus/:id` | Corpus detail | 30s stale |
| DELETE | `/api/v1/corpus/:id` | Delete corpus | — |
| GET | `/api/v1/corpus/:id/documents` | List documents | 30s stale |
| POST | `/api/v1/corpus/:id/documents/upload` | Upload PDFs | — |
| GET | `/api/v1/corpus/:id/documents/:docId` | Document detail | 60s stale |
| GET | `/api/v1/corpus/:id/graph` | Graph data | 60s stale |
| POST | `/api/v1/query` | Execute query | — |
| GET | `/api/v1/query/:id` | Query result | 5min stale |
| GET | `/api/v1/query` | Query history | 30s stale |
| POST | `/api/v1/review` | Generate review | — |
| GET | `/api/v1/review/:id` | Review detail | 5min stale |
| GET | `/api/v1/review/:id/export` | Export review | — |
| GET | `/api/v1/review` | Review list | 30s stale |
| GET | `/api/v1/pipeline/status` | Pipeline status | 10s stale |
| GET | `/api/v1/pipeline/metrics` | Module metrics | 10s stale |
| GET | `/api/v1/pipeline/logs` | Error logs | 30s stale |
| GET | `/api/v1/system/health` | System health | 10s stale |

### 9.4 Error Handling Strategy

```typescript
// All API errors normalized to:
interface ApiError {
  code: string;           // "NOT_FOUND", "VALIDATION_ERROR", "PIPELINE_ERROR"
  message: string;        // Human-readable
  details?: unknown;      // Field-level errors for forms
  requestId?: string;     // For debugging
}

// TanStack Query error handling:
// - Network errors: Toast "Connection lost. Retrying..." Auto-retry 2x.
// - 4xx errors: Show inline form validation errors or toast.
// - 5xx errors: Toast "Server error. Please try again." with retry button.
// - Pipeline errors: Show in pipeline visualization with stage highlighted.
```

---

## 10. Performance Strategy

### 10.1 Virtualization

- **Document lists**: TanStack Virtual. Fixed row height. Render 10x viewport. Handles 100k+ documents.
- **Finding lists**: TanStack Virtual. Variable row height (expanded evidence). Render 5x viewport.
- **Evidence grids**: TanStack Virtual. Grid layout for evidence card masonry.
- **Log tables**: TanStack Virtual. Fixed row height. Filtered server-side for large datasets.

### 10.2 Memoization Strategy

```typescript
// Rules:
// 1. Wrap expensive computations in useMemo
// 2. Wrap event handlers in useCallback if passed as props to memo'd children
// 3. Memo components that render frequently (list items, graph nodes, finding cards)
// 4. DON'T memo prematurely — measure first

// Expensive computations to memo:
// - Graph layout calculation (force-directed simulation)
// - Filtered/sorted document lists
// - Confidence score color derivation
// - Traceability chain tree construction
```

### 10.3 Graph Performance

React Flow with 1000+ nodes requires optimization:

1. **Node virtualization**: React Flow handles this natively — only visible nodes are rendered.
2. **Custom node components**: Use `React.memo` with shallow comparison. Keep node rendering simple (no heavy DOM).
3. **Layout computation**: Run force-layout in a Web Worker if > 500 nodes. Layout results cached in Zustand.
4. **Lazy loading**: Load graph data in tiers — first cluster-level, expand on zoom.
5. **Canvas vs SVG**: React Flow uses Canvas by default for rendering, falls back to SVG for interactions.
6. **Debounce viewport changes**: Don't re-layout on every pan/zoom — 100ms debounce.

### 10.4 Code Splitting

Next.js App Router automatically code-splits by route. Additional manual splitting:

```typescript
// Heavy components loaded lazily:
const GraphExplorer = dynamic(() => import("@/app/graph/graph-explorer"), {
  loading: () => <GraphSkeleton />,
  ssr: false,  // Graph is client-only
});

const PDFViewer = dynamic(() => import("@/app/corpus/[id]/doc/[docId]/pdf-viewer"), {
  loading: () => <PDFSkeleton />,
  ssr: false,
});

const ReviewGenerator = dynamic(() => import("@/app/reviews/new/generator-form"), {
  loading: () => <FormSkeleton />,
});
```

### 10.5 Caching Strategy

| Cache | Location | TTL | Invalidated By |
|-------|----------|-----|----------------|
| API responses | TanStack Query | Per-query (10s–5min) | WebSocket events, manual refetch |
| Graph data | TanStack Query | 60s stale, 10min cache | Document upload complete |
| PDF pages | Browser (blob URLs) | Session | Document change |
| UI preferences | localStorage (Zustand persist) | Permanent | User action |
| Query results | TanStack Query | 5min stale, 30min cache | New query execution |
| Review content | TanStack Query | 5min stale | Re-generation |

### 10.6 Lazy Loading

1. **Images**: Next.js `Image` component with lazy loading.
2. **PDF pages**: Load page N, preload N+1 and N+2. Render as canvas blobs.
3. **Graph nodes**: Load cluster view first. Load individual node details on selection.
4. **Review sections**: Load section content on scroll (intersection observer).
5. **Charts**: Load D3-based chart components only when System Monitoring tab is opened.

---

## 11. Accessibility Strategy

### 11.1 Standards

- Target **WCAG 2.1 AA** minimum.
- All shadcn/ui components are built with Radix UI primitives (WAI-ARIA compliant).

### 11.2 Graph Explorer Keyboard Navigation

The graph explorer is the most interaction-heavy component and requires dedicated keyboard support.

| Key | Action | Context |
|-----|--------|---------|
| `Tab` / `Shift+Tab` | Move focus between: search bar → graph canvas → sidebar node detail | Document order |
| `Arrow keys` | Pan graph viewport (when graph canvas is focused) | Graph canvas focused |
| `+` / `-` | Zoom in / zoom out | Graph canvas focused |
| `0` | Reset zoom to 100% | Graph canvas focused |
| `F` | Fit all nodes to viewport | Graph canvas focused |
| `Enter` / `Space` | Select focused node (show detail in sidebar) | Node in focus |
| `Escape` | Deselect node / close expanded detail | Any |
| `Ctrl+F` | Focus search input | Graph page |
| `R` | Reset viewport to initial state | Graph canvas focused |

**Focus indicator:** Each graph node receives a visible 2px outline when focused via keyboard. The focus ring uses the theme-accent color with 3px offset to ensure visibility on light and dark backgrounds.

**Focus management on node selection:**
1. On `Enter`/`Space`, focus moves to the sidebar panel
2. `Tab` navigates through node detail fields (type, confidence, source documents)
3. `Escape` returns focus to the graph canvas and deselects the node
4. If sidebar is closed, focus returns to the last focused node

### 11.3 Route Transition Focus Management

On page navigation, focus is programmatically moved to the `<h1>` of the new page to prevent focus from being lost.

```typescript
// src/lib/hooks/useRouteAnnounce.ts — applied in root layout
function useRouteAnnounce() {
  const pathname = usePathname();
  useEffect(() => {
    // Delay to allow DOM to render
    requestAnimationFrame(() => {
      const h1 = document.querySelector("h1");
      if (h1) {
        h1.setAttribute("tabindex", "-1");
        h1.focus();
      }
    });
  }, [pathname]);
}
```

### 11.4 Skip Navigation

A "Skip to main content" link is the first focusable element on every page:

```tsx
// src/components/layout/SkipNav.tsx
export function SkipNav() {
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2
                 focus:z-[9999] focus:px-4 focus:py-2 focus:bg-background focus:text-foreground
                 focus:ring-2 focus:ring-accent"
    >
      Skip to main content
    </a>
  );
}
```

Usage in root layout:
```tsx
<SkipNav />
<Header />
<main id="main-content">{children}</main>
```

### 11.5 Live Regions for Real-Time Updates

Real-time pipeline progress and review generation use ARIA live regions to announce updates to screen readers.

| Event | Region | `aria-live` | Role | Content |
|-------|--------|-------------|------|---------|
| Review progress | `#review-progress-live` | `polite` | `status` | "Generating review: stage {stage}, {progress}% complete" |
| Pipeline stage change | `#pipeline-live` | `polite` | `status` | "Pipeline stage {stage} {started/completed/failed}" |
| Document processed | `#corpus-live` | `polite` | `log` | "Document {title} processed" |
| Connection status | None (visual-only) | — | — | Connection state changes are visual-only; no announcement on reconnect |

Only the most recent event is announced (not queued). Implemented as a single `aria-live="polite"` region that receives updated text content:

```tsx
// Implementation pattern — single live region in root layout
function LiveRegion() {
  const [message, setMessage] = useState("");
  // Subscribe to WebSocket events, update message
  return <div aria-live="polite" aria-atomic="true" className="sr-only">{message}</div>;
}
```

### 11.6 General Implementation

- **Color contrast**: All text meets 4.5:1 ratio. Confidence colors (green/yellow/red) are supplemented with icons and text labels for color-blind users. Example: confidence badge shows checkmark icon (high), dash icon (medium), X icon (low) in addition to color.
- **Keyboard navigation**: All interactive elements focusable. Tab order follows visual order. Focus indicators visible (2px ring with 3px offset).
- **Screen readers**: ARIA labels on all icon-only buttons (`aria-label="Close panel"`). Landmarks (`<nav aria-label="Main">`, `<main>`, `<aside>`).
- **Reduced motion**: `prefers-reduced-motion` disables all CSS animations and transitions. Skeleton shimmer becomes a static opacity fade. React Flow animations disabled.
- **Focus management**: Slide-over panels trap focus (via Radix Dialog/Drawer). Command palette traps focus. All overlays close on `Escape`.

### 11.7 Testing

- Manual keyboard-only navigation test before every release.
- axe-core in CI for automated accessibility checks (via `@axe-core/playwright` in e2e tests).
- Focus management tested via Playwright: `page.keyboard.press("Tab")` assertions on visible focus indicators.

---

## 12. Responsive Design Plan

### 12.1 Breakpoints

| Breakpoint | Width | Target |
|------------|-------|--------|
| `sm` | 640px | Mobile landscape |
| `md` | 768px | Tablet |
| `lg` | 1024px | Tablet landscape / small desktop |
| `xl` | 1280px | Desktop |
| `2xl` | 1536px | Large desktop |

### 12.2 Layout Adaptations

| Screen | Sidebar | Content | Detail Panel |
|--------|---------|---------|--------------|
| ≥ 1280px | Expanded (260px) | Main column | Slide-over (400px) |
| 768–1279px | Icon-only (64px) | Main column | Full-screen overlay |
| < 768px | Hidden (overlay drawer) | Full width | Full-screen overlay |

### 12.3 Page-Specific Adaptations

- **Corpus Manager**: Table → card grid on mobile. Search/filter become collapsible sections.
- **Document Viewer**: PDF stack vertically above metadata on mobile. Detail tabs become accordion.
- **Graph Explorer**: Sidebar hidden by default on mobile. Gesture-based navigation (pinch zoom, pan).
- **Query Interface**: Result cards stack single column on mobile. History sidebar hidden.
- **Review Viewer**: Sidebar becomes hamburger menu. Finding cards full-width.

### 12.4 Touch Targets

- All interactive elements minimum 44x44px on touch devices.
- Swipe gestures for document page navigation, slide-over dismissal.

---

## 13. Security Considerations

### 13.1 Authentication Architecture

#### 13.1.1 Token Strategy

Two-token system using httpOnly cookies:

| Token | Storage | Lifetime | Purpose |
|-------|---------|----------|---------|
| **Access token** (JWT) | httpOnly cookie, `Path=/api`, `SameSite=Lax` | 15 minutes | API authorization |
| **Refresh token** (opaque) | httpOnly cookie, `Path=/api/auth`, `SameSite=Strict` | 7 days | Obtain new access tokens |

- Access token cookie is not accessible via `document.cookie` (XSS protection)
- Refresh token is sent only to `/api/auth/*` endpoints (CSRF protection via path scoping)
- Refresh token is rotated on each use: old token is invalidated, new pair is issued
- If a refresh token is reused after invalidation (stolen token scenario), all sessions are revoked

#### 13.1.2 Sequence Flows

**Login:**
```
User → POST /api/auth/login { email, password }
       ← Set-Cookie: access_token=... (httpOnly, Path=/api, SameSite=Lax)
       ← Set-Cookie: refresh_token=... (httpOnly, Path=/api/auth, SameSite=Strict)
       ← 200 { user: { id, name, email } }
```

**Registration:**
```
User → POST /api/auth/register { email, password, name }
       ← Set-Cookie: access_token=... (same as login)
       ← Set-Cookie: refresh_token=...
       ← 201 { user: { id, name, email } }
```

**Session refresh (transparent):**
```
ApiClient → GET /api/resource
             ← 401 { code: "UNAUTHORIZED" }
ApiClient → POST /api/auth/refresh (refresh_token cookie sent automatically)
             ← Set-Cookie: access_token=... (new)
             ← Set-Cookie: refresh_token=... (rotated)
ApiClient → GET /api/resource (retry with new access_token cookie)
             ← 200 { ... }
```

**Logout:**
```
User → POST /api/auth/logout
       ← Set-Cookie: access_token=; Max-Age=0 (clear)
       ← Set-Cookie: refresh_token=; Max-Age=0 (clear)
       ← 200
       Then: window.location = "/"
```

**Session expiry:**
- Access token expires → ApiClient transparently refreshes (single retry)
- Refresh token expires (7 days) → ApiClient receives 401 on refresh → redirect to `/login`
- Idle timeout: refresh token expires after 24h of inactivity (configurable server-side)

#### 13.1.3 Layer Responsibilities

| Layer | Responsibility |
|-------|---------------|
| **Next.js middleware** (`src/middleware.ts`) | Reads access_token cookie on every `/app/*` request. If missing or expired, redirects to `/login`. Does NOT attempt refresh (that's the client's job). Public routes (`/`, `/about`, `/login`, `/register`) pass through. |
| **Zustand** (`src/lib/store/auth.ts`) | Stores user profile (`{ id, name, email }`), authentication status (`idle / loading / authenticated / unauthenticated`), and login/register/logout actions. Token state is NOT stored in Zustand (cookies are the source of truth). |
| **TanStack Query** | The `ApiClient` interceptor handles 401 → refresh → retry transparently. Queries that fail after refresh redirect are considered failed and show error states. `useAuth` hook wraps Zustand + TanStack Query for the initial profile fetch. |
| **ApiClient** (`src/lib/api/client.ts`) | On 401 response, attempts a single POST to `/api/auth/refresh` before retrying the original request. If refresh also fails, sets auth status to `unauthenticated` which triggers redirect to `/login`. |

#### 13.1.4 Route Protection

```
Middleware (Next.js):
  /              → public
  /about         → public
  /login         → public (redirect to /app/dashboard if authenticated)
  /register      → public (redirect to /app/dashboard if authenticated)
  /app/*         → protected (redirect to /login if no valid access_token)

Client-side guard:
  <AppShell> wraps all /app/* routes.
  On mount: calls GET /api/auth/me to validate session.
  If 401: set status to unauthenticated → <LoginGate> renders redirect to /login.
  Prevents flash of protected content before middleware check.
```

#### 13.1.5 Edge Cases

| Scenario | Behavior |
|----------|----------|
| Token expires mid-session | ApiClient transparently refreshes; user sees no interruption |
| Token expires during long review generation | Review is saved server-side; user re-authenticates and retrieves from history |
| Refresh token stolen | Rotation detects replay; all sessions revoked; user must re-login |
| Multi-tab logout | Other tabs detect 401 on next API call → redirect to login |
| Server restart (all tokens invalid) | ApiClient refresh fails → redirect to login; no partial state corruption |

### 13.2 API Security

- CSRF token for all mutation endpoints.
- Rate limiting per user for query/review generation endpoints.
- Input validation at API layer (Zod schemas shared with frontend for type safety).
- File upload: Validate MIME type + extension. Size limit (50MB per file). Scan for malware (future).

### 13.3 Frontend Security

- No secrets in frontend code. All API keys server-side.
- Content Security Policy headers set via Next.js middleware.
- Sanitize document titles and metadata before rendering (XSS prevention).
- PDF viewer: Render in sandboxed iframe.

### 13.4 Data Isolation

- Multi-tenant: All data scoped to authenticated user/workspace.
- API returns 404 (not 403) for unauthorized resource access to avoid revealing existence.

---

## 14. Implementation Roadmap

### Phase 1: Foundation (Week 1–2)

```
Day 1-2:  Next.js project setup, Tailwind config, shadcn/ui init, design tokens
Day 3-4:  Shell layout (sidebar, topbar, main area), dark/light mode, responsive shell
Day 5-6:  Command palette, slide-over panel, toast system, global search
Day 7-10: Shared components (buttons, inputs, cards, badges, tables, dialogs)
Day 11-14: Landing page (hero, architecture diagram, feature grid, demo reviews)
```

### Phase 2: Core Screens (Week 3–4)

```
Day 15-18: Dashboard (stat cards, recent projects, activity feed, pipeline status)
Day 19-22: Corpus Manager (document table, upload zone, detail panel, search/filter)
Day 23-26: Document Viewer (PDF viewer, metadata panel, claims list, entities list)
Day 27-30: Knowledge Graph Explorer (React Flow setup, custom nodes/edges, sidebar, filters)
```

### Phase 3: Query & Review (Week 5–6)

```
Day 31-34: Query Interface (input, pipeline progress, evidence cards, traceability)
Day 35-38: Review Generator (step form, type selection, real-time progress, preview)
Day 39-42: Review Viewer (section navigation, finding cards, evidence expansion, traceability panel)
Day 43-44: Export functionality (PDF, Markdown, JSON download)
```

### Phase 4: Monitoring & Polish (Week 7–8)

```
Day 45-47: System Monitoring (metrics grid, processing queue, error logs, D3 charts, cache metrics)
Day 48-49: Keyboard shortcuts system, accessibility audit, screen reader testing
Day 50-51: Performance optimization (virtualization audit, memo audit, bundle analysis)
Day 52-54: Animation polish, micro-interactions, loading states, empty states, error states
Day 55-56: Cross-browser testing, mobile testing, final QA
```

### Phase 5: Release (Week 9)

```
Day 57-58: Documentation (component storybook, API integration guide, deployment guide)
Day 59:    Final performance testing, Lighthouse audit
Day 60:    Production build, deployment
```

---

## 15. Evaluation Criteria

### 15.1 Must Pass

| Criterion | Method | Target |
|-----------|--------|--------|
| All 9 screens render correctly | Manual walkthrough | No visual bugs |
| 940 existing M6 tests still pass | `pytest` | 100% |
| Graph renders 1000+ nodes at 60fps | DevTools Performance tab | ≥ 30fps |
| Document list scrolls 10000 items smoothly | Manual test + DevTools | No jank |
| PDF viewer loads in < 2s for 20-page doc | Measured load time | < 2s |
| Review generation shows real-time progress | Manual test | Stages update in real-time |
| All keyboard shortcuts work | Manual test | 100% |
| Dark/light mode all screens | Manual test | No unreadable areas |
| Command palette opens in < 100ms | Measured | < 100ms |
| All 9 screens accessible via keyboard | Manual tab-through | No dead ends |

### 15.2 Lighthouse Targets

| Metric | Target |
|--------|--------|
| Performance | ≥ 90 |
| Accessibility | ≥ 95 |
| Best Practices | ≥ 90 |
| SEO | ≥ 90 |

### 15.3 Bundle Budget

Budgets are set per route — not as global aggregate — to ensure each page loads within acceptable time.

**Per-route budgets (compressed JS + CSS total):**

| Route | Budget (compressed) | Loading Strategy |
|-------|-------------------|------------------|
| `/` (Landing) | ≤ 150 KB | Static generation (SSG). No client JS bundle — only Tailwind utility CSS. |
| `/login` / `/register` | ≤ 150 KB | Static generation. Shared auth chunk. |
| `/app/dashboard` | ≤ 250 KB (initial) | Server-side rendered (SSR). Dashboard widgets are split by feature (recent reviews, system status, metrics) and loaded on interaction. |
| `/app/reviews` | ≤ 300 KB (initial) | SSR. List view + filter panel. Detail view loaded via dynamic `import()` on row click. |
| `/app/reviews/[id]` | ≤ 200 KB (initial) + Review Viewer | SSR. Review Viewer chunk lazy-loaded (~150 KB). |
| `/app/graph` | ≤ 500 KB (lazy) | Fully lazy-loaded via `next/dynamic`. Graph chunk (~200 KB) + d3-force (~80 KB) + Fuse.js (~30 KB). Not loaded on any other route. |
| `/app/corpus` | ≤ 200 KB (initial) | SSR. Document list chunk (~80 KB). |

**Dynamic import plan:**

```typescript
// next/dynamic boundaries — each becomes a separate chunk
const GraphExplorer = dynamic(() => import("@/features/graph"), {
  loading: () => <GraphSkeleton />,
  ssr: false,
});

const ReviewViewer = dynamic(() => import("@/features/review/ReviewViewer"), {
  loading: () => <ReviewSkeleton />,
});

// Dashboard widgets — only load what's visible
const SystemMetrics = dynamic(() => import("@/features/dashboard/SystemMetrics"));
const RecentReviews = dynamic(() => import("@/features/dashboard/RecentReviews"));
const PipelineStatus = dynamic(() => import("@/features/dashboard/PipelineStatus"));
```

**Enforcement:**
- PR pipeline runs `next build --profile` and checks per-route JS/CSS sizes
- Budget violations fail CI (block PR merge)
- Tools: `@next/bundle-analyzer` (manual review) + `bundlesize` config (CI enforcement)

---

## Appendix A: Directory Structure

```
researchmind-studio/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
├── public/
│   ├── fonts/
│   └── images/
├── src/
│   ├── app/
│   │   ├── layout.tsx              // Root layout (providers, fonts)
│   │   ├── page.tsx                // Landing page
│   │   ├── app/
│   │   │   ├── layout.tsx          // App shell (sidebar, topbar)
│   │   │   ├── dashboard/
│   │   │   │   └── page.tsx
│   │   │   ├── corpus/
│   │   │   │   ├── page.tsx        // Corpus list
│   │   │   │   ├── [id]/
│   │   │   │   │   ├── page.tsx    // Corpus detail
│   │   │   │   │   └── doc/
│   │   │   │   │       └── [docId]/
│   │   │   │   │           └── page.tsx  // Document viewer
│   │   │   ├── graph/
│   │   │   │   └── page.tsx
│   │   │   ├── query/
│   │   │   │   ├── page.tsx
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx
│   │   │   ├── reviews/
│   │   │   │   ├── page.tsx
│   │   │   │   ├── new/
│   │   │   │   │   └── page.tsx
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx
│   │   │   ├── settings/
│   │   │   │   └── page.tsx
│   │   │   └── system/
│   │   │       └── page.tsx
│   │   └── api/                    // Next.js API routes (if needed for auth proxy)
│   ├── components/
│   │   ├── ui/                     // shadcn/ui primitives
│   │   ├── shell/                  // Layout components
│   │   │   ├── topbar.tsx
│   │   │   ├── sidebar.tsx
│   │   │   └── shell.tsx
│   │   ├── corpus/                 // Corpus page components
│   │   ├── document/               // Document viewer components
│   │   ├── graph/                  // Graph explorer components
│   │   ├── query/                  // Query interface components
│   │   ├── review/                 // Review components
│   │   └── shared/                 // Shared components
│   │       ├── stat-card.tsx
│   │       ├── confidence-badge.tsx
│   │       ├── entity-chip.tsx
│   │       ├── step-indicator.tsx
│   │       └── trace-chain.tsx
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts
│   │   │   ├── queries.ts
│   │   │   ├── mutations.ts
│   │   │   ├── websocket.ts
│   │   │   └── types.ts
│   │   ├── store/
│   │   │   ├── theme.ts
│   │   │   ├── ui.ts
│   │   │   └── graph.ts
│   │   └── utils/
│   │       ├── cn.ts               // clsx + tailwind-merge
│   │       └── format.ts           // Number/date formatting
│   ├── hooks/
│   │   ├── use-keyboard.ts
│   │   ├── use-debounce.ts
│   │   └── use-intersection.ts
│   └── styles/
│       └── globals.css             // Tailwind directives, design tokens
├── tailwind.config.ts
├── next.config.ts
├── tsconfig.json
├── package.json
└── README.md
```
