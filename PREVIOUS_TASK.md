# Previous Task — Configuration revision CRUD API

## Goal
Expose CRUD operations for the configuration revision model so the frontend and CLI tools can create, browse, inspect, update,
and delete configuration metadata through the FastAPI backend.

## Scope
- Implement database-layer helpers that wrap the new SQLAlchemy model (`ConfigurationRevision`) with deterministic logic (no
  randomness or side-effects besides persistence).
- Build a dedicated router under `backend/app/routes/configuration_revisions.py` that provides:
  - `POST /configuration-revisions` – create a configuration revision record.
  - `GET /configuration-revisions` – list configuration revisions ordered by `created_at` descending.
  - `GET /configuration-revisions/{configuration_revision_id}` – fetch a single configuration revision by ULID.
  - `PATCH /configuration-revisions/{configuration_revision_id}` – update mutable fields (`title`, `payload`, lifecycle flags).
  - `DELETE /configuration-revisions/{configuration_revision_id}` – remove a configuration revision.
- Define request/response schemas for the endpoints in `backend/app/schemas.py` (or a dedicated module if needed) ensuring all
  timestamps remain ISO 8601 strings.
- Return 404 errors when a configuration revision is not found and validate payload shapes using Pydantic models.

## Deliverables
1. Service-layer utilities (e.g., `backend/app/services/configuration_revisions.py`) encapsulating CRUD operations for reuse.
2. Pydantic schemas representing configuration revision creation, updates, and responses.
3. FastAPI router mounted in `main.py` exposing the endpoints listed above.
4. Unit tests under `backend/tests/` covering happy paths and 404 handling for the new API.
5. README/AGENTS updates are not required unless the architecture meaningfully changes.

## Definition of done
- `uvicorn backend.app.main:app --reload` continues to boot successfully, creating the SQLite database when missing.
- The configuration revision endpoints perform the expected CRUD operations against SQLite using deterministic logic.
- Tests introduced for this slice pass locally (`pytest -q`).
- Code and docs are committed with a clean working tree.
