# Module 8 Phase 3A — Known Failures Audit

## Context
During the frontend test suite run (`npm run test`), 3 tests consistently fail out of 348 total tests. These failures are pre-existing and were not introduced by the Phase 3A remediation work.

## Failing Tests

### 1. `QueryMetrics Component > default > renders zeroes initially`
- **File:** `tests/query/query-metrics.test.tsx`
- **Error:** `TestingLibraryElementError: Found multiple elements with the text: 0`
- **Cause:** The test suite uses `getByText("0")` to assert the component's initial state. The `QueryMetrics` component displays "0" for Evidence Extracted, "0" for Reasoning Steps, and "0%" for Overall Confidence. The testing library finds all of these text nodes simultaneously and fails because `getByText` strictly expects a single matching node.
- **Flakiness:** Highly deterministic failure (always fails). It is a poorly written test rather than a flaky component.

### 2. `QueryMetrics Component > with metrics > renders metric values correctly`
- **File:** `tests/query/query-metrics.test.tsx`
- **Error:** `TestingLibraryElementError: Found multiple elements with the text: 0`
- **Cause:** Similar to failure #1, passing the metric `0` to multiple fields results in `getByText` finding multiple matching text nodes.
- **Flakiness:** Highly deterministic failure (always fails).

### 3. `QueryMetrics Component > edge case metrics > renders metric values correctly for edge case`
- **File:** `tests/query/query-metrics.test.tsx`
- **Error:** `TestingLibraryElementError: Found multiple elements with the text: 1`
- **Cause:** The edge case payload provides `{ evidenceCount: 1, reasoningSteps: 1, overallConfidence: 0.01, ... }`. The component renders multiple "1" elements (for evidence, reasoning steps, and the string "1%" for confidence). `getByText("1")` matches multiple elements and fails.
- **Flakiness:** Highly deterministic failure (always fails).

## Conclusion
These failures are purely related to testing-library syntax (`getByText` vs `getAllByText` or `getByTestId`). They are **NOT** functional regressions. 

**Verdict:** These failures do **NOT** block the Phase 3B rollout.
