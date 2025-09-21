# ✅ Completed Task — Reuse FastAPI's cookie dependency for session validation

## Context
`/auth/session` previously fetched the session cookie from `request.cookies` and raised HTTP errors by hand. Exposing a shared dependency built on FastAPI's `APIKeyCookie` keeps cookie access consistent and leans on the framework for error handling.

## Outcome
- Added `require_session_cookie` in `backend/app/services/auth.py` so routes obtain the raw cookie through FastAPI's dependency system and automatically return `401` when it is absent.
- Updated `/auth/session` to rely on the new dependency when refreshing sessions, eliminating direct cookie lookups and reusing the validated token when issuing the replacement cookie.
- Verified the authentication flow remains unchanged by running `pytest backend/tests/test_auth.py`.
