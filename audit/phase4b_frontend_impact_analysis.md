# Phase 4B Frontend Authentication Impact Analysis

## Next.js Integration Requirements

### Public vs Protected Routes
- **Public**: /login (new), /register (new).
- **Protected**: /dashboard, /query, /reviews, /corpus, /monitoring. (Virtually the entire active app).

### Session Management Requirements
- The frontend needs to intercept 401 Unauthorized responses to transparently refresh access tokens via the /refresh endpoint.
- If refresh fails, it must redirect to /login.
- A global UI state context (or TanStack query provider wrapper) will need to hold the authenticated user's profile and roles.

### Navigation Changes
- The sidebar requires a "Logout" action.
- A "User Profile" snippet needs to be injected into the top navigation.
- A new layout wrapper might be required to boundary unauthenticated users from the pp/(protected) pages.
