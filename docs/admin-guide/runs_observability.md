# Observing ADE Runs

This guide explains how administrators inspect ADE run activity while the
feature remains backend-only. Use these steps when troubleshooting
production incidents or validating that new workspaces can execute the
engine successfully.

## 1. Downloading run logs

The runs API exposes newline-delimited JSON events via `/runs/{runId}/events/download`.
Create the run first, then download the log to inspect `run.start`,
`run.engine.*`, `console.line`, and `run.complete` events alongside the
`engine.*` telemetry payloads.

```bash
# 1) Create the run
http POST :8000/api/v1/configurations/$CONFIG_ID/runs \
  "options:={\"dry_run\": false}"

# 2) Download events
http GET :8000/api/v1/runs/$RUN_ID/events/download
```

Key things to watch while reviewing logs:

- `run.start` arrives when the worker claims the job.
- `console.line` events include the ADE engine stdout; store the NDJSON output
  alongside ticket timelines when escalating to engineering.
- `engine.run.completed` carries the full run payload (with supporting `engine.table.summary`/`engine.sheet.summary`/`engine.file.summary` events); `run.complete` is the worker’s terminal event with `status`, `exit_code`, and optional `error_message`. `run.engine.*` events are subprocess telemetry. Capture those payloads in the incident record.

## 2. Polling run status without streaming

For asynchronous automation or when safe-mode blocks execution, poll the
non-streaming endpoints:

1. Trigger the run; the response body mirrors the
   `Run` schema documented in `docs/ade_runs_api_spec.md`.
2. Poll `/api/v1/runs/{runId}` until the `status` transitions from
   `queued`/`running` to a terminal state.
3. Retrieve the raw run event log via `/api/v1/runs/{runId}/events/download`
   to review console output and events captured during execution.

## 3. Direct database inspection

When the API is unavailable you can read the Postgres tables
directly. The table layout matches the SQLAlchemy models in
`apps/ade-api/src/ade_api/models/run.py`.

```sql
SELECT id, status, exit_code, started_at, completed_at
FROM runs
WHERE configuration_id = :configuration_id
ORDER BY created_at DESC
LIMIT 20
;
```

> ⚠️ Database writes should still go through the service. Avoid deleting
> or mutating rows manually; escalate to engineering for remediation.

## 4. CLI and automation follow-ups

The repository does not yet surface runs through the developer tooling.
Track ADE-CLI-11 to add `scripts/npm-runs.mjs` with helpers for
`runs:list`, `runs:logs`, and `runs:tail`. Update this guide once the
commands land so on-call engineers can rely on them instead of raw HTTP
calls.

## 5. Monitoring environments

Environment provisioning is worker-owned and not exposed via a public API.
For visibility:

1. Inspect worker logs for `environment.*` events.
2. Check environment log files on disk:
   `.../venvs/<workspace>/<config>/<deps_digest>/<environment_id>/logs/events.ndjson`.
3. Use the `environments` table for status snapshots and troubleshooting.

Refer to the event catalog in `.workpackages/ade-event-system-refactor/020-EVENT-TYPES-REFERENCE.md`
for canonical payloads and the decision log in `docs/workpackages/WP12_ade_runs.md`
for current operational policies (safe mode, deprecation schedule).
