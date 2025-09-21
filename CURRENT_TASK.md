# 🔄 Next Task — Unify Request Auth Context Handling

## Context
The authentication refactor consolidated service helpers, but request-state updates are still split between `routes/auth.py` and `services/auth.py`. Each module defines its own `_set_request_context` with slightly different fields (`subject` vs `api_key_id`). Maintaining parallel implementations risks drift and makes it harder to add future metadata (for example, MFA markers or login sources) in a single place.

## Goals
1. Introduce a small dataclass or helper in `backend/app/services/auth.py` that builds the request auth context dictionary with optional `session_id`, `api_key_id`, and `subject` fields.
2. Update both the FastAPI dependency and the `/auth` routes to rely on this shared helper so request state is populated consistently.
3. Keep backwards compatibility for downstream code that reads `request.state.auth_context`, `request.state.auth_session`, or `request.state.api_key`.

## Implementation notes
- Prefer a dataclass with a `to_dict()` helper for clarity, but keep it lightweight and free of FastAPI imports.
- Ensure the helper accepts optional subject information so SSO logins continue to store the subject when available.
- Add or update tests around request context capture to cover the shared helper.

## Definition of done
- Only one code path is responsible for building the auth context dictionary.
- `routes/auth.py` delegates request-state mutation to the shared helper.
- `pytest backend/tests/test_auth.py` continues to pass.
