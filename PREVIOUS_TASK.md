# Current Task — Snapshot CRUD API

## Goal
Expose CRUD operations for the `Snapshot` model so the frontend and CLI tools can create, browse, inspect, update, and delete
snapshot metadata through the FastAPI backend.

## Scope
- Implement database-layer helpers that wrap the existing SQLAlchemy model with deterministic logic (no randomness or
  side-effects besides persistence).
- Build a dedicated router under `backend/app/routes/snapshots.py` that provides:
  - `POST /snapshots` – create a snapshot record.
  - `GET /snapshots` – list snapshots ordered by `created_at` descending.
  - `GET /snapshots/{snapshot_id}` – fetch a single snapshot by ULID.
  - `PATCH /snapshots/{snapshot_id}` – update mutable fields (`title`, `payload`, `is_published`).
  - `DELETE /snapshots/{snapshot_id}` – remove a snapshot.
- Define request/response schemas for the endpoints in `backend/app/schemas.py` (or a dedicated module if needed) ensuring all
  timestamps remain ISO 8601 strings.
- Return 404 errors when a snapshot is not found and validate payload shapes using Pydantic models.

## Deliverables
1. Service-layer utilities (e.g., `backend/app/services/snapshots.py`) encapsulating CRUD operations for reuse.
2. Pydantic schemas representing snapshot creation, updates, and responses.
3. FastAPI router mounted in `main.py` exposing the endpoints listed above.
4. Unit tests under `backend/tests/` covering happy paths and 404 handling for the new API.
5. README/AGENTS updates are not required unless the architecture meaningfully changes.

## Definition of done
- `uvicorn backend.app.main:app --reload` continues to boot successfully, creating the SQLite database when missing.
- The snapshot endpoints perform the expected CRUD operations against SQLite using deterministic logic.
- Tests introduced for this slice pass locally (`pytest -q`).
- Code and docs are committed with a clean working tree.
