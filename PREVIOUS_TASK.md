# Task: Redesign persistent storage layout and adopt database migrations

## Context
- All persisted state currently lives under `var/` (e.g. `var/ade.sqlite`, `var/documents/`). The directory name feels opaque and
  the backend assumes those defaults in code, docs, and diagrams.
- The application bootstraps tables with `Base.metadata.create_all(...)` in several places (FastAPI lifespan, CLI entry points,
  tests). There is no migration history, so schema changes require manual coordination and risk destructive rebuilds.
- After evaluating alternative layouts (including `backend/data/`), the cleanest approach keeps runtime artefacts outside the
  importable Python package. A repository-level `data/` root avoids writing into `site-packages` when the backend ships as a
  package, while still keeping all persisted assets together for local development and deployments.

## Goals
1. Introduce an intuitive, central storage root that keeps the SQLite database, uploaded documents, and future generated
   artefacts under a single `data/` namespace (e.g. `data/db/ade.sqlite`, `data/documents/uploads/`, `data/documents/output/`).
2. Replace ad-hoc `create_all` usage with Alembic migrations so schema evolution is versioned and reproducible.
3. Update configuration, startup routines, tests, and documentation to reflect the new storage layout and migration workflow.

## Implementation plan

### 1. Persistent storage layout
- Add a `data/` directory at the repository root (gitignored) that acts as the canonical storage root.
  - Suggested structure:
    ```
    data/
      db/ade.sqlite
      documents/
        uploads/
        output/
      (room for future artefacts such as `exports/` or `cache/`)
    ```
  - Update `.gitignore`, Docker tooling, and any other ignore lists to drop `var/` entries and cover the new `data/` structure.
- Extend `backend/app/config.Settings` with a `data_dir: Path` (env `ADE_DATA_DIR`, default `Path("data")`).
  - When `ADE_DOCUMENTS_DIR` is unset, derive it from `data_dir / "documents"`.
  - When `ADE_DATABASE_URL` is unset **and** the backend is using SQLite, derive the URL from `data_dir / "db" / "ade.sqlite"`.
    Preserve overrides for non-SQLite databases.
  - Ensure `Settings.database_path` still resolves correctly for SQLite URLs pointing into `data_dir`.
- Update startup (`backend/app/main.py` lifespan) to create:
  - `settings.data_dir`
  - `settings.documents_dir` plus the `uploads/` and `output/` children
  - the parent directory for the SQLite database when `database_path` is available.
- Remove hard-coded "var" references from service docstrings (e.g. `backend/app/services/documents.py`) and ensure any
  filesystem helpers (document storage, purge routines) operate relative to `settings.documents_dir`.
- Adjust any code that assumed `documents_dir.parent` was the storage root so it now relies on the new `data_dir` accessor.
- Update fixtures (`backend/tests/conftest.py`) to prefer `ADE_DATA_DIR` when constructing isolated environments; only fall back
  to explicit `ADE_DOCUMENTS_DIR`/`ADE_DATABASE_URL` overrides when tests need bespoke paths.
- Remove any compatibility shims or warnings related to the legacy `var/` layout; the new defaults become authoritative.

### 2. Alembic migrations
- Add Alembic to the project dependencies (`pyproject.toml` runtime deps).
- Create an Alembic configuration (`alembic.ini` at the repo root pointing to `backend/app/migrations`). The env script should:
  - Import `backend.app.models` for metadata.
  - Pull the database URL from `backend.app.config.get_settings()` so CLI usage and the FastAPI app share the same connection
    string.
  - Support both offline (script generation) and online (running against a live connection) modes.
- Generate an initial migration that captures the current schema (configurations, jobs, documents, events, maintenance_status,
  users, user_sessions, api_keys). Verify constraints/indexes match the existing models.
- Provide a lightweight helper (e.g. `backend/app/db_migrations.py` with `apply_migrations()` and `ensure_schema()` functions)
  that calls `alembic.command.upgrade(..., "head")`.
  - When the configured URL points at an in-memory SQLite database, fall back to `Base.metadata.create_all(...)` so unit tests can
    keep using transient databases without extra plumbing.
- Replace all direct `Base.metadata.create_all(...)` calls with the new helper:
  - FastAPI lifespan (`backend/app/main.py`).
  - CLI entry points (`backend/app/auth/manage.py`, `backend/app/maintenance/purge.py`).
  - Tests or utilities that previously relied on `create_all`.
- Ensure the TestClient fixture runs migrations (or the helper) before seeding the default user so test schemas match production
  migrations.
- Document how to run migrations manually (e.g. `alembic upgrade head` or `python -m backend.app.db_migrations upgrade`).

### 3. Documentation and housekeeping
- Update `AGENTS.md` planned layout to show the new `data/` tree instead of `var/`.
- Refresh `README.md`, `ADE_GLOSSARY.md`, and any other docs referencing `var/` (search the repo) to describe:
  - the `data/` storage layout
  - the new `ADE_DATA_DIR` environment variable
  - the migration workflow (initial setup requires running migrations before starting the service).
- Update docstrings/comments mentioning `var/documents` to reflect the new paths.
- Add developer notes (e.g. in `README` or a dedicated doc) describing how to move existing local data when upgrading from earlier
  checkouts (stop the service, move SQLite and documents into `data/`, restart to create subdirectories).
- Ensure `.gitignore` (and any docker-compose / deployment manifests, if present) reference the new `data/` paths.

### 4. Testing & validation updates
- Update existing tests that inspect filesystem locations (e.g. `backend/tests/test_health.py`) to expect the new `data/`
  defaults.
- Add/adjust tests covering:
  - `Settings` deriving defaults from `ADE_DATA_DIR`.
  - Alembic helper running against SQLite file URLs.
  - In-memory SQLite paths still working for tests via the helper fallback.
- Run the full backend test suite after changes (`pytest`). Consider adding a smoke test that runs the migration helper against
  a temporary database to catch misconfigured Alembic env settings.

## Acceptance criteria
- Application defaults store SQLite and documents under `data/` while remaining configurable via environment variables.
- FastAPI startup, CLIs, and tests rely on Alembic migrations (or the explicit in-memory fallback) instead of `create_all`.
- Initial Alembic migration exists and matches the current schema.
- Documentation, diagrams, and glossary entries reference the new storage layout and migration workflow.
- `.gitignore` and any developer guidance keep runtime data out of version control.
- No code paths, docs, or configs rely on `var/` for persisted assets.
- All automated tests pass after the refactor.

## Out of scope / follow-ups
- No changes to the processor or frontend behaviour (only storage + migration infrastructure).
- Do not attempt to automatically relocate existing `var/` data; rely on documentation and operator action.
- Future migrations for schema changes beyond the initial baseline can be planned separately once Alembic is in place.

## Testing
- `pytest`
- If new tooling is introduced (e.g. a wrapper module for migrations), add targeted unit tests.
