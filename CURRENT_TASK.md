# Current Task — Bootstrap the backend foundation

## Goal
Establish a minimal FastAPI + SQLite backend skeleton that the frontend and processor can depend on. The outcome is a runnable service with a clear directory layout, database session plumbing, and a health check that proves persistence works.

## Why this is first
- All future work (UI, processor, automation) depends on an API boundary and shared data model.
- SQLite keeps operations simple: a single file under `var/ade.sqlite` covers persistence for early iterations.
- A clean FastAPI project structure sets the tone for how we organise services, schemas, and tests.

## Architectural decisions locked in this task
- **Language & framework** – Python 3.11 with FastAPI and Pydantic v2.
- **Persistence** – SQLAlchemy ORM targeting SQLite; rely on `metadata.create_all()` at startup instead of migrations for now.
- **Configuration** – Pydantic settings module that defaults to `var/ade.sqlite` and allows overrides via environment variables.
- **Dependency wiring** – Session-per-request dependency with the yield pattern to keep tests deterministic.
- **Project layout** – Processing helpers live under `backend/processor/` (empty placeholder for now) to keep business logic away from HTTP concerns.

## Work plan
1. **Scaffold the Python project**
   - Add `pyproject.toml` with FastAPI, SQLAlchemy, Pydantic, and Uvicorn dependencies.
   - Create the `backend/` package with `app/` and `processor/` subpackages plus `__init__.py` files.
   - Extend `.gitignore` for `var/` and Python artifacts.
2. **Configuration module**
   - Implement `backend/app/config.py` using `BaseSettings` to load the SQLite path and debug toggle.
   - Provide a singleton accessor (`get_settings()`) to avoid repeated parsing.
3. **Database module**
   - Build `backend/app/db.py` with a SQLAlchemy engine factory, session generator, and `create_all()` call for metadata.
4. **ORM models**
   - Define SQLAlchemy models for users, API keys, document types, snapshots, live registry, runs/manifests, and uploaded documents.
   - Align field names and types with `ADE_GLOSSARY.md` (timestamps as ISO strings for now).
5. **Pydantic schemas**
   - Create `backend/app/schemas.py` with baseline schemas for health, document types, snapshots, and runs.
   - Keep them minimal—just enough to return healthy responses.
6. **FastAPI entrypoint**
   - Implement `backend/app/main.py` to create the application, register dependencies, and include routers.
   - Add startup logic that ensures tables exist and directories under `var/` are created.
7. **Router scaffold**
   - Add `backend/app/routes/` with `__init__.py`, `health.py`, and placeholders for `document_types` and `snapshots`.
   - Implement `GET /health` that checks database connectivity by executing a simple query.
8. **Tests**
   - Add `backend/tests/test_health.py` covering the health endpoint and verifying it touches the database.
9. **Developer notes**
   - Update `README.md` (already done in this iteration) with the `uvicorn` command if needed and add a backend setup snippet if the structure changes.

## Definition of done
- `uvicorn backend.app.main:app --reload` starts without errors and creates `var/ade.sqlite` if it is missing.
- `GET /health` returns `{ "status": "ok" }` (or similar) and confirms the database is reachable.
- Tests introduced in this task pass locally.
- Repository tree contains the backend scaffold described above with no stray files.

## Out of scope (future tasks)
- Authentication flows, password hashing, or admin UI screens.
- Real extraction logic, background processing, or file upload handlers.
- Frontend scaffolding, Docker packaging, and CI configuration.
- Snapshot diffing or run comparison features beyond placeholders.

## Follow-ups to consider soon
- Introduce Alembic migrations once schemas stabilise.
- Decide whether manifests and snapshots need derived tables for faster querying.
- Explore background job infrastructure if run durations become significant.
