# Module 7 — UI Architecture Audit

**Date:** 2026-06-12
**Audited Document:** `architecture/module7_ui_architecture.md`
**Status:** NOT READY — blocking fixes required

---

## Executive Summary

**Overall Score: 3 / 5**

The architecture document is thorough in scope (15 sections, 9 screens, 1211 lines) and makes reasonable high-level technology choices. However, it contains several critical gaps in areas that directly impact feasibility — specifically graph rendering at scale, real-time infrastructure robustness, authentication completeness, and performance budgeting.

The document reads as a strong *directional* guide but lacks the *specification* depth needed to begin implementation without discovering show-stopping problems mid-build.

| Area | Score | Key Issue |
|------|-------|-----------|
| Technology Stack | 4/5 | Good choices, but Framer Motion bundle cost unaddressed |
| State Management | 4/5 | Graph viewport in Zustand will cause rerender storms |
| Graph Explorer | 2/5 | React Flow at 50k nodes is infeasible without cluster rendering strategy |
| Corpus Manager | 3/5 | Search strategy unspecified (client vs server) — affects 100k-doc viability |
| Query Interface | 3/5 | Large evidence chains lack virtualization plan |
| Review Viewer | 3/5 | Hundreds of findings without virtualization is a scroll performance risk |
| Real-Time System | 2/5 | No reconnection strategy, no polling fallback, no connection status |
| Accessibility | 3/5 | Graph keyboard navigation unspecified, live regions missing |
| Responsive | 3/5 | Mobile graph filtering usability not addressed |
| Security | 3/5 | Authentication flow unspecified (login/registration/refresh) |
| UX | 3/5 | Keyboard shortcut discoverability, error boundary strategy absent |
| Performance | 2/5 | Bundle budget unrealistic for pages with React Flow or D3 |

---

## Findings Table

