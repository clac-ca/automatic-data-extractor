# Work Package: Backend Realtime API (SSE + Delta + List ID Filter)

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Expose a standard realtime surface for documents: SSE stream for notifications, delta endpoint for changes since a token, and list endpoint `id` filter support for membership checks. Stream payload should include `{documentId, op, token}` (minimal). Implement token encode/decode, LISTEN/NOTIFY listener, and auth guards.

### Research References (read first)

- `workpackages/wp-document-stream-refactor/research.md` lines 168-239 (API design: stream, delta, list id filter)
- `workpackages/wp-document-stream-refactor/research.md` lines 254-292 (event model + token semantics)
- `workpackages/wp-document-stream-refactor/research.md` lines 469-683 (backend implementation patterns + code examples)
- `workpackages/wp-document-stream-refactor/research.md` lines 865-882 (SSE vs WebSocket tradeoffs + backpressure)
- `workpackages/wp-document-stream-refactor/research.md` lines 961-969 (backend checklist)

### Scope

- In: SSE stream (renamed `/documents/stream`), delta API, list id filter support, token helpers, LISTEN/NOTIFY listener, authz, and stream payload minimization.
- Out: frontend UI logic, DB schema changes, WebSocket support.

### Work Breakdown Structure (WBS)

0.1 Research review
  - [x] Read `workpackages/wp-document-stream-refactor/research.md` lines 168-239 (stream, delta, list id filter)
  - [x] Read `workpackages/wp-document-stream-refactor/research.md` lines 469-683 (backend implementation code examples)
  - [x] Read `workpackages/wp-document-stream-refactor/research.md` lines 865-882 (SSE vs WebSocket tradeoffs/backpressure)
1.0 Token and delta helpers
  1.1 Token helpers
    - [x] Implement token encode/decode (ts + seq) (Research: lines 274-292; code example lines 488-509)
    - [x] Validate token parsing and error handling (Research: lines 218-221)
  1.2 Delta query
    - [x] Implement delta query against change feed (Research: lines 201-215; code example lines 635-669)
    - [x] Return 410 when token is too old (Research: lines 218-221, 374-381)
    - [x] Support `limit` + `hasMore` pagination (Research: lines 201-215)
2.0 SSE stream
  2.1 Stream endpoint
    - [x] Rename route to `/workspaces/{id}/documents/stream` (drop `/events/stream`) (Design decision)
    - [x] Add `/workspaces/{id}/documents/stream` SSE route (Research: lines 187-197; code example lines 576-633)
    - [x] Send keepalive comments and set no-buffer headers (Research: lines 194-197; code example lines 576-633)
    - [x] Use SSE id field for token to support Last-Event-ID (Research: lines 196-197; code example lines 611-615)
    - [x] Emit payload containing `documentId`, `op`, and `token` only (Design decision)
    - [x] Remove include=rows handling and server-side row fetch from stream (Design decision)
    - [x] Remove DocumentEventEntry.row from schema and update event model accordingly (Design decision)
    - [x] Emit `ready` event with latest **change feed token** (not sequence cursor) (Design decision)
    - [x] If a `cursor`/token query param is retained, validate it uses the new token format (Design decision)
  2.2 LISTEN/NOTIFY
    - [x] Add async listener for document change channel (Research: lines 552-573; code example lines 552-573)
    - [x] Broadcast workspace-scoped notifications (Research: lines 123-129; code example lines 564-569)
    - [x] Drop or disconnect slow consumers (bounded queues) (Research: lines 511-549, 881-882; code example lines 511-549)
    - [x] Ensure NOTIFY payload includes `{documentId, op, changedAt, seq}`; hub encodes token (Design decision)
3.0 List endpoint id filter support
  3.1 Filter registry updates
    - [x] Add `id` filter (eq/in) to document filter registry (Research: lines 223-239; code example lines 671-683)
    - [x] Validate list endpoint uses server-side filters for membership checks (Research: lines 223-239)
  3.2 List response shape
    - [x] Confirm list row shape is reused for membership fetches (Research: lines 223-239)
4.0 Auth and docs
  4.1 Auth guards
    - [x] Ensure permissions required for stream, delta, list endpoint access
  4.2 OpenAPI
    - [x] Update schema docs for new endpoints and params
    - [x] Update stream response schema to match minimal payload (Design decision)
    - [x] Remove `include=rows` parameter from stream docs/types (Design decision)
5.0 Tests
  5.1 API tests
    - [x] Unit test token encode/decode
    - [x] Delta behavior tests (ordering, 410)
    - [x] List endpoint with `id` filter returns list-row shape

### Open Questions

- None. Stream is workspace-scoped.

---

## Acceptance Criteria

- `/documents/stream` emits change notifications with keepalives and minimal payload. (Research: lines 187-197, 576-633)
- `/documents/delta` returns ordered changes and respects retention rules. (Research: lines 201-215, 374-381, 635-669)
- `/documents` with `id` filter returns DocumentListRow-compatible items. (Research: lines 223-239, 671-683)
- All endpoints are permission-guarded and documented. (Research: lines 168-239)

---

## Definition of Done

- Endpoints implemented and covered with unit-level tests. (Research: lines 903-913, 961-969)
- Listener runs per API instance and broadcasts notifications. (Research: lines 552-573, 564-569)
- OpenAPI types updated. (Research: lines 168-239)
