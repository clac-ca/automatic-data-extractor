# Current Task — Bootstrap the backend foundation

## Objective
Stand up the first slice of the backend so we can store data, serve routes, and keep the processing engine separate from web concerns. This task should leave us with a runnable FastAPI app backed by SQLite and ready for future features.

## Why this is first
- Every other component (UI, processing, automation) depends on a predictable API surface and persistence layer.
- SQLite plus SQLAlchemy lets us start quickly while keeping the option to grow later if required.
- A health-checked FastAPI app with clear directory structure anchors how we organise future services and modules.

## Deliverables
1. **Python project scaffolding** – Add `pyproject.toml`, `backend/` package initialisers, and a `README` snippet describing how to run the app.
2. **Configuration module** – `backend/app/config.py` using `pydantic-settings` (or `BaseSettings`) to load the SQLite path (`var/ade.sqlite`) and other core options.
3. **Database module** – `backend/app/db.py` that builds a SQLAlchemy engine/session factory pointed at the configured SQLite file and initialises metadata.
4. **ORM models** – `backend/app/models.py` with SQLAlchemy models for users, API keys, document types, snapshots, live registry, runs/manifests, and uploaded documents. Keep fields aligned with `ADE_GLOSSARY.md`.
5. **Pydantic schemas** – `backend/app/schemas.py` containing basic response/request models for health, document types, snapshots, and runs.
6. **FastAPI entrypoint** – `backend/app/main.py` creating the application, wiring dependency overrides for DB sessions, registering a health endpoint, and mounting a router module placeholder.
7. **Router scaffold** – `backend/app/routes/__init__.py` plus modules for `health` and stubs for future domains (e.g., `document_types`, `snapshots`). Health route should read from the DB session to confirm connectivity.
8. **Initial tests** – `backend/tests/test_health.py` verifying the health endpoint returns success and touches the database.
9. **Tooling hooks** – Update `.gitignore` for `var/`, add `requirements.txt` or rely on `pyproject` extras as needed, and document the `uvicorn` command in the main README if not already clear.

## Implementation notes
- Use SQLAlchemy 2.x declarative models with `Annotated` typing for clarity; avoid Alembic for now and rely on `metadata.create_all()` during startup.
- Keep database access synchronous inside FastAPI dependencies so we can introduce background workers later without refactoring.
- Place processing code under `backend/processor/` but leave it empty except for an `__init__.py` placeholder in this task.
- Prefer dependency-injected sessions (yield pattern) to keep tests deterministic.
- Store timestamps as UTC ISO 8601 strings for now; we can switch to integers later if needed.

## Out of scope (future tasks)
- Actual extraction logic, background job orchestration, and document storage handlers.
- Authentication flows, password hashing utilities, or admin UI routes.
- Frontend scaffolding, Docker configuration, and CI/CD automation.
- Snapshot comparison or run management endpoints beyond placeholders.

## Open questions to revisit soon
- Do we want Alembic migrations once schemas settle, or stick with `create_all` and manual SQL for now?
- Should manifests and snapshots stay as JSON blobs only, or do we extract partial columns for faster querying?
- What queue (if any) will we use when runs need to be asynchronous?

## Definition of done
- Running `uvicorn backend.app.main:app --reload` starts without errors and creates the SQLite file under `var/` if it does not already exist.
- Hitting `GET /health` returns status `ok` and indicates database connectivity.
- Automated test suite (currently just the health test) passes locally.