| ID | Finding | Severity | Classification |
|----|---------|----------|----------------|
| A1 | Framer Motion at ~30KB gzip for micro-interactions is expensive; CSS transitions cover > 90% of use cases | MEDIUM | PERFORMANCE RISK |
| A2 | D3 at ~40KB gzip for charts; recharts or visx are lighter and React-native | MEDIUM | PERFORMANCE RISK |
| A3 | No testing strategy (Vitest, Playwright, Storybook, MSW) in architecture | LOW | IMPLEMENTATION CONCERN |
| B1 | Graph viewport in Zustand causes excessive rerenders on every pan/zoom; React Flow owns viewport internally | MEDIUM | ARCHITECTURE BUG |
| B2 | WebSocket event handler calling `invalidateQueries` on unmounted components causes React state warnings | MEDIUM | IMPLEMENTATION CONCERN |
| C1 | React Flow cannot render 50k nodes; practical upper limit is ~5k with optimization, ~1k without | CRITICAL | PERFORMANCE RISK |
| C2 | Force-directed layout at 10k+ nodes takes minutes; no Web Worker or algorithmic fallback specified | HIGH | PERFORMANCE RISK |
| C3 | Node search at scale unspecified (client-side index vs server query); client-side search of 50k nodes freezes UI | HIGH | ARCHITECTURE BUG |
| C4 | Edge rendering at 10k+ creates massive SVG DOM; needs explicit Canvas rendering configuration | MEDIUM | PERFORMANCE RISK |
| C5 | Lasso selection of 1000+ nodes blocks main thread; needs throttling | MEDIUM | PERFORMANCE RISK |
| D1 | Document search for 100k docs unspecified (client filter vs server query); client-side of cached 100k is infeasible | HIGH | ARCHITECTURE BUG |
| D2 | Bulk delete at 100k-doc scale lacks confirmation, progress, undo, or chunked execution | MEDIUM | UX RISK |
| E1 | Large query results (100+ evidence items) lack virtualization or pagination | MEDIUM | PERFORMANCE RISK |
| E2 | No abort controller for in-flight queries when user submits a new query | LOW | IMPLEMENTATION CONCERN |
| F1 | Hundreds of findings without virtual scrolling creates DOM pressure | HIGH | PERFORMANCE RISK |
| G1 | WebSocket has no reconnection strategy (exponential backoff, max retries) | CRITICAL | ARCHITECTURE BUG |
| G2 | WebSocket has no polling fallback — if connection fails, real-time UX is permanently broken | CRITICAL | ARCHITECTURE BUG |
| G3 | No connection status exposed to UI (connected/disconnected/reconnecting) | MEDIUM | UX RISK |
| G4 | No message deduplication or sequence numbers on reconnect | MEDIUM | IMPLEMENTATION CONCERN |
| H1 | Graph nodes not keyboard-navigable (arrow keys, enter to select) — WCAG 2.1 AA failure | HIGH | ACCESSIBILITY GAP |
| H2 | No `aria-live` regions for real-time pipeline updates | MEDIUM | ACCESSIBILITY GAP |
| H3 | Light mode color tokens not specified; current design tokens are dark-only | MEDIUM | ACCESSIBILITY GAP |
| H4 | Slide-over panels lack focus-restore-on-close behavior | MEDIUM | ACCESSIBILITY GAP |
| I1 | Graph Explorer on mobile: complex filtering (type toggles, sliders) hidden in collapsible sidebar — no filter button/modal specified | HIGH | UX RISK |
| I2 | PDF viewer on mobile: pinch-zoom, page navigation, and search usability not addressed | MEDIUM | UX RISK |
| I3 | Review Viewer sidebar on mobile: section jumping mechanism unspecified (scroll list vs select dropdown) | MEDIUM | UX RISK |
| J1 | File upload MIME validation appears client-side; trivially bypassed — server must re-validate | HIGH | SECURITY GAP |
| J2 | Authentication flow not designed — no login, registration, token refresh, session expiry, or password reset | CRITICAL | SECURITY GAP |
| J3 | Markdown/HTML rendering of review content (titles, labels) without sanitization risks XSS | MEDIUM | SECURITY GAP |
| J4 | CSRF protection implementation unspecified (Double Submit Cookie? SameSite?) | MEDIUM | SECURITY GAP |
| K1 | Keyboard shortcut discoverability not addressed (no ⌘K help screen, no tooltip hints) | MEDIUM | UX RISK |
| K2 | Review Generator step 1 has high cognitive load: 8 type cards + 6 controls + preview panel on one screen | MEDIUM | UX RISK |
| K3 | No error boundary strategy defined (global vs per-page, fallback UI) | MEDIUM | UX RISK |
| K4 | Settings page designed in route structure but has zero content definition | LOW | IMPLEMENTATION CONCERN |
| L1 | Bundle budget (120KB initial JS) is unrealistic; React (40KB) + Next.js runtime (20KB) + TanStack Query (12KB) + Framer Motion (30KB) + page components (~20KB) = ~122KB *before* any third-party UI | HIGH | PERFORMANCE RISK |
| L2 | D3 at 40KB for charts on system monitoring page pushes lazy bundle over 80KB target | MEDIUM | PERFORMANCE RISK |
| L3 | React Flow at 50KB for graph explorer pushes lazy bundle over 80KB target | MEDIUM | PERFORMANCE RISK |

---

## Detailed Analysis

### A. Technology Stack Audit

**A1 — Framer Motion bundle cost (MEDIUM)**

Framer Motion adds ~30KB gzip to every page that uses it. For micro-interactions (button hover, card lift, toggle switch) a CSS transition is identical in perceived quality and costs 0KB. Framer Motion is justified for layout transitions (sidebar collapse, panel slide) and page transitions, but the document applies it universally. Recommendation: restrict Framer Motion to layout/panel/page transitions; use CSS transitions for micro-interactions.

