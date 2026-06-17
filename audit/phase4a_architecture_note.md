# Phase 4A Security Architecture Note

## Intended Phase 4A State

The goal of Phase 4A is to establish a secure foundation *without* activating active authentication enforcement or persisting users. The current state is strictly transitional and scaffolded to maintain system determinism while preparing for Phase 4B.

- **JWT Utilities**: jwt.encode and jwt.decode utilities are available and fully functional in security.py. They operate deterministically using a fixed iat and no exp.
- **Auth Routes**: Login, register, refresh, and logout routes are disabled and return 501 Not Implemented with the message: "Authentication activation deferred until Phase 4B."
- **Business Routes**: Query and Review routes remain completely public and unenforced. No Depends(get_current_user) dependencies are attached to these core endpoints.
- **Frontend Integration**: There is no active frontend authentication flow. The Next.js application remains fully accessible.
- **User Management**: There are no database users, mock users, or placeholder accounts.
- **Middleware**: Security headers are correctly scaffolded (with conditional HSTS). Rate limiting is present as a structural middleware but active request tracking and 429 generation are disabled.

This ensures Phase 4B can seamlessly inject persistence without dismantling temporary authentication hacks.
