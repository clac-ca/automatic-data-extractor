# 140-RUNS-AND-OUTPUTS.md  
**ADE Web – Runs, Outputs, Logs & Summaries**

---

## 0. Purpose

This document defines how the new `apps/ade-web` should integrate with the **run**-related API surface, based on `openapi.d.ts`:

- Core run resource (`RunResource`)
- Run creation (`RunCreateRequest` + `RunCreateOptions`)
- Listing runs (`RunPage`)
- Events (`/runs/{run_id}/events`) – complements `050-RUN-STREAMING-SPEC.md`
- Logs & log files
- Outputs & output files
- Run summaries (table/validation metrics)

This is the source of truth for **how the frontend talks to the run APIs**. If backend types or routes change, update this doc first.

Related docs:

- `050-RUN-STREAMING-SPEC.md` – streaming mechanics (SSE/NDJSON).
- `130-DOCUMENTS.md` – documents & their linkage to runs.
- `150-CONFIGURATIONS-API.md` – configs & builds.
- `030-UX-FLOWS.md` – UX flows for Run Detail, Documents, Config Builder.

---

## 1. Run Model (from OpenAPI)

### 1.1 `RunResource` – core run instance

```ts
/**
 * RunResource
 * @description API representation of a persisted ADE run.
 */
RunResource: {
  id: string;                    // ULID
  object: "ade.run";             // constant
  workspace_id: string;
  configuration_id: string;

  // Status (lifecycle)
  status: "queued" | "running" | "succeeded" | "failed" | "canceled";
  failure_code?: string | null;
  failure_stage?: string | null;
  failure_message?: string | null;

  // Timing & lifecycle
  created_at: string;            // date-time
  started_at?: string | null;    // date-time | null
  completed_at?: string | null;  // date-time | null
  duration_seconds?: number | null;
  exit_code?: number | null;

  // Input & output metadata
  input?: RunInput;
  output?: RunOutput;

  // Hypermedia links
  links: RunLinks;
};
````

Supporting types:

```ts
RunStatus: "queued" | "running" | "succeeded" | "failed" | "canceled";

/**
 * RunInput
 * @description Input metadata captured for a run.
 */
RunInput: {
  document_ids?: string[];
  input_sheet_names?: string[];
  input_file_count?: number | null;
  input_sheet_count?: number | null;
};

/**
 * RunOutput
 * @description Output metadata captured for a run.
 */
RunOutput: {
  has_outputs: boolean;
  output_count: number;
  processed_files?: string[];
};

/**
 * RunLinks
 * @description Hypermedia links for run-related resources.
 */
RunLinks: {
  self: string;
  summary: string;
  events: string;
  logs: string;
  logfile: string;
  outputs: string;
};
```

#### UI usage

* **Run cards / tables** (Workspace Runs, Document history, Config Builder run panel):

  * Status pill from `status`.
  * Duration from `duration_seconds` or derived from started/completed.
  * Link to Run Detail via `links.self` or `/runs/:id` route.
  * For Document-centric views (see `130-DOCUMENTS.md`):

    * Use `input.document_ids`, `input.input_sheet_names` to show which document(s)/sheet(s) were used.
* **Run Detail header:**

  * Run ID, status, configuration, created/started/completed.
  * Failure stage/message if `status = "failed"`.

---

### 1.2 Run creation (`RunCreateRequest` & `RunCreateOptions`)

```ts
/**
 * RunCreateRequest
 * @description Payload accepted by the run creation endpoint.
 */
RunCreateRequest: {
  /**
   * Stream
   * @default false
   */
  stream: boolean;
  options?: RunCreateOptions;
};

/**
 * RunCreateOptions
 * @description Optional execution toggles for ADE runs.
 */
