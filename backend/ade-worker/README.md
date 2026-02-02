# ADE Worker (data plane / run processor)

Background worker that processes queued runs, provisions environments, and
records results.

## Quickstart (dev from repo root)

```bash
cd backend
uv sync
ade db migrate
ade worker start
```

## Key commands

```bash
ade worker start
ade worker dev
ade worker gc
ade worker test
```

## Required env vars (minimal)

- `ADE_DATABASE_URL`
- `ADE_BLOB_CONNECTION_STRING` or `ADE_BLOB_ACCOUNT_URL`
- `ADE_BLOB_CONTAINER` (optional but standard)
- `ADE_ENGINE_PACKAGE_PATH` (optional override)

## Notes

- Run migrations before starting: `ade db migrate`.
- The worker does not create tables.

## Links

- `../../docs/getting-started/first-run.md`
- `../../docs/reference/cli.md`
- `../../docs/guides/developer.md`
