# Document expiration and cleanup notes

## Summary
ADE now applies a simple expiration policy to every uploaded document, records
manual deletions, and automatically purges expired bytes from within the API
process. New records carry an `expires_at` timestamp computed at ingest time so
operators know when the file should disappear. When an operator deletes a
document through the API, the automatic scheduler, or the purge CLI, the service
removes the stored bytes and stamps audit metadata (`deleted_at`, `deleted_by`,
`delete_reason`). The defaults aim to keep disk usage predictable while leaving
room for operators to adjust cadence or trigger manual sweeps when needed.

Key points:

- **Default window** – Documents expire 30 days after upload. Override the
  duration globally with `ADE_DEFAULT_DOCUMENT_RETENTION_DAYS`.
- **Manual override** – Callers may provide an ISO 8601 `expires_at` value
  when uploading. The service validates that the timestamp is in the future
  and stores it verbatim.
- **Persistence** – The resolved `expires_at` value lives alongside existing
  document metadata and is returned by all document APIs.
- **Manual deletion** – Operators call `DELETE /documents/{document_id}` with
  a `deleted_by` identifier (and optional `delete_reason`). The API removes the
  file when present, stamps audit metadata, and returns the updated document.
- **Cleanup automation** – The API checks for expired documents on startup and
  then on a configurable cadence. It reuses the soft-delete fields, reports
  missing files, and keeps the audit trail consistent. Operators can still run
  `python -m backend.app.maintenance.purge` manually for dry-runs or ad-hoc
  sweeps.

---

## Default expiration logic

1. `POST /documents` calculates `expires_at = now_utc + ADE_DEFAULT_DOCUMENT_RETENTION_DAYS`.
2. The computed timestamp is persisted with the document metadata and echoed
   in the API response so callers receive immediate confirmation.
3. Tests cover the 30-day default as well as a custom environment override to
   keep the behaviour reproducible.

Because the timestamp is stored as a UTC ISO 8601 string, downstream tooling
can sort or filter documents without worrying about database-specific time
zones.

---

## Manual overrides

- Uploaders may send a form field named `expires_at` alongside the file when
  calling `POST /documents`.
- Accepted values must parse as ISO 8601. Naive timestamps are interpreted as
  UTC. Invalid or past values return HTTP 422 with `error=invalid_expiration`.
- Overrides are stored verbatim; each upload keeps the provided timestamp even
  when the bytes match a prior file.

---

## Manual deletion API

- Send `DELETE /documents/{document_id}` with a JSON body containing
  `deleted_by` (required) and `delete_reason` (optional).
- The service removes the file from disk when present and stamps
  `deleted_at`, `deleted_by`, and `delete_reason` on the document record.
- Repeated calls return the existing metadata so operators can retry cleanup
  jobs without changing the audit trail.
- Soft-deleted documents stay queryable by ID, but list endpoints exclude them
  by default.

---

## Configuration knobs

| Environment variable | Default | Description |
|----------------------|---------|-------------|
| `ADE_DEFAULT_DOCUMENT_RETENTION_DAYS` | `30` | Number of days added to the upload timestamp when no override is provided. |
| `ADE_PURGE_SCHEDULE_ENABLED` | `true` | Toggle the automatic purge loop that runs inside the API service. |
| `ADE_PURGE_SCHEDULE_INTERVAL_SECONDS` | `3600` | Seconds between automatic purge sweeps. |
| `ADE_PURGE_SCHEDULE_RUN_ON_STARTUP` | `true` | Run a purge sweep immediately when the service starts. |

Changing the retention default only affects new uploads; existing rows keep
their stored `expires_at` value. Scheduler-related settings are read on startup,
so restart the API service after tweaking cadence or disabling the loop.

---

## Automatic purge scheduler

The FastAPI process starts a lightweight background loop that sweeps for expired
documents. The behaviour is intentionally simple:

1. When the API boots, ADE runs a purge sweep immediately (unless
   `ADE_PURGE_SCHEDULE_RUN_ON_STARTUP=false`).
2. The scheduler then sleeps for `ADE_PURGE_SCHEDULE_INTERVAL_SECONDS` seconds
   (default: 3600) before sweeping again. Each sweep reuses the same
   `purge_expired_documents` helper as the CLI.
3. Results are logged at INFO level with a structured payload (`summary={...}`)
   so log forwarders and humans see the processed count, missing files, and
   reclaimed bytes. The loop also writes the most recent summary to the
   `maintenance_status` table and exposes it under the `purge` key on
   `GET /health` (status, processed count, missing files, bytes reclaimed,
   timestamps, configured interval, and any error message).

To smoke test the scheduler locally, set `ADE_PURGE_SCHEDULE_INTERVAL_SECONDS`
to a small value (e.g. `5`) before starting the API, upload a throwaway document
that expires soon, and poll `/health`. The `purge` block will update each time a
run completes, making it easy to confirm the loop still fires after restarts or
configuration changes.

Set `ADE_PURGE_SCHEDULE_ENABLED=false` to turn the loop off entirely (for
example, in smoke tests or one-off maintenance).

---

## Automated purge command

`python -m backend.app.maintenance.purge` remains available for on-demand
sweeps. The helper runs entirely within the FastAPI codebase so it inherits the
same validation and audit metadata as the manual deletion API. Use it to perform
dry-runs, trigger an immediate cleanup before deploying, or double-check the
automatic scheduler when diagnosing retention issues.

The command:

1. Queries for documents where `expires_at <= now` and `deleted_at IS NULL`,
   ordered by expiration time.
2. Removes the stored file when it exists and stamps `deleted_at`,
   `deleted_by = "maintenance:purge_expired_documents"`, and
   `delete_reason = "expired_document_purge"` inside a single transaction per
   run.
3. Tallies processed documents, missing files, and reclaimed bytes. Missing
   files are still soft-deleted so metadata stays consistent.

Flags and behaviours:

- `--dry-run` emits the same summary without mutating the database or disk. Use
  it to confirm the candidate set before scheduling destructive runs.
- `--limit` caps how many documents are handled in a single invocation. This is
  useful when sweeping large backlogs gradually.
- The process is idempotent. Rerunning immediately after a purge finds no
  additional work unless new documents expire in the meantime.
- Structured logging (`summary={...}`) and a human-readable report surface the
  same metrics for cron jobs and operators.

---

## Open questions

- Do we need a short grace period for files attached to running jobs? Current
  behaviour assumes jobs finish quickly; revisit if that changes.
- Should the API expose a convenience endpoint for querying soon-to-expire
  documents to simplify manual cleanup scripts?
- Decide whether purge results should surface beyond logs (e.g. Prometheus
  metrics or a change feed) so ops teams can monitor long-running trends.
