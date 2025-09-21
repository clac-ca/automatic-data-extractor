# ✅ Completed Task — Streamline HTTP Basic login with a reusable dependency

## Context
Inline credential parsing inside `/auth/login/basic` made the handler noisy and hard to reuse. Moving the logic into a FastAPI dependency keeps authentication behaviour consistent wherever HTTP Basic is supported.

## Outcome
- Added `auth.require_basic_auth_user`, a dependency that uses FastAPI's `HTTPBasic` helper to look up users, enforce active status, and record the existing failure events before returning an authenticated user.
- Simplified `/auth/login/basic` so it just consumes the dependency, issues the session via `auth_service.complete_login`, and sets the cookie.
- Expanded the authentication test suite to cover successful and failing dependency paths, verifying that audit events and responses stay consistent.