**A2 — D3 bundle cost for charts (MEDIUM)**

D3 at ~40KB gzip is heavy if only used for 4 chart types on the system monitoring page. Recharts (built on D3, ~15KB) or visx (by Airbnb, ~20KB) cover line, bar, area, and gauge charts with first-class React integration. D3 should be reserved for custom visualization needs that recharts/visx cannot meet.

**A3 — No testing strategy (LOW)**

The document omits E2E (Playwright), component (Vitest + Testing Library), visual regression (Chromatic/Percy), and API mocking (MSW). This is acceptable for an architecture document (testing is a separate concern) but should be added before implementation begins.

---

### B. State Management Audit

**B1 — Graph viewport in Zustand causes rerender storms (MEDIUM)**

The `GraphStore` includes viewport state (`zoom`, `position` — implied by `selectedNodes` and layout). React Flow manages its own viewport internally and fires `onMove` callbacks on every pan/zoom frame (at 60fps). Putting this in Zustand triggers React re-renders on every frame, causing jank. Fix: React Flow viewport should stay in React Flow internal state. Zustand should only store *intentional* state (selected nodes, filters, layout mode). The viewport should only be stored if "restore last viewport" is a feature — and even then, debounced to once per second.

**B2 — WebSocket invalidation on unmounted components (MEDIUM)**

The document specifies that WebSocket events call `queryClient.invalidateQueries()`. If a user navigates away from a page and the WebSocket event arrives for a stale subscription, `invalidateQueries` triggers refetches for queries that the current page doesn't need. This is wasteful but not destructive. However, if the event handler captures React state via closure, it can trigger state updates on unmounted components. Fix: use a ref to track mounting state in the WebSocket event handler, or let TanStack Query's built-in `gcTime` handle stale data cleanup.

**B3 — Zustand `Set` serialization in GraphStore (LOW)**

The `GraphStore` uses `Set<string>` for filter types. `Set` is not JSON-serializable. If Zustand's `persist` middleware is ever applied to `GraphStore`, `Set` will be serialized as `{}`. Fix: use arrays or a simple object map instead of `Set`.

---

### C. Graph Explorer Audit

**C1 — React Flow cannot render 50k nodes (CRITICAL)**

React Flow's practical upper limit is ~1000 nodes without optimization and ~5000 with aggressive optimization (simplified node types, disabled dragging, `panOnDrag: true`, `nodesDraggable: false`). Beyond 5000, memory consumption from React component instances and event handlers causes visible jank. At 50k nodes, the browser tab will crash.

The document mentions "Progressive loading — show cluster-level view first, expand on zoom" but provides no specific strategy:
- How are clusters computed? (server-side? client-side via Web Worker?)
- What is the threshold for switching to cluster view? (10k? 20k?)
- How does "expand on zoom" work technically? (replace cluster node with sub-nodes?)
- What happens to edge rendering when clusters are collapsed? (intra-cluster edges hidden)

This is the single most technically risky aspect of the architecture. The document needs:
1. A defined node count threshold for cluster mode (recommend: 2000)
2. A protocol for server-side cluster computation (the backend returns cluster-level + detail-on-demand)
3. A specification for the expand-on-zoom interaction

**C2 — Force-directed layout at 10k+ nodes (HIGH)**

Force-directed layout (e.g., d3-force, ngraph) is O(n²) per iteration. At 10k nodes with 50k edges, even a Web Worker needs 30+ seconds to converge. At 50k nodes, it's impractical. The document says "Run force-layout in a Web Worker if > 500 nodes" but doesn't specify:
- Which algorithm (d3-force? ngraph? custom?)
- Timeout threshold (how long before showing partial layout?)
- Fallback layout (grid/circular for very large graphs?)
- Does the user see a blank canvas during layout computation?

**C3 — Node search at scale unspecified (HIGH)**

