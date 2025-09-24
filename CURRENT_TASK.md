# ADE Backend Rewrite - Next Focus

## Goal for This Iteration
Execute the Dynaconf migration described in `DYNACONF_MIGRATION_PLAN.md`, replacing the Pydantic-based settings system with the new central configuration module and directory layout.

No migrations are needed as no users are using the app yet.

## Scope
1. **Bootstrap Dynaconf**
   - Add the `config/` directory with committed templates (`settings.toml`, `.env.example`, README) and wire Dynaconf as a dependency.
2. **Implement `backend/api/config.py`**
   - Instantiate the Dynaconf singleton, expose typed helpers, and ensure FastAPI initialisation stores the settings on `app.state`.
3. **Rewire backend consumers**
   - Update modules that previously imported `AppSettings` or `get_settings` (logging, DB session/engine, service context, middleware, job queue, CLI/processor entry points) to pull from the new configuration interface.
4. **Tests and documentation**
   - Refresh fixtures to support temporary Dynaconf overrides, remove obsolete tests, and document the new workflow in `config/README.md` plus relevant project docs.

## Definition of Done
- Dynaconf-backed `backend/api/config.py` replaces `core/settings.py`, and all runtime consumers read from it.
- New configuration artefacts live under `config/` with example/default files committed and secrets/gitignore rules in place.
- Test suite, Ruff, and MyPy succeed with the new configuration stack; CLI/Alembic/processor entry points load settings correctly.
- Documentation reflects the migration, including developer guidance for overrides and environment management.
