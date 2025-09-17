# Current Task — Backend foundation

## Goal
Stand up the first runnable FastAPI service backed by SQLite. This slice establishes the shared patterns for configuration,
persistence, and routing so future features can plug into the same backbone.

## Architectural guardrails
- Python 3.11 + FastAPI + Pydantic v2 for the HTTP layer.
- SQLAlchemy ORM pointed at `var/ade.sqlite`; use SQLite defaults unless we hit scale limits.
- Deterministic processing helpers under `backend/processor/` stay pure (no I/O or randomness).
- On startup the app ensures `var/` and `var/documents/` exist.
- Domain models start with `Snapshot` only. Additional tables come later.

## Deliverables
1. **Repository scaffold** – Add `pyproject.toml`, create `backend/app/`, `backend/processor/`, and `backend/tests/` packages, and
   extend `.gitignore` to exclude `var/` plus standard Python artefacts.
2. **Configuration** – Implement `backend/app/config.py` with a `Settings` class (`BaseSettings`) and a `get_settings()` helper.
   Defaults should point at `var/ade.sqlite` and `var/documents/`, with environment overrides.
3. **Database plumbing** – Implement `backend/app/db.py` with an engine factory, `SessionLocal`, and a `get_db()` dependency that
   yields a session per request. Call `Base.metadata.create_all()` on startup.
4. **Domain model** – Define a SQLAlchemy `Snapshot` model with ULID primary key, document type, title, status flag, payload JSON,
   and created/updated timestamps (store timestamps as ISO strings for now).
5. **API skeleton** – Add `backend/app/routes/health.py` exposing `GET /health`. The handler should return `{ "status": "ok" }`
   and exercise the database (e.g., `SELECT 1`). Create `backend/app/schemas.py` for the response model and wire routers in
   `backend/app/main.py`.
6. **Application entrypoint & tests** – Implement `backend/app/main.py` to instantiate FastAPI, register routes, and run startup
   hooks (create directories + `create_all()`). Add `backend/tests/test_health.py` covering the health endpoint and asserting the
   SQLite file exists after startup.

## Definition of done
- `uvicorn backend.app.main:app --reload` starts without errors and creates `var/ade.sqlite` if it is missing.
- `GET /health` returns `{ "status": "ok" }` and proves a real database connection.
- Tests introduced in this slice pass locally.
- Repository layout matches the scaffold above; no extra systems are introduced.

## Out of scope
- Authentication, password hashing, or user management flows.
- Document uploads, processor logic, or background job orchestration.
- Frontend scaffolding, Docker packaging, and CI pipelines.
- Additional database models beyond the snapshot table.
