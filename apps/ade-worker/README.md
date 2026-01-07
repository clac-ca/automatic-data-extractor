# ADE Worker (DB-backed, no broker)

Minimal, reliable worker that processes **build** and **run** records stored in a database.

Supported databases:
- SQLite (local dev)
- SQL Server / Azure SQL (prod)

## How it works

- The application inserts rows into `builds` and `runs` with `status=queued`.
- The worker claims builds by setting `status=building` and runs by setting `status=running`.
- Runs use a **lease** (`claim_expires_at`) with periodic **heartbeats** and retry backoff.
- Builds transition to `ready`/`failed`; runs transition to `succeeded`/`failed`.

## Run

```bash
export ADE_DATABASE_URL="sqlite:///./data/db/ade.sqlite"
python -m ade_worker
```

## Important env vars

- `ADE_DATABASE_URL`
- `ADE_WORKER_DATA_DIR` (default `./data`)
- `ADE_WORKER_CONCURRENCY` (default: conservative auto)
- `ADE_WORKER_LEASE_SECONDS` (default `900`)
- `ADE_WORKER_AUTO_CREATE_SCHEMA` (default `0`)

## Schema

See `ade_worker/schema.py` for table definitions.
