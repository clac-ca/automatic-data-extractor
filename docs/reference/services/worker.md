# ADE Worker (data plane / run processor)

Background worker that processes queued runs, provisions per-config virtual
environments in a local cache, and records results.

## Quickstart (dev from repo root)

```bash
./setup.sh
cd backend
uv run ade db migrate
uv run ade worker start
```

## Key commands

```bash
uv run ade worker start
uv run ade worker dev
uv run ade worker gc
uv run ade worker test
```

## Required env vars (minimal)

- `ADE_DATABASE_URL`
- `ADE_BLOB_CONNECTION_STRING` or `ADE_BLOB_ACCOUNT_URL`
- `ADE_BLOB_CONTAINER` (optional but standard)

## Notes

- Run migrations before starting: `ade db migrate`.
- The worker does not create tables.
- Runtime cache defaults to local ephemeral storage: `/tmp/ade-worker-cache`.
- Override cache root with `ADE_WORKER_CACHE_DIR`.
- Garbage collection uses TTL-only policy:
  - `ADE_WORKER_CACHE_TTL_DAYS` for local venv cache directories
  - `ADE_WORKER_RUN_ARTIFACT_TTL_DAYS` for run temp/output artifact directories

## Links

- `../../how-to/run-local-dev-loop.md`
- `../../reference/cli-reference.md`
- `../../reference/runtime-lifecycle.md`
