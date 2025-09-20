# Current Task — Guardrails for updated authentication modes

## Objective
Add safety nets and observability around the new `ADE_AUTH_MODES` semantics so operators clearly understand when ADE is running in
open-access mode versus enforcing HTTP Basic or SSO.

## Context carried forward
- Sessions are now issued automatically; `auth_mode_sequence` only reports `none`, `basic`, and `sso` in declaration order.
- `ADE_AUTH_MODES=none` returns a synthetic administrator in `get_current_user` and unlocks every route without credentials.
- Docs and high-level tests cover the new mode list, but we lack regression tests for the parser/validator and we do not surface
  runtime warnings when deployments forget to secure ADE.
- CLI flows still allow user provisioning even when auth is disabled, making it easy to miss that open access is active.

## Deliverables
1. **Settings validation coverage**
   - Add focused unit tests for `Settings.auth_mode_sequence` and `auth.validation.validate_settings` covering duplicate entries,
     invalid values, and the guarantee that `none` cannot be combined with other modes.
   - Ensure the tests exercise error messages so operators see actionable failures during startup.
2. **Operational guardrails**
   - Emit a clear startup warning (e.g. via `logging.warning`) when ADE boots with `ADE_AUTH_MODES=none` so container logs highlight
     the risk. Confirm the warning fires once during application startup.
   - Update the CLI (`backend/app/auth/manage.py`) to print a similar warning before executing commands whenever it resolves
     `ADE_AUTH_MODES=none`.
3. **Docs & examples**
   - Extend the authentication documentation (and Quickstart if helpful) with an explicit "development only" callout for open
     access, including guidance on switching back to `basic` or `basic,sso`.
   - Provide a short `.env` example or note that highlights the default (`basic`) and how to opt into SSO alongside it.

## Acceptance criteria
- Pytest includes regression coverage for the new configuration parser/validator behaviour.
- Both the API service and CLI emit a warning when operating without authentication.
- Documentation clearly signals that `ADE_AUTH_MODES=none` is for isolated demos/tests and shows the supported secure
  configurations.
