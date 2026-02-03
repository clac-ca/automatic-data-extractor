# Work Package: CLI Standardization - ade-api

Guiding Principle:
Make ADE CLI commands consistent, discoverable, and unsurprising across all services.

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Assess and standardize the ade-api CLI (`backend/ade-api/src/ade_api/cli.py` and command modules) to match the shared CLI template, align command naming and help, and ensure consistent behavior with other service CLIs.

### Scope

- In:
  - ade-api CLI structure and command registration.
  - Command naming/semantics (start/dev/test/lint/routes/types/users).
  - Help output consistency and error handling.
- Out:
  - Changing API runtime behavior beyond CLI wiring.
  - Refactoring business logic unrelated to CLI.

### Work Breakdown Structure (WBS)

1.0 Structure alignment
  1.1 Align with standard Typer template
    - [x] Ensure `app = Typer(add_completion=False, invoke_without_command=True)`.
    - [x] Ensure `@app.callback` prints help when no subcommand is invoked.
    - [x] Ensure help strings follow a consistent style.
    - [x] Enforce `add_completion=False` and keep default help formatting.
    - [x] Ensure `no_args_is_help` is not used (exit code 2).

2.0 Command consistency
  2.1 Start/dev/test parity
    - [x] Confirm start/dev/test command naming and option patterns match worker CLI.
    - [x] Align test suite argument handling (unit/integration/all) with other services.
  2.2 Command surface review
    - [x] Review routes/types/users commands for naming consistency.
    - [x] Ensure error output uses `typer.echo(..., err=True)` + `typer.Exit` (ASCII-only, no emoji).
    - [x] Align option naming/flag style with the shared conventions (types, required options).
    - [x] Remove `ade api migrate` (use `ade db migrate` only).

3.0 Validation
  3.1 Help output
    - [x] `ade-api --help` lists commands and shows consistent phrasing.
    - [x] `ade api --help` delegates and shows the same surface.

### Open Questions

- None.

---

## Acceptance Criteria

- ade-api CLI structure and help behavior match the standard template.
- Command names and test semantics are consistent with other services.
- Help output is consistent between `ade-api` and `ade api`.

---

## Definition of Done

- WBS tasks complete and checked.
- ade-api CLI help verified.
