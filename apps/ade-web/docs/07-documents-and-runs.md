# 07 – Documents and Runs

This document explains how ADE Web models and implements:

* **Documents** – immutable input files in a workspace.
* **Runs** – executions of the ADE engine against one or more documents.
* The **Documents** and **Runs** sections in the workspace shell.
* **Run options** and **per‑document run preferences**.

Use this doc when you’re:

* Building or changing the **Documents** or **Runs** UI.
* Wiring up or consuming `/documents` and `/runs` API endpoints.
* Debugging how a document ends up with a particular status or last‑run state.

For shared terminology (Workspace, Document, Run, Configuration, Safe mode, etc.) see `01-domain-model-and-naming.md`.

> **Terminology note**
> Backend endpoints still use `/runs`; in the UI and TS types we call that entity **Run** with ID field `runId`.

---

## 1. Conceptual overview

At a high level:

* A **Document** is an immutable input file that belongs to one workspace.
* A **Run** is one execution of ADE against a set of documents with a specific configuration and run options.
* ADE Web provides:

  * A **Documents** section for managing inputs.
  * A **Runs** section as a workspace‑wide execution ledger.
  * Run entry points from **Documents** and **Configuration Builder**.

### 1.1 Relationships

* A **workspace** owns many **documents**.
* A **workspace** owns many **runs**.
* Each **Run** references:

  * A workspace.
  * A configuration (and version, when applicable).
  * One or more input documents.
  * Optional run‑time options (dry run, validate only, sheet selection, …).

Key property: **Documents and Runs are loosely coupled.**

* Documents are **immutable** and never modified by runs.
* Runs always refer to documents by ID; they never touch document content or overwrite files.

### 1.2 Execution terminology

ADE Web distinguishes three related concepts:

* **Environment** – worker-owned execution cache for a configuration + dependency digest.

  * Not a user action in the UI.
  * Provisioned automatically as runs start.

* **Run** – executes the ADE engine against one or more documents.

  * Represented by the `Run` type.
  * Lives under `/runs` endpoints.

* **Run mode** – a UI label derived from run options to clarify intent (normal vs validation vs test).

Canonical run options in the UI:

```ts
type RunMode = "normal" | "validation" | "test";

interface RunOptions {
  dryRun?: boolean;
  validateOnly?: boolean;
  inputSheetNames?: string[];
  mode?: RunMode;           // View-model helper derived from the flags above
}
```

Typical interpretations:

* **Validation run**

  * `validateOnly: true` (and usually `mode: "validation"`).
  * Checks configuration correctness without full extraction.

* **Test run**

  * Run against a sample document, typically with `mode: "test"`.
  * Often combined with `dryRun: true`.

Backend payloads use **snake_case** equivalents:

* `dry_run`, `validate_only`, `input_sheet_names`.
* The `mode` field is **UI‑only**; the backend infers behaviour from the flags.

---

## 2. Documents

### 2.1 Data model

Frontend view for document lists:

```ts
export interface DocumentListRow {
  id: string;
  workspaceId: string;

  name: string;           // Usually original filename
  fileType: "xlsx" | "xls" | "csv" | "pdf" | "unknown";
  byteSize: number;

  status: DocumentStatus; // uploaded | processing | processed | failed | archived
  createdAt: string;      // ISO 8601 string
  updatedAt: string;
  activityAt: string;

  uploader?: UserSummary | null;
  assignee?: UserSummary | null;
  tags: string[];

  latestRun?: DocumentRunSummary | null;
  latestSuccessfulRun?: DocumentRunSummary | null;
  latestResult?: DocumentResultSummary | null;
}

export interface DocumentRunSummary {
  id: string;
  status: RunStatus;
  startedAt?: string | null;
  completedAt?: string | null;
  errorSummary?: string | null; // Optional status or error message
}

export interface DocumentResultSummary {
  attention: number;
  unmapped: number;
  pending?: boolean | null;
}
```

