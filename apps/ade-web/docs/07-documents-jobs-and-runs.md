# 07 – Documents and Runs

This document describes how ADE Web models and implements:

- **Documents** – immutable input files inside a workspace.
- **Runs** – executions of the ADE engine against one or more documents.
- The **Documents** and **Runs** sections of the workspace shell.
- **Run options** and **per‑document run preferences**.

It is written for frontend engineers and backend integrators. For canonical terminology (Workspace, Document, Run, Configuration, Safe mode, etc.) see `01-domain-model-and-naming.md`.

> **Terminology note**  
> In this document we use **run** as the primary term for engine executions.  
> Some backend endpoints still use `/runs` in their path; treat those as *run APIs* with legacy naming.

---

## 1. Conceptual model

At a high level:

- A **document** is an immutable input file that belongs to a workspace.
- A **run** is one execution of ADE against a set of documents using a particular configuration and options.
- ADE Web exposes:
  - A **Documents** section for managing inputs.
  - A **Runs** section for the workspace‑wide run ledger.
  - Run entry points from **Documents** and **Config Builder**.

### 1.1 Relationships

- A **workspace** owns many **documents**.
- A **workspace** owns many **runs**.
- A **run** references:
  - One workspace.
  - One configuration and version (when applicable).
  - One or more input documents.
  - Optional run‑time options (dry run, validate only, sheet selection, …).

Documents and runs are **loosely coupled**:

- Documents are immutable and never edited by runs.
- Runs always refer to documents by ID; they do not mutate document content.

---

## 2. Documents

### 2.1 Data model

Frontend view of a document in lists:

```ts
export interface DocumentSummary {
  id: string;
  workspaceId: string;

  name: string;              // usually original filename
  contentType: string;       // e.g. "application/vnd.ms-excel"
  sizeBytes: number;

  status: DocumentStatus;    // uploaded | processing | processed | failed | archived
  createdAt: string;         // ISO 8601 string
  uploadedBy: UserSummary;

  lastRun?: DocumentLastRunSummary | null;
}

export interface DocumentLastRunSummary {
  id: string;
  status: RunStatus;
  finishedAt?: string | null;
  message?: string | null;   // optional human‑readable note
}
````

A separate `DocumentDetail` type can extend this if the detail endpoint returns more metadata.

**Immutability:**

* Uploading a revised version produces a **new** `document.id`.
* All run APIs use document IDs; they never modify the underlying file.

### 2.2 Status lifecycle

`DocumentStatus` is defined centrally; ADE Web does not derive it from runs.

Conceptually:

* `uploaded` – file is stored, no run yet.
* `processing` – at least one active run includes this document.
* `processed` – the last relevant run succeeded.
* `failed` – the last relevant run failed.
* `archived` – document is retained for history but excluded from normal interactions.

Typical transitions:

* `null` → `uploaded` when upload completes.
* `uploaded | processed | failed` → `processing` when a run starts.
* `processing` → `processed` on successful completion.
* `processing` → `failed` on error.
* Any → `archived` via explicit user action.

The UI:

* Displays `status` as a badge in the Documents list.
* Shows `lastRun` as a secondary indicator (“Last run: succeeded 2 hours ago”).
* Only changes status by refetching from the backend.

---

## 3. Documents screen architecture

**Route:** `/workspaces/:workspaceId/documents`
**Responsibilities:**

1. List and filter documents in the workspace.
2. Provide upload and download actions.
3. Provide “Run extraction” entry points.
4. Surface last run status and key metadata.

### 3.1 Data sources and hooks

Typical hooks used by `DocumentsScreen`:

```ts
const [searchParams, setSearchParams] = useSearchParams();
const filters = parseDocumentFilters(searchParams);

