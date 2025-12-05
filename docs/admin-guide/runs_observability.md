# Observing ADE Runs

This guide explains how administrators inspect ADE run activity while the
feature remains backend-only. Use these steps when troubleshooting
production incidents or validating that new workspaces can execute the
engine successfully.

## 1. Streaming an active run

The runs API mirrors the OpenAI streaming pattern and exposes
newline-delimited JSON events. When the caller enables `stream: true`, the API
emits lifecycle notifications (`run.queued`, `run.start`, `console.line`,
`run.complete`) and forwards all `engine.*` telemetry.

```bash
http --stream POST :8000/api/v1/configurations/$CONFIG_ID/runs stream:=true \
  "options:={\"dry_run\": false}"
```

Key things to watch while streaming:

- The first `run.queued`/`run.start` events confirm the database row exists and provide the final
  `run_id` for follow-up queries.
- `console.line` events include the ADE engine stdout; store the NDJSON output
  alongside ticket timelines when escalating to engineering.
- `engine.run.summary` carries the authoritative run summary (with supporting `engine.table.summary`/`engine.sheet.summary`/`engine.file.summary` events); `run.complete` includes the exit code and error message if the engine
  failed. Capture those payloads in the incident record.

## 2. Polling run status without streaming

For asynchronous automation or when safe-mode blocks execution, poll the
non-streaming endpoints:

1. Trigger the run with `stream: false`; the response body mirrors the
   `Run` schema documented in `docs/ade_runs_api_spec.md`.
2. Poll `/api/v1/runs/{run_id}` until the `status` transitions from
   `queued`/`running` to a terminal state.
3. Retrieve the raw run event log via `/api/v1/runs/{run_id}/events/download`
   (legacy `/logs` remains as an alias) to review console output and
   events captured during execution.

## 3. Direct database inspection

When the API is unavailable you can read the SQLite/PostgreSQL tables
directly. The table layout matches the SQLAlchemy models in
`apps/ade-api/src/ade_api/features/runs/models.py`.

```sql
SELECT id, status, exit_code, started_at, finished_at
FROM runs
WHERE configuration_id = :configuration_id
ORDER BY created_at DESC
LIMIT 20;
```

> ⚠️ Database writes should still go through the service. Avoid deleting
> or mutating rows manually; escalate to engineering for remediation.

## 4. CLI and automation follow-ups

The repository does not yet surface runs through the developer tooling.
Track ADE-CLI-11 to add `scripts/npm-runs.mjs` with helpers for
`runs:list`, `runs:logs`, and `runs:tail`. Update this guide once the
commands land so on-call engineers can rely on them instead of raw HTTP
calls.

## 5. Monitoring configuration builds

Build activity is emitted through the unified run event stream. Use the same
troubleshooting workflow you use for runs:

1. Trigger a build (or run with `stream: true`) using
   `POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds`
   or the run creation endpoint. Watch for `build.queued`,
   `build.start`, `build.phase.start`, `build.complete`, and `console.line`
   events (`payload.scope: "build"`).
2. For status snapshots, hit `/api/v1/builds/{build_id}`. For history,
   use `GET /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds`
   with optional `status` filters. For live logs/events,
   attach to `/api/v1/runs/{run_id}/events?stream=true&after_sequence=<cursor>`
   (build + run + console output in one ordered stream).
3. Database fallbacks mirror runs: inspect the `builds` table if the API is
   unavailable. Build log polling endpoints are deprecated in favor of the run
   event stream.

Refer to the event catalog in `.workpackages/ade-event-system-refactor/020-EVENT-TYPES-REFERENCE.md`
for canonical payloads and the decision log in `docs/workpackages/WP12_ade_runs.md`
for current operational policies (safe mode, deprecation schedule).
