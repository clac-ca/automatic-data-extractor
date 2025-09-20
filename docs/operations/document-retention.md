---
Audience: Platform administrators, Support teams
Goal: Explain ADE's document retention defaults, overrides, and purge automation so operators keep storage predictable.
Prerequisites: Admin access to ADE, ability to run CLI utilities, and familiarity with environment management.
When to use: Review before adjusting retention windows, troubleshooting missing documents, or auditing purge behaviour.
Validation: After changes, upload a test document, confirm `expires_at`, and verify the purge summary on `GET /health` reflects the new settings.
Escalate to: Platform owner if documents disappear unexpectedly or the purge scheduler fails repeatedly.
---

# Document retention policy

ADE treats every upload as an auditable record with a deterministic expiration date. Retention behaviour is implemented across `backend/app/config.py`, `backend/app/services/documents.py`, `backend/app/maintenance/autopurge.py`, and surfaced via `backend/app/routes/health.py`.

## Policy highlights

- **Default window:** Documents expire 30 days after upload (`ADE_DEFAULT_DOCUMENT_RETENTION_DAYS`).
- **Manual override:** Uploaders may provide an ISO 8601 `expires_at` value when calling `POST /documents`.
- **Persistence:** Resolved `expires_at` values are stored with document metadata and surfaced in every response (`DocumentResponse` schema).
- **Deletion record:** Manual deletions and automatic purges stamp `deleted_at`, `deleted_by`, and `delete_reason`, then emit `document.deleted` events for auditability.

## Upload lifecycle (`backend/app/services/documents.py`)

1. `POST /documents` resolves `expires_at = now + retention_window` unless a valid override is supplied.
2. Overrides must parse as future UTC timestamps; invalid values return HTTP 422 (`error=invalid_expiration`).
3. The chosen value is persisted alongside checksums and returned in the API response.

## Manual deletion (`backend/app/routes/documents.py`)

- Send `DELETE /documents/{document_id}` with JSON `{ "deleted_by": "operator@example.com", "delete_reason": "out-of-scope" }`.
- The service removes on-disk bytes when present and records soft-delete metadata.
- Repeated calls return the same metadata so retrying failed clean-up jobs is safe.
- Every path emits a `document.deleted` event via `backend/app/services/events.py` for traceability.

## Automatic purge scheduler (`backend/app/maintenance/autopurge.py`)

- The API launches a background loop at startup when `ADE_PURGE_SCHEDULE_ENABLED=true`.
- The scheduler optionally runs once immediately (`ADE_PURGE_SCHEDULE_RUN_ON_STARTUP=true`), then every `ADE_PURGE_SCHEDULE_INTERVAL_SECONDS` seconds.
- Each sweep calls `purge_expired_documents` with `event_source="scheduler"`, records results in `maintenance_status`, and logs a structured summary.
- Failures are persisted via `record_auto_purge_failure` so `/health` callers can detect issues.

Validation: After shortening the interval (e.g., export `ADE_PURGE_SCHEDULE_INTERVAL_SECONDS=5` locally), restart ADE, upload a document with near-term expiry, and poll `/health` to watch the `purge` block update.

## Manual purge CLI (`backend/app/maintenance/purge.py`)

Run `python -m backend.app.maintenance.purge` to sweep expired documents on demand.

- `--dry-run` lists candidate documents without deleting them.
- `--limit` caps the number of deletions per invocation.
- Each run emits the same structured summary as the scheduler and records audit events with `source="cli"`.

Use the CLI before deployments or when diagnosing scheduler issues. Disable the automatic scheduler temporarily by setting `ADE_PURGE_SCHEDULE_ENABLED=false` and restarting, then re-enable once remediation completes.

## Escalation triggers

Escalate to platform owners when:

- `/health` reports repeated purge failures or stale timestamps.
- Documents vanish before their recorded `expires_at`.
- Manual CLI runs report large counts of missing files (`missing_paths > 0`).
- Purge summaries stop appearing in structured logs.
