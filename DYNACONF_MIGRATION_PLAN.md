# Dynaconf Migration Plan

## Background
- Current configuration lives in `backend/app/core/settings.py` (Pydantic `AppSettings`, custom TOML/env loaders, FastAPI DI).
- This approach leaks a massive settings schema into OpenAPI, duplicates Behaviour already provided by mature configuration tooling, and complicates renaming or extending configuration keys.
- The application has no external consumers yet, so we can replace the configuration stack wholesale without maintaining backwards compatibility.

## Target Architecture Snapshot
```
backend/
├── app/
│   ├── api/
│   ├── cli/
│   ├── config.py            # NEW: Dynaconf singleton + typed façade/helpers
│   ├── core/
│   ├── db/
│   ├── extensions/
│   ├── migrations/
│   ├── models/
│   ├── modules/
│   │   ├── auth/
│   │   ├── configurations/
│   │   ├── documents/
│   │   ├── events/
│   │   ├── health/
│   │   ├── jobs/
│   │   ├── results/
│   │   ├── service_accounts/
│   │   ├── users/
│   │   └── workspaces/
│   ├── schemas/
│   ├── services/
│   └── main.py
├── config/
│   ├── settings.toml        # multi-environment defaults
│   ├── secrets.toml         # optional secrets source (gitignored)
│   ├── .env.example         # sample environment overrides
│   └── README.md            # configuration reference
├── processor/
├── tests/
├── pyproject.toml
└── alembic.ini
```
Key changes:
- Central configuration entry point in `backend/app/config.py` exporting `settings` (Dynaconf) and typed helpers.
- Configuration artefacts collected under `config/` for clarity and documentation.
- Runtime consumers read from the Dynaconf singleton (or typed façade); FastAPI dependency injection is no longer used for settings.

## Goals / Scope
- Adopt Dynaconf as the authoritative configuration system, with a simplified directory layout and modernised settings names.
- Remove the Pydantic `AppSettings` model and all helper utilities (`get_settings`, `_resolve_files`, `reset_settings_cache`, etc.).
- Update every backend consumer (FastAPI app, services, DB layer, logging, CLI, processor, Alembic) to import from the new `app.config` module.
- Introduce a thin typed façade (Protocol/dataclass/functions) so IDEs and type-checkers continue to help developers.
- Normalise configuration key names, defaults, and documentation—rename or remove legacy options freely.
- Provide clear developer documentation for configuration sources, environment switching, secrets handling, local overrides, and disabling docs outside dev.

## Non-Goals
- Preserving compatibility with existing environment variable names or the `AppSettings` API.
- Retaining Swagger parity with the old docs; we can reorganise anything impacted by the new configuration flow.

## Code Touchpoints & Expected Changes
- `backend/app/main.py`: instantiate the Dynaconf singleton, populate `app.state.settings`, remove `AppSettings` typings, adjust dependency injection.
- `backend/app/core/service.py`: replace `Depends(get_settings)` with direct access to `request.app.state.settings`/Dynaconf.
- `backend/app/core/logging.py`: consume new typed façade for log level, etc.
- `backend/app/db/engine.py` & `backend/app/db/session.py`: rework cache keys and constructors to read from Dynaconf (string primitives) and drop `AppSettings` parameters.
- `backend/app/migrations/env.py`: load configuration via the new module to keep Alembic CLI functional.
- `backend/app/cli/*` and `processor/*`: audit for `get_settings` imports and switch them to the new API.
- `backend/tests/**`: rewrite fixtures/tests that manipulate settings; introduce Dynaconf-aware helpers for overrides.
- Project root documentation (`README.md`, `DOCUMENTATION.md`), new `config/README.md`, and sample files.
- Remove `backend/app/core/settings.py`, `backend/tests/core/test_settings.py`, and any other dead references.

## Implementation Strategy
1. **Dependencies & Layout**
   - Create the `config/` directory with template files (`settings.toml`, `secrets.toml`, `.env.example`, README).
2. **Configuration Module**
   - Implement `backend/app/config.py` with `settings = Dynaconf(...)` pointing to the new file locations and env prefixes.
   - Provide optional typed façade (Protocol or dataclass) exposing structured accessors; include helpers for common path resolution and test overrides.
3. **Backend Refactor**
   - Replace all imports of `AppSettings`/`get_settings` with the new interface.
   - Update service context creation, middleware, logging, and any other component referencing `AppSettings` attributes.
   - Ensure `create_app` writes the Dynaconf instance to `app.state.settings` and exposes overrides for tests/CLI if desired.
4. **Supporting Tools & Processor**
   - Update CLI utilities and `processor` entry points to depend on `app.config.settings`.
   - Verify job queues or asynchronous workers initialise the configuration correctly.
5. **Testing & Fixtures**
   - Introduce fixtures/helpers to temporarily override Dynaconf settings (e.g., context manager using `settings.setenv`).
   - Rewrite or delete unit tests tied to `AppSettings` and add coverage for new configuration behaviours.
6. **Cleanup & Documentation**
   - Remove obsolete modules (`core/settings.py`, `reset_settings_cache`, etc.) and update imports.
   - Archive or delete `backend.backup/` (document decision).
   - Refresh docs to cover the new configuration workflow and mention Swagger docs no longer expose the settings schema.

## Validation Plan
- Run `pytest backend/tests` (full suite) and any CLI/processor tests.
- Run static analysis (ruff, mypy) to ensure typed façade integration passes checks.
- Manual smoke test: start FastAPI, confirm `/docs` omits settings block, exercise key endpoints.
- Execute `alembic upgrade head` and other CLI commands to ensure they load settings correctly.
- Verify new sample configuration files produce sensible defaults (e.g., data directories resolved, logging works).

## Risks & Considerations
- **Rename fallout:** Updated key names/defaults must be reflected in deployment manifests and documentation; add a migration checklist.
- **Type coverage:** Without care, Dynaconf usage becomes dynamic; mitigate with the typed façade and strict lint settings.
- **Hidden consumers:** Scripts/tests outside the backend might still import `get_settings`; audit thoroughly.
- **Secrets hygiene:** Ensure `config/secrets.toml` remains gitignored and guide teams on secure secret loading.

## Follow-ups / Decisions
- Finalise the new prefix/naming convention for environment variables.

## Next Steps
1. Get buy-in on this migration blueprint.
2. Land the dependency/layout scaffolding PR (Dynaconf + new config directory).
3. Execute the backend refactor and cleanup.