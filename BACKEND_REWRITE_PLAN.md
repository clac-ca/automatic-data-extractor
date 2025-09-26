# ADE backend rewrite – architecture notes

The FastAPI backend has been refactored to favour deterministic, auditable flows
that match how the ADE frontend and CLI operate. This document records the
current shape of the system, highlights the module boundaries, and captures the
next milestones that unblock the frontend roadmap in `FRONTEND_DESIGN.md`.

---

## 1. Guiding principles

- **Clarity first** – Prefer explicit services and dependency wiring over hidden
  side effects. Every request path should be traceable.
- **Deterministic workflows** – Jobs run synchronously within the request by
  default; background infrastructure only appears when requirements demand it.
- **Workspaces everywhere** – Routes are mounted under
  `/workspaces/{workspace_id}` using the `workspace_scoped_router` helper so
  multi-tenant logic stays consistent.
- **Small, auditable codebase** – Keep dependencies minimal, lean on the standard
  library, and document contracts that the frontend depends on.

---

## 2. Delivered capabilities

The rewrite currently supports the three core workflows that power the product:

1. **Document intake** – Upload, list, download, and soft-delete documents while
   persisting metadata and file blobs to disk.
2. **Job execution** – Validate submissions, execute the extractor synchronously,
   capture metrics/logs, and persist status transitions.
3. **Results review** – Serve extracted tables and metadata so analysts can audit
   outputs and export data.

Supporting modules provide configuration management, workspace administration,
and authentication for both UI and CLI clients.

---

## 3. Module boundaries

| Module | Key responsibilities | Primary endpoints |
| ------ | -------------------- | ----------------- |
| `documents` | Metadata persistence, file storage, soft deletion, downloads. | `POST /documents`, `GET /documents`, `GET /documents/{id}`, `GET /documents/{id}/download`, `DELETE /documents/{id}` |
| `jobs` | Job submission, extractor invocation, status tracking, metrics/logs. | `POST /jobs`, `GET /jobs`, `GET /jobs/{id}` |
| `results` | Serve extracted tables tied to jobs or documents. | `GET /jobs/{id}/tables`, `GET /jobs/{id}/tables/{table_id}`, `GET /documents/{id}/tables` |
| `configurations` | CRUD, versioning, and activation of extractor configurations. | `GET /configurations`, `POST /configurations`, `PUT /configurations/{id}`, `DELETE /configurations/{id}`, `POST /configurations/{id}/activate` |
| `workspaces` | Workspace metadata, membership management, default selection. | `GET /workspaces`, `GET /workspaces/{id}`, `PATCH /workspaces/{id}`, `GET /workspaces/{id}/members`, `PATCH /workspaces/{id}/members/{user_id}`, `DELETE /workspaces/{id}/members/{user_id}`, `POST /workspaces/{id}/default` |
| `auth` | Token issuance for username/password credentials. | `POST /auth/token` |

Cross-cutting infrastructure lives under `backend/api/core` and `backend/api/db`:

- **Repositories** – Thin SQLAlchemy abstractions for documents, jobs,
  configurations, results, and workspaces.
- **Storage** – `DocumentStorage` streams uploads and downloads from
  `data/documents/` with concurrency-safe helpers.
- **Processor** – `backend/processor/run` acts as the deterministic extraction
  entry point invoked by `JobsService`.
- **Events** – Optional audit trail emitter; currently write-only but ready to
  expose via `/events` when the UI needs it.

---

## 4. Data contracts & error handling

- **Documents** – Responses serialise to `DocumentRecord` with metadata stored in
  `metadata_` JSON columns. Soft deletes retain `deleted_at`, `deleted_by`, and
  optional `delete_reason` for audit.
- **Jobs** – `JobRecord` includes `document_type`, `configuration_id`,
  `configuration_version`, status, metrics, and logs. Failures return structured
  payloads (e.g., `{ "error": "job_failed", ... }`).
- **Results** – `ExtractedTableRecord` returns schema (columns), sample rows, and
  metadata. `HTTP 409` indicates the job is still processing; callers should
  retry.
- **Configurations** – Enforce document type and version rules; activation toggles
  a boolean while preserving history.
- **Authentication** – Tokens encapsulate `workspace:*` permissions; dependencies
  validate access before hitting module services.

These schemas directly power the typed clients in the frontend API layer.

---

## 5. Alignment with frontend roadmap

| Frontend milestone | Backend dependencies | Status |
| ------------------ | -------------------- | ------ |
| Shell & overview | `GET /workspaces`, `GET /documents`, `GET /jobs`, retention metadata fields on workspaces. | Ready (retention metadata exposed via workspace model). |
| Documents & jobs foundation | Document CRUD, multipart upload handling, job submission, job detail. | Ready; service tests cover upload/download/job lifecycle. |
| Results explorer | Job/document tables endpoints, job metrics/logs. | Ready; results module returns sample rows and schema. |
| Configuration workflows | Configuration CRUD + activation endpoints. | Ready; ensure permission checks enforced per workspace. |
| Workspace settings | Workspace metadata + membership endpoints. | Ready; audit events available for future activity feed. |
| Polish & automation | Events feed, retention automation, admin tooling. | Partial; event read API and retention scheduler tracked below. |

Frontend implementers should rely on these contracts; any adjustments must be
reflected in both this plan and `FRONTEND_DESIGN.md`.

---

## 6. Immediate roadmap

1. **Retention policies** – Implement scheduled cleanup for expired documents,
   job logs, and extracted tables. Surface retention metadata through the
   workspaces API so the frontend can show warnings.
2. **Permission defaults** – Seed sensible workspace permission sets on
   creation. Provide migration scripts so existing workspaces receive the new
   defaults.
3. **Event surfacing** – Expose a read-only `/events` endpoint to drive activity
   panels and audit logs in the UI.
4. **Extractor integration** – Replace the stub processor with the production ADE
   pipeline while keeping synchronous semantics.
5. **Operational tooling** – Expand CLI/admin endpoints for resubmitting failed
   jobs, rotating service-account keys, and monitoring storage usage.

Revisit this plan whenever backend contracts or priorities change; the frontend
roadmap depends on these milestones staying accurate.
