# Deployment checklist for ADE Runs

Use this runbook when rolling the runs API to staging or production. It
extends the general admin guide with migration ordering, configuration
flags, and rollback considerations.

## 1. Pre-deploy validation

- Confirm the target environment includes the Alembic migration
  `apps/ade-api/migrations/versions/0002_runs_tables.py`.
- Run `ade ci` locally and ensure the backend image builds with the new
  FastAPI routers mounted (`/api/v1/configs/{config_id}/runs`, `/api/v1/runs/...`).
- Review `docs/ade_runs_api_spec.md#manual-qa-checklist` and run at least
  one streaming and one non-streaming scenario against staging.

## 2. Configuration flags

- `ADE_SAFE_MODE` – if enabled, the service will short-circuit run
  execution and return a validation error. Disable the flag in production
  to permit engine execution. Document the toggle in your change
  management system when flipping it.
- `ADE_VENVS_DIR` – ensure the directory exists on local storage and
  matches the path used by the builder
  (`${ADE_VENVS_DIR}/<workspace>/<config>/<build_id>/.venv`). Without the
  venv the runner will emit `run.completed` with `exit_code=2` and an error
  message (hydration will recreate it if DB metadata is intact).

## 3. Release sequence

1. Apply database migrations.
2. Deploy the updated API container.
3. Verify health probes and log output for the new router registration
   (`ade_api.features.runs.router`).
4. Trigger a dry-run execution (`dry_run=true`) to verify streaming events
   and database persistence.
5. Notify frontend teams that the API is live so they can schedule their
   UI integration.

## 4. Rebuilds and troubleshooting

- **Trigger rebuilds:** POST `/api/v1/workspaces/{workspace}/configurations/{config}/builds` (optionally `{"stream":true}`) or submit a run with `force_rebuild=true`. Each rebuild produces a new `build_id` and venv under `ADE_VENVS_DIR`.
- **Diagnose build failures:** Check build status via `GET /api/v1/builds/{build_id}` and attach to the run event stream (`/api/v1/runs/{run_id}/events?stream=true`) to read build events + `console.line` (scope `build`). The marker `ade_build.json` under `ADE_VENVS_DIR/<ws>/<cfg>/<build_id>/.venv` captures fingerprint/versions.
- **Diagnose hydration failures:** The worker will attempt to hydrate the venv locally from DB metadata; errors surface as run 409s or engine exits. Ensure `ADE_VENVS_DIR` is writable/local and has free space; deleting a stale build folder is safe—the next run rehydrates it.
- **Local cleanup:** It is safe to delete old build folders under `ADE_VENVS_DIR` (prefer keeping the active `build_id`). Cache pruning does not affect correctness; the system will recreate missing venvs on demand.

## 4. Rollback strategy

- If the deployment fails before database migrations run, redeploy the
  previous container image.
- If migrations succeeded but the service misbehaves, roll back the image
  and leave the schema in place; the new tables are additive and unused by
  the prior build.
- Capture the run `events.ndjson` files (or download via `/runs/{run_id}/logfile`)
  for debugging before redeploying to avoid losing incident context.
