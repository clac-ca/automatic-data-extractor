# 130-DOCUMENTS.md  
**ADE Web – Documents, Uploads, Sheets & Downloads**

---

## 0. Purpose

This document explains how `apps/ade-web` should use the **Documents**-related backend APIs described in `openapi.d.ts` to deliver the Documents UX:

- Listing documents in a workspace.
- Uploading new documents (with metadata and expiration).
- Viewing document details (status, last run, uploader, tags).
- Inspecting worksheets/sheets for a document.
- Downloading original files.
- Soft-deleting (archiving) documents.
- Connecting documents to runs (last run status + “start run” flow).

It is a companion to:

- `010-WORK-PACKAGE.md` – overall goals.
- `030-UX-FLOWS.md` – detailed Documents & Runs flows.
- `050-RUN-STREAMING-SPEC.md` – run streaming/replay behavior.
- `110-BACKEND-API.md` – global backend route catalog.
- `120-AUTH.md` – auth/session handling.

---

## 1. Backend Documents API Surface (from OpenAPI)

All document operations are **workspace-scoped**:

```ts
/api/v1/workspaces/{workspace_id}/documents
/api/v1/workspaces/{workspace_id}/documents/{document_id}
...
````

From `openapi.d.ts`, the main endpoints:

### 1.1 List documents

**Path:**
`GET /api/v1/workspaces/{workspace_id}/documents`
**Operation:** `list_documents_api_v1_workspaces__workspace_id__documents_get`

**Parameters:**

* `path.workspace_id: string` – workspace ULID.
* `query.page?: number`
* `query.page_size?: number`
* `query.include_total?: boolean`
* `query.sort?: string | null`

  * Description: CSV, prefix `-` for DESC.
  * Allowed fields (from description): `last_run_at`, `name`, `source`, `status`, `created_at`.
  * Example: `-created_at,name`.

**Response:**

* `200 application/json → components["schemas"]["DocumentPage"]`

  * `items: DocumentOut[]`
  * `page: number`
  * `page_size: number`
  * `has_next: boolean`
  * `has_previous: boolean`
  * `total?: number | null`
* Errors:

  * `400` – invalid/unsupported query params.
  * `401` – auth required.
  * `403` – workspace permissions do not allow document access.
  * `422` – validation error (`HTTPValidationError`).

### 1.2 Upload document

**Path:**
`POST /api/v1/workspaces/{workspace_id}/documents`
**Operation:** `upload_document_api_v1_workspaces__workspace_id__documents_post`

**Parameters:**

* `path.workspace_id: string` – workspace ULID.
* Request body: `multipart/form-data`:

  ```ts
  components["schemas"]["Body_upload_document_api_v1_workspaces__workspace_id__documents_post"] = {
    /**
     * File
     * Format: binary
     */
    file: string;
    /** Metadata */
    metadata?: string | null;
    /** Expires At */
    expires_at?: string | null; // ISO 8601 date-time string
  }
  ```

**Response:**

* `201 application/json → DocumentOut` – the newly created document.
* Errors:

  * `400` – invalid metadata payload or expiration timestamp.
  * `401` – auth required.
  * `403` – workspace permissions do not allow uploads.
  * `413` – uploaded file exceeds configured size limit.
  * `422` – validation error (`HTTPValidationError`).

### 1.3 Get document metadata

**Path:**
`GET /api/v1/workspaces/{workspace_id}/documents/{document_id}`
**Operation:** `read_document_api_v1_workspaces__workspace_id__documents__document_id__get`

**Parameters:**

* `path.workspace_id: string`
* `path.document_id: string`

**Response:**

* `200 application/json → DocumentOut`
* Errors:

  * `401` – auth required.
  * `403` – workspace permissions do not allow document access.
  * `404` – document not found in this workspace.
  * `422` – validation error (`HTTPValidationError`).

### 1.4 Soft delete (archive) document

**Path:**
`DELETE /api/v1/workspaces/{workspace_id}/documents/{document_id}`
**Operation:** `delete_document_api_v1_workspaces__workspace_id__documents__document_id__delete`

**Parameters:**

* `path.workspace_id: string`
* `path.document_id: string`

**Response:**

* `204` – successfully soft-deleted (no content).
* Errors:

  * `401` – auth required.
  * `403` – workspace permissions do not allow deletion.
  * `404` – document not found.
  * `422` – validation error.

> **Note:** OpenAPI calls this “Soft delete a document”. In the data model, this generally corresponds to `DocumentStatus = "archived"` and non-null `deleted_at`.

### 1.5 Download original document

**Path:**
`GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/download`
**Operation:** `download_document_api_v1_workspaces__workspace_id__documents__document_id__download_get`

**Parameters:**

* `path.workspace_id: string`
* `path.document_id: string`

**Response:**

* `200` – original file stream.

  * OpenAPI models content as:

    ```ts
    "application/json": unknown;
    ```

    but in practice this is typically a binary file (e.g., `application/octet-stream`, CSV, XLSX) with `Content-Disposition` header providing filename. Frontend must treat it as a **blob download**.
* Errors:

  * `401` – auth required.
  * `403` – workspace permissions do not allow downloads.
  * `404` – document missing or stored file unavailable.
  * `422` – validation error.

### 1.6 List document sheets

**Path:**
`GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/sheets`
**Operation:** `list_document_sheets_endpoint_api_v1_workspaces__workspace_id__documents__document_id__sheets_get`

**Parameters:**

* `path.workspace_id: string`
* `path.document_id: string`

**Response:**

* `200 application/json → DocumentSheet[]`
* Errors:

  * `404` – document not found in workspace.
  * `422` – “The workbook exists but could not be parsed for worksheets.”

> While the OpenAPI snippet only explicitly shows 200/404/422, it’s reasonable to assume auth/permissions behavior is aligned with other document endpoints (401/403) in practice.

---

## 2. Documents Data Model (from OpenAPI)

### 2.1 `DocumentOut` – the core document type

Schema: `components["schemas"]["DocumentOut"]`

Fields (simplified):

* Identity & workspace:

  * `id: string` – document ULID (26 chars).
  * `workspace_id: string` – workspace ULID.
* File info:

  * `name: string` – display name mapped from original filename.
  * `content_type?: string | null` – MIME type (e.g., `text/csv`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`).
  * `byte_size: number` – size in bytes.
