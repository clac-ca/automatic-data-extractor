# 🔄 Next Task — Reuse FastAPI's cookie dependency for session validation

## Context
`/auth/session` still reads the session cookie directly from `request.cookies` and raises HTTP errors manually. The auth service already wraps FastAPI's `APIKeyCookie` helper inside `_session_cookie_value`, but that dependency is private and optional. Promoting a shared dependency for required session cookies keeps auth routes consistent, trims duplicate error handling, and leans on FastAPI's built-in security tooling.

## Goals
1. Expose a public dependency in `backend/app/services/auth.py` that uses `APIKeyCookie` to retrieve the configured session cookie and raise `401` when it is missing.
2. Update `/auth/session` (and any other routes that need the raw cookie) to consume the new dependency instead of accessing `request.cookies` directly.
3. Ensure the behaviour and responses remain unchanged by relying on existing helpers for audit logging and cookie refreshes.

## Definition of done
- Auth routes no longer call `request.cookies.get(settings.session_cookie_name)` directly; they use the shared dependency instead.
- Authentication tests continue to pass without behavioural regressions.
