# Next Module Integration Strategy

## 1. System Integration Points

### Backend Hooks (`backend/api`)
- All new features must be exposed via FastAPI endpoints conforming to the established `/api/v1/` patterns.
- Existing core orchestrators must be utilized directly:
  - `QueryEngine` for query resolution.
  - `ReviewOrchestrator` for report generation.
  - `TraceabilityVerifier` for citation confidence checks.

### Frontend Hooks (`frontend/`)
- UI changes must integrate directly with existing Next.js App Router paths (`/query`, `/reviews`, `/dashboard`).
- Data must be passed via strictly typed interfaces reflecting the OpenAPI schemas of the backend.

## 2. Testing Integration
- **E2E & Integration:** New modules must not rely on `unittest.mock`. Actual class implementations must be wired end-to-end to ensure real integration paths are tested.
- **Environment Containment:** Any pipeline testing must adhere to the `D:\RM\.tmp` and `D:\RM\.cache` strict boundaries. Integration tests that produce file outputs must direct them to `D:\RM\.tmp` and exclude themselves from auto-collection to maintain a clean git working tree.

## 3. Deployment Constraints
- Main branch remains untouched. All integrations occur on `module5-development`.
- Only after successful integration, verification of determinism, and full containment will the module be considered ready for final promotion.