* Metadata & tagging:

  * `metadata?: { [key: string]: unknown }` – arbitrary metadata.
  * `tags?: string[]` – user-applied tags (empty list when none).
* Status & classification:

  * `status: DocumentStatus` – `"uploaded" | "processing" | "processed" | "failed" | "archived"`.
  * `source: DocumentSource` – `"manual_upload"` (for now, single-valued enum).
* Lifetime & timestamps:

  * `expires_at: string` – ISO 8601 date-time when the document expires.
  * `last_run_at?: string | null` – last run event timestamp.
  * `created_at: string`
  * `updated_at: string`
  * `deleted_at?: string | null`
  * `deleted_by?: string | null`
* Relationships:

  * `uploader?: UploaderOut | null`

    * `id: string` (uploader ULID)
    * `name?: string | null`
    * `email: string`
  * `last_run?: DocumentLastRun | null`

    * `run_id?: string | null`
    * `status: RunStatus` (`"queued" | "running" | "succeeded" | "failed" | "canceled"`)
    * `run_at?: string | null`
    * `message?: string | null` (status or error message).

### 2.2 Document status & source

* `DocumentStatus` (enum):

  ```ts
  "uploaded" | "processing" | "processed" | "failed" | "archived"
  ```

  **Semantics (for UI):**

  * `uploaded` – stored but not yet processed by a run.
  * `processing` – a run is currently processing this document.
  * `processed` – last run succeeded; normalized output should exist.
  * `failed` – last run failed; `last_run.message` likely contains details.
  * `archived` – soft-deleted; should not appear by default in main list.

* `DocumentSource` (enum):

  ```ts
  "manual_upload"
  ```

  For now, everything is “Manual upload”, but we treat this as a generic label (future sources could include “API”, “integration”, etc.).

### 2.3 Pagination `DocumentPage`

Schema: `DocumentPage`:

```ts
DocumentPage: {
  items: DocumentOut[];
  page: number;
  page_size: number;
  has_next: boolean;
  has_previous: boolean;
  total?: number | null;
}
```

Used by `GET /documents` for list view.

### 2.4 `DocumentSheet`

Schema: `DocumentSheet`:

```ts
DocumentSheet: {
  name: string;              // sheet name
  index: number;             // 0-based or 1-based index (treat as display order)
  /**
   * @default worksheet
   * @enum {string}
   */
  kind: "worksheet" | "file"; // "worksheet" for tab in workbook, "file" for single-sheet file
  /**
   * Is Active
   * @default false
   */
  is_active: boolean;
}
```

Intended for:

* Showing a list of worksheets for an Excel/Sheets-like document.
* Distinguishing between multi-sheet workbook vs. single-sheet file.

