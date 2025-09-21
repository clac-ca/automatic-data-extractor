# 🔄 Next Task — Simplify `get_current_user`

## Context
`auth/service.py` now hosts the low-level primitives for sessions, API keys, and auth events, but `auth/dependencies.get_current_user` still performs a long sequence of database lookups, refresh calls, and manual commit/rollback handling. The control flow is hard to audit and makes it easy to introduce regressions when adding new auth modes. Centralising this orchestration inside the service module will keep the dependency thin and make future changes (like new auth modes or telemetry) safer.

## Goals
1. Add a focused helper (function or lightweight dataclass) to `auth/service.py` that accepts the active DB session, settings, and incoming credentials (session cookie + bearer/API key tokens) and returns the resolved user plus any refreshed session or API key models.
2. Move the database transaction logic for session refresh/revocation and API key usage updates into this helper so `get_current_user` only coordinates FastAPI dependencies and request state updates.
3. Preserve the existing request context information (`auth_context`, `auth_session`, `api_key`) so downstream routes continue to behave the same.
4. Keep error handling identical—unauthenticated and invalid token responses should not change status codes or messages.

## Implementation notes
- Reuse the existing primitives in `auth/service.py`; avoid duplicating token hashing or timestamp utilities.
- A small return object (e.g. dataclass with `user`, `mode`, `session`, `api_key`, `error`) can make the dependency code clearer—prefer explicit fields over tuples.
- Continue to rely on FastAPI's `HTTPBearer`, `APIKeyHeader`, and `APIKeyCookie` dependencies for credential parsing.
- Update or extend tests only where necessary to cover the new helper.

## Definition of done
- `get_current_user` delegates the heavy lifting to the new helper and contains minimal branching.
- The new helper is covered by unit or integration tests to prove behaviour matches the previous implementation.
- No regressions in existing authentication flows (`pytest backend/tests/test_auth.py`).
