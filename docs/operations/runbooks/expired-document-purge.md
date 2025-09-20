---
Audience: Platform administrators, Support teams
Goal: Restore automated document purge behaviour and reclaim storage when scheduled sweeps lag or fail.
Prerequisites: Shell access to the ADE deployment, ability to run Python modules, and admin credentials for the API.
When to use: Invoke when `/health` reports purge failures, storage usage spikes, or expired documents remain on disk past their policy window.
Validation: Verify purge summaries in `/health`, confirm event logs record deletions, and ensure storage usage decreases after remediation.
Escalate to: Platform owner or infrastructure team if manual runs fail or storage remains constrained after completing the steps.
---

# Runbook: expired document purge

## Triggers

- `/health` shows `purge.status != "ok"` or stale `completed_at` timestamps.
- Storage utilisation alarms fire for the documents volume.
- Support tickets report documents persisting beyond their `expires_at` values.

## Diagnostics

1. Inspect the latest scheduler status:
   - `curl https://ade.example.com/health | jq '.purge'`
   - Confirm `interval_seconds`, `started_at`, and `completed_at` timestamps.
2. Review structured logs for `Automatic purge run` entries. Missing logs suggest the scheduler is disabled.
3. List pending expired documents via a Python shell:
   ```bash
   python - <<'PY'
   from backend.app.db import get_sessionmaker
   from backend.app.models import Document
   from datetime import datetime, timezone

   session_factory = get_sessionmaker()
   with session_factory() as session:
       rows = (
           session.query(Document)
           .filter(Document.expires_at <= datetime.now(timezone.utc))
           .filter(Document.deleted_at.is_(None))
           .order_by(Document.expires_at)
           .limit(20)
           .all()
       )
       for row in rows:
           print(row.document_id, row.expires_at)
   PY
   ```
4. Confirm configuration settings via `ADE_PURGE_SCHEDULE_*` environment variables (see [Environment variables](../../reference/environment-variables.md)).

## Resolution

1. **Manual purge:**
   - Run `python -m backend.app.maintenance.purge --limit 100` to process a batch.
   - Use `--dry-run` first when operating in production.
2. **Scheduler reset:**
   - If the scheduler is disabled, set `ADE_PURGE_SCHEDULE_ENABLED=true`, ensure `ADE_PURGE_SCHEDULE_INTERVAL_SECONDS` is reasonable, and restart the service.
   - Verify startup logs show `Automatic purge run completed`.
3. **Address missing files:**
   - Manual purge output may report `missing_paths`. Investigate filesystem drift before rerunning to avoid repeated failures.
4. **Document escalations:**
   - If expired documents must remain temporarily (e.g., legal hold), annotate tickets and adjust the retention override rather than deleting.

## Validation

- Call `GET /health` and ensure the `purge` block reflects the latest run with `status: "ok"` and current timestamps.
- Review `document.deleted` events via `GET /events?event_type=document.deleted&source=scheduler` to confirm purge actions recorded correctly.
- Check disk utilisation to ensure reclaimed bytes align with run summaries.

## Escalation

Escalate with logs, health output, and the manual purge summary when:

- Manual purge runs fail with repeated exceptions.
- Scheduler restarts do not produce new purge summaries within twice the configured interval.
- Storage remains critically high after successful purges (indicates retention window may be too long or new uploads are overwhelming capacity).
