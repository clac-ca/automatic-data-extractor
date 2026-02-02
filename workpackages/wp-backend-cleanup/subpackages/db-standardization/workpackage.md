# Work Package: DB Module Standardization

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Standardize API and worker DB modules to use consistent naming and layout, and remove unused helpers.

### Scope

- In:
  - Flatten ade-api DB helpers to a single module (ade_api/db.py).
  - Remove unused worker DB helpers.
  - Align section layout and exports across API/worker DB modules.
- Out:
  - Changing DB behavior or query semantics.

### Work Breakdown Structure (WBS)

1.0 API DB Module Simplification
  1.1 Flatten module
    - [x] Move database helpers into ade_api/db.py and remove ade_api/db/ package
    - [x] Update imports to use the new module
2.0 Worker DB Cleanup
  2.1 Remove unused helpers
    - [x] Drop advisory_lock context manager
3.0 Worker DB Session Standardization
  3.1 Normalize session usage
    - [x] Convert worker db helpers to accept Session (caller owns transaction)
    - [x] Update worker call sites and tests to pass Session
4.0 Shared Session Helpers
  4.1 Use session_scope in CLI/scripts
    - [x] Update ade-api CLI/scripts to use ade_db.session_scope + build_engine
    - [x] Remove build_engine re-export from ade_api.db
5.0 Layout Standardization
  5.1 Align structure
    - [x] Normalize section ordering + __all__ declarations
6.0 Validation
  6.1 Tests and runtime checks
    - [x] Run ade test

---

## Acceptance Criteria

- ade-api exposes DB helpers via a single module (ade_api.db).
- Worker DB helpers accept Session and callers own transactions.
- Worker DB module has no unused helpers.
- API/worker DB modules follow a consistent layout.
- ade-api CLI/scripts use shared session_scope and build_engine directly.
- Tests pass.

---

## Definition of Done

- WBS complete and checked.
- `ade test` passes.
