# M7-8 System Monitoring Architecture

## 1. Scope
**In Scope:**
- System-wide visibility of M1 through M6 modules.
- Live-simulated polling for operational health and queue processing.
- Aggregated performance graphs and real-time statistics.
- Strict deterministic mocked monitoring logs for testing.

**Out of Scope:**
- Active administration (restarting modules, purging queues).
- Interactive debugging of M4 graph algorithms.
- Real-time websockets (polling used instead for architectural simplicity).

## 2. Screen Architecture
The primary monitoring page acts as a grid dashboard.
- **Top Row:** System Health Panel & Global Metrics Overview.
- **Middle Row:** Performance Charts & Processing Queue.
- **Bottom Row:** Recent Errors & Corpus Statistics.
- **Sidebar/Modal:** Detailed Module Metrics.

## 3. Data Flow
1. **Zustand Store:** Manages active filters (time range) and selected UI focus.
2. **TanStack Query Hooks:** Fetches mock snapshot data via simulated API calls with 10s caching strategies.
3. **Mock Service:** Uses CRC32 + LCG deterministic PRNGs driven by the currently selected timestamp/range boundaries to ensure predictable charts.

## 4. State Management
- **Zustand `useMonitoringStore`:** `filters`, `selectedModule`, `selectedMetric`, `selectedJob`, `selectedError`.
- **TanStack `useQuery`:** `useSystemHealth()`, `usePerformanceMetrics()`, `useQueueJobs()`, `useRecentErrors()`.

## 5. Accessibility
- All error states are visually distinguishable beyond color (e.g., specific Lucide icons for Success, Warning, Error).
- Progress bars and charts include `aria-valuenow` attributes.

## 6. Performance Strategy
- **Route Budget:** `< 200 KB`.
- Avoid heavy SVG chart libraries. Use Tailwind + generic `div` bars to plot metrics for near-zero bundle cost.
- **Scalability Limit:** Up to 10k metric points are supported via internal grouping and virtualization if the queue table expands.