A more detailed `DocumentRecord` (from `DocumentOut`) can extend this when the detail endpoint returns extra metadata.

**Immutability rules**

* Uploading a “new version” of a file always yields a **new** `document.id`.
* All run APIs consume **document IDs** and never mutate or replace the underlying file.

### 2.2 Status lifecycle

`DocumentStatus` is defined centrally (e.g. in `@schema/document`) and must not be re‑declared ad‑hoc.

Conceptual meanings:

* `uploaded` – file is stored; no run yet.
* `processing` – at least one active run currently includes this document.
* `processed` – the last relevant run completed successfully.
* `failed` – the last relevant run completed with an error.
* `archived` – document is retained for history but excluded from normal interactions.

Typical transitions:

* `null` → `uploaded` when upload completes.
* `uploaded | processed | failed` → `processing` when a run starts for this document.
* `processing` → `processed` when the run succeeds.
* `processing` → `failed` when the run fails.
* Any → `archived` via explicit user action.

UI behaviour:

* The `status` field is rendered as a badge in the Documents list.
* `latestRun` is shown as a secondary indicator (e.g. “Latest run: succeeded 2 hours ago”).
* The UI **never infers** document status from run history; it only displays what the backend returns.

---

## 3. Documents screen

**Route:** `/workspaces/:workspaceId/documents`

**Responsibilities:**

1. List and filter documents within a workspace.
2. Provide upload and download actions.
3. Provide entry points for starting runs (“Run extraction”).
4. Surface last run status and other key metadata.

### 3.1 Data hooks and endpoints

Typical hooks used by the `DocumentsScreen`:

```ts
const [searchParams, setSearchParams] = useSearchParams();
const filters = parseDocumentFilters(searchParams);

const documentsQuery = useDocumentsQuery(workspaceId, filters);
const uploadMutation = useUploadDocumentMutation(workspaceId);
```

Underlying REST calls:

* `useDocumentsQuery` →
  `GET /api/v1/workspaces/{workspaceId}/documents`
* `useUploadDocumentMutation` →
  `POST /api/v1/workspaces/{workspaceId}/documents`
* `useDocumentSheetsQuery` (lazy) →
  `GET /api/v1/workspaces/{workspaceId}/documents/{documentId}/sheets`

The hooks live in the Documents feature and delegate HTTP details to shared API modules.

### 3.2 Filters, search, and sorting

Documents URL state is encoded in query parameters:

* `q` – free‑text search (name and potentially other fields).
* `status` – comma‑separated list of document statuses.
* `sort` – sort key, e.g.:

  * `-createdAt` (newest first)
  * `-latestRunAt` (most recently run first)
* `view` – optional preset (e.g. `all`, `mine`, `attention`, `recent`).

Rules:

* All filter changes must be reflected in the URL via `setSearchParams`.
* For small toggles (e.g. clicking a status pill), use `setSearchParams(..., { replace: true })` to avoid filling history with near‑duplicate entries.
* The parameter names above are **canonical** for Documents. Add or change them only via the helper functions:

  * `parseDocumentFilters(searchParams)`
  * `buildDocumentSearchParams(filters)`

This keeps deep links, docs, and components aligned.

### 3.3 Upload flow

User flow:

1. User clicks “Upload documents” or uses the shortcut (`⌘U` / `Ctrl+U`).
2. A file picker opens (and/or a drag‑and‑drop zone is available).
3. For each selected file, call `uploadMutation.mutate({ file })`.
4. While upload is in progress:

   * Show progress when feasible (per file or aggregate).
   * Avoid submitting the same selection twice.
5. On success:

   * Show a success toast (e.g. “Uploaded 3 documents”).
   * Invalidate the documents query to refresh the list.
6. On failure:

   * Show an error toast and/or an inline `Alert` using backend error text if available.

Guidelines:

* Keep the UX optimistic, but treat the documents query as the **source of truth** for final status.
* Handle duplicate file names gracefully; uniqueness is not required.

