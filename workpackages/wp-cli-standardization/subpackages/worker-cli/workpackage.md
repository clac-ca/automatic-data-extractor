# Work Package: CLI Standardization - ade-worker

Guiding Principle:
Make ADE CLI commands consistent, discoverable, and unsurprising across all services.

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Assess and standardize the ade-worker CLI (`backend/ade-worker/src/ade_worker/cli.py`) to match the shared CLI template and align command names, help, and error handling with other services.

### Scope

- In:
  - ade-worker CLI structure and command definitions.
  - Test command semantics and suite options.
  - Help output and error handling consistency.
- Out:
  - Changing worker runtime behavior beyond CLI wiring.

### Work Breakdown Structure (WBS)

1.0 Structure alignment
  1.1 Align with standard Typer template
    - [x] Ensure `app = Typer(add_completion=False, invoke_without_command=True)`.
    - [x] Ensure `@app.callback` prints help when no subcommand is invoked.
    - [x] Align help string style with other service CLIs.
    - [x] Enforce `add_completion=False` and keep default help formatting.
    - [x] Ensure `no_args_is_help` is not used (exit code 2).

2.0 Command consistency
  2.1 Start/dev/test parity
    - [x] Ensure command names align with api CLI (start/dev/test).
    - [x] Align test suite argument parsing with the standard (unit/integration/all).
  2.2 Output and error handling
    - [x] Ensure subprocess output prefix is consistent (ASCII `->`).
    - [x] Ensure errors use `typer.echo(..., err=True)` + `typer.Exit` (ASCII-only, no emoji).
    - [x] Align option naming/flag style with the shared conventions (types, required options).

3.0 Validation
  3.1 Help output
    - [x] `ade-worker --help` lists commands and shows consistent phrasing.
    - [x] `ade worker --help` delegates and shows the same surface.

### Open Questions

- None.

---

## Acceptance Criteria

- ade-worker CLI structure and help behavior match the standard template.
- Test command semantics are consistent with other services.
- Help output is consistent between `ade-worker` and `ade worker`.

---

## Definition of Done

- WBS tasks complete and checked.
- ade-worker CLI help verified.
