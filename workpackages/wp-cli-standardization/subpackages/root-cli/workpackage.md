# Work Package: CLI Standardization - Root ade

Guiding Principle:
Make ADE CLI commands consistent, discoverable, and unsurprising across all services.

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Audit and standardize the root `ade` CLI implementation (`backend/cli.py`) to match the shared CLI template, ensure consistent naming and help behavior, and clean delegation to service CLIs and web/npm commands.

### Scope

- In:
  - Root CLI structure (Typer app config, callback help, command layout).
  - Delegation to `ade-api`, `ade-worker`, `ade-db`, `ade-storage`.
  - Web command mapping to npm scripts (dev/build/test/etc.).
  - Consistent error handling and output formatting.
- Out:
  - Changing service behavior beyond CLI wiring.
  - Adding new root commands unrelated to CLI standardization.

### Work Breakdown Structure (WBS)

1.0 Structure and conventions
  1.1 Align root CLI to the standard template
    - [x] Ensure `app = Typer(add_completion=False, invoke_without_command=True)`.
    - [x] Ensure `@app.callback` prints help when no subcommand is invoked.
    - [x] Ensure command help strings are short and consistent.
    - [x] Enforce `add_completion=False` and keep default help formatting.
    - [x] Ensure `no_args_is_help` is not used (exit code 2).
  1.2 Standardize output and error handling
    - [x] Use a consistent command prefix (ASCII `->`) for subprocess output.
    - [x] Use ASCII-only output (no emoji) for errors and warnings.
    - [x] Use `typer.echo(..., err=True)` and `typer.Exit(code=...)` for errors.

2.0 Delegation consistency
  2.1 Service delegation
    - [x] Ensure `ade api|worker|db|storage` delegates using Typer sub-apps with `allow_extra_args`.
    - [x] Ensure `ade <service>` without args shows that service help.
  2.2 Web delegation
    - [x] Ensure `ade web` maps to npm scripts with standard command names.
    - [x] Ensure missing frontend/entrypoint errors are clear and consistent.

3.0 Validation
  3.1 Help matrix
    - [x] `ade --help` lists root commands.
    - [x] `ade api --help`, `ade worker --help`, `ade db --help`, `ade storage --help` show help.
    - [x] `ade web --help` lists web commands.

### Open Questions

- None.

---

## Acceptance Criteria

- Root CLI follows the standard Typer template and help behavior.
- Delegation to service CLIs and web commands is consistent and predictable.
- Help output matches the command matrix in docs.

---

## Definition of Done

- WBS tasks complete and checked.
- Root CLI help matrix validated.
