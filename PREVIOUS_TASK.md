# ✅ Completed Task — Collapse AuthResolution into get_authenticated_identity

## Context
`AuthResolution` and `AuthFailure` were the last wrappers between credential resolution and FastAPI dependencies. They duplicated the shape of `AuthenticatedIdentity` and forced callers to branch on success vs. failure.

## Outcome
- Reworked `resolve_credentials` to return `AuthenticatedIdentity` directly or raise an `HTTPException`, keeping the lazy commit logic for revoked sessions intact.
- Simplified `get_authenticated_identity` to delegate to the resolver without additional branching while still supporting the open-access mode.
- Updated authentication tests to expect the flattened return value (or captured exceptions) and reran `pytest backend/tests/test_auth.py` to confirm behaviour.