### 2.5 Supporting types

* `UploaderOut` – who uploaded the document:

  * `id: string`
  * `name?: string | null`
  * `email: string`

* `DocumentLastRun`:

  * `run_id?: string | null` – cross-link to run detail.
  * `status: RunStatus`
  * `run_at?: string | null`
  * `message?: string | null`

These are used heavily in the documents list and detail views to tie documents to runs.

---

## 3. Frontend API Wrapper Design

Implement a dedicated `documentsApi` under `features/documents/api/documentsApi.ts` that uses **OpenAPI types** directly:

```ts
import type { paths, components } from "@/generated-types/openapi";

type DocumentOut = components["schemas"]["DocumentOut"];
type DocumentPage = components["schemas"]["DocumentPage"];
type DocumentSheet = components["schemas"]["DocumentSheet"];

type ListDocumentsResponse =
  paths["/api/v1/workspaces/{workspace_id}/documents"]["get"]["responses"][200]["content"]["application/json"];
```

Recommended wrapper methods:

* `listDocuments(workspaceId: string, params?: { page?: number; pageSize?: number; sort?: string; includeTotal?: boolean; }): Promise<DocumentPage>`
* `uploadDocument(workspaceId: string, file: File, options?: { metadata?: unknown; expiresAt?: string | null; }): Promise<DocumentOut>`
* `getDocument(workspaceId: string, documentId: string): Promise<DocumentOut>`
* `deleteDocument(workspaceId: string, documentId: string): Promise<void>`
* `downloadDocument(workspaceId: string, documentId: string): Promise<Blob>` (wraps fetch+`blob()` and filename from `Content-Disposition`)
* `listDocumentSheets(workspaceId: string, documentId: string): Promise<DocumentSheet[]>`

Use React Query hooks on top:

* `useDocumentList(workspaceId, query)`
* `useDocument(workspaceId, documentId)`
* `useDocumentSheets(workspaceId, documentId)`
* `useUploadDocument(workspaceId)` (mutation)
* `useDeleteDocument(workspaceId)` (mutation)

All calls should use our shared `fetchWithAuth` with `credentials: "include"`.

---

## 4. UX Flows & How They Map to the API

### 4.1 Documents list screen

**Goal:** show all documents in current workspace with clear status and last run information, and provide quick actions (upload, run, download, delete).

**API usage:**

* On mount or workspace change:

  * Call `listDocuments(currentWorkspaceId, { page, pageSize, sort })`.
* Use `DocumentPage.items` to render table rows.

**Columns (recommended):**

* Name (`DocumentOut.name`)
* Status (`DocumentStatus`), with pill colors:

  * uploaded → neutral
  * processing → info / spinner
  * processed → success
  * failed → error
  * archived → muted/strikethrough (not shown by default)
* Last run:

  * Status: `DocumentOut.last_run?.status`
  * Time: `last_run_at` or `last_run?.run_at`
  * Error message snippet: `last_run?.message`
* Uploader:

  * `uploader.name || uploader.email`
* Size:

  * Byte size converted to human-readable (KB/MB/GB).
* Expires in:

  * Derived from `expires_at` vs now.

**Sorting:**

* UI sort selector maps to API query `sort`:

  * “Newest first” → `sort="-created_at"`
  * “Oldest first” → `sort="created_at"`
  * “Last run (recent)” → `sort="-last_run_at"`
  * “Name (A–Z)” → `sort="name"`
  * “Status” → `sort="status"`

**Error handling:**

* 401/403 → delegated to `AuthProvider` / guarded routes.
* 400/422 → show toast: “Couldn’t load documents. Invalid query or server validation issue.”

---

### 4.2 Upload flow

**Goal:** user drops or selects a file and sees it appear in the list with clear feedback, optional metadata, and optionally an immediate “Start run” CTA.

**API usage:**

* Form data:

  ```ts
  const form = new FormData();
  form.append("file", file);
  if (metadata != null) {
    form.append("metadata", JSON.stringify(metadata));  // our proposed convention
  }
  if (expiresAt != null) {
    form.append("expires_at", expiresAt); // ISO 8601 string, e.g., "2025-01-01T00:00:00Z"
  }
  ```

* `POST /documents` with `multipart/form-data`.

**Metadata convention (frontend-side):**

Even though OpenAPI only says `metadata: string`, we should treat it as a **JSON string** with a stable schema we define for the frontend, e.g.:

```ts
type DocumentUploadMetadataV1 = {
  version: 1;
  original_filename: string;
  user_label?: string;
  notes?: string;
  tags?: string[];
};
```

