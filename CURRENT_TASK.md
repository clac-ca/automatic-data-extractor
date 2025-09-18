# Current Task — Document ingestion API

## Goal
Stand up the first-party document ingestion workflow so every job input is backed by deterministic metadata and an on-disk file managed by the backend.

## Background
- Jobs now require callers to provide a `uri` + `hash`, but there is no canonical service to accept uploads or generate those identifiers.
- Settings already reserve `var/documents/` for persistence. We need helpers that write into this directory, guard against collisions, and expose metadata via the API.
- Downstream orchestration (manual uploads, CLI automation, future background processors) should all rely on the same API surface.

## Scope
- Introduce a `Document` SQLAlchemy model that stores `document_id` (ULID), `original_filename`, `content_type`, `byte_size`, `sha256`, `stored_uri`, and timestamps. Use JSON for any optional metadata required later.
- Add storage helpers under `backend/app/services/documents.py` that:
  - Accept bytes/streams and persist them inside `var/documents/` using a deterministic hashed path.
  - De-duplicate uploads by returning the existing record when the SHA-256 digest matches an existing file.
  - Expose listing + lookup utilities ordered by recency so routes/tests stay thin.
- Build a FastAPI router mounted at `/documents` supporting:
  - `POST /documents` (multipart upload) → creates or reuses a document record and returns metadata including the canonical `stored_uri` consumers pass into job inputs.
  - `GET /documents` → list documents ordered by `created_at` desc.
  - `GET /documents/{document_id}` → fetch metadata for a specific document.
  - Optional `GET /documents/{document_id}/download` can stream files if it stays simple.
- Ensure upload size limits and error handling are documented even if enforcement stays TODO.
- Update README, ADE_GLOSSARY.md, and AGENTS.md to reference the document ingestion workflow and the new API surface.

## Deliverables
1. SQLAlchemy model + Alembic-not-required migration (via `Base.metadata.create_all`) that introduces the `documents` table.
2. Service helpers covering hashed file storage, deduplication, and metadata retrieval with deterministic URIs.
3. FastAPI routes + Pydantic schemas for create/list/get (and optional download) operations.
4. Pytest coverage exercising upload workflows (fresh upload, duplicate hash, list ordering, metadata retrieval) using temporary directories.
5. Documentation updates that describe how callers upload documents before launching jobs.

## Definition of done
- `uvicorn backend.app.main:app --reload` boots, creating the `documents` table and the hashed storage directory structure when missing.
- Uploading the same file twice reuses the prior metadata, does not duplicate the file on disk, and the API returns consistent URIs.
- Jobs can rely on the returned `stored_uri` without manual filesystem knowledge.
- `pytest -q` passes with the new document ingestion tests.
- Docs, glossary, and agent notes explain the upload → job flow with the updated vocabulary.
