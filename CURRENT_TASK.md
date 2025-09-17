# Current Task — Backend bootstrap

## Goal
Stand up the first runnable FastAPI service with SQLite so every future team can plug into the same API surface and persistence layer.

## Why start here
- All UI, processor, and automation work will call the backend; we need a working skeleton before building features.
- SQLite keeps operations simple—copy the database file plus `var/documents/` and the deployment is backed up.
- Establishing the directory layout and config patterns now prevents churn when the codebase grows.

## Architectural decisions locked for this slice
- **Runtime** – Python 3.11 with FastAPI and Pydantic v2.
- **Persistence** – SQLAlchemy ORM pointed at SQLite in `var/ade.sqlite`. Tables are created with `metadata.create_all()` on startup; migrations can wait.
- **Configuration** – Pydantic `BaseSettings` with defaults pointing to `var/ade.sqlite` and `var/documents/`, overridable via environment variables.
- **Dependency wiring** – Session-per-request dependency using the `yield` pattern to keep tests deterministic.
- **Layout** – `backend/app/` for HTTP concerns, `backend/processor/` reserved for future pure logic helpers.

## Ordered work plan
1. **Repository scaffold**
   - Add `pyproject.toml` with FastAPI, SQLAlchemy, Pydantic, and Uvicorn.
   - Create `backend/app/`, `backend/processor/`, and `backend/tests/` packages (`__init__.py` as needed).
   - Extend `.gitignore` to exclude `var/` and standard Python build artefacts.
2. **Settings & filesystem prep**
   - Implement `backend/app/config.py` with a `Settings` class and `get_settings()` helper.
   - Ensure startup creates `var/` and `var/documents/` when missing.
3. **Database plumbing**
   - Add `backend/app/db.py` with an engine factory, `SessionLocal`, and a `get_db()` dependency.
   - Call `Base.metadata.create_all()` during startup to guarantee tables exist.
4. **Minimal models**
   - Define SQLAlchemy models for `DocumentType` and `Snapshot` with the fields required by `ADE_GLOSSARY.md` (ids, names/titles, status, payload JSON placeholder).
   - Keep timestamps as ISO strings for now to avoid premature utilities.
5. **Schemas & routing**
   - Add `backend/app/schemas.py` with a `HealthResponse` model and lightweight DTOs for document types or snapshots (id + label only).
   - Create `backend/app/routes/health.py` implementing `GET /health` that checks the database connection (e.g., `SELECT 1`).
   - Wire routers in `backend/app/main.py`, leaving TODO comments for future endpoints.
6. **Application entrypoint**
   - Implement `backend/app/main.py` to instantiate FastAPI, register dependencies, run startup hooks (directory creation, `create_all()`), and expose the app instance.
7. **Tests**
   - Add `backend/tests/test_health.py` covering the health endpoint and asserting the SQLite file is created after startup.

## Definition of done
- `uvicorn backend.app.main:app --reload` starts without errors and creates `var/ade.sqlite` when missing.
- `GET /health` returns a JSON payload such as `{ "status": "ok" }` and confirms a real database connection.
- Tests introduced in this slice pass locally.
- Repository layout matches the scaffold above; no extra systems are introduced.

## Deferred
- Authentication, password hashing, or user management flows.
- Real extraction logic, file uploads, or background processing.
- Frontend scaffolding, Docker packaging, and CI pipelines.
- Additional database models beyond the two defined here.
