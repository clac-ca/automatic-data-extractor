# 07-documents-jobs-and-runs

**Purpose:** All operator workflows: working with documents, jobs, and runs.

### 1. Overview

* Audience: analysts/operators, but written for implementers.
* Relationship to doc 01 (domain definitions).

### 2. Documents domain model

* Recap of document fields:

  * `id`, `name`, `contentType`, `size`, `status`, timestamps, `uploader`, `last_run`.

* Status transitions:

  * `uploaded` → `processing` → `processed` / `failed`.
  * `archived` and how it is reached.

* Immutability:

  * Re-uploading creates new document ID.

### 3. Documents screen behaviour

* List filtering:

  * Query `q`, status filters, sorting (`-created_at`, `-last_run_at`).
  * View presets: `mine`, `team`, `attention`, `recent` (if you have them).

* Upload flow:

  * Upload button + ⌘U / Ctrl+U.
  * Progress & error states.

* Row content:

  * What we show per document (type icon, size, last run status, uploader).

* Actions:

  * Run extraction.
  * Download original file.
  * Archive/delete.

### 4. Document sheets

* `/documents/{document_id}/sheets` expectations:

  * Fields: `name`, index, `is_active`.

* Sheet-selection UX:

  * When sheet list is fetched.
  * How we show checkboxes or multi-select.

* Fallback behaviour:

  * If endpoint missing or fails → show warning and “Use all worksheets”.

### 5. Jobs (workspace ledger)

* Job fields recap:

  * `id`, `status`, timestamps, initiator, config version, input documents, outputs.

* Jobs screen:

  * Filters: status, config, date range, initiator.
  * Columns: Job ID, status, config, created at, duration, initiator.

* Job detail view:

  * Link path (e.g. `/workspaces/:id/jobs/:jobId` if you have it).
  * Tabs/panels for logs, telemetry, outputs.

### 6. Runs and run options

* How “job” vs “run” are presented:

  * If the UI only exposes jobs, say so.
  * If there’s a separate “run detail” surface, describe it.

* Run options:

  * `dry_run`, `validate_only`, `input_sheet_names`.
  * Where/how they are exposed in UI (e.g. advanced settings in run dialog).

### 7. Per-document run preferences

* What’s remembered:

  * Preferred config, config version, sheet subset, maybe run options.

* Where it’s stored:

  * LocalStorage key pattern: `ade.ui.workspace.<workspaceId>.document.<documentId>.run-preferences`.

* Behaviour:

  * Applied automatically when opening the run dialog again.
  * How to reset/override.

* Cross-link to doc 10 section on persistence.

### 8. Backend contracts for documents & jobs

* Endpoint list with quick notes:

  * Documents: `/workspaces/{workspace_id}/documents`, `/documents/{document_id}`, `/download`, `/sheets`.
  * Jobs: `/workspaces/{workspace_id}/jobs`, `/jobs/{job_id}/artifact`, `/logs`, `/outputs`.

* Mapping to hooks:

  * `useDocumentsQuery`, `useUploadDocumentMutation`, `useJobsQuery`, `useJobOutputsQuery`, etc.
