# ADE Backend Rewrite - Next Focus

## Status Snapshot
- `backend/app` successfully renamed to `backend/api`; imports, tooling, and docs now reference the clarified package.
- FastAPI server starts via `uvicorn backend.api.main:app`; linting and tests pass against the new layout.
- Plans and docs updated to point at `backend/api`, paving the way for operational tooling work.

## Goal for This Iteration
Stand up the first-party CLI following `CLI_IMPLEMENTATION_PLAN.md`, providing an `ade` entry point that reuses backend services for core operational tasks.

## Scope
1. **Scaffold & wiring**
   - Create the `backend/cli` package skeleton (app, runner, context, io, commands) and register the `ade` console script.
   - Ensure CLI modules import shared settings/services from `backend/api` without duplicating logic.
2. **Command implementation**
   - Implement the v1 command groups (database migrations, user management, API keys, service accounts, config inspection) as async handlers per the plan.
   - Provide safe output formatting (table/JSON) with redaction for secrets.
3. **Tests & documentation**
   - Add unit/integration tests covering command parsing and happy/error paths.
   - Document usage in `docs/admin-guide/operations.md` and surface the CLI in README/onboarding notes.

## Definition of Done
- `backend/cli` package exists with runnable `ade` console script (`python -m backend.cli` and installed entry point) covering scoped commands.
- Automated tests validate command behaviour; linting/type checks pass with the new package.
- Documentation updated to describe CLI usage, and follow-up items (deferred commands, future enhancements) recorded.
