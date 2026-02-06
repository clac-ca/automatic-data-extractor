# ADE DB (schema + Alembic migrations)

Database schema and migrations for ADE.

## Quickstart (dev from repo root)

```bash
cd backend
uv sync
ade db migrate
```

## Key commands

```bash
ade db migrate
ade db history
ade db current
ade db stamp <rev>
ade db reset
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

- `src/ade_db/migrations/README.md`
- `../../docs/reference/cli-reference.md`
- `../../docs/how-to/run-migrations-and-resets.md`
