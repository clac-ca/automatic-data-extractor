# ADE DB (schema + Alembic migrations)

Database schema and migrations for ADE.

## Quickstart (dev from repo root)

```bash
./setup.sh
cd backend
uv run ade db migrate
```

## Key commands

```bash
uv run ade db migrate
uv run ade db history
uv run ade db current
uv run ade db stamp <rev>
uv run ade db reset
```

`ade db reset` is destructive and requires `--yes`.

## Required env vars (minimal)

- `ADE_DATABASE_URL`
- `ADE_DATABASE_AUTH_MODE` (optional)
- `ADE_DATABASE_SSLROOTCERT` (optional)

## Notes

- Migrations install the NOTIFY trigger used by the worker.
- All services require migrations before start.

## Links

- `../../../backend/src/ade_db/migrations/README.md`
- `../../reference/cli-reference.md`
- `../../how-to/run-migrations-and-resets.md`
