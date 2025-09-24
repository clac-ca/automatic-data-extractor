# 🚧 ADE Backend Rewrite – Next Focus

## Status Snapshot
- FastAPI package now lives under `backend/api` with imports, tooling, and docs updated.
- Jobs service still runs synchronously and records metrics/logs for completed runs.
- Retention/backfill work for job metadata and extracted tables remains outstanding.

## Goal for This Iteration
Introduce a retention policy for jobs, logs, and extracted tables so stale artefacts are
automatically purged according to configuration.

## Scope
1. **Configuration & plumbing**
   - Add retention knobs to settings (days to keep jobs, logs, tables) and expose them via docs.
   - Ensure scheduler/maintenance entry points read the new values.
2. **Purge implementation**
   - Extend the maintenance/purge service to delete expired jobs, logs, and extracted tables.
   - Persist a summary of the sweep (counts, reclaimed bytes) for observability.
3. **API & tests**
   - Provide endpoints or CLI hooks to trigger the purge manually.
   - Add integration tests covering automatic startup sweep and manual invocation.
4. **Docs & communication**
   - Update README and relevant plans to describe the retention behaviour and configuration.
   - Note follow-up tasks for deployment teams (e.g., updating environment variables, alerting).

## Definition of Done
- Configurable retention settings exist with sensible defaults.
- Purge routine removes jobs, logs, and tables older than the configured threshold.
- Tests verify both scheduled and manual purges.
- Documentation reflects the retention feature and downstream reminders are captured.
