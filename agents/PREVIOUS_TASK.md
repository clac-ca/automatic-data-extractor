## Context
`CURRENT_TASK.md` asked us to ensure both the FastAPI app and CLI bootstrap the
SQLite database before serving traffic, fixing the missing `users` table error
encountered by `ade users create`.

## Outcome
- Added a reusable `bootstrap_database` helper that guarantees the SQLite
  directory exists and runs `alembic upgrade head` exactly once per settings
  configuration.
- Integrated the helper into the FastAPI lifespan and CLI session manager so
  web requests and CLI commands both migrate the schema before opening a
  session.
- Introduced regression tests that prove API startup and CLI session helpers
  materialise the `users` table automatically.

## Next steps
- Update the developer documentation to describe the new automatic bootstrap
  behaviour and clarify how to run migrations manually when needed.
- Consider establishing a clean `mypy` baseline so future backend changes can
  rely on type-checking without surfacing dozens of legacy errors.