We can then:

* On upload:

  * Set `original_filename = file.name`.
  * Use `user_label` from input if user renames.
  * Add tags from UI.
* On read:

  * Parse `DocumentOut.metadata` if it looks like this structured payload and use it for UI hints (display “user label” etc.).

**UX:**

* Show uploading state per file (local progress; the backend does not stream upload progress beyond normal HTTP).
* On success:

  * `DocumentOut` returned; insert at top of list (or refetch list).
  * Status is likely `"uploaded"` initially.
* On errors:

  * `400` – “Invalid metadata or expiration date.”
  * `401/403` – auth/permission errors via auth handling.
  * `413` – “File too large (exceeds configured limit).”
  * `422` – generic validation error.

**Optional UX:**

* After successful upload, show a “Start run” action (see 4.4) that uses runs APIs to process the document.

---

### 4.3 Document detail & sheets

**Goal:** when a user clicks a document, they see:

* Core metadata (name, size, content type).
* Status & lifetime (expires at, created/updated).
* Uploader info.
* Last run summary.
* Available sheets (for multi-sheet workbooks).
* Actions: download original, start run, delete.

**API usage:**

* `GET /documents/{document_id}` → `DocumentOut`.
* `GET /documents/{document_id}/sheets` → `DocumentSheet[]`.

**UI behaviors:**

* Show a header with:

  * Name, size, content type.
  * Status pill.
  * “Uploaded by {uploader} at {created_at}”.
  * “Expires {relative time}” (if soon, highlight).
* “Sheets” panel:

  * Call `listDocumentSheets` and show each `DocumentSheet`:

    * Name, index.
    * Kind:

      * “Worksheet” vs “File”.
    * `is_active`:

      * Distinguish default/active sheet.
  * If 422 (“could not be parsed for worksheets”):

    * Show gentle message: “We couldn’t read worksheets from this file; it will be treated as a single-sheet document.”
* `last_run`:

  * Show run status (pill), timestamp, and message.
  * If `run_id` is present:

    * “View run” button → opens Run Detail screen for that `run_id`.
  * If no `last_run`:

    * Show “No runs yet. Start a run to process this document.”

---

### 4.4 Starting runs from Documents (conceptual)

While run creation endpoints are defined elsewhere (see `110-BACKEND-API.md` and `050-RUN-STREAMING-SPEC.md`), the **Documents UI** should surface a first-class “Start run” flow:

* On each document row / detail page:

  * “Start run” button.
* Implementation:

  * Use active workspace + selected configuration (from Config Builder) to construct a run creation call.
  * Associate the document via run request body (the exact field is defined in the runs schema, not in documents).

After run creation:

* Document status should move to `"processing"` based on backend updates.
* `DocumentOut.last_run` will update to point to the newly created run.
* Run Detail screen uses run endpoints and `useRunStream` to show progress.

> **Key point:** Documents remain the **entry point**; run streaming & telemetry belong to the **runs** subsystem, but Documents should surface the linkage via `DocumentLastRun`.

---

### 4.5 Downloading original & outputs

From Documents screen, we support:

* **Download original**:

  * Uses `/documents/{document_id}/download`.
  * Implementation:

    * `fetch` with `credentials: "include"`.
    * `response.blob()`.
    * Determine filename via `Content-Disposition` header or fallback to `DocumentOut.name`.
    * Trigger browser download (e.g., create `objectURL` + synthetic `<a download>`).

* **Download normalized/output files**:

  * Not directly via Documents endpoints.
  * Use runs endpoints:

    * `GET /api/v1/runs/{run_id}/outputs`
    * `GET /api/v1/runs/{run_id}/outputs/{output_path}`
  * Recommended UX:

    * From Document Detail “Runs & Outputs” panel:

      * Show latest run outputs.
      * Provide download actions that call runs outputs APIs.

---

### 4.6 Delete (soft-archive) documents

From Documents list/detail:

* “Delete” (or “Archive”) action calls:

  * `DELETE /documents/{document_id}`.

* On success (204):

  * Remove from current list or mark as archived.

* UX suggestions:

  * Confirm dialog: “Are you sure you want to archive this document? Runs and logs will not be deleted.”
  * Optionally show subtle toast.

**Future extensions:**

* Filter/toggle to include archived documents if/when the backend exposes query filters (currently not in OpenAPI for documents list).

---

## 5. Document Status & Run Status – Unified UX

We should present a **single mental model** that bridges document status and run status:

* `DocumentStatus.uploaded` + `DocumentLastRun = null`:

  * “Uploaded” badge; call-to-action is “Start run”.