RunCreateOptions: {
  // Execution toggles
  dry_run: boolean;
  validate_only: boolean;
  force_rebuild: boolean;

  // Documents & sheets
  document_ids?: string[] | null;
  /** @deprecated single document id */
  input_document_id?: string | null;
  input_sheet_name?: string | null;
  input_sheet_names?: string[] | null;

  /**
   * Metadata
   * @description Opaque metadata to propagate with run telemetry.
   */
  metadata?: { [key: string]: string };
};
```

**Best practices:**

* Always call run creation with **`stream: true`** when you intend to attach live SSE (`useRunStream`).
* Use **`document_ids`** for input documents (not `input_document_id`).
* Use **`input_sheet_names`** (plural) with `DocumentSheet.name` for sheet selection (avoid `input_sheet_name`).
* Only set `dry_run` / `validate_only` from explicit UX choices (don’t silently change behavior).

---

### 1.3 Logs & log entries

```ts
/**
 * RunLogEntry
 * @description Single run log entry returned by the logs endpoint.
 */
RunLogEntry: {
  id: number;
  created: number;                 // likely epoch millis
  stream: "stdout" | "stderr";
  message: string;
};

/**
 * RunLogsResponse
 * @description Envelope for run log fetch responses.
 */
RunLogsResponse: {
  run_id: string;
  object: "ade.run.logs";
  entries: RunLogEntry[];
  next_after_id?: number | null;
};
```

Used by `GET /runs/{run_id}/logs`.

---

### 1.4 Outputs & output files

```ts
/**
 * RunOutputFile
 * @description Single file emitted by a streaming run output directory.
 */
RunOutputFile: {
  name: string;
  kind?: string | null;
  content_type?: string | null;
  byte_size: number;
  download_url?: string | null;
};

/**
 * RunOutputListing
 * @description Collection of files produced by a streaming run.
 */
RunOutputListing: {
  files?: RunOutputFile[];
};
```

Used by `GET /runs/{run_id}/outputs`.

---

### 1.5 Run summaries (`RunSummaryV1`)

```ts
/**
 * RunSummaryV1
 * @description Top-level run summary schema (v1).
 */
RunSummaryV1: {
  schema: "ade.run_summary/v1";      // constant
  version: string;                   // "1.0.0" etc
  run: RunSummaryRun;
  core: RunSummaryCore;
  breakdowns: RunSummaryBreakdowns;
};

RunSummaryRun: {
  id: string;
  workspace_id?: string | null;
  configuration_id?: string | null;
  configuration_version?: string | null;
  status: "succeeded" | "failed" | "canceled";
  failure_code?: string | null;
  failure_stage?: string | null;
  failure_message?: string | null;
  engine_version?: string | null;
  config_version?: string | null;
  env_reason?: string | null;
  env_reused?: boolean | null;
  started_at: string;
  completed_at?: string | null;
  duration_seconds?: number | null;
};

RunSummaryCore: {
  input_file_count: number;
  input_sheet_count: number;
  table_count: number;
  row_count?: number | null;
  canonical_field_count: number;
  required_field_count: number;
  mapped_field_count: number;
  unmapped_column_count: number;
  validation_issue_count_total: number;
  issue_counts_by_severity?: { [severity: string]: number };
  issue_counts_by_code?: { [code: string]: number };
};

RunSummaryBreakdowns: {
  by_file?: RunSummaryByFile[];
  by_field?: RunSummaryByField[];
};

RunSummaryByFile: {
  source_file: string;
  table_count: number;
  row_count?: number | null;
  validation_issue_count_total: number;
  issue_counts_by_severity?: { [severity: string]: number };
  issue_counts_by_code?: { [code: string]: number };
};

