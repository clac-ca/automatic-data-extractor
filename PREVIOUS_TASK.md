# 🔄 Next Task — Consolidate Authentication Service Layer

## Context
The `backend/app/auth` package has grown into several small modules (`api_keys.py`, `sessions.py`, `events.py`, `passwords.py`,
and a CLI helper) that all wrap the same database tables. This fragmentation makes it difficult to see the full login story and
prevents us from leaning on FastAPI's built-in security helpers without a maze of cross-imports. By collapsing the hot-path
logic (session issuance/refresh, API key lookups, login event recording) into a single service module we can keep the auth
routes and dependencies short, auditable, and aligned with FastAPI conventions.

## Goals
1. Introduce a focused `auth/service.py` (or equivalent) that provides the minimal primitives the routes need: issue/refresh
   sessions, revoke sessions, resolve API keys, and record login/logout events.
2. Update `dependencies.py` and the auth routes to call this consolidated service while relying on FastAPI's `HTTPBasic`,
   `HTTPBearer`, and `APIKeyHeader` dependencies for credential parsing instead of bespoke wrappers.
3. Delete or inline the now-redundant modules (`api_keys.py`, `sessions.py`, `events.py`) once their functionality is
   transplanted, keeping the CLI manageable with the new service.
4. Ensure the simplified layout keeps existing authentication behaviours identical and the regression suite stays green.

## Implementation notes
- Map each helper function to its call sites before moving it so we do not accidentally drop required logic.
- Keep the new service functions straightforward—no generic abstractions or class hierarchies.
- Preserve the deterministic hashing helpers used in tests (e.g. session token hashing) by re-exposing them from the new
  module.

## Definition of done
- `backend/app/auth` exposes a single service module plus `dependencies.py`/`passwords.py`; the legacy helper modules are
  removed.
- Authentication (basic login, session refresh, API key access, SSO) continues to pass the current test suite.
- No new dependencies are added.
