# 🔄 Next Task — Centralize Login Session Issuance

## Context
With credential resolution handled by `auth/service.resolve_credentials`, the Basic and SSO login endpoints still duplicate the
sequence of issuing a session, recording the login success event, committing the transaction, refreshing ORM models, and updating
FastAPI request state. This duplication makes future auth modes harder to add and risks behavioural drift if one path forgets to
update telemetry or metadata. Consolidating the shared work into a focused helper keeps each route small and ensures the login
pipeline stays consistent.

## Goals
1. Add a helper to `auth/service.py` (or a narrow companion module) that accepts the database session, settings, target user,
   login mode, and request metadata (IP address, user agent, optional subject) and returns the persisted session plus the raw
   session token.
2. Replace the duplicated logic in `/auth/login/basic` and `/auth/sso/callback` with calls to this helper so the routes only need
   to manage FastAPI surfaces like cookie handling and response serialization.
3. Preserve existing login success telemetry — payload fields such as IP, user agent, and subject (for SSO) must remain
   unchanged.

## Implementation notes
- Reuse `service.issue_session` and `service.login_success` inside the helper rather than reimplementing token handling.
- Keep the helper synchronous and side-effect free beyond database writes; it should not touch FastAPI `Request` or `Response`
  objects.
- Extend the authentication tests to cover the new helper directly and prove both login endpoints still behave the same.
- Confirm cookie attributes and request context updates inside the routes remain identical to today's behaviour.

## Definition of done
- Both Basic and SSO login routes delegate session issuance and event recording to the new helper.
- Login success events still emit the same payload structure and values as before the refactor.
- `pytest backend/tests/test_auth.py` continues to pass without regressions.
