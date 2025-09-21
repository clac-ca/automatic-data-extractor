# 🔄 Next Task — Streamline HTTP Basic login with a reusable dependency

## Context
The `/auth/login/basic` route currently performs credential parsing, validation, and event logging inline. Moving that logic
into a dedicated dependency built on FastAPI's `HTTPBasic` helper will shrink the route handler and make the authentication
workflow easier to reuse elsewhere.

## Goals
1. Introduce a dependency in `backend.app.services.auth` that validates HTTP Basic credentials, records the existing
   success/failure events, and returns an active `User`.
2. Update the `/auth/login/basic` route to consume the new dependency so the handler only needs to call
   `auth_service.complete_login(...)` and set the cookie.
3. Extend or adjust tests in `backend/tests/test_auth.py` to cover both successful and failure paths via the new dependency.
4. Ensure no behavioural regressions for CLI-driven user management or API key authentication.

## Definition of done
- The new dependency encapsulates HTTP Basic verification and event logging, and the route uses it instead of inline logic.
- Login success and failure responses (status codes, error messages, audit events) match the current behaviour.
- `pytest backend/tests/test_auth.py` passes.
