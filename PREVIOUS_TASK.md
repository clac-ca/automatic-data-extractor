# ✅ Completed Task — Remove Legacy Request Auth Context Fallback

## Context
`AuthenticatedIdentity` now propagates a `RequestAuthContext` dataclass through FastAPI requests, but the middleware still mirrored that data into a legacy `request.state.auth_context` dictionary. The duplicate storage path was unused and forced conversion logic that obscured the single source of truth.

## Outcome
- Updated `set_request_auth_context` to store only the dataclass instance on `request.state`.
- Simplified `get_request_auth_context` so it returns the stored dataclass or `None`, eliminating dictionary reconstruction and legacy handling.
- Refreshed authentication tests to reflect the streamlined storage strategy.