const documentsQuery = useDocumentsQuery(workspaceId, filters);
const uploadMutation = useUploadDocumentMutation(workspaceId);
```

* `useDocumentsQuery` → `GET /api/v1/workspaces/{workspace_id}/documents`
* `useUploadDocumentMutation` → `POST /api/v1/workspaces/{workspace_id}/documents`
* `useDocumentSheetsQuery` (lazy) → `GET /documents/{document_id}/sheets`

These hooks live in the Documents feature folder and delegate HTTP details to `shared` API modules.

### 3.2 Filters, search, and sorting

Documents URL state is encoded via query parameters:

* `q` – free‑text search (by name, possibly other fields).

* `status` – comma‑separated list of document statuses.

* `sort` – sort key, e.g.:

  * `-created_at` (newest first)
  * `-last_run_at` (recent runs first)

* `view` – optional preset (e.g. `all`, `mine`, `attention`, `recent`).

Rules:

* Filter changes are reflected in the URL using `setSearchParams`.
* For small, frequent adjustments (toggling a status pill), we call `setSearchParams` with `{ replace: true }` to avoid polluting history.

### 3.3 Upload flow

User flow:

1. User clicks “Upload documents” or presses `⌘U` / `Ctrl+U`.
2. A file picker opens (or a drag‑and‑drop zone is available).
3. For each selected file, `uploadMutation.mutate({ file })` is called.
4. During upload:

   * Show progress (if easily available).
   * Disable duplicate submissions of the same file selection.
5. On success:

   * Show a success toast (“Uploaded 3 documents”).
   * Invalidate the documents query to refresh the list.
6. On failure:

   * Show an error toast and/or inline `Alert` with backend error text.

Implementation guidelines:

* Keep upload UX optimistic but let the documents query be the source of truth for final status.
* Handle duplicate file names gracefully; they are not required to be unique.

### 3.4 Row actions

Each `DocumentRow` typically exposes:

* **Download** – invokes `GET /documents/{document_id}/download`.
* **Run extraction** – opens the run dialog (section 8).
* **Archive/Delete** – invokes `DELETE /documents/{document_id}` (usually soft delete).

Run‑related actions must be:

* **Permission‑gated** – hidden/disabled if the user cannot start runs.
* **Safe‑mode‑aware** – disabled with a clear tooltip when Safe mode is enabled.

---

## 4. Document sheets

For multi‑sheet spreadsheets, the user can choose which worksheets to process.

### 4.1 API contract

Endpoint:

```text
GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/sheets
```

Expected shape:

```ts
export interface DocumentSheet {
  name: string;
  index: number;
  isActive?: boolean;  // optional “active”/default sheet signal
}
```

Errors and unsupported types:

* If the backend can’t list sheets (unsupported format, parse failure, etc.), it may return an error or an empty list.
* The frontend must gracefully fall back to a “use all sheets” mode.

### 4.2 Use in run dialogs

`useDocumentSheetsQuery(workspaceId, documentId)` is called:

* Lazily when a run dialog opens **and** the document looks like a spreadsheet.
* Or on demand when the user expands a “Sheets” section.

UI behaviour:

* If sheets are returned:

  * Show a multi‑select checklist of worksheet names.
  * Default selection:

    * All sheets, or
    * Only `isActive` sheets if the backend provides that signal.

* If sheets cannot be loaded:

  * Show a small inline warning (“Couldn’t load worksheets; running on all sheets.”).
  * Omit `inputSheetNames` from the run request.

Selected sheet names are passed to the run API as `input_sheet_names`.

---

## 5. Runs

A **run** is one execution of the ADE engine. ADE Web exposes two main perspectives on runs:

* The **Runs** ledger – workspace‑wide history (`/workspaces/:workspaceId/runs`, API currently `/runs`).
* **Config‑scoped runs** – initiated from Config Builder against a specific configuration.

### 5.1 Run data model

Workspace‑level run summary:

```ts
export interface RunSummary {
  id: string;
  workspaceId: string;
  status: RunStatus;        // queued | running | succeeded | failed | cancelled

  createdAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;

  initiatedBy: UserSummary | "system";

  configurationId?: string | null;
  configurationVersionId?: string | null;

  inputDocuments: {
    count: number;
    examples: Array<{ id: string; name: string }>;
  };

  options?: RunOptions;
  message?: string | null;
}

