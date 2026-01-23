# ADE Worker (DB-backed, no broker)

Minimal, reliable worker that processes **run** records and provisions reusable
**environment** rows stored in a database.

Supported databases:
- SQL Server / Azure SQL

## How it works

- The API inserts rows into `runs` with `status=queued`.
- The worker ensures matching `environments` rows (keyed by `deps_digest`) and claims them
  by setting `status=building`.
- The worker only claims runs whose environment is `ready`, setting run status to `running`.
- Runs use a **lease** (`claim_expires_at`) with periodic **heartbeats** and retry backoff.
- Environments transition to `ready`/`failed`; runs transition to `succeeded`/`failed`.
- Dependency changes create **new environments** (no in-place rebuilds).
- Successful runs persist `run_metrics`, `run_fields`, and `run_table_columns` from `engine.run.completed`.

## Run

```bash
export ADE_SQL_HOST="sql"
export ADE_SQL_PORT="1433"
export ADE_SQL_DATABASE="ade"
export ADE_SQL_USER="sa"
export ADE_SQL_PASSWORD="YourStrong!Passw0rd"
python -m ade_worker
```

## Important env vars

- `ADE_SQL_HOST`, `ADE_SQL_PORT`, `ADE_SQL_DATABASE`, `ADE_SQL_USER`, `ADE_SQL_PASSWORD`
- `ADE_DATABASE_AUTH_MODE` (optional; `managed_identity` for Azure SQL)
- `ADE_DATA_DIR` (default `./data`)
- `ADE_ENGINE_PACKAGE_PATH` (default `ade-engine @ git+https://github.com/clac-ca/ade-engine@main`; accepts local path or pip spec)
- `ADE_WORKER_CONCURRENCY` (default: conservative auto)
- `ADE_WORKER_LEASE_SECONDS` (default `900`)
- `ADE_WORKER_ENABLE_GC` (default `1` for single-host)
- `ADE_WORKER_GC_INTERVAL_SECONDS` (default `3600`)
- `ADE_WORKER_ENV_TTL_DAYS` (default `30`)
- `ADE_WORKER_RUN_ARTIFACT_TTL_DAYS` (default `30`)

## Schema

See `ade_worker/schema.py` for table definitions.
The worker never creates tables; run migrations via ade-api before starting ade-worker.

## Garbage collection

GC is optional and safe-by-default:

- Environments are deleted only when the configuration is **not active**,
  the environment is cold (`last_used_at` / `updated_at` older than TTL),
  and no queued/running runs reference it.
- Run artifacts are deleted only for terminal runs older than the TTL.

In multi-worker deployments, enable GC on **exactly one** worker by setting
`ADE_WORKER_ENABLE_GC=1` on that instance (set `0` elsewhere).
