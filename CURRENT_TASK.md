# Current Task — Manual document deletion API

## Goal
Give operators a supported way to remove uploaded document bytes while keeping an
audit trail in the metadata.

## Background
- Documents now carry an `expires_at` timestamp but bytes stick around until
  someone deletes them manually.
- Operators currently rely on ad-hoc scripts. We should expose a sanctioned
  endpoint that enforces validation and records who performed the deletion.
- The retention notes in `docs/document_retention_and_deletion.md` call out soft
  deletion plus audit logging as the next milestone.

## Scope
- Extend the `documents` table with soft-delete fields (`deleted_at`,
  `deleted_by`, `delete_reason`) stored as ISO 8601 timestamps and free-form
  text.
- Implement a document service helper that marks the metadata, removes the file
  from disk when it exists, and no-ops when the file has already vanished.
- Add `DELETE /documents/{document_id}` to FastAPI. Require a `deleted_by`
  string and optional `delete_reason` body payload. Return 200 with the updated
  document record.
- Ensure existing listings exclude deleted rows by default, with an option to
  include them later when we expose admin views.
- Tests should cover successful deletions, repeated calls, and attempts to
  delete missing documents.

## Out of scope
- Background purging of expired files (tracked separately).
- Legal hold or retention exception handling beyond the soft delete fields.
- Bulk deletion endpoints.

## Deliverables
1. SQLAlchemy model update introducing the deletion metadata columns.
2. Service function that performs the soft delete and removes on-disk files.
3. FastAPI route and schema updates accepting deletion payloads and omitting
   deleted rows from document listings.
4. Tests proving the happy path, double-deletes, and error conditions.
5. Documentation updates (README, glossary, retention notes) describing the new
   endpoint and metadata fields.

## Definition of done
- Deleted documents retain metadata with `deleted_at` and `deleted_by` set and
  files removed when present.
- Uploading a file after deletion creates a fresh record (uploads always
  allocate new storage).
- Listing endpoints skip deleted documents by default.
- Tests and docs describe the behaviour and edge cases clearly.
