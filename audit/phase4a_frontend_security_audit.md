# Phase 4A Frontend Security Audit

## Vulnerability Landscape

### Token Storage Strategy
- **Current State:** N/A (Missing).
- **Risk:** Storing JWTs in localStorage or sessionStorage exposes them to Cross-Site Scripting (XSS) attacks. If any dependency is compromised, tokens can be exfiltrated.
- **Requirement:** Next.js Server Components should proxy authentication, storing the raw JWT in an HTTP-Only, Secure, SameSite=Strict cookie. The React client should never have access to the raw token string.

### XSS Risks
- **Current State:** React naturally sanitizes text nodes, but dangerously setting inner HTML is highly risky.
- **Risk:** If Markdown parsing in the Review generation flow is not strictly sanitized, injected <script> tags could execute.
- **Requirement:** Implement robust Markdown sanitization (e.g., DOMPurify) before rendering LLM outputs to the UI.

### Environment Variables & Secrets
- **Current State:** NEXT_PUBLIC_API_URL is exposed, which is necessary.
- **Risk:** Ensuring that no backend secrets (like OpenAI keys or database URIs) are prefixed with NEXT_PUBLIC_, which would leak them into the client bundle.
- **Requirement:** Strict env validation isolating Next.js server-only secrets from NEXT_PUBLIC_ variables.

### API Communication & Error Handling
- **Current State:** pi-client.ts sanitizes 500-level errors effectively.
- **Risk:** Exposing internal system errors via 4xx/5xx responses could give attackers footprinting data.
- **Requirement:** Maintain current obfuscation of 500-level errors while ensuring no user data leaks in 400 validation error text.