### 3.4 Row actions

Each `DocumentRow` typically provides:

* **Download**

  * Calls: `GET /api/v1/workspaces/{workspaceId}/documents/{documentId}/download`.

* **Run extraction**

  * Opens the run dialog (see §7) with this document preselected.

* **Archive/Delete**

  * Calls: `DELETE /api/v1/workspaces/{workspaceId}/documents/{documentId}`
    (usually a soft delete / archive).

Constraints:

* **Permissions** – hide or disable run actions if the user is not allowed to start runs.
* **Safe mode** – when Safe mode is active, run actions must be disabled with a clear tooltip (see §10).

---

## 4. Document sheets

For multi‑sheet spreadsheets, users can choose which worksheets to process in a run.

### 4.1 API contract

Endpoint:

```text
GET /api/v1/workspaces/{workspaceId}/documents/{documentId}/sheets
```

Expected shape:

```ts
export interface DocumentSheet {
  name: string;
  index: number;
  isActive?: boolean; // Optional “active”/default sheet signal
}
```

Error / unsupported cases:

* If the backend cannot list sheets (unsupported file type, parse error, etc.), it may:

  * Return an error, or
  * Return an empty list.
* The frontend must then fall back to **“use all sheets”** semantics.

### 4.2 Use in run dialogs

`useDocumentSheetsQuery(workspaceId, documentId)` is used:

* Lazily when a run dialog opens **and** the document looks like a spreadsheet.
* Or only when the user expands a “Worksheets” section.

UI behaviour:

* If sheets are returned:

  * Show a multi‑select checklist of worksheet names.
  * Default selection:

    * Either all sheets, or
    * Only sheets marked `isActive` when the backend provides that signal.
* If sheets cannot be loaded:

  * Show a small inline warning such as
    “Couldn’t load worksheets; running on all sheets.”
  * Omit `inputSheetNames` from the run request (backend interprets as “all sheets”).

Selected sheet names are passed to the run API as `input_sheet_names`.

---

## 5. Runs

A **Run** represents one execution of the ADE engine.

ADE Web exposes Runs from two angles:

* The **Runs ledger** – workspace‑wide history:
  UI route `/workspaces/:workspaceId/runs`, REST plural `/runs`.
* **Configuration‑scoped runs** – initiated from Configuration Builder for a specific configuration.

### 5.1 Run data model

Workspace‑level run record:

```ts
export interface RunListItem {
  runId: string;
  workspaceId: string;
  status: RunStatus;   // queued | running | succeeded | failed | cancelled

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

type RunMode = "normal" | "validation" | "test";

export interface RunOptions {
  dryRun?: boolean;
  validateOnly?: boolean;
  inputSheetNames?: string[];
  mode?: RunMode;         // View-model helper; API uses snake_case flags
}
```

A more detailed run detail view extends this with:

* Full list of input documents.
* Links to input/output downloads and event logs.
* Log / console linkage.

### 5.2 Run status

Canonical `RunStatus` values (defined centrally in `@schema`):

* `queued` – accepted, waiting to start.
* `running` – in progress.
* `succeeded` – completed successfully.
* `failed` – completed with an error.

Semantics:

* Status meanings are the same for:

  * Runs started from Documents,
  * Runs started from the Runs screen,
  * Configuration‑scoped runs from Configuration Builder.
* ADE Web **never infers** run status; it always displays what the backend reports.
* Runs are created via `/configurations/{configurationId}/runs`; once created, each run:

  * Has a globally unique `runId`.
  * Is accessible as `/api/v1/runs/{runId}`.
  * Appears in the workspace ledger.

---

## 6. Runs ledger screen

The **Runs** section is the workspace‑wide ledger of engine activity.

**Route:** `/workspaces/:workspaceId/runs`

**Responsibilities:**

1. Show all runs in a workspace.
2. Allow filtering/sorting by status, configuration, initiator, and time.
3. Provide access to logs, event history, and the normalized output.

