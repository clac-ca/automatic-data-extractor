# 07 – Documents, jobs, and runs

This document describes how ADE Web models **documents** and **jobs**, how users start and monitor processing, and how these concepts map to backend APIs and frontend components.

It is written for implementers. For terminology and canonical naming, see **01‑domain‑model‑and‑naming.md**.

---

## 1. Scope and goals

This doc covers:

- The **data model and lifecycle** for documents and jobs.
- The UX and component structure of the **Documents** and **Jobs** sections.
- How users **run extraction** for one or more documents, including options.
- How we **remember run preferences** per document.
- The relevant **backend endpoints** and how they are consumed in the frontend.

It intentionally does **not** cover:

- Configuration/version lifecycle (see **08‑configurations‑and‑config‑builder.md**).
- The Config Builder workbench (see **09‑workbench‑editor‑and‑scripting.md**).

---

## 2. Concepts and relationships

At a high level:

- A **document** is an immutable uploaded input file (Excel, CSV, PDF, …) that belongs to a **workspace**.
- A **job** is a workspace‑scoped execution of ADE against one or more documents using a specific **config version** and set of **run options**.
- Each job may internally correspond to one or more **engine runs** in the backend. ADE Web treats these as implementation details and exposes **jobs** as the primary user‑facing concept.

The primary relationships:

- A **workspace** owns many **documents**.
- A **workspace** owns many **jobs**.
- A **job** references:
  - One workspace,
  - One config (and a specific version),
  - One or more input documents (by ID),
  - Run‑time options (dry‑run, validate‑only, worksheet selection, …).

---

## 3. Documents

### 3.1 Document data model

A document is an immutable input owned by a workspace.

**Key fields (frontend model):**

```ts
export interface DocumentSummary {
  id: string;
  workspaceId: string;
  name: string;              // usually original filename
  contentType: string;       // e.g. "application/vnd.ms-excel"
  sizeBytes: number;
  status: DocumentStatus;    // see below
  createdAt: string;         // ISO timestamp
  uploadedBy: UserSummary;
  lastJob?: {
    id: string;
    status: JobStatus;
    finishedAt?: string;
    summary?: string | null;
  };
}
````

We keep a separate `DocumentDetail` type if the detail endpoint exposes additional metadata. The UI primarily uses `DocumentSummary` in list views.

### 3.2 Document status lifecycle

`DocumentStatus` is defined centrally (see doc 01). ADE Web relies on the backend to calculate it, but the UI assumes:

* `uploaded` – file is stored; no job has started.
* `processing` – at least one job is currently running for this document.
* `processed` – the last job completed successfully.
* `failed` – the last job completed with an error.
* `archived` – the document is retained for history but not shown in normal flows.

Typical transitions:

* New upload → `uploaded`.
* User starts a job → `processing`.
* Job succeeds → `processed`.
* Job fails → `failed`.
* Document archived via explicit action → `archived`.

The **Documents** screen never mutates `status` directly; it refetches document data after relevant operations (upload, job completion, archive).

### 3.3 Documents screen

**Location:** `features/workspace-shell/documents/`

**Primary components:**

* `DocumentsScreen` – route container for `/workspaces/:workspaceId/documents`.
* `DocumentsToolbar` – search box, filters, upload button.
* `DocumentsTable` – paginated list of documents.
* `DocumentRow` – row rendering for a single document.
* `DocumentActions` – per‑row actions (run extraction, download, archive).

**Data flow:**

* Query params:

  * `q`: search string (name, maybe source metadata).
  * `status`: comma‑separated filter.
  * `sort`: sort key (e.g. `-created_at`, `-last_job_at`).
  * `view`: preset (e.g. `all`, `mine`, `attention`, `recent`).

* Hook:

  ```ts
  const { data, isLoading, error } = useDocumentsQuery(workspaceId, { q, status, sort, view });
  ```

* Backend:

  * Maps onto `GET /api/v1/workspaces/{workspace_id}/documents` with corresponding query params.

**UX behaviour:**

* Search is debounced; changing filters updates the URL via `useSearchParams`.
* Status pills / filters are mirrored in the URL for shareability.
* Clicking a row:

  * Either opens a document detail view (if you have one), or
  * Brings up a contextual “Run extraction” dialog prefilled with this document.

### 3.4 Document upload

Uploading is considered an operation within the Documents section.

**Trigger:**

* Toolbar “Upload” button.
* Keyboard shortcut: `⌘U` / `Ctrl+U` when Documents screen is active.

**Flow:**

1. User selects file(s) via file picker or drag‑and‑drop.

2. ADE Web calls:

   ```ts
   useUploadDocumentMutation(workspaceId)
   // -> POST /api/v1/workspaces/{workspace_id}/documents
   ```

3. On success:

   * UI shows a success toast (“Uploaded 3 documents”).
   * Documents query is invalidated/refetched.
   * Newly uploaded documents appear with `status: uploaded`.

4. On error:

   * Error toast and inline `Alert` in upload dialog/dropzone.
   * The error message from the backend is surfaced verbatim where appropriate.

Uploads are **synchronous** from the UI’s perspective; we do not currently implement resumable uploads.

### 3.5 Document sheets

For multi‑sheet spreadsheets, ADE Web surfaces sheet information where relevant (e.g. run dialogs).

**Backend contract:**

* `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/sheets` returns:

  ```ts
  export interface DocumentSheet {
    name: string;
    index: number;
    isActive: boolean;
  }
  ```

**Frontend usage:**

* Hook: `useDocumentSheetsQuery(workspaceId, documentId)`.
* Used in:

  * **Run extraction** dialogs (Documents screen & Config Builder).
  * Any document detail page that needs to preview which sheets exist.

**Behaviour:**

* If sheets endpoint succeeds:

  * Dialog shows a list of worksheets with checkboxes.
  * Default selection is:

    * `isActive` sheet(s) if flagged, or
    * All sheets if none are flagged.

* If sheets endpoint fails or is unavailable:

  * Show a non‑blocking warning (inline `Alert`).
  * Provide a simple “Use all worksheets” option.
  * The run request omits `input_sheet_names`, leaving selection to the backend.

ADE Web never attempts to interpret sheet content; it only displays metadata and sends sheet names to the backend as requested.

---

## 4. Jobs and engine runs

In the UI, **jobs** are the primary unit of work. The backend may expose “runs” as a lower‑level concept; ADE Web hides that complexity unless explicitly needed.

### 4.1 Job data model

**Key fields (frontend model):**

```ts
export interface JobSummary {
  id: string;
  workspaceId: string;
  status: JobStatus;            // queued | running | succeeded | failed | cancelled
  createdAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;

