# ADE Config Simplicity – Next Task

## Objective
Load application settings once during startup, store them on `app.state`, and read them inside route handlers without exposing config in OpenAPI.

## Why
- Keeps configuration out of endpoint signatures so FastAPI docs stay clean.
- Centralizes settings loading for reuse across API routes, services, and background jobs.
- Simplifies tests by letting them override the loader in one place.

## Scope
1. **Settings Loader**
   - Create `backend/app/config.py` with a `Settings` data model and a memoized `load_settings()` helper that reads environment variables (with `.env` support for local dev).
2. **Startup Wiring**
   - During app startup/lifespan, call `load_settings()` once and stash the result on `app.state.settings`.
3. **Route & Service Access**
   - Update routes, services, and utilities to fetch config via `request.app.state.settings` (or `app.state.settings` outside requests) instead of dependency injection parameters.
4. **Testing & Docs**
   - Provide a test helper to override the settings loader or mutate `app.state.settings` in fixtures.
   - Document the pattern in `README.md` or `AGENTS.md` so future changes follow the same approach.

## Done When
- API routes no longer declare settings dependencies; `/openapi.json` is free of config schema.
- `app.state.settings` is populated during startup and reused everywhere.
- Tests and docs reflect the new access pattern.
