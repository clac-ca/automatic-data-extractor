# Work Package: CLI Standardization - ade-db

Guiding Principle:
Make ADE CLI commands consistent, discoverable, and unsurprising across all services.

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Assess and standardize the ade-db CLI (`backend/ade-db/src/ade_db/cli.py`) to match the shared CLI template and ensure consistent command naming and help behavior.

### Scope

- In:
  - ade-db CLI structure and command registration.
  - Command naming and option styles (migrate/history/current/stamp).
  - Help output consistency with other service CLIs.
- Out:
  - Changing Alembic behavior beyond CLI wiring.

### Work Breakdown Structure (WBS)

1.0 Structure alignment
  1.1 Align with standard Typer template
    - [x] Ensure `app = Typer(add_completion=False, invoke_without_command=True)`.
    - [x] Ensure `@app.callback` prints help when no subcommand is invoked.
    - [x] Align help string style with other service CLIs.
    - [x] Enforce `add_completion=False` and keep default help formatting.
    - [x] Ensure `no_args_is_help` is not used (exit code 2).

2.0 Command consistency
  2.1 Command surface review
    - [x] Confirm migrate/history/current/stamp naming and help text are consistent.
    - [x] Ensure error output uses `typer.echo(..., err=True)` + `typer.Exit`.
    - [x] Align option naming/flag style with the shared conventions (types, required options).

3.0 Validation
  3.1 Help output
    - [x] `ade-db --help` lists commands and shows consistent phrasing.
    - [x] `ade db --help` delegates and shows the same surface.

### Open Questions

- None.

---

## Acceptance Criteria

- ade-db CLI structure and help behavior match the standard template.
- Command names and help text are consistent with other services.
- Help output is consistent between `ade-db` and `ade db`.

---

## Definition of Done

- WBS tasks complete and checked.
- ade-db CLI help verified.
