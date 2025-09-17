# Current Task — Snapshot publication flow

## Goal
Re-evaluate how ADE tracks the "live" snapshot for each document type so the published configuration is always obvious to both the API and the UI. Instead of maintaining a second registry table, make the snapshot record itself the source of truth: only one snapshot per document type can be published at a time, and every run that omits an explicit `snapshot_id` will automatically target that published version.

## Background
- The existing CRUD endpoints already create, list, update, and delete snapshot rows with an `is_published` flag.
- A previous iteration introduced a `live_snapshots` table plus `/live-snapshots` routes, but the flow now feels redundant: publication state lives on the snapshot and the extra registry complicates both the API and the front-end mental model.
- Front-end operators expect to browse drafts, publish one snapshot, and let the system default to that published version unless they pin an older snapshot for a run.

## Scope
- Remove the `live_snapshots` table, models, services, and routes so snapshot publication is managed directly on the `snapshots` table.
- Extend the `Snapshot` model with a `published_at` timestamp and service helpers that:
  - ensure publishing a snapshot automatically unpublishes any other snapshot for the same document type,
  - allow snapshots to be un-published back to draft state, and
  - provide utilities to fetch the current published snapshot or resolve a requested snapshot ID (falling back to the published one when omitted).
- Update the snapshot service layer and FastAPI routes so toggling `is_published` via `POST /snapshots` or `PATCH /snapshots/{id}` enforces the single-published invariant.
- Add an endpoint (e.g., `GET /snapshots/published/{document_type}`) that returns the active published snapshot, returning HTTP 404 when none exists.
- Refresh Pydantic schemas and API responses to surface the new `published_at` metadata.
- Replace the previous `/live-snapshots` test suite with coverage that exercises publication transitions, demotion of older snapshots, and the published snapshot lookup helper.
- Update glossary/background docs to explain that the live pointer is now derived from the single published snapshot (and remove references to the dropped table).

## Deliverables
1. Simplified data model with publication tracked directly on snapshots and `published_at` timestamps recorded.
2. Deterministic service-layer logic (`publish`, `unpublish`, `get_published_snapshot`, and `resolve_snapshot`) that prevents multiple published snapshots per document type.
3. FastAPI routing that exposes the published snapshot lookup and returns clear HTTP errors when none is available.
4. Pytest coverage validating publishing/unpublishing behaviour, default resolution, and the new endpoint; existing snapshot tests continue to pass with the updated responses.
5. Glossary/README updates reflecting the new publication workflow and the absence of the `live_snapshots` table.

## Definition of done
- `uvicorn backend.app.main:app --reload` still boots, creating/refreshing the updated `snapshots` table without the `live_snapshots` registry.
- Publishing a snapshot through the API demotes the previous one; unpublishing clears the default.
- `resolve_snapshot` returns the published snapshot when no ID is supplied and raises helpful errors for missing publication or mismatched document types.
- `pytest -q` passes with new and updated tests covering publication flows.
- Planning docs (`CURRENT_TASK.md`, `ADE_GLOSSARY.md`, README if touched) align with the simplified model, and `git status` is clean.
