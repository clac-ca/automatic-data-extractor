# Work Package: CLI + Settings Cleanup

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Simplify CLI and env handling across ade-api and ade-worker, eliminating duplicated parsing and aligning defaults with the shared packages and the root ade CLI.

### Scope

- In:
  - Normalize env defaults and service selection behavior.
  - Remove redundant CLI plumbing once centralized in ade CLI.
  - Ensure documentation reflects the simplified configuration.
- Out:
  - Behavior changes unrelated to simplification.

### Work Breakdown Structure (WBS)

1.0 Inventory and Alignment
  1.1 Identify duplicated CLI/env logic
    - [x] Inventory ade-api CLI env handling
    - [x] Inventory ade-worker CLI env handling
  1.2 Define desired defaults
    - [x] Document port and service defaults
2.0 Refactor
  2.1 ade-api CLI simplification
    - [x] Remove redundant CLI parsing where root CLI handles it
  2.2 ade-worker CLI simplification
    - [x] Remove redundant CLI parsing where root CLI handles it
3.0 Documentation
  3.1 Update docs
    - [x] Update CLI/env var references if changed
4.0 Validation
  4.1 Tests
    - [x] Run ade test

### Open Questions

- Any env var names that must remain for backward compatibility?

---

## Acceptance Criteria

- CLI/env handling is minimal and consistent across services.
- Docs match behavior.
- Tests pass.

---

## Definition of Done

- WBS complete and checked.
- `ade test` passes.
