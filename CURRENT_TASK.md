# 🔄 Next Task — Make get_authenticated_identity the sole credential resolver

## Context
With `resolve_credentials` now returning an `AuthenticatedIdentity` (or raising), `get_authenticated_identity` only checks for the open-access mode before delegating. Keeping both functions as public entrypoints creates surface area we no longer need.

## Goals
1. Inline the credential resolution logic into `get_authenticated_identity` (or make the helper private) so FastAPI consumers have a single dependency to import.
2. Preserve the existing lazy commit/rollback behaviour for session revocation and API key usage updates.
3. Update tests to exercise `get_authenticated_identity` directly and drop any references to a public `resolve_credentials` helper.

## Definition of done
- `resolve_credentials` is either removed or renamed private and no longer exported.
- Tests cover authentication flows through `get_authenticated_identity` without importing the helper.
- `pytest backend/tests/test_auth.py` passes.
