# ADE Worker (DB-backed, no broker)

Minimal, reliable worker that processes **run** records and provisions reusable
**environment** rows stored in a database.

Supported databases:
- Postgres

## How it works

- The API inserts rows into `runs` with `status=queued`.
- Postgres triggers `NOTIFY ade_run_queued` when a run is queued.
- Each worker keeps a dedicated `LISTEN` connection and wakes immediately on notifications.
- On wake (or periodic safety sweep), the worker claims runs using
  `SELECT ... FOR UPDATE SKIP LOCKED`.
- For each claimed run, the worker ensures a matching `environments` row exists
  (keyed by `deps_digest`). If the environment is not `ready`, the worker blocks
  on an advisory lock and builds it before running the engine.
- Runs use a **lease** (`claim_expires_at`) with periodic **heartbeats** and retry backoff.
- Environments transition to `ready`/`failed`; runs transition to `succeeded`/`failed`.
- Dependency changes create **new environments** (no in-place rebuilds).
- Successful runs persist `run_metrics`, `run_fields`, and `run_table_columns` from `engine.run.completed`.

## Run

```bash
export ADE_DATABASE_URL="postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable"
export ADE_DATABASE_AUTH_MODE="password"
python -m ade_worker
```

## Important env vars

- `ADE_DATABASE_URL` (canonical SQLAlchemy URL)
- `ADE_DATABASE_AUTH_MODE` (`password` or `managed_identity`)
- `ADE_DATABASE_SSLROOTCERT` (optional CA path for `verify-full`)
- `ADE_DATA_DIR` (default `./data`)
- `ADE_ENGINE_PACKAGE_PATH` (default `ade-engine @ git+https://github.com/clac-ca/ade-engine@main`; accepts local path or pip spec)
- `ADE_WORKER_CONCURRENCY` (default: conservative auto)
- `ADE_WORKER_LEASE_SECONDS` (default `900`)
- `ADE_WORKER_LISTEN_TIMEOUT_SECONDS` (default `60`, safety sweep interval)
- `ADE_WORKER_ENV_TTL_DAYS` (default `30`)
- `ADE_WORKER_RUN_ARTIFACT_TTL_DAYS` (default `30`)

## Schema

See `ade_worker/schema.py` for table definitions.
The worker never creates tables; run migrations via ade-api before starting ade-worker.

## Garbage collection

GC runs as a scheduled job (cron/K8s job). Invoke it with `ade-worker gc`.

- Environments are deleted only when the configuration is **not active**,
  the environment is cold (`last_used_at` / `updated_at` older than TTL),
  and no queued/running runs reference it.
- Run artifacts are deleted only for terminal runs older than the TTL.
