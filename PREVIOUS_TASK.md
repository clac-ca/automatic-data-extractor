# ✅ Completed Task — Document and smoke-test the new ADE CLI entrypoint

## Context
The authentication commands now hang off `backend.app.cli`, so the documentation and tests needed to surface the new
`python -m backend.app auth ...` entrypoint.

## Outcome
- Updated the README and security docs to show the new CLI syntax and example commands.
- Refreshed the system overview and environment variable reference so every auth guide now points at `python -m backend.app auth`.
- Added a CLI integration test that exercises `backend.app.cli.main()` to create and list users against the SQLite fixture.
