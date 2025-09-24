# ADE Backend Rewrite - Next Focus

## Status Snapshot
- AppSettings still injects the full configuration schema into OpenAPI, exposing internal knobs in `/openapi.json`.
- FastAPI health is restored after the Response annotation fix, so we can refactor configuration without blocking runtime.
- No external users are live yet, letting us rework configuration loading without migration constraints.

## Goal for This Iteration
Adopt an `.env`-driven configuration loader that keeps settings out of FastAPI/Pydantic schemas and retires the `AppSettings` dependency injection path.

## Scope
1. **Establish `.env` workflow**
   - Add `.env`, `.env.example`, and supporting docs; ensure secrets stay gitignored and tests can seed defaults.
2. **Implement `backend/api/config.py`**
   - Load environment variables (parse `.env` during local development), expose a typed helper, and stash the config on `app.state` during startup.
3. **Remove `AppSettings` usage**
   - Update modules that currently depend on `AppSettings`/`get_settings` (logging, DB factories, service context, middleware, job queue, CLI/processor entrypoints) to use the new config helper.
4. **Validation & docs**
   - Adjust fixtures to override env vars safely, prune obsolete tests, and document the `.env` workflow so `/openapi.json` stays free of configuration entries.

## Definition of Done
- `AppSettings` and related helpers are removed, and runtime components read from the new `.env`-backed config module.
- `.env` artefacts and documentation are in place with secrets excluded from Git history.
- `/openapi.json` no longer exposes configuration fields; FastAPI starts with settings sourced from environment values.
- Test suite, Ruff, and MyPy succeed with the environment-based loader; CLI/Alembic/processor entry points resolve configuration via the new helper.
