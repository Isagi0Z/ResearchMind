# Phase 4A Security Architecture

## Overview
The ResearchMind security architecture will transition from an entirely open local prototype to a production-grade secured API boundary. The architecture centers around stateless JWT (JSON Web Token) authentication, strict CORS policies, and HTTP-Only token transportation to mitigate frontend exposure.

## Core Components
1. **Identity Provider (FastAPI uth.py):** Handles credential verification, token issuance (Access & Refresh), and revocation list checking.
2. **Transport Security:** Next.js Server Components and API Routes acting as a BFF (Backend-For-Frontend) to proxy requests, storing the JWT in HTTP-Only, Secure, SameSite=Strict cookies.
3. **Role-Based Access Control (RBAC):** Token payloads will contain scope claims (ole: user vs ole: admin). FastAPI dependency injection (Depends(require_admin)) will enforce these scopes at the route level.
4. **Boundary Defense:** Rate limiting (Token Bucket) implemented via a lightweight middleware/Redis to prevent LLM abuse and DoS attacks.

## Determinism Integrity
All cryptographic processes (e.g., JWT signing algorithms, UUID generation for session IDs) will utilize the same deterministic crc32 / LCG fallback strategies when running under test environments, ensuring test reproducibility without compromising production entropy.
