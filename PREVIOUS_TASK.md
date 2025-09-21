# ✅ Completed Task — Cache authenticated identities on the request

## Context
Repeated dependency calls to `get_authenticated_identity` re-opened SQLAlchemy sessions and re-ran credential resolution whenever router-level and route-level dependencies both requested the current user. Route handlers also had to declare the dependency just to access the resolved identity.

## Outcome
- Stored the first resolved `AuthenticatedIdentity` on `request.state` so subsequent dependencies can reuse it without performing new database work.
- Simplified the FastAPI dependency stack by inlining the session and API key resolution logic inside `get_authenticated_identity`, removing the now-redundant dependency wrappers.
- Added targeted tests that exercise both cold and cached paths—including a router/route combination—and documented how dependency overrides should clear the cached state in tests.
