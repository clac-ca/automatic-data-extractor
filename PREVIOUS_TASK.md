# ✅ Completed Task — Make get_authenticated_identity the sole credential resolver

## Context
`resolve_credentials` still exposed a parallel public API alongside `get_authenticated_identity`, leaving FastAPI consumers with two imports and duplicated resolution logic.

## Outcome
- Inlined the session and API key resolution workflow inside `get_authenticated_identity`, keeping the lazy commit/rollback behaviour for token revocation and metadata updates intact.
- Dropped the exported `resolve_credentials` helper so only the dependency remains part of the public surface.
- Updated authentication tests to cover the dependency directly and reran `pytest backend/tests/test_auth.py` to confirm behaviour.
