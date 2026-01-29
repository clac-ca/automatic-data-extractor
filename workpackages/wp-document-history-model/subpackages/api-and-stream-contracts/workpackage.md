# Work Package: API and Stream Contracts

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - WBS checkboxes are for implementation execution; do not mark complete during planning.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Define the API contract changes implied by the simplified data model, including removal of ETag/If-Match, idempotency headers, and updates to the document change stream (SSE + delta). Keep the contracts aligned to the most common structure and naming.

### Scope

- In:
  - Document list/detail response shapes after removing documents.version and ETags.
  - Request behavior changes after removing idempotency_keys.
  - Change feed (SSE) and delta endpoints: payloads, cursors, filters.
  - Frontend usage guidance (notify + fetch, filter by id).
  - Clarify that API uses "documents" while DB retains files/file_versions.
  - Standardize kind values in API responses (input/output/log/export).
- Out:
  - Database schema changes (handled in data model subpackage).

### Work Breakdown Structure (WBS)

1.0 API surface changes
  1.1 Document list/detail
    - [ ] Remove ETag/version/docNo/expiresAt fields from document responses.
    - [ ] Confirm list query parameters and response meta fields remain stable.
  1.2 Write endpoints
    - [ ] Remove If-Match requirement for update/delete/tag endpoints.
    - [ ] Remove Idempotency-Key handling from document upload and run create routes.
2.0 Change feed contracts
  2.1 SSE stream
    - [ ] Verify event types/payloads match document.changed/document.deleted with numeric id.
    - [ ] Ensure Last-Event-ID/cursor handling remains numeric.
  2.2 Delta endpoint
    - [ ] Keep /documents/delta params + response aligned to numeric cursor.
    - [ ] Confirm list(id filter) lookup behavior for client refresh.
3.0 Client guidance + types
  3.1 Frontend alignment
    - [ ] Update frontend API calls/types for removed headers/fields.
    - [ ] Ensure streaming + delta client flow remains consistent.

### Open Questions

- Resolved: Keep existing routes with updated payloads.
- Resolved: Maintain strict query guard behavior as-is unless a new stream filter requires exceptions.

### Outputs

#### API contract summary

- Terminology: API uses "documents" while DB tables remain `files`/`file_versions`.
- `kind` values in API responses: `input`, `output`, `log`, `export` (UI Documents list filters to `input`).
- Remove `version` and `etag` from document list/detail payloads.
- Remove `If-Match` for document update/delete.
- Remove `Idempotency-Key` headers for upload/run create.

#### Realtime/change feed contract

- SSE stream: `GET /workspaces/{workspaceId}/documents/stream`
  - `ready` event: `{ "lastId": "<cursor|null>" }`
  - `document.changed` / `document.deleted` events: `{ "documentId": "<uuid>", "op": "upsert|delete", "id": "<cursor>" }`
  - `Last-Event-ID` is numeric cursor; server accepts `cursor` query param as fallback.
- Delta endpoint: `GET /workspaces/{workspaceId}/documents/delta?since=<cursor>&limit=<n>`
  - Response: `{ changes: [{ id, documentId, op }], nextSince, hasMore }`
  - 410 if cursor expired (client should refresh list).

#### Client usage guidance

- Notify + fetch: on SSE event, call delta then fetch rows via list endpoint with `filters: [{ id: "id", operator: "in", value: [docId] }]`.
- Page 1: auto-refresh if affected rows are not visible or reorder-sensitive.
- Page N: show "updates available" and refresh on user action.

---

## Acceptance Criteria

- API contracts are defined without ETag/If-Match and idempotency headers.
- Change feed contract uses a numeric cursor and minimal payloads.
- Client guidance explains how to apply updates with filters and pagination.

---

## Definition of Done

- The API contract is updated and consistent with the target data model and terminology package.
