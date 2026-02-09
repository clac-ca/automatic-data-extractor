# Work Package: Document Change Feed Redesign (Option A)

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Redesign the document change feed to a simpler, standard approach: a single append-only `document_changes` table with a numeric cursor and a shared trigger function, while retaining separate triggers on source tables. This removes partition/DDL complexity, simplifies cursors, and keeps SSE + delta durable.

### Scope

- In:
  - Replace time+seq token with a single numeric change id cursor.
  - Use a single `record_document_change(...)` trigger function for all change sources.
  - Keep separate triggers (files, file_tags, runs) that call the shared function.
  - Simplify retention to a scheduled DELETE based on age or id.
  - Update SSE and delta APIs to use numeric cursor semantics.
  - Update frontend stream + delta handling to use numeric cursor.
  - Add/adjust tests for stream → delta → list(id filter).
- Out:
  - Websocket implementation.
  - Removing the change table entirely.
  - Multi-tenant fanout beyond workspace scoping.

### Work Breakdown Structure (WBS)

1.0 Database redesign
  1.1 Schema + migration
    - [x] Define new `document_changes` schema (id bigserial PK, workspace_id, document_id, op, changed_at).
    - [x] Add indexes (workspace_id, id) and (document_id, id).
    - [x] Drop partitioning functions/DDL and old token seq logic.
    - [x] Add retention cleanup function or rely on scheduled DELETE.
  1.2 Triggers (Option A)
    - [x] Implement `record_document_change(workspace_id, document_id, op, changed_at)` function.
    - [x] Update file/tag/run triggers to call the shared function.
    - [x] Ensure triggers cover all doc-visible updates (version, deleted_at, assignee, metadata, tags, runs).

2.0 API layer updates
  2.1 Change token + delta
    - [x] Replace time+seq token encoding with numeric cursor (id).
    - [x] Update `/documents/stream` ready payload and event `id`.
    - [x] Update `/documents/delta` to accept `since=<id>` and return `nextSince=<id>`.
  2.2 Safety + retention
    - [x] Replace partition maintenance loop with retention cleanup job.
    - [x] Ensure 410 logic uses earliest retained id (or cutoff timestamp).

3.0 Frontend updates
  3.1 Stream + delta logic
    - [x] Update stream handling to use numeric cursors.
    - [x] Keep list(id filter) membership checks; update row logic if needed.
  3.2 UX correctness
    - [x] Keep page-1 inline updates; page-N banner.
    - [x] Sidebar assigned-docs stream continues to use same delta flow.

4.0 Tests + docs
  4.1 Tests
    - [x] Update unit tests for change token handling.
    - [x] Update integration delta tests for numeric cursor.
    - [x] Add/adjust SSE end-to-end test (stream → delta → list).
  4.2 Docs
    - [x] Update API docs with numeric cursor semantics and retention behavior.

### Open Questions

- Retention policy: resolved to age-based cleanup using `changed_at` and `document_changes_retention_days`.
- Triggers: retain `files` update trigger on `version`/`deleted_at`; assignee/metadata updates bump `version` so they emit.
- Cleanup runs inside the API maintenance loop via DELETE; no external job required.

---

## Acceptance Criteria

- Document change feed uses a single numeric cursor id (no time/seq encoding).
- `document_changes` table is non-partitioned and uses a single shared trigger function.
- SSE delivers events with `id` matching the change id and a `ready` payload that includes latest id.
- `/documents/delta` accepts `since=<id>` and returns `{changes, nextSince, hasMore}` based on numeric id.
- Frontend stream + delta flow continues to update page 1 inline and show the page-N updates banner.
- Updated tests pass: change token unit tests, delta integration tests, SSE end-to-end.

---

## Definition of Done

- Migration applies cleanly on a fresh DB and on an existing DB.
- All updated endpoints and schemas are reflected in OpenAPI and frontend types.
- Tests updated and green for the relevant suites.
- Docs updated to reflect new cursor semantics.