  initiator: UserSummary | SystemInitiator;
  configurationId: string;
  configurationName: string;
  configurationVersion: string; // stable identifier/tag

  inputDocuments: {
    count: number;
    examples: Array<{ id: string; name: string }>;
  };

  options: {
    dryRun?: boolean;
    validateOnly?: boolean;
    inputSheetNames?: string[] | null;
  };

  summary?: string | null;      // human-readable summary, if provided
  errorMessage?: string | null;
}
```

A `JobDetail` type extends this with log/telemetry/outputs references.

### 4.2 Job lifecycle

`JobStatus` is defined centrally (see doc 01):

* `queued` – request accepted, waiting to start.
* `running` – job is actively processing.
* `succeeded` – job completed successfully.
* `failed` – job completed with an error.
* `cancelled` – job ended early by user/system.

Status transitions are entirely driven by the backend. ADE Web receives them via:

* Polling of job detail.
* Or NDJSON event streams (see below).

The frontend maps these statuses to:

* Visual badges (colour + label).
* Filter pills on the Jobs screen.

### 4.3 Jobs screen

**Location:** `features/workspace-shell/jobs/`

**Primary components:**

* `JobsScreen` – route container for `/workspaces/:workspaceId/jobs`.
* `JobsFilters` – status/config/initiator/date filters.
* `JobsTable` – paginated list of jobs.
* `JobRow` – single job row.
* `JobStatusBadge` – consistent status rendering.

**Data flow:**

* Query params (typical):

  * `status`: comma‑separated job statuses.
  * `config`: filter by configuration id/version.
  * `initiator`: filter by user id or “system”.
  * `from`, `to`: date range.

* Hook:

  ```ts
  const { data, isLoading, error } = useJobsQuery(workspaceId, filters);
  ```

* Backend:

  * `GET /api/v1/workspaces/{workspace_id}/jobs`.

**UX behaviour:**

* Clicking a row opens a job detail view:

  * Either a full screen route (e.g. `/workspaces/:id/jobs/:jobId`), or
  * A drawer/modal overlay.

* From the job detail, users can:

  * Download artifacts and outputs.
  * Inspect logs and telemetry.
  * Navigate back to a related document or configuration.

### 4.4 Job detail and logs

**Backend endpoints:**

* `GET /api/v1/workspaces/{workspace_id}/jobs/{job_id}` – job metadata.
* `GET /api/v1/workspaces/{workspace_id}/jobs/{job_id}/artifact` – combined outputs.
* `GET /api/v1/workspaces/{workspace_id}/jobs/{job_id}/outputs` – list of output files.
* `GET /api/v1/workspaces/{workspace_id}/jobs/{job_id}/outputs/{output_path}` – single file download.
* `GET /api/v1/workspaces/{workspace_id}/jobs/{job_id}/logs` – log file download or NDJSON stream, depending on implementation.

**Frontend structure:**

* `JobDetailPanel` (or screen) composes:

  * A **summary header** (job id, status, config, initiator, document info).
  * A **logs/console** panel (if streaming or showing text logs).
  * An **outputs** panel (artifact + individual outputs).
  * A **telemetry** summary (rows processed, warnings, etc.), when available.

**Streaming vs file download:**

* Where the backend exposes NDJSON logs (recommended), ADE Web uses a `useJobLogStream` hook that:

  * Connects to the logs endpoint.
  * Parses events line‑by‑line.
  * Updates incremental console output.

* Where only a static log file download is available, ADE Web:

  * Shows a “Download logs” button.
  * Optionally offers a “View logs inline” mode by fetching and rendering the file client‑side.

The important point: the Jobs UI is designed to accommodate both streaming and non‑streaming backends via a thin abstraction in `shared/ndjson` or `shared/logs`.

---

## 5. Running extraction from a document

Jobs can be created from multiple entry points. The most common is “Run extraction” for a specific document.

### 5.1 Run extraction dialog (Documents)

From the **Documents** screen:

1. User clicks “Run extraction” on a document row.

2. ADE Web opens a `RunExtractionDialog` with:

   * The current workspace and selected document prefilled.
   * A configuration selector (with active config/version default).
   * An optional worksheet selector (for spreadsheets).
   * Advanced options (dry run, validate only).

3. On “Run job”:

   * ADE Web constructs a `JobCreateRequest`.
   * Safe mode is checked before and during submit (buttons disabled with tooltip if enabled).
   * A job is created via backend (see below).
   * The dialog closes and:

     * Either navigates to the job detail view, or
     * Shows a toast with a link to the job.

### 5.2 Run options

Run options are driven by backend capabilities, but the frontend standardises them as:

```ts
export interface JobRunOptions {
  dryRun?: boolean;
  validateOnly?: boolean;
  inputSheetNames?: string[];   // subset of sheets from /sheets endpoint
}
```

UI rules:

* **Dry run:**

  * Labelled clearly (“Dry run – don’t write final outputs”).
  * Only shown if supported by backend / configuration.

* **Validate only:**

  * “Run validators only” checkbox or similar.
  * Mutually exclusive with some other options if the backend requires it.

* **Input sheet names:**

  * Multi‑select of available sheets.
  * Omitted from request if “all sheets” are selected.

### 5.3 Backend interaction

There are two relevant job‑creation endpoints in the API:

* **Workspace jobs:**

  * `POST /api/v1/workspaces/{workspace_id}/jobs` (`submit_job_endpoint`).
  * Best for general user‑triggered jobs from Documents screen.

* **Config‑scoped runs:**

  * `POST /api/v1/configs/{config_id}/runs` (`create_run_endpoint`).
  * Used by Config Builder for test runs / validation runs scoped to a config.

ADE Web uses:

* `/workspaces/{workspace_id}/jobs` for **normal operational jobs** (Documents and Jobs screens).
* `/configs/{config_id}/runs` for **Config Builder test runs** (see doc 09).

A typical workspace job request looks like:

```json
{
  "configuration_id": "cfg_123",
  "configuration_version": "v2024.05.01",
  "input_document_ids": ["doc_abc"],
  "dry_run": false,
  "validate_only": false,
  "input_sheet_names": ["Sheet1", "Sheet2"]
}
```

The response returns a `job_id` which is used to:

* Link to `/workspaces/:workspaceId/jobs` (filtered to that job), and/or
* Subscribe to its logs.

---

## 6. Per‑document run preferences

To make repeated runs smoother, ADE Web remembers user preferences **per document, per workspace**.

### 6.1 What we store

For each document, we remember:

* **Preferred configuration**:

  * `configurationId`
  * `configurationVersion` (when explicitly selected)

* **Preferred sheet subset**:

  * `inputSheetNames` used in the last successful run started from the Documents screen.

* **Optional run options** (if you decide to persist them):

  * `dryRun`, `validateOnly`.

### 6.2 Storage and keying

Preferences are stored in localStorage via a shared helper, never via direct `window.localStorage` calls inside features.

Key pattern:

```text
ade.ui.workspace.<workspaceId>.document.<documentId>.run-preferences
```

Value shape (JSON):

```ts
interface DocumentRunPreferences {
  configurationId?: string;
  configurationVersion?: string;
  inputSheetNames?: string[];
  dryRun?: boolean;
  validateOnly?: boolean;
  // version field reserved for future migrations
  version: 1;
}
```

### 6.3 Behaviour

* On opening a **Run extraction** dialog:

  * ADE Web reads preferences (if present).
  * Valid configuration and version IDs are resolved against current configuration list.
  * If a referenced config/version no longer exists, the preference is ignored (and optionally cleared).

* On submitting a job from the dialog:

  * Preferences are updated with the latest choices.

* Reset:

  * The dialog may include “Reset to defaults”, which clears the stored preferences for that document.

Preferences are purely **client‑side**; clearing browser storage must not affect backend behaviour.

---

## 7. Backend contracts (summary)

This section summarises the backend routes ADE Web expects for documents and jobs. For full detail, see **04‑data‑layer‑and‑backend‑contracts.md**.

### 7.1 Documents

* `GET /api/v1/workspaces/{workspace_id}/documents`

  * Filters: `q`, `status`, `sort`, `view` (implementation‑defined).
  * Returns `DocumentSummary[]`.

* `POST /api/v1/workspaces/{workspace_id}/documents`

  * Multipart upload.
  * Returns created `Document` metadata.

* `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}`

  * Returns `DocumentDetail`.

* `DELETE /api/v1/workspaces/{workspace_id}/documents/{document_id}`

  * Soft delete / archive.

* `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/download`

  * Raw file download.

* `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/sheets`

  * Sheet metadata (name, index, `is_active`).

### 7.2 Jobs and runs

* `GET /api/v1/workspaces/{workspace_id}/jobs`

  * Jobs ledger, filterable by status, config, date, initiator.

* `POST /api/v1/workspaces/{workspace_id}/jobs`

  * Submit general jobs (documents + config version + options).

* `GET /api/v1/workspaces/{workspace_id}/jobs/{job_id}`

  * Job detail.

* `GET /api/v1/workspaces/{workspace_id}/jobs/{job_id}/artifact`

  * Combined outputs (e.g. zip).

* `GET /api/v1/workspaces/{workspace_id}/jobs/{job_id}/outputs`

  * List of individual outputs.

* `GET /api/v1/workspaces/{workspace_id}/jobs/{job_id}/outputs/{output_path}`

  * Download individual output.

* `GET /api/v1/workspaces/{workspace_id}/jobs/{job_id}/logs`

  * Log download or NDJSON stream.

* `POST /api/v1/configs/{config_id}/runs`

  * Config‑scoped runs; used by Config Builder for test/validate runs.

* `GET /api/v1/runs/{run_id}` / `.../logs` / `.../outputs` (if utilized)

  * Low‑level run detail/logs; ADE Web treats these as implementation details behind jobs/config runs.

---

## 8. Safe mode interactions

Safe mode (see **05‑auth‑session‑rbac‑and‑safe‑mode.md**) affects the Documents and Jobs workflows:

* When `safeMode.enabled === true`:

  * **Blocked actions:**

    * “Run extraction” buttons on the Documents screen.
    * “Run job” submit in run dialogs.
    * Any restart job / rerun actions (if implemented).

  * **Allowed actions:**

    * Uploading documents (if you choose to allow it).
    * Viewing documents and jobs.
    * Downloading outputs and logs.

* UX:

  * A workspace‑level safe mode banner is visible in the shell.
  * Actions are disabled rather than hidden, with tooltips:

    > “Safe mode is enabled: <detail from backend>”

Implementation detail:

* The feature layer checks safe mode via a shared hook (`useSafeModeStatus`) and uses that to disable controls and/or show banners.
* Safe mode is also enforced server‑side; UI disabling is purely to avoid surprise.

---

## 9. Implementation notes and extension points

A few “architectural” decisions to keep in mind:

* The **Documents** and **Jobs** sections are deliberately **thin**:

  * Most data‑fetching logic lives in `shared/` API hooks.
  * The screens focus on wiring URL state + UI components to those hooks.

* Jobs are the **only user‑facing execution primitive**:

  * “Run” is treated as a verb in UI copy (“Run job”, “Run extraction”).
  * The `runs` API is used behind the scenes (Config Builder) but not surfaced as a separate domain in the UI.

* Per‑document run preferences are strictly **per user** and **per workspace**:

  * They should never leak across users.
  * They should be safe to clear at any time.

* The design allows future extension:

  * **Bulk jobs:** multiple documents selected → single job request with `input_document_ids` array.
  * **Job cancellation:** adding a “Cancel job” action that calls a future `/jobs/{job_id}/cancel` endpoint.
  * **Saved queries:** extend Documents/Jobs filters to support named filter presets.

When adding new features touching documents/jobs, ensure:

* Status enums and domain names are updated in **01‑domain‑model‑and‑naming.md**.
* New endpoints are mapped in **04‑data‑layer‑and‑backend‑contracts.md**.
* Any additional persisted preferences follow the existing key‑naming scheme (see section 6.2 and doc 10).