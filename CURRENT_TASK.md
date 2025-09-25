# Current Task – Bootstrap the SQLite database

## Problem
- Running `ade users create` fails with `sqlite3.OperationalError: no such table: users`.
- The FastAPI app (and the CLI that reuses its settings) never creates the SQLite file or applies Alembic migrations before the first query.

## Goal
Make sure the backend creates the SQLite database directory/file and runs migrations before serving requests or running CLI commands.

## Plan
1. Add a small helper (e.g. `backend/api/db/bootstrap.py`) that ensures the data directory exists for SQLite URLs and runs `alembic upgrade head`.
2. Call the helper from the FastAPI lifespan startup so the schema is ready when the API starts.
3. Reuse the same helper in the CLI runtime before opening a database session.
4. Add regression tests for API startup and the CLI command, and update docs if behaviour changes.

## Checks
- `pytest backend/tests/api backend/tests/cli`
- `ruff check backend`
- `mypy backend`
