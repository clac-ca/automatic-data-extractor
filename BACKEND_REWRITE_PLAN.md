# ADE Backend Rewrite – Architecture Notes

## Why this rewrite?
The prior FastAPI backend recreated legacy message-passing concepts (timeline
events, background hubs, opaque status transitions) that made debugging and
iteration painful. The rewrite intentionally collapses that complexity: every
workflow should be deterministic, auditable, and understandable by a small
internal team. Upload a file, run the extractor, review tables—that’s the entire
mission.

Key guardrails:

- Keep the codebase approachable for a small internal team.
- Prefer explicit services over implicit cross-module side effects.
- Preserve deterministic behaviour so extraction results are auditable.
- Expand scope only when the synchronous path is exercised by the UI and CLI.

## Capabilities delivered so far

The rebuilt backend currently supports the three workflows needed by the new
frontend and CLI:

1. **Document intake** – Receive uploads, capture metadata, store the file on
   disk, and manage soft deletion + download streams.
2. **Job execution** – Validate the requested document/configuration, run the
   extractor synchronously inside the request, persist metrics/logs, and track
   status transitions.
3. **Result review** – Read stored tables and logs so analysts can verify the
   output or export it for downstream usage.

All routes are scoped beneath `/workspaces/{workspace_id}` via the
`workspace_scoped_router` helper. Authorization relies on the `workspace:*`
permission set stored on the workspace context.

## Module boundaries

The FastAPI application under `backend/api/` exposes domain modules backed by
shared infrastructure components:

| Module | Responsibility |
| ------ | -------------- |
| `documents` | Manage metadata, storage lifecycle, and download helpers. |
| `jobs` | Submit extraction runs, track status, and link inputs/outputs. |
| `results` | Surface extracted tables and related artefacts for review. |
| `configurations` | CRUD + activation for extractor definitions. |
| `workspaces` | Membership management and workspace metadata. |

Cross-cutting helpers live outside the modules:

- `services.storage.DocumentStorage` – Safe filesystem access rooted in
  `data/documents/` with streaming helpers using `run_in_threadpool`.
- `processor.run(job_request)` – Deterministic extraction entry point returning
  structured tables and job metrics.
- `repositories.*` – Thin SQLAlchemy wrappers used by services.

### Documents module

- **Endpoints** – `POST /documents`, `GET /documents`, `GET /documents/{id}`,
  `GET /documents/{id}/download`, `DELETE /documents/{id}`.
- **Service** – `DocumentsService` handles file validation, persistence through
  `DocumentStorage`, metadata writes, soft deletion (with optional reason), and
  audit trail emission.
- **Storage** – Files live under `data/documents/` with streaming downloads via
  `StreamingResponse`. Missing files raise `DocumentFileMissingError` so the UI
  can surface a precise error.

_Status:_ Implemented with integration tests covering upload, download, and
soft-delete cases.

### Jobs module

- **Endpoints** – `POST /jobs`, `GET /jobs`, `GET /jobs/{id}` with filters for
  status and input document.
- **Service** – `JobsService` validates the requested configuration, seeds the
  job record (`pending → running → succeeded/failed`), invokes
  `backend.processor.run`, captures metrics/logs, and persists the resulting
  tables via the results repository.
- **Error handling** – Propagates structured errors for missing documents,
  configuration mismatches, and extractor failures. Job execution errors return
  a `{ "error": "job_failed", ... }` payload.

_Status:_ Implemented synchronously with unit and service-level tests. The
message hub remains for audit purposes but no longer controls execution.

### Results module

- **Endpoints** – `GET /jobs/{id}/tables`, `GET /jobs/{id}/tables/{table_id}`,
  `GET /documents/{id}/tables`.
- **Service** – `ExtractionResultsService` verifies job status before serving
  tables, preventing premature access. It can emit "viewed" events for audit and
  reuses shared repositories for persistence.
- **Error handling** – Returns HTTP 409 when a job is not yet complete so the
  frontend can display “processing” states, and 404 for missing tables/documents.

_Status:_ Implemented and covered by backend tests; ready for frontend
integration.

### Configurations & workspaces

Although the initial rewrite focused on documents/jobs/results, the supporting
modules are also online:

- **Configurations** – Full CRUD (`GET`, `POST`, `PUT`, `DELETE`) plus activation
  endpoint and active-list filter. Services enforce document-type and versioning
  rules.
- **Workspaces** – Membership CRUD, workspace metadata management, and default
  workspace selection. Dependencies populate `request.state.current_workspace`
  for downstream services.

These routes unblock the frontend configuration library and workspace switcher.

## Data model checkpoints

- Continue using the existing `documents`, `jobs`, `extracted_tables`, and
  `configurations` tables to avoid mid-rewrite migrations.
- Timeline/event columns have been collapsed into explicit job status fields;
  richer timelines can return later using the new event system.
- Files are still stored on disk; future retention work will reclaim storage
  based on document expiry or workspace quotas.
- A single `users` table with `is_service_account` covers both human and machine
  access. API keys always reference `users.user_id` for auditing.

## Processing lifecycle

1. Upload document (metadata stored, file persisted on disk).
2. Submit job referencing document + configuration version.
3. Job service writes a `jobs` row with status `pending`, then runs the extractor
   in-process.
4. On success the service persists extracted tables, updates status to
   `succeeded`, and records duration/row counts.
5. On failure the service captures the error, updates status to `failed`, and
   retains partial logs for debugging.

Background queue infrastructure stays dormant until we have a proven need for
async execution. The single-process worker keeps observability straightforward
while we validate flows with the UI.

## Immediate roadmap

1. **Retention policies** – Implement scheduled cleanup for expired documents,
   job logs, and extracted tables. Expose retention metadata so the frontend can
   message upcoming deletions.
2. **Permission defaults** – Seed sensible workspace permissions on creation so
   owners automatically gain access to documents, jobs, results, and
   configurations without manual grants.
3. **Audit surfacing** – Decide how timeline/events should re-emerge. Likely a
   read-only `/events` endpoint consumed by the frontend’s activity views.
4. **Extractor integration** – Replace the stub processor with the real ADE
   extraction pipeline, ensuring interfaces stay deterministic.
5. **Operational tooling** – Build CLI/admin endpoints for resubmitting failed
   jobs, rotating service-account keys, and monitoring storage utilisation.

Revisit this plan whenever we change models or introduce async execution; the
frontend design in `FRONTEND_DESIGN.md` depends on the contracts outlined here.