RunSummaryByField: {
  field: string;
  label?: string | null;
  required: boolean;
  mapped: boolean;
  max_score?: number | null;
  validation_issue_count_total: number;
  issue_counts_by_severity?: { [severity: string]: number };
  issue_counts_by_code?: { [code: string]: number };
};
```

**UI usage in Run Detail / Config Builder:**

* **Top summary bar**:

  * Status (from `run.status`).
  * Duration, engine version, config version.
* **Core metrics** tiles:

  * Input files/sheets, tables, rows.
  * Required vs mapped fields; unmapped column count.
  * Overall validation issues.
* **Per-file summary**:

  * Show list of source files with table/row counts & issue counts.
* **Per-field summary**:

  * Show canonical fields, whether required & mapped.
  * Visualize validation severity distribution.

Run Summary is fetched via `GET /runs/{run_id}/summary`.

---

## 2. Run Endpoints

### 2.1 Get run

**Path:** `GET /api/v1/runs/{run_id}`
**Op:** `get_run_endpoint_api_v1_runs__run_id__get`

* Parameters:

  * `path.run_id: string`
* Response:

  * `200: RunResource`
  * `404: not found` (implicit via validation/HTTPError)

**Wrapper:**

```ts
getRun(runId: string): Promise<RunResource>;
```

Used:

* On Run Detail load.
* For quick “status card” refreshes where we don’t need full summary.

---

### 2.2 Get run events (streaming / replay)

**Path:** `GET /api/v1/runs/{run_id}/events`
**Op:** `get_run_events_endpoint_api_v1_runs__run_id__events_get`

Parameters:

```ts
query?: {
  format?: "json" | "ndjson";
  stream?: boolean;
  after_sequence?: number | null;
  limit?: number;
};
path: { run_id: string };
```

See `050-RUN-STREAMING-SPEC.md` for **exact streaming semantics**:

* SSE: `stream=true`, `format=json` (or default).
* Replay: `stream=false`, `limit` and `after_sequence` used for pagination.
* NDJSON: `format="ndjson"` for bulk fetch; typically used via `fetchRunTelemetry` / `useRunTelemetry`.

Front-end must **not** use ad-hoc EventSource logic outside the shared streaming primitives.

---

### 2.3 Get structured logs

**Path:** `GET /api/v1/runs/{run_id}/logs`
**Op:** `get_run_logs_endpoint_api_v1_runs__run_id__logs_get`

Parameters:

```ts
query?: {
  after_id?: number | null;
  limit?: number;
};
path: { run_id: string };
```

Response:

* `200: RunLogsResponse` (includes `entries: RunLogEntry[]` + `next_after_id`)

**Wrapper:**

```ts
getRunLogs(runId: string, params?: {
  afterId?: number | null;
  limit?: number;
}): Promise<RunLogsResponse>;
```

Frontend usage:

* Optional **“Structured logs”** tab in Run Detail.
* Might be used to backfill the console if we want non-streaming log retrieval.

---

### 2.4 Download log file

**Path:** `GET /api/v1/runs/{run_id}/logfile`
**Op:** `download_run_logs_file_endpoint_api_v1_runs__run_id__logfile_get`

* Response:

  * `200`: file payload (generator marks content as none; treat as file/blob).
  * `404`: logs unavailable.

**Wrapper:**

```ts
downloadRunLogfile(runId: string): Promise<Blob | void>;
```

UI:

* “Download logs” button in Run Detail (and potentially Document detail → last run).
* Fallback when structured logs / console view is not enough.

---

### 2.5 List outputs

**Path:** `GET /api/v1/runs/{run_id}/outputs`
**Op:** `list_run_outputs_endpoint_api_v1_runs__run_id__outputs_get`

* Response:

  * `200: RunOutputListing`
  * `404`: outputs unavailable

**Wrapper:**

```ts
listRunOutputs(runId: string): Promise<RunOutputListing>;
```

UI:

* “Outputs” panel in Run Detail:

  * Table of `RunOutputFile` entries with name, type, size.
  * Download action per file (uses download endpoint below).
* Document detail “Downloads” section (see `130-DOCUMENTS.md`):

  * For last run, reuse this listing.

---

### 2.6 Download specific output file

**Path:** `GET /api/v1/runs/{run_id}/outputs/{output_path}`
**Op:** `download_run_output_endpoint_api_v1_runs__run_id__outputs__output_path__get`

Parameters:

```ts
path: {
  run_id: string;
  output_path: string;
};
```

* Response:

  * `200`: file payload
  * `404`: not found

**Wrapper:**

```ts
downloadRunOutput(runId: string, outputPath: string): Promise<Blob | void>;
```

UI:

* Bound to each row in the Outputs list.
* Use `RunOutputFile.download_url` if provided; otherwise build URL using route.

---

### 2.7 Get run summary

**Path:** `GET /api/v1/runs/{run_id}/summary`
**Op:** `get_run_summary_endpoint_api_v1_runs__run_id__summary_get`

* Response:

  * `200: RunSummaryV1`
  * `404`: summary not found

**Wrapper:**

```ts
getRunSummary(runId: string): Promise<RunSummaryV1>;
```

UI:

* Drives **RunSummaryPanel** and per‑file/per‑field breakdown components.
* Also used in Config Builder’s run panel to show key metrics alongside console.

---

### 2.8 List workspace runs

**Path:** `GET /api/v1/workspaces/{workspace_id}/runs`
**Op:** `list_workspace_runs_endpoint_api_v1_workspaces__workspace_id__runs_get`

Parameters:

```ts
query?: {
  page?: number;
  page_size?: number;
  include_total?: boolean;
  input_document_id?: string | null;
};
path: { workspace_id: string };
requestBody?: {
  "application/json": ("queued" | "running" | "succeeded" | "failed" | "canceled")[] | null;
};
```

Response:

* `200: RunPage` (`items: RunResource[]`)

**Wrapper:**

```ts
listWorkspaceRuns(
  workspaceId: string,
  options?: {
    page?: number;
    pageSize?: number;
    includeTotal?: boolean;
    inputDocumentId?: string | null;
    statuses?: RunStatus[] | null;
  }
): Promise<RunPage>;
```

Usage:

* **Workspace “Recent runs”** section on home screen.
* **Document history**:

  * Call with `input_document_id = documentId` to show runs for that document.
* Optional filters:

  * Status multi-select that maps to request body.

---

### 2.9 Create run (from configuration)

**Path:** `POST /api/v1/configurations/{configuration_id}/runs`
**Op:** `create_run_endpoint_api_v1_configurations__configuration_id__runs_post`

Parameters:

```ts
path: { configuration_id: string };
requestBody: { "application/json": RunCreateRequest };
```

Response:

* `201: RunResource`

**Wrapper:**

```ts
createRun(configurationId: string, req: RunCreateRequest): Promise<RunResource>;
```

Frontend usage:

* **Config Builder**:

  * “Run” and “Validate” actions:

    * Build correct `RunCreateOptions` from UI (dry_run, validate_only, force_rebuild).
    * For “run from document” inside Config Builder, also set `document_ids` & `input_sheet_names` if appropriate.
  * Immediately feed `run.id` into `useRunStream(run.id)` for live updates.
* **Documents → Run with config**:

  * When a document user selects a config to run:

    * Use this endpoint to create the run with `document_ids: [doc.id]`.

---

## 3. Frontend Abstractions

Under `features/runs/api`:

```ts
// Read patterns
getRun
getRunSummary
getRunLogs
listRunOutputs
listWorkspaceRuns

// Mutations
createRun

// Downloads
downloadRunLogfile
downloadRunOutput
```

Under `features/runs/hooks`:

* `useRun(runId)`
* `useRunSummary(runId)`
* `useRunOutputs(runId)`
* `useWorkspaceRuns(workspaceId, options)`
* `useCreateRun(configurationId)` – mutation that:

  * Creates run (with `stream: true`).
  * Connects streaming (`useRunStream`).
  * Integrates with Config Builder or Documents as needed.

**Important:** All these wrappers should use **generated OpenAPI types** from `openapi.d.ts` (re-exported via `schema/`) – no hand‑rolled run types.

---

## 4. Definition of Done – Runs & Outputs

Runs are “sufficiently integrated” when:

1. All endpoints in this doc are wrapped in a clearly named API module and used via React Query hooks.
2. Run Detail screen can:

   * Load `RunResource`, `RunSummaryV1`, stream events, list outputs, and download logs.
3. Documents screen can:

   * Start runs from a document and view run history using `listWorkspaceRuns(..., { inputDocumentId })`.
4. Config Builder screen can:

   * Start runs and validation runs, and display summary + console using **shared** run primitives.
5. No ad-hoc types: everything is typed via `openapi.d.ts`.