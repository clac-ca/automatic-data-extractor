> **Agent Instructions (read first)**
>
> * Treat this work package as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as tasks are completed, and add new items when new work is discovered.
> * Prefer small, incremental commits aligned to checklist items.
> * If the plan must change, **update this document first**, then update the code.

---

We do not need backwards compatibility; schema and API changes can be in-place.

## What we are fundamentally doing

We are making ADE uploads fast and standard while keeping the backend model simple:

* Upload bytes quickly (no workbook inspection and no derived metadata persistence during upload).
* Show an upload queue with real progress (per-file + overall), cancel, and retry.
* Discover sheets only when needed via `GET /documents/{id}/sheets` (inspect the stored file; do not persist sheets).
* Optional UX: a “Run on upload” toggle that queues a run after each successful upload using the existing run queue.
* Bulk document runs use `/configurations/{configuration_id}/runs/batch` with no sheet selection.

There is only one durable queue: the run queue (`RunWorkerPool`).

---

## Work Package Checklist

* [x] Finalize Pass 1 design decisions (on-demand sheets, no sheet persistence, run-on-upload UX)
* [x] Backend: remove upload-time sheet caching (stop writing `documents.attributes["worksheets"]`) — removed worksheet caching from document create flow
* [x] Backend: ensure `/documents/{id}/sheets` inspects the stored file only (no cached fallback) — dropped cached fallback paths
* [x] Frontend: implement XHR upload queue (progress, cancel, retry, concurrency=3) — added XHR helper + concurrency queue
* [x] Frontend: integrate upload queue into Documents page (does not block browsing) — new Upload Queue panel + non-blocking UI
* [x] Frontend: add “Run on upload” toggle + config selector + per-file run enqueue status — toggle + per-file run status in queue
* [x] Backend: add batch run endpoint `POST /configurations/{configuration_id}/runs/batch` (all-or-nothing, no sheet selection) — new schemas/service/router endpoint
* [x] Frontend: update Documents bulk run action to use batch endpoint (no sheet selection) — batch run dialog wired to new endpoint
* [x] Tests: backend coverage for “upload is fast ingest” + `/sheets`; frontend queue state tests — new integration + queue hook tests
* [x] Docs: update docs/notes for new upload UX and “run on upload” — updated API guide + frontend notes

> **Agent note:**
> Keep brief status notes inline, for example:
> `- [x] Remove upload worksheet caching — <commit or short note>`

---

# ADE File Upload Optimization (Simple)

## 1. Objective

**Goal:**
Make multi-file uploads feel modern and fast:

* Users see an upload queue with progress (per-file + overall), cancel, and retry.
* Upload requests return quickly (no `.xlsx` inspection during upload).
* Sheets are loaded only when needed for sheet selection.
* Optional UX: users can enable “Run on upload” to automatically queue runs for uploaded files.
* Bulk document runs use a batch endpoint to enqueue runs in one request.

You will:

* Implement a client upload queue using `XMLHttpRequest` to provide upload progress events.
* Remove upload-time sheet caching/persistence in the API.
* Add “Run on upload” UX that calls the existing run creation endpoint after upload success.
* Add a batch run endpoint and wire the Documents bulk action to use it.

The result should:

* Reduce “time to first uploaded file” for multi-file uploads.
* Provide clear visibility into upload progress and run enqueue outcomes.
* Keep the system simple: no document-processing queue and no sheet persistence.
* Allow multi-select run submission via one request with all-or-nothing semantics.

Non-goals:

* Presigned/object-storage uploads and resumable uploads (tus/multipart).
* Server-side “upload-and-run” combined endpoint.
* Persisting sheet metadata in the database.
* A batch progress/streaming resource (use per-run events instead).

---

## 2. Context (Starting point)

Current behavior feels slow and non-standard:

* ade-web uploads multiple files by looping and awaiting one POST per file (serial).
* ade-api performs `.xlsx` inspection during upload to cache sheets into `documents.attributes["worksheets"]`.
* ade-web uses `fetch` via `openapi-fetch`, which cannot surface upload progress events.
* Documents view supports multi-select but has no batch run API; bulk runs fall back to single-run flows.

