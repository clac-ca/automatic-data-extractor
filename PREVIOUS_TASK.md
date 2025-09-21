# ✅ Completed Task — Remove RequestAuthContext Request State Storage

## Context
`AuthenticatedIdentity` already exposes the resolved user, session, API key, and a `RequestAuthContext`. We still mirrored the context onto `request.state.auth_context_model` via helper functions, even though nothing in production read it. The extra mutation path made login flows and dependencies harder to follow.

## Outcome
- Deleted the `set_request_auth_context` and `get_request_auth_context` helpers and stopped mutating `request.state` during authentication.
- Taught `get_authenticated_identity` to derive SSO subjects from the loaded user model so context stays populated without per-request state.
- Simplified login routes and tests to assert directly against the dependency return values, then re-ran `pytest backend/tests/test_auth.py` to verify behaviour.
