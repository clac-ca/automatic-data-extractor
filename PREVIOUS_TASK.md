# ✅ Completed Task — Drop Request State Mirrors for Session and API Key Models

## Context
`AuthenticatedIdentity` already carries the resolved session and API key ORM models, but `get_authenticated_identity` continued mirroring those objects onto `request.state.auth_session` and `request.state.api_key`. The redundant attributes added request mutation without any call sites consuming them.

## Outcome
- Removed the `request.state.auth_session` and `request.state.api_key` writes when resolving an authenticated identity.
- Updated authentication tests to assert against the `AuthenticatedIdentity` payload instead of the removed request state attributes.
- Re-ran `pytest backend/tests/test_auth.py` to confirm behaviour is unchanged.
