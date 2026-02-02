# Work Package: Simplification Sweep

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Remove unused helpers/settings and tighten the worker path surface to reduce clutter.

### Scope

- In:
  - Remove unused worker settings fields and path helpers.
  - Remove unused ade-db helper functions.
- Out:
  - Removing any behavior that is actively used.
  - Changing runtime semantics beyond cleanup.

### Work Breakdown Structure (WBS)

1.0 Worker Settings Cleanup
  1.1 Remove unused fields
    - [x] Drop worker_max_attempts_default from worker settings
2.0 Path Helpers Cleanup
  2.1 Remove unused PathManager helpers
    - [x] Remove unused workspaces_root helper
3.0 DB Helpers Cleanup
  3.1 Remove unused ade-db helpers
    - [x] Remove build_engine_from_url (unused)
4.0 Validation
  4.1 Tests and runtime checks
    - [x] Run ade test

---

## Acceptance Criteria

- Unused settings/helpers removed with no behavior loss.
- Tests pass.

---

## Definition of Done

- WBS complete and checked.
- `ade test` passes.
