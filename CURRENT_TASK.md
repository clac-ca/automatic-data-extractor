# 🔄 Next Task — Adopt the cached identity helper across stateful routers

## Context
`get_cached_authenticated_identity` now exposes the resolved `AuthenticatedIdentity` for any route running behind router-level authentication. Most routers still import `get_current_user` directly and reimplement actor metadata defaults, so we have an opportunity to standardise on the helper and trim redundant wiring.

## Goals
1. Update the configurations, jobs, and events routers to import `auth_service` once and rely on `get_cached_authenticated_identity(request)` whenever handler logic needs the current user.
2. Ensure event-producing endpoints (e.g., configuration updates, job mutations) automatically default `actor_type`, `actor_id`, and `actor_label` from the cached identity when callers omit them.
3. Remove any remaining per-handler `Depends(get_current_user)` declarations made redundant by router-level authentication, and document the pattern in the developer docs or inline comments.

## Definition of done
- Routers behind authentication consistently use `auth_service` plus the cached identity helper instead of re-declaring dependencies.
- Event metadata defaults to the authenticated user without altering behaviour when clients supply explicit overrides.
- Tests cover the new defaults, and documentation or inline notes describe when to use the helper versus `Depends(get_authenticated_identity)`.
