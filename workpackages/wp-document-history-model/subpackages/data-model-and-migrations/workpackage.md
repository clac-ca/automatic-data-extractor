# Work Package: Data Model and Migrations

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - WBS checkboxes are for implementation execution; do not mark complete during planning.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Translate the chosen common architecture into a target schema and a clean migration plan. Focus on removing nonessential complexity (idempotency_keys, documents.version) and consolidating change-feed migrations into a single source of truth.

### Scope

- In:
  - Target schema for documents, document_versions, and document_changes.
  - Decision on audit_log presence and structure (if any).
  - Migration plan to remove `idempotency_keys` and `documents.version`.
  - Merge change-feed migrations into one consolidated migration.
  - Keep DB table naming as files/file_versions with API terminology mapping to documents.
  - Update file kind enum values to standard set: input, output, log, export.
  - Standardize file naming keys and storage metadata fields for intuitive behavior.
- Out:
  - API/stream contract updates (handled in API subpackage).

### Work Breakdown Structure (WBS)

1.0 Schema changes + migration
  1.1 Alembic migration
    - [x] Drop `idempotency_keys`.
    - [x] Drop `files.version`, `files.doc_no`, and `files.expires_at`.
    - [x] Rename `files.parent_file_id` -> `files.source_file_id`.
    - [x] Rename `file_versions.blob_version_id` -> `storage_version_id` (nullable).
    - [x] Update `files.kind` values to input/output/log/export.
    - [x] Normalize `files.name_key` values by kind rule.
    - [x] Backfill `file_versions.content_type` for generated outputs.
  1.2 ORM + repository updates
    - [x] Update SQLAlchemy models to match the new schema.
    - [x] Update document/run services that reference removed/renamed fields.
2.0 Data safety + ops notes
  2.1 Operational notes
    - [x] Document cursor reset/data loss impacts in docs or runbook.
    - [x] Note required refresh/rebuild steps after migration.

### Open Questions

- Resolved: Keep document_changes for realtime; audit_log is optional for compliance/history only.
- Resolved: Keep DB table names (files/file_versions) and map to documents terminology in API/docs.
- Resolved: Drop `expires_at`; blob lifecycle is the source of truth.
- Resolved: Rename `parent_file_id` to `source_file_id` for clarity.
- Resolved: Drop `doc_no` (IDs are sufficient; simplifies uploads).

### Outputs

#### Target schema decisions

- Tables remain `files` / `file_versions` / `document_changes`.
- `files.kind` values: `input`, `output`, `log`, `export`.
- `files.name` is display-only; `files.name_key` is an internal unique key derived by kind:
  - input: normalized filename
  - output: `output:<source_file_id>` (or `output:<run_id>` if outputs are per-run)
  - log: `log:<run_id>`
  - export: `export:<export_job_id>`
- Rename `files.parent_file_id` -> `files.source_file_id`.
- Drop `files.expires_at`.
- Drop `files.version`.
- Drop `files.doc_no`.
- Rename `file_versions.blob_version_id` -> `file_versions.storage_version_id` and store actual storage version id (nullable).
- Enforce `file_versions.content_type` populated for generated outputs.
- Keep `document_changes` as a flat cursor table for realtime deltas.
- Audit history remains optional; no audit_log by default.

#### Migration plan summary

- Collapse document change-feed migrations into a single migration that:
  - drops legacy document event NOTIFY artifacts
  - creates `document_changes` flat table + `record_document_change()` + triggers
- Schema simplifications:
  - drop `files.version`
  - drop `files.expires_at`
  - rename `files.parent_file_id` -> `files.source_file_id`
  - rename `file_versions.blob_version_id` -> `storage_version_id`
  - update `files.kind` values from `document` -> `input` (and add `log`, `export`)
  - normalize `files.name_key` by kind rule
  - backfill output `content_type`
- Data impact notes:
  - cursor reset expected; UI should refetch after migration
  - backfills are deterministic and can run in a single migration step for small datasets

---

## Acceptance Criteria

- A target schema diagram or table list exists with the chosen common structure.
- Migration steps are documented, including consolidation of change-feed migrations.
- The plan explicitly calls out removal of idempotency_keys and documents.version.
- Operational impacts (cursor resets, data loss) are clearly documented.

---

## Definition of Done

- The migration plan is complete, consistent with the terminology package, and ready for implementation.