The document says "Search input: Search nodes by label or ID" without specifying client vs server search. At 50k nodes, client-side search of the full dataset (even with Fuse.js) blocks the main thread for 500ms+. At 100k+, it's unusable. If search is server-side, the document doesn't specify the API endpoint, debounce timing, or loading state.

**C4 — Edge rendering and Canvas configuration (MEDIUM)**

React Flow renders edges as SVG by default. 10k edges create 10k SVG elements in the DOM. React Flow v12 supports `edgeTypes` with Canvas rendering, but this requires explicit configuration not mentioned in the document.

---

### D. Corpus Manager Audit

**D1 — Search strategy for 100k documents unspecified (HIGH)**

The document says "Search input (filters table by title/author)" but doesn't specify client-side vs server-side. For 100k documents:
- Client-side: requires fetching all 100k documents, then filtering in JavaScript. Feasible only if search is debounced and run on cached data (~10MB for 100k titles). Acceptable if the API returns all document metadata in one request (unlikely for large corpora).
- Server-side: requires an API endpoint with `?q=searchterm&page=1` semantics. The current API design has no search endpoint.

The document should specify server-side search with debounced client input (300ms) and a dedicated `GET /api/v1/corpus/:id/documents?q=:query` endpoint.

**D2 — Bulk delete at scale (MEDIUM)**

"Delete selected" for 100k documents needs:
- Confirmation dialog with count
- Server-side batch execution (not N individual DELETE requests)
- Progress indicator
- Undo capability (short window)
- Optimistic removal from TanStack Query cache

None of these are mentioned.

---

### E. Query Interface Audit

**E1 — Large evidence chains lack virtualization (MEDIUM)**

The document describes evidence cards as a flat list. For queries returning 100+ evidence items, the DOM will contain 100+ card components. With TanStack Virtual, this is trivially solved: virtualize the evidence list with variable row height (evidence cards have variable content length). The document already uses TanStack Virtual for document lists but doesn't extend it to evidence items.

**E2 — No abort controller for in-flight queries (LOW)**

If a user submits a query and then submits a different query (or navigates away), the in-flight request continues. For long-running queries (M5 pipeline may take seconds), this wastes server resources and risks state updates on unmounted components. TanStack Query supports `AbortController` via `queryClient.cancelQueries`.

---

### F. Review Viewer Audit

**F1 — Hundreds of findings without virtualization (HIGH)**

A review can contain hundreds of findings across multiple sections. Each finding card includes statement text, confidence badge, type badge, expandable evidence (potentially 5+ items), and a traceability button. At 200 findings with all evidence expanded, the DOM could contain 1000+ elements. Combined with the sidebar section navigation and toolbar, this creates significant scroll jank.

Fix: virtualize the finding list per section using TanStack Virtual with variable row height (findings have variable height when evidence is expanded). This approach is already mentioned in the performance strategy (section 10.1) but not applied to the Review Viewer design.

---

### G. Real-Time System Audit

**G1 — No WebSocket reconnection strategy (CRITICAL)**

The document defines WebSocket event types and invalidation logic but omits reconnection entirely. Without:
- Exponential backoff (1s, 2s, 4s, 8s, max 30s)
- Maximum retry count (or infinite for persistent connections)
- Jitter to prevent thundering herd on server restart
- Connection state management (connecting, open, closing, closed)

...the WebSocket connection will fail permanently on any network interruption. The architecture *must* specify a reconnection strategy before implementation.

**G2 — No polling fallback (CRITICAL)**

If WebSocket connections are blocked by a corporate firewall, proxy, or restrictive network policy (common in academic environments — the target user demographic), the entire real-time UX is broken: pipeline progress never updates, review generation appears stuck, document processing status never refreshes.

Fix: implement a polling fallback that kicks in after N failed WebSocket connection attempts. For pipeline status, poll `GET /api/v1/pipeline/status` every 5s. For review generation, poll `GET /api/v1/review/:id` every 2s. Switching between WebSocket and polling should be transparent to the UI layer (abstracted in a `useRealtime` hook).

