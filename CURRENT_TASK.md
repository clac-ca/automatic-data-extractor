# 🚧 ADE Backend Rewrite – Next Focus

## Status Snapshot
- Synchronous `JobsService` persists metrics/logs, replaces extracted tables, and
  raises structured failures when the stub processor errors.
- Results router/service expose job and document table listings, returning 409
  for pending/failed runs and 404 for missing artefacts.
- End-to-end tests span upload → job → results, including deletion and failure
  scenarios.

## Goal for This Iteration
Introduce baseline retention so job metadata, logs, and extracted tables do not
grow without bound now that the synchronous pipeline is in place.

## Scope
1. **Retention policies**
   - Add configurable retention windows for jobs, job logs/metrics, and
     associated extracted tables.
   - Ensure purging skips recent/succeeded records that fall within the window.
2. **Cleanup execution path**
   - Expose a deterministic cleanup entry point (CLI task or scheduled service
     hook) that removes expired jobs/tables and reports summary metrics.
   - Cover purge behaviour with tests that seed aged records and verify retained
     items remain intact.
3. **Documentation & backlog**
   - Document the retention settings in `BACKEND_REWRITE_PLAN.md` and README.
   - Capture follow-ups for permission seeding and timeline rebuild once
     retention is live.

## Definition of Done
- Configurable cleanup removes expired jobs and tables without touching recent
  runs.
- Automated tests cover purge scenarios and ensure metrics/logs persist for
  retained jobs.
- Documentation reflects the retention behaviour and records remaining backlog
  items.