* `DocumentStatus.processing` + `last_run.status in {"queued", "running"}`:

  * Show running badge + spinner.
  * Last run row shows progress (link to Run Detail).
* `DocumentStatus.processed` + `last_run.status = "succeeded"`:

  * “Processed” badge.
  * Show success icon and last run timestamp.
  * Provide “Download normalized” / “View run” actions.
* `DocumentStatus.failed` + `last_run.status = "failed"`:

  * Error badge; show message snippet.
  * “View run logs” button opens run details at failure point.
* `DocumentStatus.archived`:

  * Display only if user explicitly opts into showing archived.
  * Greyed out, no new runs allowed.

This should feel consistent across:

* Documents list.
* Document detail.
* Any workspace-level run summaries.

---

## 6. Error & Edge-case Handling

### 6.1 Upload

* `400` – invalid metadata/expiration:

  * Parse metadata in frontend before sending; validate expiration date/time.
  * Show inline error near metadata/expiration controls.
* `413` – file too large:

  * Inform user of size limit (as known in docs/config).
* `401/403` – handled by auth guard; also show “You don’t have permission to upload in this workspace” if 403 persists.
* `422` – generic validation → toast, with optional “details” when we surface `HTTPValidationError`.

### 6.2 List

* If list fails with `403`, show:

  * “You don’t have permission to view documents in this workspace.”
* Network errors:

  * Retry button at top of Documents list.

### 6.3 Sheets

* `404`:

  * Document may have been deleted between open and sheet query.
  * Show: “This document no longer exists or has been removed.”
* `422`:

  * “We couldn’t read worksheets from this file; treating it as a single sheet.”

### 6.4 Download

* `404`:

  * Show message “File is missing or unavailable. The document entry may be stale.”
* Failed `blob()` or empty response:

  * Show “Download failed. Please try again or contact support.”

---

## 7. Security & Permissions

Documents endpoints are **protected** and workspace-aware:

* Listing, uploading, reading, deleting, downloading documents require:

  * An authenticated session (see `120-AUTH.md`).
  * Appropriate workspace permissions.

Front-end must:

* Use `credentials: "include"` with our shared API client.
* Combine:

  * `BootstrapEnvelope.global_permissions`
  * Workspace-scoped permissions (`/me/permissions?workspace_id=...`)

to gate:

* Upload action (“can upload documents”).
* Delete action (“can delete documents”).
* Viewing/Downloading where necessary.

We still assume backend is authoritative; 403s must be handled gracefully.

---

## 8. Implementation Notes & Checklist

**API module (`documentsApi`):**

* [ ] Implement `listDocuments`, `uploadDocument`, `getDocument`, `deleteDocument`, `downloadDocument`, `listDocumentSheets` using OpenAPI types.
* [ ] Ensure multipart form upload for `POST /documents` uses:

  * `file` field as the `File` object.
  * `metadata` serialized as JSON string (optional).
  * `expires_at` as ISO 8601 (optional).
* [ ] Use `fetch` or Axios with `responseType: "blob"` for download.

**React Query hooks:**

* [ ] `useDocumentList(workspaceId, filters)` – handles pagination & sorting; exposes `isLoading`, `error`, `data`.
* [ ] `useUploadDocument` – mutation with optimistic UI where appropriate.
* [ ] `useDocument` & `useDocumentSheets` – detail view.

**UI integration:**

* [ ] Documents list screen per `030-UX-FLOWS.md`.
* [ ] Document detail panel with:

  * Metadata + status + last run + uploader.
  * Sheets panel using `DocumentSheet`.
  * “Download original” action wired to `downloadDocument`.
  * “Start run” button wired to runs API.
* [ ] Delete/Archive action using `DELETE /documents/{document_id}`.

**Testing:**

* [ ] Unit tests for `documentsApi` methods (correct paths & types).
* [ ] Integration tests:

  * “Upload → appears in list with status uploaded.”
  * “Upload large file → shows size limit error (413).”
  * “Detail view shows last run & links to run detail.”
  * “Download triggers blob download with correct filename.”

---

## 9. Non-goals / Future Work

Out of scope for this workpackage (but enabled by this design):

* Rich tag editing (create/edit/delete tags).
* Advanced search & filtering (by tags, source, uploader, status).
* Document metadata editing after upload.
* Hard delete and restore/undelete.
* Cross-workspace document moves or sharing.
* Document-level access controls beyond workspace roles.

Those can become follow-up workpackages once the core Documents flows are solid.