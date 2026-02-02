# ADE API (FastAPI control plane)

API service for ADE: auth, configuration lifecycle, documents, runs, and
system status.

## Quickstart (dev from repo root)

```bash
cd backend
uv sync
ade db migrate
ade api dev
```

Alternative: run `./setup.sh` from the repo root to install backend + frontend
dependencies.

## Key commands

```bash
ade api dev
ade api start
ade api routes
ade api types
ade api test
ade api lint
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

- `../../docs/getting-started/first-run.md`
- `../../docs/reference/cli.md`
- `../../docs/guides/developer.md`
