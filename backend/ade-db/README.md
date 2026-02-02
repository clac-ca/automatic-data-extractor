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
```

## Required env vars (minimal)

- `ADE_DATABASE_URL`
- `ADE_DATABASE_AUTH_MODE` (optional)
- `ADE_DATABASE_SSLROOTCERT` (optional)

## Notes

- Migrations install the NOTIFY trigger used by the worker.
- All services require migrations before start.

## Links

- `src/ade_db/migrations/README.md`
- `../../docs/reference/cli.md`
