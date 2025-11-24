# ADE Alembic migrations

This directory houses the Alembic environment and versioned migrations for the rebuilt backend.
Use `apps/ade-api/alembic.ini` with `alembic upgrade head` to apply schema changes against the
`Settings.database_dsn` target (or override with `ALEMBIC_DATABASE_URL`).
