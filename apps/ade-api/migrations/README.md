# ADE Alembic migrations

This directory houses the Alembic environment and versioned migrations for the rebuilt backend.
Use `apps/ade-api/alembic.ini` with `alembic upgrade head` to apply schema changes against
`ADE_DATABASE_URL` (the same URL used by the API and worker).

Recent migrations add the `ade_run_queued` NOTIFY trigger used by event-driven workers, so
ensure you run migrations before starting `ade-worker`.

## Usage

Postgres:

```bash
ADE_DATABASE_URL="postgresql+psycopg://user:password@pg.example.com:5432/dbname?sslmode=verify-full" \
ADE_DATABASE_SSLROOTCERT="/path/to/ca.crt" \
  alembic -c apps/ade-api/alembic.ini upgrade head
```

Managed Identity (Azure Database for PostgreSQL):

```bash
ADE_DATABASE_URL="postgresql+psycopg://<identity-name>@pg.example.com:5432/dbname?sslmode=verify-full" \
ADE_DATABASE_SSLROOTCERT="/path/to/ca.crt" \
ADE_DATABASE_AUTH_MODE=managed_identity \
  alembic -c apps/ade-api/alembic.ini upgrade head
```