### 6.1 Data and filters

Typical usage:

```ts
const filters = parseRunFilters(searchParams);
const runsQuery = useRunsQuery(workspaceId, filters);
// Internally calls GET /api/v1/workspaces/{workspaceId}/runs
```

URL‑encoded filters:

* `status` – comma‑separated list of `RunStatus` values.
* `configurationId` – configuration ID or version identifier.
* `initiator` – user ID or `"system"`.
* `from`, `to` – created‑at time window.

The helper functions:

* `parseRunFilters(searchParams)`
* `buildRunSearchParams(filters)`

own the query parameter contract. Add or change filters **only** through those helpers.

### 6.2 Run list UI

Each list row shows:

* Run ID (in a short display form).
* Status badge.
* Configuration name and/or version (if available).
* Input document summary (e.g. “3 documents”, with tooltip listing examples).
* Initiator (user or system).
* Created time and duration.

Row interaction:

* Clicking a row opens **Run detail** either:

  * As a dedicated route: `/workspaces/:workspaceId/runs/:runId`, or
  * As a side panel / dialog anchored to the list.

### 6.3 Run detail and logs

The Run detail view composes several sections:

* **Header**

  * Run ID, status, configuration, initiator.
  * Created / started / finished timestamps, plus computed duration.

* **Logs / console**

  * Backed by either:
    * The **job stream** (live SSE) when tailing a running job, or
    * The archived **NDJSON** log file for historical runs.
  * Rendered similarly to the Configuration Builder console (virtualized, bounded tail).

* **Outputs**

  * Event log download (NDJSON events).
  * Single normalized output file with download URL and readiness flag.

Data hooks:

* `useRunQuery(runId)` → `GET /api/v1/runs/{runId}` (global; `runId` is unique).
* `useRunOutputQuery(runId)` → `/api/v1/runs/{runId}/output`.
* `useJobLogsStream(jobId)` → `/api/v1/jobs/{jobId}/events/stream`:

  * Live-only tail (no replay/resume).
  * Uses standard SSE `event:` dispatch where each SSE message contains a JSON `EventRecord`.
  * Stream-level context is emitted once as `event: job.meta` (an `EventRecord` with identifiers in `data`).
  * Completion is indicated by `event: run.complete` (terminal worker event with status/exit info). Subprocess telemetry uses `run.engine.*`.
  * For schema details, see `apps/ade-web/docs/04-data-layer-and-backend-contracts.md` §6.

If a backend also exposes workspace‑scoped detail endpoints, we may add a `useWorkspaceRunQuery(workspaceId, runId)`; the global `useRunQuery(runId)` remains the canonical entry point.

While a run is `queued` or `running`:

* The detail view keeps the log stream open.
* The Runs list may either poll or rely on detail views to trigger data refresh.

### 6.4 “Run again” semantics

Runs are **append‑only**.

A “Run again” action in the ledger always creates a **new** run, using the previous run as a template:

* **Configuration version** – defaults to the same version as the source run (user can override).
* **Document set** – defaults to the same input documents.
* **RunOptions** – copied (including `dryRun`, `validateOnly`, `inputSheetNames`) unless the user modifies them.

This mirrors the per‑document run preference pattern: previous choices are **helpful defaults**, not authoritative configuration.

---

## 7. Starting runs

Users can start new runs from three main surfaces:

* **Documents** – “Run extraction” from a specific document row.
* **Runs** – “New run” (for multi‑document runs, if supported).
* **Configuration Builder** – “Run extraction” or “Validate configuration” against a sample document.

### 7.1 Run options in the UI

ADE Web exposes options through the `RunOptions` shape (camelCase in the UI, converted to snake_case in API payloads):

* **Dry run**

  * Label: “Dry run (don’t write outputs)”.
  * Intended for testing; the engine executes without emitting final outputs.

* **Validate only**

  * Label: “Run validators only”.
  * Skips full extraction; sets `validateOnly: true` and typically `mode: "validation"`.

