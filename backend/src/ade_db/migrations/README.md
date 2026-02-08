# ADE Alembic migrations

This directory houses the Alembic environment and versioned migrations for the backend.
Migrations are packaged inside the unified backend distribution and should be run via the
CLI so the packaged Alembic config is used.

The initial schema installs the `ade_run_queued` NOTIFY trigger used by event-driven
workers, so ensure you run migrations before starting `ade-worker`.

## Baseline rewrite notice

Migration history was rewritten into a baseline-first chain:

- `0001_initial_schema` is the canonical schema baseline.
- `0002_run_status_cancelled` and `0003_authn_rework` are compatibility no-ops.

Because this is a breaking migration rewrite, environments should be reset before
applying migrations:

```bash
ade db reset --yes
ade db migrate
```

## Usage

Postgres:

```bash
ADE_DATABASE_URL="postgresql+psycopg://user:password@pg.example.com:5432/dbname?sslmode=verify-full" \
ADE_DATABASE_SSLROOTCERT="/path/to/ca.crt" \
  ade db migrate
```

Managed Identity (Azure Database for PostgreSQL):

```bash
ADE_DATABASE_URL="postgresql+psycopg://<identity-name>@pg.example.com:5432/dbname?sslmode=verify-full" \
ADE_DATABASE_SSLROOTCERT="/path/to/ca.crt" \
ADE_DATABASE_AUTH_MODE=managed_identity \
  ade db migrate
```
