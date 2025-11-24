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
- `ADE_VENVS_DIR` – ensure the directory exists and contains the virtual
  environments produced by the build pipeline
  (`${ADE_VENVS_DIR}/<workspace>/<config>/<build_id>`). Without the venv the
  runner will emit `run.completed` with `exit_code=2` and an error message.

## 3. Release sequence

1. Apply database migrations.
2. Deploy the updated API container.
3. Verify health probes and log output for the new router registration
   (`ade_api.features.runs.router`).
4. Trigger a dry-run execution (`dry_run=true`) to verify streaming events
   and database persistence.
5. Notify frontend teams that the API is live so they can schedule their
   UI integration.

## 4. Rollback strategy

- If the deployment fails before database migrations run, redeploy the
  previous container image.
- If migrations succeeded but the service misbehaves, roll back the image
  and leave the schema in place; the new tables are additive and unused by
  the prior build.
- Capture `run_logs` rows for debugging before redeploying to avoid losing
  incident context.
