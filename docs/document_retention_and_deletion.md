# Document expiration and cleanup notes

## Summary
ADE now applies a simple expiration policy to every uploaded document and
records manual deletions. New records carry an `expires_at` timestamp computed
at ingest time so operators know when the file should disappear. When an
operator deletes a document through the API, the service removes the stored
bytes and stamps audit metadata (`deleted_at`, `deleted_by`,
`delete_reason`). The defaults aim to keep disk usage predictable while leaving
space for future automation that actually purges expired bytes.

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
- **Cleanup automation** – A background purge worker is still forthcoming.
  Until it exists, use the expiration timestamp plus the manual deletion API to
  keep storage tidy.

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

Changing the default only affects new uploads; existing rows keep their stored
`expires_at` value.

---

## Cleanup expectations

Automated deletion work remains on the roadmap. When we implement it, the
worker can:

1. Query for documents where `expires_at <= now` and the file still exists.
2. Delete the file from disk and record an audit trail that preserves
   metadata.
3. Surface metrics (count of purged files, reclaimed bytes) so operators can
   confirm the system is healthy.

In the meantime, operators can run ad-hoc scripts or cron jobs that read the
stored timestamps and invoke the manual deletion API. Keep audit requirements
in mind: log who initiated the purge and when so the `deleted_by` field stays
trustworthy.

---

## Open questions

- Do we need a short grace period for files attached to running jobs? Current
  behaviour assumes jobs finish quickly; revisit if that changes.
- Should the API expose a convenience endpoint for querying soon-to-expire
  documents to simplify manual cleanup scripts?
- Once deletion automation lands, decide how to communicate purge events back
  to callers (webhooks, metrics, or change feed).
