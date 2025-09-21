# ✅ Completed Task — Inline RequestAuthContext into AuthenticatedIdentity

## Context
`RequestAuthContext` duplicated fields that were already available on the resolved user, session, and API key. Flattening those attributes onto `AuthenticatedIdentity` keeps authentication metadata in one place and simplifies how dependencies read it.

## Outcome
- Removed the `RequestAuthContext` dataclass and taught `AuthenticatedIdentity` to expose the auth mode, session/api key identifiers, and SSO subject directly.
- Simplified `get_authenticated_identity` to populate the flattened fields for session, API key, and open-access flows without constructing an intermediate context object.
- Updated authentication tests to assert against the new attributes (and added checks for the derived IDs) before rerunning `pytest backend/tests/test_auth.py` to confirm behaviour.