**G3 — No connection status in UI (MEDIUM)**

Without exposing WebSocket connection state to the UI, users have no way to know if real-time updates are working. A common pattern: a small indicator in the top bar (green dot = connected, yellow = reconnecting, red = disconnected). This is standard in Linear, Vercel, and similar tools.

**G4 — No message deduplication (MEDIUM)**

When WebSocket reconnects, it may receive duplicate events (pipeline:stage_complete that was already processed before disconnection). The simplest fix: include a `sequence` number or `timestamp` in each event. The client tracks the last processed sequence and ignores older events.

---

### H. Accessibility Audit

**H1 — Graph keyboard navigation (HIGH)**

React Flow supports keyboard interaction but requires explicit implementation:
- Arrow keys to move focus between nodes (React Flow provides `onNodesChange` but not built-in keyboard navigation between arbitrary nodes)
- Enter/Space to select a focused node
- Tab to move between the graph canvas and surrounding UI
- Escape to deselect

Without this, the graph explorer fails WCAG 2.1 AA 2.1.1 (Keyboard). The document targets WCAG 2.1 AA but doesn't specify graph keyboard navigation.

**H2 — No `aria-live` regions (MEDIUM)**

Real-time pipeline updates (stage start, complete, error) should be announced to screen readers via `aria-live="polite"` regions. The document mentions "live regions for pipeline progress updates" in the accessibility implementation section but doesn't specify where or how these are implemented in the per-page designs.

**H3 — Light mode color tokens absent (MEDIUM)**

The design system tokens (section 7.2) specify only dark mode colors. Light mode is the "secondary" target but has no token definitions. Dark mode colors won't work for light mode — `--color-bg: #0a0a0b` is pure black, `--color-text: #f4f4f5` is near-white. Light mode needs the inverse. This will be discovered mid-implementation, causing rework.

**H4 — Slide-over focus restore (MEDIUM)**

The document specifies focus trapping in slide-over panels (correct) and dismiss on Escape (correct). Missing: when the slide-over closes, focus must return to the element that triggered it (usually a button). Without this, keyboard users are disoriented — WCAG 2.1 AA 2.4.3 (Focus Order).

---

### I. Responsive Design Audit

**I1 — Graph Explorer filtering on mobile (HIGH)**

On mobile (< 768px), the sidebar is "hidden by default" and filters are inside it. The document doesn't specify how users access filters on mobile: a floating filter button (like Google Maps)? A bottom sheet? A toolbar at the top? Without a mechanism, the graph explorer's primary interaction (filtering) is inaccessible on mobile.

**I2 — PDF viewer on mobile (MEDIUM)**

PDF viewing on small screens presents challenges: text is too small to read at fit-to-width, pinch-zoom requires precise gestures, page navigation with fat fingers is error-prone, and annotations/highlights overlay tiny targets. The document says "PDF stack vertically above metadata on mobile" but doesn't address readability or navigation.

**I3 — Review Viewer section jumping on mobile (MEDIUM)**

On mobile, the sidebar "becomes hamburger menu." The document doesn't specify whether section jumping uses a scrolling list, a select dropdown, or a bottom sheet. A hamburger menu with 5-10 section items works, but the interaction pattern is unspecified.

---

### J. Security Audit

**J1 — File upload MIME validation (HIGH)**

