# CLI Implementation Plan

## Objective
Provide a lightweight `ade` command that mirrors the familiar structure of `backend/api`, while keeping the functionality focused on core admin workflows (user bootstrap and API key management).

## Package Layout
```
backend/cli/
├── __init__.py
├── main.py              # entry point; analogous to backend/api/main.py
├── app.py               # build_cli_app() wires parser + command registry
├── core/
│   ├── __init__.py
│   ├── runtime.py       # settings + session helpers (like backend/api/core)
│   └── output.py        # print_json(), print_rows(), password file reader
└── commands/
    ├── __init__.py
    ├── users.py         # user commands (create/list/activate/...)
    └── api_keys.py      # API key commands (issue/list/revoke)
```
- Console script (`pyproject.toml`):
  ```toml
  [project.scripts]
  ade = "backend.cli.main:main"
  ```
- All code uses stdlib (`argparse`, `asyncio`, `json`, `pathlib`, `textwrap`).

## Command Surface (v1)
```
ade users create --email EMAIL [--role admin|member]
                  [--password TEXT]
                  [--inactive]
ade users list [--json]
ade users activate USER_ID
ade users deactivate USER_ID
ade users set-password USER_ID (--password TEXT)

ade api-keys issue (--user-id USER_ID | --email EMAIL) [--expires-in DAYS]
ade api-keys list [--json]
ade api-keys revoke API_KEY_ID
```
- Default output: human-readable text (one row per line).
- `--json`: emit JSON array/object for scripting.
- Raw API key displayed only once at issuance.

## Implementation Checklist
1. **Scaffold** package structure above and register console script.
2. **Runtime helpers (`core/runtime.py`)**
   - `load_settings()` → `backend.api.core.settings.get_settings()`.
   - `open_session()` → async context manager wrapping `backend.api.db.session.get_sessionmaker()`.
   - `normalise_email(value)` → copy logic from `AuthService.normalise_email` (strip + lower).
   - `read_secret(path)` → read first line, strip newline.
3. **Output helpers (`core/output.py`)**
   - `print_rows(rows, columns)` for plain text.
   - `print_json(data)` for `--json` flag.
4. **Application wiring**
   - `commands/users.py`: async functions `create`, `list`, `activate`, `deactivate`, `set_password` that accept parsed args and call `UsersRepository` + `hash_password`.
   - `commands/api_keys.py`: async functions `issue`, `list_keys`, `revoke` using `AuthService` helpers.
   - `app.build_cli_app()` constructs `argparse.ArgumentParser`, registers domain subparsers, and assigns handlers via `set_defaults(handler=...)`.
   - `main.main()` creates parser via `build_cli_app()`, parses args, runs handler with `asyncio.run()`, and handles unexpected exceptions (stderr + exit code 1).
5. **Password handling**
   - Enforce mutual exclusivity between `--password` and `--password-file`; require one when needed.
   - Hash passwords with `hash_password` before persisting.
6. **Email lookup**
   - Prefer `--user-id`; if `--email` provided, normalise and call `UsersRepository.get_by_email` to locate the account.
7. **Testing**
   - Unit: parser wiring (ensure each subcommand resolves to expected handler), helper functions (email normalisation, secret file reading).
   - Integration: execute `python -m backend.cli ...` inside pytest using the existing SQLite fixtures (`backend/tests/conftest.py`) to verify DB side effects and stdout/stderr.
8. **Documentation**
   - Document CLI usage in `docs/admin-guide/getting_started.md` (create admin, reset password, rotate API key).
   - Add quickstart snippet to README.

## Future Enhancements
- Introduce a `--service-account` flag that creates users with `is_service_account=True` and emits automation-friendly labels.
- Add migration/job tooling subcommands only when requirements appear.
- Optionally extend `core/output` with table formatting if administrators request richer output.
