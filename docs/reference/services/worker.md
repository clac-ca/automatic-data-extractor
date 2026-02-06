# ADE Worker (data plane / run processor)

Background worker that processes queued runs, provisions environments, and
records results.

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
- `ADE_ENGINE_SPEC` (optional override)

## Notes

- Run migrations before starting: `ade db migrate`.
- The worker does not create tables.

## Links

- `../../how-to/run-local-dev-loop.md`
- `../../reference/cli-reference.md`
- `../../reference/runtime-lifecycle.md`
