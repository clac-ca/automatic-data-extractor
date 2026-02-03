# Work Package: CLI Standardization - ade-storage

Guiding Principle:
Make ADE CLI commands consistent, discoverable, and unsurprising across all services.

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Assess and standardize the ade-storage CLI (`backend/ade-storage/src/ade_storage/cli.py`) to match the shared CLI template and ensure consistent command naming and help behavior.

### Scope

- In:
  - ade-storage CLI structure and command registration.
  - Command naming and help text (check/verify).
  - Error handling and output formatting consistency.
- Out:
  - Changing storage adapter behavior beyond CLI wiring.

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
    - [x] Confirm command naming (`check`) is consistent and intuitive.
    - [x] Ensure error output uses `typer.echo(..., err=True)` + `typer.Exit`.
    - [x] Align option naming/flag style with the shared conventions (types, required options).

3.0 Validation
  3.1 Help output
    - [x] `ade-storage --help` lists commands and shows consistent phrasing.
    - [x] `ade storage --help` delegates and shows the same surface.

### Open Questions

- None.

---

## Acceptance Criteria

- ade-storage CLI structure and help behavior match the standard template.
- Command names and help text are consistent with other services.
- Help output is consistent between `ade-storage` and `ade storage`.

---

## Definition of Done

- WBS tasks complete and checked.
- ade-storage CLI help verified.
