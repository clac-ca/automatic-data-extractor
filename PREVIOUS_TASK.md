# ✅ Completed Task — Expose a helper for cached authentication identities

## Context
Routes already relying on router-level authentication needed a straightforward way to reuse the cached `AuthenticatedIdentity` without re-declaring `Depends(get_current_user)`. We also wanted a guardrail that fails loudly when authentication has not executed.

## Outcome
- Added `get_cached_authenticated_identity(request)` to return the identity stored on `request.state` and raise a descriptive `RuntimeError` when it is missing.
- Updated the documents router to import `auth_service` once, reuse the cached identity, and automatically populate event actor metadata without redundant dependencies.
- Documented the helper in the authentication guide and expanded tests to cover both the happy path and the missing-cache failure.
