# 🔄 Next Task — Remove RequestAuthContext Request State Storage

## Context
`AuthenticatedIdentity` already carries the authenticated user, session, API key, and a `RequestAuthContext` instance for downstream dependencies. The service still writes that context onto `request.state.auth_context_model`, and the login routes call `set_request_auth_context` to keep it in sync. No production code reads from `request.state`, so the extra mutation path increases indirection without providing value.

## Goals
1. Remove the `set_request_auth_context` and `get_request_auth_context` helpers that read or write `request.state.auth_context_model`.
2. Update authentication dependencies and routes to rely on the `AuthenticatedIdentity` payload instead of request state for context propagation.
3. Simplify tests to assert against the dependency return values rather than request state mutation.

## Implementation notes
- Search for `set_request_auth_context` and `get_request_auth_context` usage before deleting the helpers.
- Update the login flows and open-access mode to surface the refreshed context through return values or response payloads.
- Ensure any documentation that references `request.state.auth_context_model` is updated or removed.

## Definition of done
- No code writes to or reads from `request.state.auth_context_model` during authentication.
- `AuthenticatedIdentity` remains the single source of truth for the resolved user, session, API key, and context data.
- `pytest backend/tests/test_auth.py` passes.
