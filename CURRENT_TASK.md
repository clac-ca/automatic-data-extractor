# Current Task — Observe automatic purge scheduler

## Goal
Surface lightweight telemetry for the in-process purge scheduler so operators
can confirm sweeps are running and reclaiming disk space without tailing logs.

## Background
- The API now runs an automatic purge sweep on startup and at a configurable
  interval. Results are logged with a structured payload (`summary={...}`).
- Operators want a simple way to confirm the loop is still firing (and how much
  data it reclaims) without parsing historical logs.
- The purge CLI remains available for manual runs and dry-runs, but the default
  workflow should hinge on the automatic scheduler.

## Scope
- Persist the "last purge" status inside ADE itself (SQLite table preferred over
  external services or ad-hoc files) so the data survives restarts and ships
  inside the container.
- Expose the stored status via a small read-only API endpoint and wire it into
  the health router, or extend `/health` with a purge section.
- Consider emitting a Prometheus metric for processed count/bytes reclaimed
  while keeping the implementation simple (no new dependencies if avoidable).
- Document how operators can validate the scheduler locally (e.g. by shortening
  the interval) and where to look in the UI/API for status updates.

## Out of scope
- Replacing the existing structured logging. Keep it as-is for historical
  troubleshooting.
- Building a brand-new monitoring stack; expose a hook that integrates with the
  existing tooling.
- UI polish beyond surfacing raw status (charts/dashboards can wait).

## Deliverables
1. Durable storage for the most recent automatic purge summary (success/failure,
   processed count, missing files, bytes reclaimed, timestamp).
2. API surface (health endpoint or dedicated route) that returns the stored
   summary so operators/tools can query it programmatically.
3. Documentation updates covering how to tweak the interval for smoke tests,
   how to read the status, and guidance for alerting on stale runs.

## Definition of done
- Operators know where to fetch the latest purge summary without scraping logs.
- Instructions describe how to shorten the interval locally to verify the
  scheduler.
- Retention docs and README reference the new status surface.
