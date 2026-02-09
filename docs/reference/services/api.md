# ADE API (FastAPI control plane)

API service for ADE: auth, configuration lifecycle, documents, runs, and
system status.

## Quickstart (dev from repo root)

```bash
./setup.sh
cd backend
uv run ade db migrate
uv run ade api dev
```

## Key commands

```bash
uv run ade api dev
uv run ade api start
uv run ade api routes
uv run ade api types
uv run ade api test
uv run ade api lint
```

## Required env vars (minimal)

- `ADE_DATABASE_URL`
- `ADE_SECRET_KEY`
- `ADE_BLOB_CONNECTION_STRING` or `ADE_BLOB_ACCOUNT_URL`
- `ADE_BLOB_CONTAINER` (optional but standard)

## Notes

- Run migrations before starting: `ade db migrate`.
- Default API port is `http://localhost:8001` (see CLI reference).

## Links

- `../../how-to/run-local-dev-loop.md`
- `../../how-to/manage-runtime-settings.md`
- `../../reference/cli-reference.md`
- `../../explanation/system-architecture.md`
