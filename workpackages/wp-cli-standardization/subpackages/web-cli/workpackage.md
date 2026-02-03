# Work Package: CLI Standardization - ade web

Guiding Principle:
Make ADE CLI commands consistent, discoverable, and unsurprising across all services.

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Assess and standardize the `ade web` command surface (root CLI subcommands mapped to npm scripts) to match the shared CLI template, with consistent naming and help behavior.

### Scope

- In:
  - `ade web` command definitions in the root CLI.
  - Mapping to npm scripts in `frontend/ade-web/package.json`.
  - Help text consistency and error output formatting.
- Out:
  - Rewriting frontend tooling or adding a Node CLI wrapper.

### Work Breakdown Structure (WBS)

1.0 Structure alignment
  1.1 Align with standard CLI conventions
    - [x] Ensure `ade web` subcommands are listed and named consistently (dev/build/test/lint/typecheck/preview).
    - [x] Ensure help strings match the style used in other CLIs.
    - [x] Enforce `add_completion=False` and keep default help formatting.
    - [x] Ensure `no_args_is_help` is not used (exit code 2).

2.0 Command surface review
  2.1 Npm script parity
    - [x] Verify each `ade web <cmd>` maps to an npm script with the same name.
    - [x] Ensure missing frontend or npm errors are clear and consistent.
    - [x] Align option naming/flag style with the shared conventions (types, required options).

3.0 Validation
  3.1 Help output
    - [x] `ade web --help` lists commands and shows consistent phrasing.

### Open Questions

- None.

---

## Acceptance Criteria

- `ade web` commands are consistent with other service CLI patterns.
- Command names map cleanly to npm scripts.
- Help output matches the standard CLI style.

---

## Definition of Done

- WBS tasks complete and checked.
- `ade web --help` verified.