export interface RunOptions {
  dryRun?: boolean;
  validateOnly?: boolean;
  inputSheetNames?: string[];
}
```

A `RunDetail` type extends this with:

* Full document list.
* Links to outputs (artifact + individual files).
* Optional telemetry summary.
* Log/console linkage.

### 5.2 Run status

`RunStatus` values:

* `queued` – accepted, waiting to start.
* `running` – currently executing.
* `succeeded` – completed successfully.
* `failed` – completed with error.
* `cancelled` – terminated early by user/system.

Status semantics are the same whether the run came from:

* Documents screen.
* Runs screen.
* Config Builder (test runs).

ADE Web never infers status; it shows what the backend reports.

---

## 6. Runs ledger screen

Conceptually: **Runs** is the workspace‑wide ledger of engine activity.

**Route:** `/workspaces/:workspaceId/runs` (UI; underlying backend routes currently use `/runs`)
**Responsibilities:**

1. Show all runs in a workspace.
2. Allow filtering/sorting by status, configuration, initiator, and time.
3. Provide access to logs, telemetry, and outputs.

### 6.1 Data and filters

Hook:

```ts
const filters = parseRunFilters(searchParams);
const runsQuery = useRunsQuery(workspaceId, filters);
// internally calls GET /api/v1/workspaces/{workspace_id}/runs
```

Typical filters encoded in the URL:

* `status` – comma‑separated `RunStatus` values.
* `config` – configuration id or version.
* `initiator` – user id or `system`.
* `from`, `to` – created‑at time window.

### 6.2 Run list UI

Each row shows:

* Run ID (short display form).
* Status badge.
* Configuration name/version (if present).
* Input document summary (“3 documents”, with tooltip listing examples).
* Initiator.
* Created time and duration.

Row interaction:

* Clicking a row opens a **Run detail** view, either:

  * As its own route: `/workspaces/:workspaceId/runs/:runId`, or
  * As a side panel/dialog anchored on the list.

### 6.3 Run detail and logs

Run detail view composes:

* **Header:**

  * Run ID, status, configuration, initiator.
  * Timestamps and duration.

* **Logs/console:**

  * Either streaming NDJSON, or a loaded log file.
  * Rendered similarly to the Config Builder console.

* **Telemetry summary:**

  * Rows processed, warnings, errors, per‑table counts, etc. (when available).

* **Outputs:**

  * Link to combined artifact download.
  * Table of individual output files.

Data sources:

* `useRunQuery(workspaceId, runId)` → `GET /runs/{run_id}` or `/runs/{run_id}`.
* `useRunOutputsQuery(workspaceId, runId)` → `/runs/{run_id}/outputs` or `/runs/{run_id}/outputs`.
* `useRunLogsStream(workspaceId, runId)`:

  * Connects to `/runs/{run_id}/logs` or `/runs/{run_id}/logs`.
  * Parses NDJSON events.
  * Updates console output incrementally.

While a run is `queued` or `running`:

* The detail view holds an active log stream.
* The Runs ledger may poll or simply rely on detail views to trigger refreshes.

---

## 7. Starting runs

Users can start new runs from multiple surfaces:

* **Documents** section: “Run extraction” for a specific document.
* **Runs** section: “New run” (if you support multi‑document runs).
* **Config Builder**: “Run extraction” against a sample document (config‑scoped).

### 7.1 Run options in the UI

ADE Web exposes run options as the backend supports them:

* **Dry run**

  * Label: “Dry run (don’t write outputs)”.
  * Intended for testing.

* **Validate only**

  * Label: “Run validators only”.
  * Skip full extraction.

* **Sheet selection**

  * Label and UI: “Worksheets”.
  * Uses sheet metadata described in section 4.

General rules:

* Options live under an “Advanced settings” expander in run dialogs.
* Defaults are product decisions and may be remembered per document (see next section).

### 7.2 Workspace‑level run creation (Documents & Runs)

From the **Documents** screen:

1. User clicks “Run extraction” on a document row.

2. ADE Web opens `RunDocumentDialog` with:

   * Selected document prefilled.
   * Preferred configuration/version and sheet subset loaded from per‑document preferences (if any).

3. On submit:

   * ADE Web calls `POST /api/v1/workspaces/{workspace_id}/runs` (legacy path for workspace runs).
   * Payload includes:

     * `input_document_ids: [documentId]`
     * Optional `input_sheet_names`
     * Optional `dry_run` / `validate_only`
     * Selected configuration/version identifiers.

4. On success:

   * Show a success toast.
   * Optionally navigate to the Run detail view.
   * Invalidate runs and documents queries.

From the **Runs** screen:

* A “New run” action could open a similar dialog allowing multiple documents to be selected.

### 7.3 Config‑scoped runs (Config Builder)

Config Builder uses **config‑scoped runs** primarily for test/validation:

* `POST /api/v1/configs/{config_id}/runs` with a similar payload.
* Response provides a `run_id`.
* ADE Web streams that run’s events into the workbench console via `/api/v1/runs/{run_id}/logs`.

The semantics (status, options, outputs) are identical; only the entry point and visual context differ. Full details live in `09-workbench-editor-and-scripting.md`.

---

## 8. Per‑document run preferences

To make repeated runs smoother, ADE Web remembers per‑document, per‑workspace, per‑user preferences.

### 8.1 What is persisted

For each `(workspaceId, documentId, user)` we may store:

```ts
export interface DocumentRunPreferences {
  configurationId?: string;
  configurationVersionId?: string;
  inputSheetNames?: string[];
  options?: {
    dryRun?: boolean;
    validateOnly?: boolean;
  };
  version: 1;
}
```

Fields are optional; missing fields fall back to sensible defaults.

### 8.2 Storage and keying

Preferences live in browser `localStorage` via a shared helper, not direct calls from components.

Key pattern:

```text
ade.ui.workspace.<workspaceId>.document.<documentId>.run-preferences
```

Invariants:

* **Per‑user** and **per‑workspace** (keys include `workspaceId`).
* Never contain secrets; safe to clear.
* Backend remains the source of truth for configuration availability.

### 8.3 Read/write strategy

**Reading on dialog open:**

* When a run dialog opens for a document:

  1. Load preferences with `getDocumentRunPreferences(workspaceId, documentId)`.
  2. Check that referenced configuration/version still exists:

     * If not, drop those fields from the loaded preferences.
  3. Use the remaining fields to pre‑fill config, version, sheet selection, and advanced options.

**Writing on successful submit:**

* After a run is successfully submitted from the Documents screen:

  * Merge the final dialog choices into `DocumentRunPreferences`.
  * Save using `setDocumentRunPreferences(...)`.

**Reset:**

* Run dialog may expose “Reset to defaults”, which:

  * Clears the `run-preferences` entry for that document.
  * Reverts to system defaults on next open.

Implementation detail:

* All logic should live in a small module (e.g. `shared/runPreferences.ts`) and a feature hook (`useDocumentRunPreferences`), so changing key patterns or versioning is centralised.

---

## 9. Backend contracts (summary)

The Documents and Runs features depend on the following backend endpoints. Detailed typings and error semantics are documented in `04-data-layer-and-backend-contracts.md`.

### 9.1 Documents

* `GET /api/v1/workspaces/{workspace_id}/documents`
  List documents (supports `q`, `status`, `sort`, `view`).

* `POST /api/v1/workspaces/{workspace_id}/documents`
  Upload a document.

* `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}`
  Retrieve document metadata.

* `DELETE /api/v1/workspaces/{workspace_id}/documents/{document_id}`
  Soft delete / archive.

* `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/download`
  Download original file.

* `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/sheets`
  List worksheets (optional, spreadsheet only).

### 9.2 Workspace runs (ledger)

*Backend naming currently uses `/runs`; conceptually these are runs.*

* `GET /api/v1/workspaces/{workspace_id}/runs`
  List runs for the workspace (filters by status, configuration, initiator, date).

* `POST /api/v1/workspaces/{workspace_id}/runs`
  Start a new workspace run (used by Documents / Runs).

* `GET /api/v1/workspaces/{workspace_id}/runs/{run_id}`
  Run detail.

* `GET /api/v1/workspaces/{workspace_id}/runs/{run_id}/artifact`
  Download combined outputs.

* `GET /api/v1/workspaces/{workspace_id}/runs/{run_id}/outputs`
  List individual output files.

* `GET /api/v1/workspaces/{workspace_id}/runs/{run_id}/outputs/{output_path}`
  Download a single output.

* `GET /api/v1/workspaces/{workspace_id}/runs/{run_id}/logs`
  Run logs (ideally NDJSON stream, but can be a file).

### 9.3 Config‑scoped runs

Used by Config Builder:

* `POST /api/v1/configs/{config_id}/runs`
  Start a config‑scoped run.

* `GET /api/v1/runs/{run_id}`
  Run detail.

* `GET /api/v1/runs/{run_id}/artifact` (if provided).

* `GET /api/v1/runs/{run_id}/outputs` + `/outputs/{output_path}`.

* `GET /api/v1/runs/{run_id}/logs`
  NDJSON event stream.

All run endpoints should share consistent `RunStatus` values and event semantics.

---

## 10. Safe mode interactions

Safe mode (see `05-auth-session-rbac-and-safe-mode.md`) acts as a kill switch for engine execution.

In the context of Documents and Runs:

* When **Safe mode is enabled**:

  * Run dialogs cannot submit.
  * “Run extraction” buttons are disabled.
  * Any “New run” actions are disabled.
* Read‑only operations still work:

  * Listing documents and runs.
  * Viewing run details.
  * Downloading artifacts, outputs, and logs.

UI behaviour:

* A workspace‑level safe mode banner is shown inside the shell.
* Disabled controls show a tooltip such as:

  > “Safe mode is enabled: <backend message>”

Server‑side checks remain authoritative; UI disabling is a convenience to avoid surprises.

---

## 11. Design invariants

To keep this surface easy to reason about (for humans and AI agents), we rely on a few invariants:

1. **Documents show backend status.**
   ADE Web never infers document status from run history; it merely displays what the backend reports.

2. **Run semantics are consistent everywhere.**
   Status values, options (`dryRun`, `validateOnly`, `inputSheetNames`), and timestamps mean the same thing in:

   * Documents last‑run summaries,
   * Runs ledger,
   * Config‑scoped runs.

3. **Runs are append‑only.**
   Runs are created, progress, and complete; they are not edited after creation. “Run again” always creates a new run.

4. **Per‑document run preferences are hints, not configuration.**
   They influence UI defaults only. If configurations disappear or change, preferences are safely ignored.

5. **Safe mode always wins.**
   If Safe mode is on, the UI never attempts to create new runs, and the backend enforces that rule.

With these invariants respected, the Documents and Runs features remain predictable and easy to extend, and the mapping between frontend behaviour and backend APIs stays clear.