# Current Task — Backend foundation

## Objective
Deliver the first runnable FastAPI service backed by SQLite. This slice sets the shared patterns for configuration, persistence,
and routing so every later feature plugs into the same backbone.

## Why this comes first
- All UI, processor, and automation work will rely on the backend API; a working skeleton unblocks every team.
- SQLite plus on-disk documents keeps deployment and backups trivial—copy `var/ade.sqlite` and `var/documents/` together.
- Establishing the directory layout and settings early prevents churn when the codebase grows.

## Scope decisions for this slice
- **Runtime** – Python 3.11 with FastAPI and Pydantic v2.
- **Persistence** – SQLAlchemy ORM pointed at SQLite in `var/ade.sqlite`. Use `Base.metadata.create_all()` on startup; migrations
  can wait until tables stabilise.
- **Configuration** – Pydantic `BaseSettings` with defaults aimed at `var/ade.sqlite` and `var/documents/`, overridable via
  environment variables.
- **Dependency wiring** – Session-per-request dependency using the `yield` pattern to keep tests deterministic.
- **Domain footprint** – Start with a single `Snapshot` table (ULID primary key, document type string, title, status flag,
  payload JSON, and created/updated timestamps). Additional tables can follow future slices.
- **Layout** – `backend/app/` for HTTP concerns, `backend/processor/` reserved for future pure logic helpers.

## Ordered work plan
1. **Repository scaffold**
   - Add `pyproject.toml` with FastAPI, SQLAlchemy, Pydantic, and Uvicorn dependencies.
   - Create `backend/app/`, `backend/processor/`, and `backend/tests/` packages (`__init__.py` as needed).
   - Extend `.gitignore` to exclude `var/` and standard Python build artefacts.
2. **Settings & filesystem prep**
   - Implement `backend/app/config.py` with a `Settings` class and `get_settings()` helper.
   - Ensure startup creates `var/` and `var/documents/` when missing.
3. **Database plumbing**
   - Add `backend/app/db.py` with an engine factory, `SessionLocal`, and a `get_db()` dependency.
   - Call `Base.metadata.create_all()` during startup to guarantee tables exist.
4. **Domain model**
   - Define the SQLAlchemy `Snapshot` model with the fields noted above, using SQLite JSON storage for the payload.
   - Keep timestamps as ISO strings for now to avoid premature utilities.
5. **API skeleton**
   - Add `backend/app/schemas.py` with a `HealthResponse` model (status string, optional database check details).
   - Create `backend/app/routes/health.py` implementing `GET /health` that exercises the database connection (e.g., `SELECT 1`).
   - Wire routers in `backend/app/main.py`, leaving TODO comments for future endpoints.
   - Startup hooks should create directories and run `create_all()`.
6. **Application entrypoint & tests**
   - Implement `backend/app/main.py` to instantiate FastAPI and register dependencies and startup tasks.
   - Add `backend/tests/test_health.py` covering the health endpoint and asserting the SQLite file exists after startup.

## Definition of done
- `uvicorn backend.app.main:app --reload` starts without errors and creates `var/ade.sqlite` when missing.
- `GET /health` returns a JSON payload such as `{ "status": "ok" }` and proves a real database connection.
- Tests introduced in this slice pass locally.
- Repository layout matches the scaffold above; no extra systems are introduced.

## Deferred
- Authentication, password hashing, or user management flows.
- Document uploads, processor logic, or background job orchestration.
- Frontend scaffolding, Docker packaging, and CI pipelines.
- Additional database models beyond the snapshot table.