We want the smallest design that:

* speeds uploads immediately,
* adds progress + cancel + retry,
* reuses the existing run queue,
* avoids introducing a second queue for “analysis”.

---

## 3. Target architecture / structure (ideal)

Desired end state:

* Upload is fast ingest only: store bytes, create document row, return `DocumentOut`.
* Sheets are fetched on demand via `/documents/{id}/sheets` by inspecting the stored file.
* Runs are queued via existing run APIs/worker pool.
* UI manages concurrency and progress (client responsibility).
* Bulk document runs use `/configurations/{configuration_id}/runs/batch` with all-or-nothing semantics.

File tree impact:

```text
apps/ade-api/
  src/ade_api/features/documents/service.py      # remove upload-time sheet caching; simplify /sheets behavior
  src/ade_api/features/documents/router.py       # keep /sheets contract; no 409/not-ready states
  src/ade_api/features/runs/schemas.py           # add batch request/response types
  src/ade_api/features/runs/service.py           # batch run creation helper
  src/ade_api/features/runs/router.py            # /runs/batch endpoint

apps/ade-web/
  src/shared/api/client.ts                       # expose shared headers helper for XHR
  src/shared/uploads/xhr.ts                      # XHR upload helper (progress + abort)
  src/shared/uploads/queue.ts                    # concurrency-limited upload queue
  src/shared/documents/uploads.ts                # document upload adapter
  src/screens/Workspace/sections/Documents/*     # integrate upload queue, “Run on upload”, and bulk runs
```

---

## 4. Design (for this work package)

### 4.1 Design goals

* Fast uploads: no server-side workbook inspection on upload.
* Standard UX: progress, cancel, retry, partial success.
* Simple backend: no new job tables/worker pools; only the existing run queue executes background work.
* Clear behavior: avoid additional document “processing” states.

### 4.2 Key components / modules

Backend (ade-api):

* `DocumentsService.create_document()` — fast ingest; does not inspect or cache sheets.
* `DocumentsService.list_document_sheets()` — inspects stored file on demand.
* Existing `RunsService.prepare_run()` + `RunWorkerPool` — executes queued runs.
* New `RunsService.prepare_runs_batch()` + runs router `/runs/batch` — enqueue multiple runs at once.

Frontend (ade-web):

* `uploadWithProgressXHR()` — does a `multipart/form-data` POST with progress callbacks + abort.
* `useUploadQueue()` — queue state machine + concurrency control.
* Documents page integration — displays queue and updates document list.
* “Run on upload” integration — after upload success, call run creation endpoint and display result per file.

### 4.3 Key flows

1) Upload (fast ingest)

* User selects N files (or drag/drop).
* UI enqueues items and uploads with concurrency `3`.
* Each file upload calls `POST /api/v1/workspaces/{workspace_id}/documents`.
* UI updates document list incrementally (invalidate/refetch).

2) Run on upload (optional)

* UI toggle “Run on upload” is off by default.
* When enabled, user must select a configuration (required).
* After each successful upload, UI calls `POST /api/v1/configurations/{configuration_id}/runs` with:
  * `options.input_document_id = <uploaded document id>`
  * `options.input_sheet_names = null` (engine default; no sheet selection step)
* UI shows per-file run enqueue status:
  * queued (run id)
  * failed (queue full, missing config/document, etc.)

3) Bulk runs from Documents selection

* User selects multiple documents and chooses a configuration.
* UI calls `POST /api/v1/configurations/{configuration_id}/runs/batch` with `document_ids`.
* No sheet selection in batch runs; each run processes the full document.
* All-or-nothing: if any document is invalid or the queue is full, no runs are created.

4) Sheet selection (on demand)

* When a sheet picker is opened (run drawer/dialog), call `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/sheets`.
* UI shows “Loading sheets…” while awaiting response.
* On `422` parsing error, UI disables sheet selection and allows the run to proceed without `input_sheet_names`.

### 4.4 Decisions (fixed)

