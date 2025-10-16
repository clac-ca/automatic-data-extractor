<!-- Keep this document up to date when the documents route changes. -->
# Documents Route Reference

## Overview
The `DocumentsRoute` lists workspace documents, orchestrates uploads, and exposes per-row actions (details, download, delete). Filters live in the URL via `useDocumentsParams`, the data layer streams paginated results from `useDocumentsQuery`, and the route renders `DocumentsToolbar`, `DocumentsTable`, and `DocumentsEmptyState` to surface filters, results, and drag-and-drop uploads.

```
DocumentsRoute
├─ useDocumentsParams      → URL ↔ filter/sort/pagination synchronisation
├─ useDocumentsQuery       → GET /workspaces/:workspaceId/documents
├─ useUploadDocumentsMutation → POST /workspaces/:workspaceId/documents
├─ useDeleteDocumentsMutation → DELETE /workspaces/:workspaceId/documents/:documentId
└─ downloadWorkspaceDocument   → GET /workspaces/:workspaceId/documents/:documentId/download
```

## Data flow
1. `useDocumentsParams()` parses the current search string, debounces free-text search, and returns both the URL state and a normalised API payload.
2. `useDocumentsQuery(workspace.id, apiParams)` fetches paginated `DocumentRecord` rows. `toDocumentRows` memoises the envelope as `DocumentRow` models for the grid.
3. Table sorting is driven directly by the URL sort parameter (`parseSortParam`/`toSortParam`), guaranteeing server-side ordering.
4. User actions bubble back to the route:
   - Sorting → `handleSortChange` → `nextSort` + `setSort` → telemetry (`documents.sort`).
   - Filtering → `setUploader` / `setStatuses` / `setCreatedRange` / `setLastRunRange` / `setSearch` / tag helpers → telemetry (`documents.filter_*`).
   - Inspect → `handleInspect` → `WorkspaceChrome` inspector → telemetry (`documents.view_details`).
   - Download → `handleDownload` → `downloadWorkspaceDocument` → `triggerBrowserDownload`.
   - Delete → `handleDelete` → `useDeleteDocumentsMutation`.
   - Upload (button, dropzone, or file input change) → `handleFilesSelected` → `useUploadDocumentsMutation`.
5. Mutation hooks invalidate `documentKeys.lists(workspaceId)` so TanStack Query re-fetches the active result set with the current filters.

## Local state
- `sortState` ({ `column`, `direction` }): derived from the URL sort parameter, defaults to `uploadedAt` descending.
- `feedback` (object or `null`): transient alerts for uploads/downloads/deletes.
- `downloadingId` / `deletingId` (string or `null`): row-level loading states during actions.
- `dragDepth` (number): tracks nested drag events to show the drop overlay.

Derived helpers: `rows` (normalised page items), `availableTags` (tag suggestions from the current envelope), `hasActiveFilters`, `hasNext`, `showEmptyState`, and `isDragging`.

## Filter logic details
- **Uploader toggle:** `setUploader("me")` maps to `uploader=me`, instructing the API to resolve the current actor’s ULID server-side.
- **Status multi-select:** `setStatuses([...])` forwards repeatable `status` params; the backend validates against the canonical enum.
- **Tags:** `addTag`/`removeTag` manage repeatable `tag` params with deduplication; the backend treats tags as “any-of”.
- **Date ranges:** `setCreatedRange` / `setLastRunRange` push inclusive UTC bounds via `created_from`/`created_to` and `last_run_from`/`last_run_to`.
- **Search:** `setSearch` keeps the free-text term in the URL immediately; the API payload debounces to ~300 ms via `useDebouncedValue`.
- **Sort:** `parseSortParam` normalises the API sort string and `toSortParam` serialises single-field requests, keeping pagination stable through `created_at DESC, document_id DESC` tie-breaks.

## Component responsibilities
- **`DocumentsToolbar`:** Renders the uploader toggle, status multi-select, tag combobox, date-range pickers, search input, pagination summary, and upload CTA. It omits default filters from the URL.
- **`DocumentsTable`:** Displays the sortable grid, row actions, skeleton placeholders, and formatting helpers (timestamps, status badges, tags, file size). Headers emit `aria-sort` for accessibility.
- **`DocumentsEmptyState`:** Shows onboarding copy when no documents exist or when filters hide all results, with quick actions to clear filters or upload.
- **`DocumentDetails`:** Inspector content showing human-readable metadata (including uploader summary and retention window).

## Telemetry
All tracked events flow through `trackDocumentsEvent`, namespaced as `documents.<action>` with the current workspace ID (plus action-specific payload).
