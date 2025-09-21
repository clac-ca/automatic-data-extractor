# 🔄 Next Task — Collapse AuthResolution into get_authenticated_identity

## Context
Flattening `RequestAuthContext` left `AuthResolution` and `AuthFailure` as the last indirection between resolved credentials and the FastAPI dependency. Those dataclasses now duplicate the shape of `AuthenticatedIdentity` and only exist so `get_authenticated_identity` can branch on success or failure. We can simplify the authentication flow further by letting the resolution step return an `AuthenticatedIdentity` directly (or raise an HTTP-aware error), eliminating the extra wrappers.

## Goals
1. Remove the `AuthResolution` dataclass and return an `AuthenticatedIdentity` (or raise) from the credential resolver.
2. Raise clear HTTP errors for invalid sessions and API keys without the intermediary dataclass, keeping any required headers (e.g. `WWW-Authenticate`).
3. Update callers and tests to rely on the streamlined dependency so nothing references `AuthResolution` or `AuthFailure`.

## Implementation notes
- Inline or rewrite `resolve_credentials` so it either yields an `AuthenticatedIdentity` or raises `HTTPException`. Keep the lazy-commit logic around session revocation intact.
- Adjust unit tests that currently inspect `AuthResolution` to assert against the new return value or captured exceptions.
- Ensure the exported surface in `auth_service.__all__` reflects the new structure (dropping removed names).

## Definition of done
- `AuthResolution` and `AuthFailure` are removed from the codebase.
- `resolve_credentials` (or its replacement) returns the flattened identity or raises an `HTTPException` that matches previous behaviour.
- `pytest backend/tests/test_auth.py` passes.
