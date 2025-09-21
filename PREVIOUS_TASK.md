# 🔄 Next Task — Reuse Auth Dependency State in Session & Profile Endpoints

## Context
The `get_current_user` dependency now relies on FastAPI security primitives and records the active session or API key on
`request.state`. The session refresh (`/auth/session`), logout, and `/auth/me` endpoints still re-implement the same lookups and
commit logic, issuing extra queries and diverging from the new code path. Aligning these routes with the dependency keeps the
behaviour consistent and removes the duplicated cookie handling that the recent refactor eliminated.

## Goals
1. Update `/auth/logout`, `/auth/session`, and `/auth/me` to consume `request.state.auth_session`, `request.state.api_key`, and
   `request.state.auth_context` when present instead of re-querying sessions and users from scratch.
2. Ensure session refreshes and revocations share the single database transaction established by the dependency (no
   `get_sessionmaker()` round-trips inside the routes).
3. Keep response payloads and audit events unchanged so the existing regression tests continue to pass.
4. Verify the dependency still populates context for API-key-only requests so `/auth/logout` can remain a no-op for those
   clients.

## Implementation notes
- Call `dependencies.get_current_user` once per request and rely on the state it sets; only fall back to manual lookups when
  absolutely necessary (e.g. cookie missing).
- Use `request.state.auth_session` to decide whether to refresh or revoke the session, and avoid redundant `sessions.get_session`
  queries.
- Preserve cookie clearing semantics and log events in the same circumstances as today.
- Keep the code straightforward: prefer direct `if` checks and explicit commits over new abstractions.

## Definition of done
- The auth routes no longer open ad-hoc database sessions or duplicate cookie parsing; they rely on the dependency’s state.
- Regression tests in `backend/tests/test_auth.py` still succeed without behavioural changes.
- No new dependencies or helper modules introduced.