* **Sheet selection**

  * Label: e.g. “Worksheets”.
  * Uses sheet metadata from §4.
  * Selected sheet names are sent as `input_sheet_names`.

* **Mode (optional view‑model helper)**

  * `mode: "normal" | "validation" | "test"`.
  * Used only within the UI to clarify intent and simplify tests.
  * Not required or consumed by the backend.

General UI rules:

* Options are grouped under an **“Advanced settings”** expander in run dialogs.
* Defaults are a product decision and can be remembered per document (see §8).
* This section is the **canonical definition** of `RunOptions`; other docs should link here instead of redefining the shape.

### 7.2 Run creation (Documents, Runs, Configuration Builder)

All run submissions target the configuration-scoped endpoint:

```text
POST /api/v1/configurations/{configurationId}/runs
```

Common payload fields:

* `input_document_ids: [...]` (usually one document from Documents; may be multiple from Runs).
* Optional `input_sheet_names`.
* Run options mapped from `RunOptions` → snake_case (`dry_run`, `validate_only`).
* `stream` flag when inline streaming is desired (Configuration Builder often sets this to `true`).

Flows:

* **Documents screen** – `RunDocumentDialog` pre-fills the selected document and preferred configuration/version/sheets. On submit, it calls the endpoint above and invalidates runs/documents queries or navigates to run detail.
* **Runs screen** – “New run” allows selecting multiple documents and a configuration, then calls the same endpoint.
* **Configuration Builder** – uses the same endpoint (typically with `stream: true`) for validation/test runs and streams events into the workbench console via:

  ```text
  GET /api/v1/runs/{runId}/events/stream
  ```

Responses include the run `id`; follow-up fetches/streams use the global run endpoints. Semantics (status transitions, options, output) are identical regardless of surface.

---

## 8. Per‑document run preferences

To streamline repeated runs, ADE Web remembers **per‑document**, **per‑workspace**, **per‑user** preferences.

### 8.1 What is persisted

For each `(workspaceId, documentId, user)` we may store:

```ts
export interface DocumentRunPreferences {
  configurationId?: string;
  configurationVersionId?: string;
  inputSheetNames?: string[];
  options?: Pick<RunOptions, "dryRun" | "validateOnly">;
  version: 1;
}
```

Notes:

* All fields are optional; missing fields fall back to defaults.

### 8.2 Storage and keying

Preferences are stored in browser `localStorage` via shared helpers (not via ad‑hoc `localStorage` calls from components).

Key pattern:

```text
ade.ui.workspace.<workspaceId>.document.<documentId>.run-preferences
```

Invariants:

* **Per workspace** – keys include `workspaceId`.
* **Per user** – scoped naturally by browser profile.
* Never contain secrets; can be safely cleared.
* Backend remains the source of truth for which configurations and versions exist.

### 8.3 Read/write strategy

**On dialog open:**

1. Load preferences using `getDocumentRunPreferences(workspaceId, documentId)`.
2. Validate referenced configuration / version:

   * If the configuration or version no longer exists, drop those fields.
3. Use remaining fields to pre‑fill:

   * Configuration
   * Configuration version
   * Sheet selection
   * Advanced options (`dryRun`, `validateOnly`)

**On successful submit:**

* After a run is submitted successfully from the Documents screen:

  * Merge the final dialog choices into `DocumentRunPreferences`.
  * Save via `setDocumentRunPreferences(...)`.

**Resetting:**

* The run dialog may offer “Reset to defaults”, which:

  * Removes the `run-preferences` entry for that document.
  * Causes the next open to use system defaults only.

Implementation detail:

* All of this logic should live in a small shared module (e.g. `shared/runPreferences.ts`) and a feature hook such as `useDocumentRunPreferences`, so:

  * Key patterns,
  * Versioning,
  * Migration

can be updated in one place.

---

## 9. Backend contracts (summary)

