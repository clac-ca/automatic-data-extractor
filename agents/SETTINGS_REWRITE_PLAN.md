# Settings Rewrite Plan

## Overview
We want ADE’s configuration to feel like any modern Python + TypeScript project: every option has a sensible default, overriding it is as easy as setting an environment variable, and there is no hidden behaviour tied to faux “environment” modes. This plan documents the changes needed to get there.

## Guiding Principles
1. **Explicit over implicit** – remove `ADE_ENVIRONMENT` and any behaviour that depends on environment names. If a deployment needs docs or logging enabled, it should set `ADE_API_DOCS_ENABLED=true`, not `ADE_ENVIRONMENT=staging`.
2. **Defaults everywhere** – every setting in code provides a safe default (matching `.env.example`). The app should boot even if `.env` is missing.
3. **Standard Pydantic usage** – rely on typed fields, default values, and validators/descriptions. Avoid custom source hooks or ad hoc computed properties unless they add clear value.
4. **Minimal coupling** – middleware, CLI, tests, and frontend config all read the same variables without extra wrapper functions.

## Current State (observations)
- `backend/api/settings.py`
  - Still declares `environment` and computed helpers (`cors_allow_origins_list`, `docs_urls`, etc.).
  - Parses CORS values from a string manually instead of using a typed list field.
  - Enables docs by default even though `.env.example` ships with `ADE_API_DOCS_ENABLED=false`.
- `backend/api/main.py`
  - Depends on `docs_urls`/`openapi_docs_url` properties instead of using direct `api_docs_enabled` checks.
- `backend/api/extensions/middleware.py`
  - Expects `settings.cors_allow_origins_list` (tight coupling to the helper).
- `cli/commands/start.py`
  - Already accepts `--env KEY=VALUE` and merges overrides for backend/front-end processes.
- `frontend`
  - Reads `VITE_API_BASE_URL`; vitest setup ensures a default when not provided.
- `.env.example`
  - Includes `ADE_ENVIRONMENT` and sets docs disabled; mismatched with code defaults.
- Tests (`backend/tests/core/test_settings.py`)
  - Assert on `environment` and expect special casing of docs behaviour.

## Proposed Changes
### 1. Backend Settings Model
- Remove `environment` and the computed docs helper methods. Replace with simple checks when building the FastAPI app.
- Keep the raw `ADE_CORS_ALLOW_ORIGINS` value as a string field and expose a helper property that normalises comma-separated strings or JSON arrays into a list FastAPI can consume.
- Keep `ADE_API_DOCS_ENABLED` default **False** for secure-by-default posture. Include a descriptive `Field` explaining how to turn docs on.
- Keep `sso_enabled` only if value-added; otherwise, compute in call sites (e.g., `if settings.sso_client_id and ...`).
- Ensure `Settings.model_config` only specifies `env_prefix`/`env_file`; drop unused extras.

### 2. FastAPI App Wiring
- In `backend/api/main.py`, derive docs URLs with simple conditionals:
  ```python
  docs_url = settings.docs_url if settings.api_docs_enabled else None
  openapi_url = settings.openapi_url if settings.api_docs_enabled else None
  ```
- Adjust middleware to consume `settings.cors_allow_origins_list` (the parsed list view).

### 3. Testing Updates
- Rewrite `backend/tests/core/test_settings.py` to:
  - Remove references to `environment`.
  - Assert defaults reflect doc disabled state and empty CORS list.
  - Validate both comma-separated and JSON array inputs for `ADE_CORS_ALLOW_ORIGINS`.
  - Add a test showing `ADE_API_DOCS_ENABLED=true` overrides the default.

### 4. Environment Templates & Documentation
- Update `.env.example` so every value matches code defaults exactly (docs disabled, empty CORS list, etc.).
- Remove `ADE_ENVIRONMENT` from templates and docs; describe the new approach in README/admin guide.
- Provide a small table summarising key env vars, defaults, and when to override them.

### 5. CLI Behaviour
- Confirm existing `--env` flow applies overrides for both processes; add or update tests to show `ade start --env ADE_API_DOCS_ENABLED=true` exposes docs.
- Document the flag in CLI help/docs to encourage explicit overrides.

### 6. Frontend Alignment
- Ensure frontend documentation references the same env vars (primarily `VITE_API_BASE_URL`).
- If the frontend needs additional defaults, document them near backend settings to reduce search time.

## Execution Order
1. Refactor `backend/api/settings.py` and adjust middleware/app entrypoints.
2. Update `.env.example`, README, and other docs.
3. Review & fix tests; add new cases for overrides.
4. Validate `ade start` locally (with and without `--env`).
5. Perform final pass verifying defaults match documentation.

## Risks / Questions
- Do any deployment scripts or environments still rely on `ADE_ENVIRONMENT`? If yes, provide migration guidance.
- Identify sensitive defaults (e.g., `ADE_AUTH_TOKEN_SECRET`) that should be highlighted as production must-overrides.

Tracking the above work sequentially will ensure settings become predictable, explicit, and easy to reason about across the entire ADE stack.