* No document-processing queue and no document worker pool.
* No sheet persistence anywhere (neither in `documents.attributes` nor in a separate table).
* Upload is fast ingest only; `/sheets` always inspects the stored file.
* “Run on upload” is frontend-driven (client calls existing run creation endpoint).
* Batch runs use `/configurations/{configuration_id}/runs/batch` with all-or-nothing semantics and no sheet selection.

---

## 5. API contracts

Upload:

* `POST /api/v1/workspaces/{workspace_id}/documents` (multipart `file`)
  * Returns `201 DocumentOut`
  * No sheet inspection occurs during upload

Sheets:

* `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/sheets`
  * `200` + `[DocumentSheet]` when the stored file is available and can be inspected
  * `404` when the document is missing or the stored file is unavailable
  * `422` when the workbook exists but cannot be parsed for sheets

Run creation (used by “Run on upload”):

* `POST /api/v1/configurations/{configuration_id}/runs`
  * `201` with `RunResource` on success
  * `429` with `{"error":{"code":"run_queue_full",...}}` when the run queue is full

Batch run creation (bulk action):

* `POST /api/v1/configurations/{configuration_id}/runs/batch`
  * Body: `{ "document_ids": ["..."], "options": { ... } }` (no `input_sheet_names`)
  * `201` with `{ "runs": [RunResource, ...] }` on success
  * `404` if any document is missing
  * `429` with `{"error":{"code":"run_queue_full",...}}` when the run queue cannot fit the full batch

---

## 6. Frontend UX requirements

Upload queue UI:

* Per-file row shows:
  * filename + size
  * progress bar with percent + bytes uploaded
  * states: queued, uploading, succeeded, failed, cancelled (clear labels, not just icons)
  * inline error message on failure
  * actions: cancel (while uploading), retry (on failure), remove (after terminal state)
* Overall summary shows:
  * total count and overall progress
  * “x succeeded · y failed · z cancelled”
  * “Clear completed” action (does not remove in-flight items)
* Concurrency: `3`.

Run on upload UI:

* Toggle: “Run on upload”.
* Configuration selector (required when toggle is enabled).
* When disabled (no config or safe mode), show a short helper message.
* Per-file run enqueue status displayed next to upload status, with “View run” when available.
* No auto-retry for run enqueue failures; user triggers a manual run if needed.

Bulk run UI (Documents multi-select):

* “Run selected” uses `/runs/batch` and skips sheet selection.
* Confirm the count + configuration before submitting (lightweight confirm).
* UI surfaces batch success/failure and links to created runs.
* All-or-nothing: if batch fails, no runs are created.

---

## 7. Acceptance criteria

* Uploading 10 files starts multiple uploads in parallel (not serial-only).
* UI shows real upload progress and allows cancel/retry.
* Upload request latency is not dominated by `.xlsx` inspection (inspection happens only on `/sheets`).
* With “Run on upload” enabled, each uploaded file results in a queued run or a clear per-file error (including queue full).
* Bulk “Run selected” uses `/runs/batch` and enqueues all runs or fails as a unit.

---

## 8. Implementation notes for agents

Backend:

* Do workbook inspection in a threadpool; never block the event loop with `openpyxl`.
* Remove behavior that writes `documents.attributes["worksheets"]` during upload.
* Ensure `/sheets` does not use cached worksheet metadata from the document record.
* Batch runs: validate all document IDs at once, enforce `queue_size` for the full batch, and create runs in a single transaction.

Frontend:

* Use XHR for upload progress. Mirror existing auth/CSRF behavior from `apps/ade-web/src/shared/api/client.ts`:
  * `X-Requested-With: fetch`
  * `Authorization: <token>` when present
  * `X-CSRF-Token` for POST
  * `withCredentials=true` to preserve session cookies when applicable
* Keep the queue logic isolated (shared module) and keep UI rendering simple.
* Types: run `ade types` if backend OpenAPI changes affect the frontend.
* Validation: run `ade tests` before committing; run `ade ci` before pushing/PR.
* Bulk run action should call `/runs/batch` and skip sheet selection.
