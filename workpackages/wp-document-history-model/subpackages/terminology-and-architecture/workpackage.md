# Work Package: Terminology and Architecture

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - WBS checkboxes are for implementation execution; do not mark complete during planning.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Create a clear glossary and architecture summary that uses common industry terminology for document state, byte history, audit logs, and change feeds. Capture the differences between audit_log, document_versions, and document_changes and map them to ADE naming.

### Scope

- In:
  - Common terminology definitions (document, document version, revision, audit log, change feed/outbox, cursor).
  - Compare models: split history (document_versions + audit_log) vs unified revisions table.
  - Map existing ADE tables to the standard terms and identify renames/aliases for clarity.
- Out:
  - Database schema changes and migrations (handled in data model subpackage).

### Work Breakdown Structure (WBS)

1.0 Terminology alignment in code/docs
  1.1 Apply standard naming
    - [ ] Update docs to reflect the agreed terminology (documents, document_versions, change feed).
    - [ ] Verify API descriptions reinforce "documents" while DB tables remain files/file_versions.
  1.2 File kind naming
    - [ ] Align `kind` values in code/docs to input/output/log/export.

### Open Questions

- Resolved: Use a minimal change feed table for realtime. Add audit_log only if compliance/history is required.
- Resolved: Keep existing table names in the DB for now (files/file_versions) and map to document terms in API/docs.

### Outputs

#### Terminology inventory (current ADE)

- files: current document metadata and pointer to current file version (current state).
- file_versions: immutable byte history (content snapshots and storage pointers).
- file_tags: document tagging join table (metadata state).
- file_comments / file_comment_mentions: document discussion metadata (metadata state).
- runs / run_fields / run_metrics / run_table_columns: run execution history tied to file_versions.
- document_changes: realtime change feed cursor table (best-effort deltas).
- audit_log: not present today (optional future compliance history).

#### Glossary and usage

- Document: the user-facing entity (metadata + current file pointer).
- Document version: an immutable snapshot of file bytes and file metadata.
- Revision: a generic term for a point-in-time snapshot (can include metadata + bytes).
- Audit log: append-only history for compliance/debugging; long retention, richer payloads.
- Change feed: lightweight append-only stream for realtime updates; short retention.
- Outbox: a DB table used to fan out events reliably (a change feed is a form of outbox).
- Cursor: a monotonic pointer into a feed (typically bigserial id).

Usage guidance:
- Document_versions store file history; do not use for metadata-only edits unless modeling full revisions.
- Audit_log is for compliance/history, not realtime UI updates.
- Document_changes is for realtime UI deltas; keep it small and fast.

#### Architecture options (summary)

Model A (documents + document_versions + audit_log + document_changes):
- Pros: standard, clear separation, audit history optional.
- Cons: extra table if audit_log is required.

Model B (documents + unified document_revisions + change feed):
- Pros: unified history, simple mental model.
- Cons: higher write amplification, heavier queries, less common in CRUD apps.

Model C (documents + document_versions only, no metadata history):
- Pros: simplest schema and writes.
- Cons: no metadata history beyond current state.

#### Recommended model (most common)

Adopt Model A without audit_log by default:
- Most common for CRUD apps with file history.
- documents hold current state; document_versions hold byte history.
- document_changes enables realtime updates with minimal payloads.
- audit_log is optional and can be added later if compliance is required.

#### ADE naming map

- files -> documents (API/docs terminology)
- file_versions -> document_versions
- file_tags -> document_tags
- file_comments -> document_comments
- document_changes stays as-is (change feed)

#### File kind naming decision

- Keep the column name `kind` for simplicity and minimal churn.
- Use standard, descriptive enum values: `input`, `output`, `log`, `export`.
- UI "Documents" view maps to `kind=input`.

---

## Acceptance Criteria

- A glossary exists that clearly distinguishes audit_log vs document_versions vs document_changes.
- A recommended architecture model is documented with rationale and mapping to ADE naming.
- Any required naming alignments or aliases are identified.

---

## Definition of Done

- WBS tasks are checked off and the glossary + recommendation are written and ready to feed the data model work.
