# ADE Alembic migrations

This directory houses the Alembic environment and versioned migrations for the rebuilt backend.
Use `apps/ade-api/alembic.ini` with `alembic upgrade head` to apply schema changes against the
`ADE_SQL_*` target (or override with `ALEMBIC_DATABASE_URL`).

## Usage

SQL Server / Azure SQL:

```bash
ADE_SQL_HOST="server.database.windows.net" \
ADE_SQL_PORT="1433" \
ADE_SQL_DATABASE="dbname" \
ADE_SQL_USER="user" \
ADE_SQL_PASSWORD="password" \
  alembic -c apps/ade-api/alembic.ini upgrade head
```

Managed Identity (Azure SQL):

```bash
ADE_SQL_HOST="server.database.windows.net" \
ADE_SQL_PORT="1433" \
ADE_SQL_DATABASE="dbname" \
ADE_DATABASE_AUTH_MODE=managed_identity \
  alembic -c apps/ade-api/alembic.ini upgrade head
```