"Validate MIME type + extension" likely refers to client-side validation (`accept=".pdf"` and `File.type === "application/pdf"`). Client-side MIME validation is trivially bypassed by renaming a malicious file. Server-side validation is mandatory. The document mentions this implicitly (it's listed under "API Security" section 13.2) but doesn't clarify that client validation is UX-only and server validation is the security boundary.

**J2 — Authentication flow undefined (CRITICAL)**

The document specifies "JWT-based auth. Token stored in httpOnly cookie" and "Token refresh handled transparently by ApiClient" but omits:
- How does the user obtain the initial JWT? (login form? OAuth? API key?)
- Registration flow (sign-up form, email verification?)
- Token refresh mechanism (refresh token in a separate cookie? automatic refresh on 401?)
- Session timeout (idle timeout? absolute timeout?)
- Password reset flow
- "Sign in with Google" or SSO? (not required but should be considered)
- Logout (clear cookies, invalidate tokens server-side)

Authentication is foundational. Without specifying the flow, implementation cannot begin.

**J3 — Review content XSS risk (MEDIUM)**

Review content is template-generated by the backend, but document titles, entity labels, and user-supplied review titles are inserted into the template. If these contain `<script>` or event handler attributes, and the frontend renders them as HTML (e.g., `dangerouslySetInnerHTML`), XSS is possible. The document mentions "Sanitize document titles and metadata before rendering" but doesn't specify sanitization library (DOMPurify recommended) or whether content should be rendered as text vs HTML.

**J4 — CSRF protection unspecified (MEDIUM)**

JWT in httpOnly cookies protects against XSS-based token theft but is vulnerable to CSRF if the cookie is sent automatically with requests. The document mentions "CSRF token for all mutation endpoints" but doesn't specify the mechanism: Double Submit Cookie pattern? SameSite=Strict or Lax? Anti-CSRF token in a custom header?

---

### K. UX Audit

**K1 — Keyboard shortcut discoverability (MEDIUM)**

The document defines 12 keyboard shortcuts but doesn't specify how users discover them. Best practices:
- A "?" or "⌘K" screen showing all available shortcuts
- Tooltip hints on sidebar items showing the shortcut (e.g., "Dashboard (g d)")
- An onboarding tooltip for new users

Without discoverability, keyboard shortcuts are hidden power features that most users won't know exist.

**K2 — Review Generator step 1 cognitive load (MEDIUM)**

Step 1 of the Review Generator presents: 8 review type cards (each with title, description, section count) + 6 parameter controls (min confidence slider, max themes, max findings, include contradictions toggle, include gaps toggle, target entities multi-select) + a preview sidebar showing the estimated section structure. This is a dense screen. Consider progressive disclosure: first select review type (full-width cards), then show parameters as a secondary step or inline after selection.

**K3 — No error boundary strategy (MEDIUM)**

The document specifies loading and error states per page but doesn't mention React Error Boundaries. Without them, an uncaught JavaScript error in one component (e.g., a Graph Node render crash, a PDF page render failure) takes down the entire page. Strategy: one global Error Boundary at the shell level, and per-page Error Boundaries for complex screens (Graph Explorer, Document Viewer, Review Viewer).

**K4 — Settings page undefined (LOW)**

The route structure includes `/app/settings` but the document provides zero content definition. Settings should include: profile, API keys, theme, notifications, data export, account management.

---

### L. Performance Audit

**L1 — Bundle budget unrealistic (HIGH)**

Target: < 120KB initial JS (compressed). Estimate for the dashboard page:
- React + ReactDOM: ~40KB gzip (vendor chunk)
- Next.js App Router runtime: ~20KB gzip
- TanStack Query: ~12KB gzip
- Zustand: ~1KB gzip
- Framer Motion: ~30KB gzip
- shadcn/ui components on page: ~10KB gzip
- Application components (stat cards, etc.): ~15KB gzip
- **Total: ~128KB** — over budget before any page-specific logic

If Framer Motion is removed from the initial bundle and lazy-loaded only for pages that use layout animations, the initial bundle drops to ~98KB. This is achievable.

For graph explorer (lazy): React Flow at ~50KB + custom nodes/edges at ~15KB + layout algorithm at ~10KB = ~75KB. Under the 80KB target.

For system monitoring (lazy): D3 at ~40KB + chart components at ~10KB = ~50KB. If recharts replaces D3: ~15KB + ~10KB = ~25KB.

**Recommendation:** Remove Framer Motion from initial bundle. Use CSS transitions for micro-interactions. Dynamically import Framer Motion for page transitions and layout animations. Replace D3 with recharts or visx.

**L2 — D3 bundle for system monitoring (MEDIUM)**

See A2. D3 at 40KB is ~50% of the lazy chunk budget for system monitoring alone. Using recharts (15KB) saves 25KB.

**L3 — React Flow bundle for graph explorer (MEDIUM)**

React Flow at 50KB leaves only 30KB for custom nodes, layout algorithm, and sidebar components within the 80KB lazy budget. This is tight but achievable if custom nodes are kept simple (no heavy dependencies).

---

## Blocking Fixes (Required Before Implementation)

These issues make implementation infeasible or high-risk without resolution:

| ID | Finding | Why Blocking |
|----|---------|--------------|
| J2 | Authentication flow undefined | Cannot build any authenticated screen without knowing login/register/refresh flow |
| G1 | WebSocket reconnection strategy missing | Real-time pipeline UX will break on any network interruption |
| G2 | No polling fallback for WebSocket | Academic users behind firewalls cannot use real-time features |
| C1 | React Flow at 50k nodes infeasible | Graph explorer will crash with large corpora; must specify cluster rendering strategy |
| L1 | Bundle budget unrealistic | ~128KB initial JS exceeds 120KB target; need specific reduction plan |

## Recommended Improvements

| ID | Finding | Effort |
|----|---------|--------|
| A1 | Restrict Framer Motion to layout transitions | Low |
| A2 | Replace D3 with recharts/visx for standard charts | Low |
| B1 | Keep viewport in React Flow state, not Zustand | Low |
| C2 | Specify layout algorithm, timeout, and fallback for large graphs | Medium |
| C3 | Specify server-side node search with debounced client input | Low |
| D1 | Specify server-side search endpoint and debounce timing | Low |
| D2 | Add bulk operation UX: confirmation, progress, undo | Medium |
| E1 | Virtualize evidence cards with TanStack Virtual | Low |
| F1 | Virtualize finding lists per section | Low |
| G3 | Add connection status indicator to top bar | Low |
| G4 | Add sequence numbers to WebSocket events | Low |
| H1 | Specify graph keyboard navigation implementation | Medium |
| H2 | Add `aria-live` regions for pipeline updates | Low |
| H3 | Define light mode color tokens | Low |
| H4 | Implement focus restoration on slide-over close | Low |
| I1 | Specify mobile filter access mechanism for graph | Low |
| K1 | Add keyboard shortcut discoverability (⌘K help) | Low |
| K3 | Define error boundary strategy | Low |

---

## Final Question

**Can implementation begin immediately?**

### YES AFTER FIXES

**Justification:**

The architecture is directionally sound — the technology choices are appropriate, the screen designs are well-conceived, and the state management split (TanStack Query / Zustand / RHF) is correct. However, five blocking issues prevent safe implementation:

1. **No authentication flow** (J2) — every screen behind `/app/*` is unreachable without login/register/refresh
2. **No WebSocket reconnection strategy** (G1) — real-time pipeline UX is non-functional on any network interruption
3. **No polling fallback** (G2) — academic users behind firewalls cannot use real-time features
4. **Graph at 50k nodes infeasible** (C1) — the highest-risk architectural assumption without a cluster rendering specification
5. **Bundle budget unrealistic** (L1) — initial JS exceeds target by ~8% before page components

These five issues must be resolved in the architecture document before a single line of frontend code is written. The remaining findings (high-severity) should be resolved before Phase 3 (Query/Review implementation) to avoid rework, but do not block Phase 1 (Foundation) or Phase 2 (Core Screens).

**Recommendation:** Fix the architecture document, then proceed with Phase 1 implementation. Estimated document update effort: 2–3 days.
