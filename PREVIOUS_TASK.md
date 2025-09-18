# Current Task — Automated purge of expired documents

## Goal
Ship a supported maintenance command that removes expired document bytes and
marks their metadata using the existing soft-delete fields so operators can keep
`var/documents/` tidy without hand-written scripts.

## Background
- Every upload now stores an `expires_at` timestamp and the manual deletion API
  updates `deleted_at`, `deleted_by`, and `delete_reason` while removing the
  file from disk.
- Storage will keep growing until someone invokes the delete endpoint or
  removes files manually. Operators want a sanctioned way to sweep expired
  documents on a schedule.
- The document retention notes already call out background purge automation as
  the next milestone. Legal hold support is explicitly out of scope for ADE, so
  we only need to honour `expires_at` and the existing soft-delete markers.

## Scope
- Add a document service helper that queries for documents where
  `expires_at <= now` and `deleted_at IS NULL`, orders them by expiration, and
  yields their metadata in manageable batches.
- Implement a `purge_expired_documents` helper that reuses
  `services.documents.delete_document` to remove files, updates metadata inside
  a transaction, and returns a summary (processed count, files missing on disk,
  bytes reclaimed).
- Create a small CLI module (e.g. `python -m backend.app.maintenance.purge`) that
  opens a database session, runs the purge helper, and prints a human-friendly
  report. Accept `--limit` to cap the number of documents per run and
  `--dry-run` to show what would be removed without mutating data.
- Log and return structured details so future automation (cron, Kubernetes job)
  can alert on failures. Bubble up non-recoverable errors with a non-zero exit
  code.
- Document the command in the README and update
  `docs/document_retention_and_deletion.md` with the automated purge flow.

## Out of scope
- Background scheduling or long-lived worker processes; assume cron or an ops
  job runner will call the CLI.
- Legal hold or retention exception workflows; ADE will continue relying on
  `expires_at` plus manual deletion.
- UI affordances for scheduling or monitoring purge runs.

## Deliverables
1. SQLAlchemy query + helper that exposes expired, undeleted documents in
   batches.
2. `purge_expired_documents` service that deletes due records, tallies
   statistics, and is safe to rerun.
3. CLI entry point under `backend/app/maintenance/` with `--limit` and
   `--dry-run` flags that prints a summary and sets exit codes correctly.
4. Pytest coverage exercising the service and CLI path (success, dry-run,
   missing file cases).
5. Documentation updates describing how and when to run the purge command and
   what operators should expect.

## Definition of done
- Running the CLI without `--dry-run` removes expired files from disk, stamps
  `deleted_at`/`deleted_by`, and reports counts for purged vs. missing files.
- `--dry-run` leaves data untouched while returning the same summary counts.
- Purge runs are idempotent: rerunning immediately yields zero additional work
  and no crashes even if files disappeared between lookup and deletion.
- Tests cover happy path, dry-run, missing file handling, and limit handling.
- README + retention docs describe the new tooling so operators can schedule it.
