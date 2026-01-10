# ADE Alembic migrations

This directory houses the Alembic environment and versioned migrations for the rebuilt backend.
Use `apps/ade-api/alembic.ini` with `alembic upgrade head` to apply schema changes against the
`ADE_DATABASE_URL` target (or override with `ALEMBIC_DATABASE_URL`).

## Usage

Local SQLite:

```bash
ADE_DATABASE_URL=sqlite:///./data/db/ade.sqlite \
  alembic -c apps/ade-api/alembic.ini upgrade head
```

SQL Server / Azure SQL:

```bash
ADE_DATABASE_URL="mssql+pyodbc://user:password@server.database.windows.net:1433/dbname?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no" \
  alembic -c apps/ade-api/alembic.ini upgrade head
```

Managed Identity (Azure SQL):

```bash
ADE_DATABASE_URL="mssql+pyodbc://@server.database.windows.net:1433/dbname?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no" \
ADE_DATABASE_AUTH_MODE=managed_identity \
  alembic -c apps/ade-api/alembic.ini upgrade head
```
