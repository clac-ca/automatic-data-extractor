# Work Package: Storage Cleanup

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Make ade-storage the single source of truth for blob adapter selection and storage layout paths used by both ade-api and ade-worker.

### Scope

- In:
  - Remove duplicate storage adapter logic in ade-api/ade-worker.
  - Centralize path/layout helpers in ade-storage.
  - Normalize storage settings usage across services.
- Out:
  - Changing storage semantics or retention behavior.

### Work Breakdown Structure (WBS)

1.0 Inventory and Consolidation
  1.1 Identify duplicate storage helpers
    - [x] Inventory ade-api storage helpers and path utilities
    - [x] Inventory ade-worker storage helpers and path utilities
  1.2 Define ade-storage authoritative helpers
    - [x] Ensure ade-storage exposes adapters + layout API used by both services
    - [x] Document intended import surface
2.0 Refactor ade-api
  2.1 Replace local storage helper usage
    - [x] Update ade-api imports to ade_storage.*
    - [x] Remove unused/duplicate ade-api storage helpers
3.0 Refactor ade-worker
  3.1 Replace local storage helper usage
    - [x] Update ade-worker imports to ade_storage.*
    - [x] Remove unused/duplicate ade-worker storage helpers
4.0 Validation
  4.1 Tests and runtime checks
    - [x] Run ade test

### Open Questions

- Are there storage helpers we should keep temporarily to avoid risky changes?

---

## Acceptance Criteria

- ade-api and ade-worker use ade-storage for adapter + layout.
- No duplicated storage helpers remain.
- Tests pass.

---

## Definition of Done

- WBS complete and checked.
- `ade test` passes.