The Documents and Runs features rely on the following backend endpoints. Detailed typings and error semantics live in `04-data-layer-and-backend-contracts.md`.

### 9.1 Documents

* `GET /api/v1/workspaces/{workspaceId}/documents`
  List documents (supports `q`, `sort`, `filters`).

* `POST /api/v1/workspaces/{workspaceId}/documents`
  Upload a new document.

* `GET /api/v1/workspaces/{workspaceId}/documents/{documentId}`
  Retrieve document metadata.

* `DELETE /api/v1/workspaces/{workspaceId}/documents/{documentId}`
  Soft delete / archive a document.

* `GET /api/v1/workspaces/{workspaceId}/documents/{documentId}/download`
  Download the original file.

* `GET /api/v1/workspaces/{workspaceId}/documents/{documentId}/sheets`
  List worksheets (for spreadsheet‑like formats; optional).

### 9.2 Workspace runs (ledger)

* `GET /api/v1/workspaces/{workspaceId}/runs`
  List runs in a workspace (filters by status, configuration, initiator, date).

### 9.3 Run detail & artifacts (global)

* `GET /api/v1/runs/{runId}`
  Global run detail.

* `GET /api/v1/runs/{runId}/events/stream`
  Run event stream (NDJSON SSE); `GET /runs/{runId}/events/download` downloads the NDJSON log.

* `GET /api/v1/runs/{runId}/input`
  Input metadata (document, content type, byte size).

* `GET /api/v1/runs/{runId}/input/download`
  Download the original input file.

* `GET /api/v1/runs/{runId}/output`
  Output metadata (ready flag, size, content type, download URL).

* `GET /api/v1/runs/{runId}/output/download`
  Download the normalized output (returns 409 until ready).

### 9.4 Run creation (configuration-scoped)

* `POST /api/v1/configurations/{configurationId}/runs`
  Start a run for a configuration (used by Documents, Runs, and Configuration Builder surfaces).

All run endpoints share consistent `RunStatus` values and event semantics.

---

## 10. Safe mode interactions

Safe mode (see `05-auth-session-rbac-and-safe-mode.md`) is a kill switch for engine execution.

When **Safe mode is enabled**:

* Run‑creating actions are disabled:

  * Run dialogs cannot be submitted.
  * “Run extraction” buttons on Documents are disabled.
  * Any “New run” actions on the Runs screen are disabled.

* Read‑only operations remain available:

  * Listing documents and runs.
  * Viewing run details.
* Downloading outputs and event logs.

UI behaviour:

* The workspace shell shows a Safe mode banner.
* Disabled controls show a tooltip, e.g.:

  > “Safe mode is enabled: <backend message>”

The backend always enforces Safe mode; UI disabling is a convenience to avoid surprising errors.

---

## 11. Design invariants

To keep Documents and Runs predictable (for both humans and agents), ADE Web relies on a few invariants:

1. **Document status comes from the backend.**
   The UI never derives `DocumentStatus` from run history; it only displays what the backend reports.

2. **Run semantics are consistent everywhere.**
   `RunStatus`, `RunOptions` (`dryRun`, `validateOnly`, `inputSheetNames`, `mode`), and timestamps mean the same thing in:

   * Document `latestRun` summaries,
   * The Runs ledger,
   * Configuration‑scoped runs.

3. **Runs are append‑only.**
   Runs are created, progress, and complete; they are not edited afterward.
   “Run again” always creates a new run using the previous run’s configuration, document set, and run options unless the user explicitly changes them.

4. **Per‑document run preferences are hints, not configuration.**
   Preferences only influence UI defaults. If configurations or versions disappear or become invalid, those preferences are ignored.

5. **Safe mode always wins.**
   When Safe mode is on, the UI must not attempt to create new runs, and the backend must reject any such requests.

As long as these invariants hold, Documents and Runs remain easy to reason about, and the mapping between frontend behaviour and backend APIs stays straightforward.
