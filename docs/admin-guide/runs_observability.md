# Observing ADE Runs

This guide explains how administrators inspect ADE run activity while the
feature remains backend-only. Use these steps when troubleshooting
production incidents or validating that new workspaces can execute the
engine successfully.

## 1. Streaming an active run

The runs API mirrors the OpenAI streaming pattern and exposes
newline-delimited JSON events. When the caller enables `stream: true`, the API
emits lifecycle notifications (`run.created`, `run.started`, `run.log`,
`run.completed`).

```bash
http --stream POST :8000/api/v1/configs/$CONFIG_ID/runs stream:=true \
  "options:={\"dry_run\": false}"
```

Key things to watch while streaming:

- `run.created` confirms the database row exists and provides the final
  `run_id` for follow-up queries.
- `run.log` events include the ADE engine stdout; store the NDJSON output
  alongside ticket timelines when escalating to engineering.
- `run.completed` includes the exit code and error message if the engine
  failed. Capture the payload in the incident record.

## 2. Polling run status without streaming

For asynchronous automation or when safe-mode blocks execution, poll the
non-streaming endpoints:

1. Trigger the run with `stream: false`; the response body mirrors the
   `Run` schema documented in `docs/ade_runs_api_spec.md`.
2. Poll `/api/v1/runs/{run_id}` until the `status` transitions from
   `queued`/`running` to a terminal state.
3. Fetch buffered logs from `/api/v1/runs/{run_id}/logs?after_id=<last_id>`
   to tail progress. The endpoint returns batches of 1000 log entries in
   chronological order.

## 3. Direct database inspection

When the API is unavailable you can read the SQLite/PostgreSQL tables
directly. The table layout matches the SQLAlchemy models in
`apps/api/app/features/runs/models.py`.

```sql
SELECT id, status, exit_code, started_at, finished_at
FROM runs
WHERE config_id = :config_id
ORDER BY created_at DESC
LIMIT 20;
```

```sql
SELECT id, created_at, stream, message
FROM run_logs
WHERE run_id = :run_id
ORDER BY id ASC;
```

> ⚠️ Database writes should still go through the service. Avoid deleting
> or mutating rows manually; escalate to engineering for remediation.

## 4. CLI and automation follow-ups

The repository does not yet surface runs through the developer tooling
(`npm run workpackage`, `scripts/npm-*.mjs`). Track ADE-CLI-11 to add
`scripts/npm-runs.mjs` with helpers for `runs:list`, `runs:logs`, and
`runs:tail`. Update this guide once the commands land so on-call
engineers can rely on them instead of raw HTTP calls.

## 5. Monitoring configuration builds

The builds API now mirrors the runs interface with streaming NDJSON events
and polling endpoints. Use the same troubleshooting workflow when verifying
environment preparation:

1. Trigger a build with `stream: true` using
   `POST /api/v1/workspaces/{workspace_id}/configs/{config_id}/builds`.
   Watch for `build.created`, `build.step`, `build.log`, and
   `build.completed` events.
2. When automation needs to poll instead of stream, hit
   `/api/v1/builds/{build_id}` for status snapshots and
   `/api/v1/builds/{build_id}/logs` for buffered output (supports `after_id`).
3. Database fallbacks mirror runs: inspect the `builds` and `build_logs`
   tables if the API is unavailable. See
   `apps/api/app/features/builds/models.py` for column definitions.

Refer to `docs/ade_builds_api_spec.md` for the full schema/event catalog and
the decision log in `docs/workpackages/WP12_ade_runs.md` for current
operational policies (safe mode, deprecation schedule).
