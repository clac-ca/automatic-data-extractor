# CLI Implementation Plan

## Intent
- Deliver a first-party command-line interface that covers the day-to-day operational tasks currently performed by ad-hoc SQL, FastAPI requests, or manual Alembic usage.
- Keep the interface small, deterministic, and dependency-light so it can ship with the backend package and run anywhere Python 3.11 is available.
- Provide one canonical entry point () that reuses existing services and repositories instead of duplicating business logic.

## Guiding Principles
- **Reuse existing layers**: call repositories/services so validation and side-effects remain consistent with the API.
- **Zero new runtime dependencies**: build the CLI with / from the standard library.
- **Deterministic output**: default to plain text / JSON, no interactive prompts; allow piping into scripts.
- **Safe defaults**: dry-run or confirmation flags for destructive actions; never print secrets unless explicitly requested.

## Target Structure
python -m backend.app.cli
- Console script  exported via .
- All commands executed via  wrappers so we can await repository/service calls.

## Command Surface (v1)
1. **Database**
   - 
   - 
   - 
   - Implementation: call Alembic programmatically ( + ). Reuse existing .

2. **User management**
   - 
   - 
   - 
   - 
   - Implementation: use  with hashing helpers from .

3. **API keys**
   - 
   - 
   - 
   - 
   - Implementation: instantiate  with CLI . Emit raw key once to stdout.

4. **Service accounts**
   - 
   - 
   - 
   - Implementation: reuse .

5. **Configuration/system info**
   - 
   -  (resolve , , etc.).
   - Implementation: read from settings (initially Pydantic, later Dynaconf); redact ,  by default.

6. **Future (not in v1 / optional toggles)**
   - Job queue helpers (), document maintenance, etc. Documented as out-of-scope for the first iteration to avoid scope creep.

## Shared Infrastructure
- 
  -  reuse  (and in future Dynaconf) with optional env overrides.
  -  use  to provide  with automatic cleanup.
  - Provide helper  returning  without Request/Queue so services function CLI-side.
- 
  - Formatters for table output (-style using stdlib string formatting) and JSON serialization via .
  - Secret redaction helper that masks values containing , , , etc.
- 
  - Register command groups with  subparsers; each subcommand delegates to coroutine function.

## Implementation Steps
1. Scaffold  package with bootstrap modules (empty command stubs returning ).
2. Implement settings/session helpers and ensure they work in isolation (unit tests).
3. Add DB command wrappers using Alembic API; support  fallback if needed.
4. Implement user commands
   - Hash passwords with .
   - Ensure emails are normalized via repository validations.
   - Provide safe output (user id, email, role, active flag).
5. Implement API key commands
   - Use  / .
   - Display raw key only once; add  to suppress extra text for scripting.
6. Implement service account commands using repository operations (create/list/deactivate).
7. Implement config commands with redaction logic.
8. Wire CLI entry point in  ().
9. Update packaging (if needed) to include new package in .

## Testing Strategy
- Unit tests per command module using  and  fixtures; run commands via helper calling the coroutine directly.
- Integration smoke tests invoking  against a temporary SQLite database (copy of  fixture) to ensure argparse wiring works.
- CLI tests should clean up any created records and avoid printing secrets unless verifying redaction.

## Documentation Updates
- Add CLI section under  with examples ().
- Update root  quickstart to mention CLI availability for DB migrations and admin bootstrap.

## Out of Scope
- Interactive prompts and TUI features.
- Long-running job worker/queue management (can be a follow-up command once requirements stabilise).
- Windows-specific executables beyond what  already supports.

## Risks & Mitigations
- **Async context leakage**: ensure every command uses  with  to close sessions.
- **Secret leakage**: redaction helper must default to hiding sensitive settings; require explicit  to show them.
- **Alembic path resolution**: reuse the existing config () and project root detection from  to avoid misconfigured migrations.
- **Dependency drift**: sticking to stdlib avoids adding Typer/Click, keeping footprint low.

## Next Steps
1. Sign off on this plan.
2. Create scaffold PR establishing the CLI package and console script (no functionality yet).
3. Iteratively implement command groups with tests and docs.
