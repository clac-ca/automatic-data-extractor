# Deployment checklist for ADE Runs

Use this runbook when rolling the runs API to staging or production. It
extends the general admin guide with migration ordering, configuration
flags, and rollback considerations.

## 1. Pre-deploy validation

- Confirm the target environment includes the Alembic migration
  `apps/ade-api/migrations/versions/0004_environments_runs_no_builds.py`.
- Run `ade ci` locally and ensure the backend image builds with the new
  FastAPI routers mounted (`/api/v1/configurations/{configurationId}/runs`, `/api/v1/runs/...`).
- Review `docs/ade_runs_api_spec.md#manual-qa-checklist` and run at least
  one queued run + SSE tail scenario against staging.

## 2. Configuration flags

- `ADE_SAFE_MODE` – if enabled, the service will short-circuit run
  execution and return a validation error. Disable the flag in production
  to permit engine execution. Document the toggle in your change
  management system when flipping it.
- `ADE_VENVS_DIR` – ensure the directory exists on local storage and
  matches the path used by the worker
  (`${ADE_VENVS_DIR}/<workspace>/<config>/<deps_digest>/<environment_id>/.venv`).
  If the venv is missing, the worker will provision a new environment.

## 3. Release sequence

1. Apply database migrations.
2. Deploy the updated API container.
3. Deploy or restart the worker process/container so queued jobs can execute.
4. Verify health probes and log output for the new router registration
   (`ade_api.features.runs.router`).
5. Trigger a dry-run execution (`dry_run=true`) and tail
   `/runs/{runId}/events/stream` to verify event logs and database persistence.
6. Notify frontend teams that the API is live so they can schedule their
   UI integration.

## 4. Environments and troubleshooting

- **Trigger new environments:** Environments are rebuilt when dependency manifests change (new `deps_digest`) or when the environment is missing on disk. There is no build API; deleting a stale environment folder is safe—the worker recreates it on demand.
- **Diagnose environment failures:** Inspect the environment log on disk (`.../venvs/<workspace>/<config>/<deps_digest>/<environment_id>/logs/events.ndjson`) alongside the worker logs. Environment events use the `environment.*` namespace.
- **Diagnose missing venvs:** If the environment directory is missing, the worker requeues provisioning and the run waits until it becomes `ready`. Ensure the venv root is writable/local and has free space.
- **Local cleanup:** It is safe to delete old environment folders under `ADE_VENVS_DIR` once they are no longer referenced by queued/running runs. The worker GC can handle this automatically.

## 4. Rollback strategy

- If the deployment fails before database migrations run, redeploy the
  previous container image.
- If migrations succeeded but the service misbehaves, roll back the image
  and leave the schema in place; the new tables are additive and unused by
  the prior build.
- Capture the run `events.ndjson` files (or download via `/runs/{runId}/events/download`)
  for debugging before redeploying to avoid losing incident context.
