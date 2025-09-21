# 🔄 Next Task — Drop Request State Mirrors for Session and API Key Models

## Context
`AuthenticatedIdentity` now exposes the resolved session and API key models directly to route dependencies. The authentication service still mirrors those ORM objects onto `request.state.auth_session` and `request.state.api_key`, but no runtime code reads those attributes. Keeping the redundant copies increases mutation on the request object without providing value.

## Goals
1. Stop writing `request.state.auth_session` and `request.state.api_key` inside `get_authenticated_identity`.
2. Update tests to reference the `AuthenticatedIdentity` payload instead of the removed request state attributes.
3. Confirm there are no remaining call sites that rely on the request state mirrors.

## Implementation notes
- Search the codebase for `auth_session` and `request.state.api_key` reads before removing the writes.
- If downstream code needs the session or API key, document how to access it from `AuthenticatedIdentity`.
- Maintain the existing behaviour for anonymous/open-access requests.

## Definition of done
- `get_authenticated_identity` no longer mutates `request.state` with session or API key objects.
- Tests only assert against `AuthenticatedIdentity` for session/API key access.
- `pytest backend/tests/test_auth.py` passes.
