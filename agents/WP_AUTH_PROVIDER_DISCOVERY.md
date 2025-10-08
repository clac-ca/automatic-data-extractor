# Work Package: Auth Provider Discovery API

## Status
- **Owner:** Platform Squad
- **Last Reviewed:** 2024-03-21
- **State:** _Pending build_

Provider discovery is still missing. The rebuilt login and setup flows depend on
a stable `/auth/providers` contract before we can ship the new SPA.

## Objective
Expose `/auth/providers` so the frontend knows which SSO options to show and
whether credentials should be hidden.

## Current State Findings
- The legacy SPA bundles provider discovery with setup and session bootstrap.
  The rebuild will replace that context with TanStack Query hooks, so discovery
  must stand alone.
- Backend auth services still host the initial-setup workflow. Discovery should
  remain decoupled so the new `/setup` wizard can reference it without inheriting
  legacy glue.
- Auth endpoints are moving to the standard session resource
  (`GET/POST/DELETE /auth/session`, `POST /auth/session/refresh`). Discovery must
  align with that naming and avoid the legacy `/auth/me` flow.

## Deliverables
- Auth settings that validate provider definitions (`id`, `label`, optional
  `icon_url`, `start_url`) plus a `force_sso` flag.
- Pure helper in `app/features/auth/service.py` that returns provider metadata
  and the `force_sso` decision.
- Public FastAPI route `/auth/providers` returning `{ providers, force_sso }`.
- Unit tests covering empty, populated, and force-only configurations.
- Documentation update describing configuration and `force_sso` behaviour during
  setup and login.

## Tasks
1. Extend `app/core/config.py` with Pydantic models for provider definitions and
   the `force_sso` flag; prune unused auth settings.
2. Implement the provider helper in `app/features/auth/service.py` and reuse it
   anywhere discovery is needed.
3. Add response schemas to `app/features/auth/schemas.py` and expose the
   unauthenticated `/auth/providers` route in `app/features/auth/router.py`.
4. Cover helper and route with unit tests.
5. Update docs (`agents/FRONTEND_DESIGN.md`, auth runbook) to reflect the
   contract.

## Testing
- `pytest` for new auth helper and router tests.
- `mypy` for updated settings and schemas.

## Out of Scope
- Admin UI for managing providers.
- Frontend implementation work.
- Telemetry beyond standard request logging.

## Dependencies
- Existing OIDC configuration support; no new external libraries required.

## Frontend Impact
- `/auth/providers` blocks login and setup decisions. Until it exists the SPA
  cannot decide whether to hide credentials, render SSO tiles, or explain the
  break-glass administrator flow during setup.
