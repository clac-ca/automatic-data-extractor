# 🔄 Next Task — Expose a helper for reading the cached identity from the request

## Context
`get_authenticated_identity` now caches the resolved `AuthenticatedIdentity` on `request.state`, but route handlers and services still need a clean way to retrieve it when they already depend on router-level authentication. Providing a tiny accessor keeps downstream code from re-declaring authentication dependencies just to get at the user and makes the new cache easier to adopt.

## Goals
1. Add a helper (for example `auth_service.get_cached_identity(request: Request)`) that returns the cached identity or raises a clear error if authentication has not run yet.
2. Update at least one router that currently uses `Depends(get_current_user)` inside a route handler despite having a router-level dependency, demonstrating the helper in action.
3. Document and test the helper so contributors know how and when to use it, including behaviour when the cache is missing.

## Definition of done
- The helper reads `request.state` without re-running authentication and returns the same identity object set by `get_authenticated_identity`.
- A representative route handler uses the helper instead of a redundant dependency, with no change to behaviour or authorisation checks.
- Tests cover successful retrieval and the error path when the cache is absent, and documentation or inline notes describe the helper’s usage.
