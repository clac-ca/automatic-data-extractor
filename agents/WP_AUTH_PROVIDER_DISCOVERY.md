# Work Package: Auth Provider Discovery API

## Objective
Expose an `/auth/providers` endpoint that returns configured SSO providers plus a `force_sso` flag so the login screen can decide which flows to render.

## Deliverables
- Settings extensions to describe available providers (name, optional icon URL, start URL or symbolic key).
- Auth service helper that inspects settings and determines whether credentials should be hidden.
- New FastAPI route `/auth/providers` returning provider metadata and `force_sso` boolean; unauthenticated and cacheable.
- Tests covering scenarios: no providers, providers configured, force-only deployments, and validation of required settings.

## Key Decisions
- Use static configuration (environment or settings table) for provider definitions; defer dynamic admin UI.
- Keep the response schema minimal: `providers` array with `id`, `label`, `icon_url`, `start_url`; `force_sso` boolean.
- Reuse existing `/auth/sso/login` start flow when providers reference ADE-hosted redirect endpoints.

## Tasks
1. Extend `app/core/config.py` to surface provider definitions and a `force_sso` flag.
2. Add serialization schemas for provider responses under `app/auth/schemas.py`.
3. Implement service method that assembles provider metadata and the flag, validating configuration.
4. Register `/auth/providers` route in `app/auth/router.py`, mark it public (`security: []`).
5. Document behaviour in `agents/FRONTEND_DESIGN.md` if needed and add unit tests (service + router).

## Testing
- pytest focusing on new auth tests (service + router).
- mypy for schema/setting additions.

## Out of Scope
- Admin UI for managing providers.
- Frontend changes.
- Telemetry wiring beyond simple request logging.

## Dependencies
- Requires existing OIDC configuration support but no new external libraries.

## Frontend impact
- `/api/auth/providers` is blocking the login spec in `agents/FRONTEND_DESIGN.md` (provider tiles + `force_sso` toggle). Until this endpoint exists, the SPA cannot decide whether to suppress credentials or render SSO options.
