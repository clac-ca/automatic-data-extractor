# CLI Implementation Plan

## Intent
- Deliver a first-party command-line interface that covers common ADE operational tasks currently handled with ad-hoc SQL, manual FastAPI calls, or direct Alembic usage.
- Keep the interface small, deterministic, and dependency-light so it can ship with the backend package and run anywhere Python 3.11 is available.
- Provide one canonical entry point (`ade`) that reuses existing services and repositories instead of duplicating business logic.

## Guiding Principles
- **Reuse existing layers**: call repositories/services so validation and side-effects remain consistent with the API.
- **No new runtime dependencies**: build the CLI with `argparse` + `asyncio` (stdlib only).
- **Deterministic output**: default to plain text or JSON, no interactive prompts; allow piping into scripts.
- **Safe defaults**: confirmations for destructive actions; never print secrets unless explicitly requested.

## Target Structure
```
backend/cli/
├── __init__.py
├── app.py          # argparse bootstrap (`python -m backend.cli`)
├── runner.py       # command dispatcher invoked by console script
├── context.py      # helpers to load settings and yield AsyncSession instances
├── io.py           # formatting + redaction helpers
└── commands/
    ├── __init__.py
    ├── db.py               # alembic wrappers
    ├── users.py            # user CRUD + password
    ├── api_keys.py         # issue/list/revoke API keys
    ├── service_accounts.py # service account lifecycle
    └── config.py           # print effective settings / paths
```
- Console script entry in `pyproject.toml`: `[project.scripts] ade = "backend.cli.app:main"`.
- Every command implemented as an `async` coroutine; `app.py` wraps handlers with `asyncio.run`.

## Command Surface (v1)
1. **Database**
   - `ade db upgrade [--revision head]`
   - `ade db downgrade --revision REV`
   - `ade db current`
   - Implementation: use Alembic command API with existing `alembic.ini` and env module.

2. **User management**
   - `ade users create --email EMAIL [--role admin|member] [--password TEXT|--password-file PATH] [--inactive]`
   - `ade users list [--format json|table]`
   - `ade users activate USER_ID`
   - `ade users deactivate USER_ID`
   - `ade users set-password USER_ID --password TEXT|--password-file PATH`
   - Implementation: use `UsersRepository` + `hash_password`; reuse `UserRole` enum for validation.

3. **API keys**
   - `ade api-keys issue --email EMAIL [--expires-in DAYS]`
   - `ade api-keys issue --service-account NAME [--expires-in DAYS]`
   - `ade api-keys list [--format json|table]`
   - `ade api-keys revoke API_KEY_ID`
   - Implementation: instantiate `AuthService` with a CLI `ServiceContext`; display raw key once and redact thereafter.

4. **Service accounts**
   - `ade service-accounts create --name NAME --display-name TEXT [--description TEXT]`
   - `ade service-accounts list`
   - `ade service-accounts deactivate SERVICE_ACCOUNT_ID`
   - Implementation: reuse `ServiceAccountsRepository` for persistence.

5. **Configuration / diagnostics**
   - `ade config show [--json] [--include-secrets]`
   - `ade config paths`
   - Implementation: load settings, redact fields containing `secret`, `token`, `password` unless `--include-secrets` is passed.

6. **Deferred (documented follow-ups)**
   - Job queue helpers (`ade jobs run-worker`), maintenance scripts, or batch imports — keep out of v1 to minimise scope.

## Shared Infrastructure
- `context.py`
  - `load_settings()` delegates to `get_settings()` (later Dynaconf) with optional env override.
  - `async_session()` uses `get_sessionmaker(settings)` to yield `AsyncSession` with `async with` semantics.
  - `build_service_context(session, settings)` returns `ServiceContext` without Request/task queue so services function in CLI context.
- `io.py`
  - Table formatter using stdlib string alignment.
  - `print_json(data)` helper with `json.dumps(..., indent=2)`.
  - `redact_sensitive(mapping)` masking values whose keys contain `secret`, `token`, `password` (case-insensitive).
- `runner.py`
  - Builds top-level `argparse.ArgumentParser`, registers subparsers, and dispatches to async handlers via a small helper.

## Implementation Steps
1. Scaffold `backend/cli` package with empty modules and register console script (no commands yet).
2. Implement `context.py` helpers and unit-test them.
3. Add Alembic wrappers in `commands/db.py`; ensure project root/alembic path detection mirrors `backend/api/core/settings.py`.
4. Implement user commands leveraging `UsersRepository` and password utilities.
5. Implement API key commands via `AuthService` (`issue_api_key_for_email`, `issue_api_key_for_service_account`, `list_api_keys`, `revoke_api_key`).
6. Implement service account commands, including uniqueness checks and deactivate flag updates.
7. Build configuration commands with redaction and path resolution using `Path` operations already present in settings.
8. Flesh out `io.py` for consistent table/JSON output and ensure commands honour `--format`/`--quiet` options.
9. Add CLI documentation to `docs/admin-guide/operations.md` once commands stabilise.

## Testing Strategy
- Unit tests import command coroutines directly, using pytest async fixtures and temporary SQLite DBs seeded via repositories.
- Integration tests invoke `python -m backend.cli ...` (or the console script) under `pytest` with isolated environment variables to ensure argument parsing works end-to-end.
- Assertions verify exit codes, stdout/stderr, and ensure secrets are redacted unless explicitly requested.

## Documentation Updates
- Add “Command-line tools” section to `docs/admin-guide/operations.md` with examples for DB upgrade, user bootstrap, and API key issuance.
- Mention the CLI in the rewritten root `README.md` quickstart as the preferred way to initialise the system.

## Out of Scope
- Interactive prompts / TUI experiences.
- Running the extraction worker loop or long-lived daemons (future command once requirements are clear).
- Windows `.exe` packaging; rely on `python -m backend.cli` or the `ade` entry point.

## Risks & Mitigations
- **Async resource leaks**: ensure every command uses `asyncio.run` + context managers so sessions are closed.
- **Secret exposure**: default to redacted output; `--include-secrets` must be explicit and should warn when used.
- **Alembic config mismatch**: reuse existing env module and project root detection to avoid divergence.
- **Command sprawl**: keep v1 focused; document future candidates instead of partially implementing them.

## Next Steps
1. Get sign-off on this plan.
2. Submit a scaffold PR creating the CLI package and console script wiring.
3. Implement command groups iteratively with accompanying tests and docs.

