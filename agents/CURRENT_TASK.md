# Current Task – Document database bootstrap behaviour

## Problem
- We now bootstrap the SQLite database automatically, but the docs still focus on manual setup.
- Developers need clear guidance on what happens on startup and how to run Alembic migrations explicitly when required.

## Goal
Update the developer documentation so the automatic bootstrap flow and manual migration commands are easy to understand.

## Plan
1. Review backend setup docs (README, docs/) for database and migration instructions that need updating.
2. Document the new bootstrap helper, clarifying that FastAPI startup and CLI commands run Alembic migrations automatically.
3. Add a short section outlining how to run `alembic upgrade head` manually for troubleshooting or CI workflows.
4. Note any environment variables or prerequisites developers should set before running migrations.

## Checks
- `ruff check docs backend`
