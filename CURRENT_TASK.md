# 🔄 Next Task — Provide AuthenticatedIdentity Dependency

## Context
`RequestAuthContext` is now attached to each request as a dataclass, but FastAPI routes still need direct access to `Request` so they can pull sessions, API keys, and context from `request.state`. A dedicated dependency that returns a typed bundle would let routes declare what they need via dependency injection, trim per-route boilerplate, and move us closer to standard FastAPI patterns instead of custom state juggling.

## Goals
1. Introduce a lightweight `AuthenticatedIdentity` dataclass in `backend/app/services/auth.py` that packages the current `User`, `RequestAuthContext`, and any associated `UserSession` or `ApiKey` instances.
2. Implement a new dependency (for example `get_authenticated_identity`) that reuses the existing credential resolution logic to populate the dataclass without duplicating state manipulation. The helper should rely on FastAPI's DI (`Depends`) instead of manual request plumbing.
3. Update the `/auth` routes (`logout`, `session_status`, `current_user_profile`) to consume the new dependency rather than reading from `request.state` directly.
4. Keep `get_current_user` available for other routers by delegating to the new dependency or otherwise reusing the same code path so behaviour stays consistent.

## Implementation notes
- The dataclass should allow `session` and `api_key` to be `None` while still exposing the underlying models when present.
- Prefer building on `set_request_auth_context`/`get_request_auth_context` to avoid mutating request state in multiple places.
- Add or update unit tests to cover the new dependency and the refactored routes, keeping the test suite deterministic.

## Definition of done
- `AuthenticatedIdentity` (or equivalent) is defined and used by a new dependency in `services/auth.py`.
- `/auth/logout`, `/auth/session`, and `/auth/me` rely on the new dependency rather than `request.state` lookups.
- `get_current_user` still returns the `User` object and continues to pass existing tests.
- `pytest backend/tests/test_auth.py` passes.
