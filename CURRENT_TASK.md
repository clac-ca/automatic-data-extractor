# Current Task — Backend foundation slice

## Outcome
Stand up a minimal FastAPI service backed by SQLite. The service should expose a health endpoint, prove that persistence works, and establish the directory layout other teams will build on.

## Why this comes first
- Every future component (UI, processor, automation) depends on a shared API surface and data model.
- SQLite keeps operations simple: copy the database file and the documents folder to back up ADE.
- A clean FastAPI project structure sets expectations for routes, services, and tests.

## Architectural choices locked in
- **Runtime** – Python 3.11 with FastAPI and Pydantic v2.
- **Persistence** – SQLAlchemy ORM pointed at SQLite. Use `metadata.create_all()` during startup; migrations can wait.
- **Configuration** – Pydantic settings module with sensible defaults (`var/ade.sqlite`, `var/documents/`) and environment overrides.
- **Dependency wiring** – Session-per-request dependency using the yield pattern to keep tests deterministic.
- **Layout** – `backend/app/` for HTTP concerns, `backend/processor/` reserved for future pure logic helpers.

## Work sequence
1. **Project scaffold**
   - Add `pyproject.toml` with FastAPI, SQLAlchemy, Pydantic, and Uvicorn.
   - Create the `backend/app/` and `backend/processor/` packages (just `__init__.py` for the processor).
   - Extend `.gitignore` to exclude `var/` and Python build artefacts.
2. **Settings & paths**
   - Implement `backend/app/config.py` with a `Settings` class and `get_settings()` helper.
   - Ensure startup creates `var/` and `var/documents/` if they are missing.
3. **Database plumbing**
   - Build `backend/app/db.py` with an engine factory, `SessionLocal`, and a session dependency (`get_db`).
   - Call `Base.metadata.create_all()` during startup to guarantee tables exist.
4. **Data models**
   - Define SQLAlchemy models for: `User`, `ApiKey`, `DocumentType`, `Snapshot`, `LiveRegistry`, `Upload`, `Run`, and `Manifest`.
   - Match field names to `ADE_GLOSSARY.md` and keep timestamps as ISO strings for now.
5. **Schemas**
   - Add `backend/app/schemas.py` containing `HealthResponse` plus minimal DTOs for document types and snapshots (id + name/title only).
6. **Application entrypoint**
   - Implement `backend/app/main.py` to instantiate FastAPI, register dependencies, include routers, and run startup hooks.
   - During startup: create directories, initialise settings, prime the database connection, and run `create_all()`.
7. **Routes**
   - Create `backend/app/routes/` with `__init__.py` and `health.py`.
   - Implement `GET /health` returning status + database check (e.g., `SELECT 1`). Leave TODO stubs for future routers.
8. **Tests**
   - Add `backend/tests/test_health.py` covering the health endpoint and asserting the DB file is created.

## Definition of done
- `uvicorn backend.app.main:app --reload` starts without errors and creates `var/ade.sqlite` if it is missing.
- `GET /health` returns `{ "status": "ok" }` (or similar) and verifies a real database connection.
- Tests introduced in this task pass locally.
- Repository structure matches the layout described above.

## Deferred for later tasks
- Authentication flows, password hashing, or user management screens.
- Real extraction logic, file uploads, or background processing.
- Frontend scaffolding, Docker packaging, and CI configuration.
- Snapshot diffing or advanced querying optimisations.
