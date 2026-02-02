# Work Package: Module Layout Cleanup

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Remove redundant modules in ade-api and ade-worker after DB and storage consolidation, and simplify layout to reduce indirection.

### Scope

- In:
  - Remove legacy helpers that duplicate ade-db/ade-storage.
  - Flatten or consolidate small utility modules where it clarifies ownership.
- Out:
  - Any functional behavior changes.

### Work Breakdown Structure (WBS)

1.0 Cleanup pass
  1.1 Identify redundant modules
    - [x] Review ade-api modules for redundancy
    - [x] Review ade-worker modules for redundancy
  1.2 Remove or consolidate
    - [x] Delete redundant files and update imports
2.0 Validation
  2.1 Tests
    - [x] Run ade test

### Open Questions

- Any modules that should remain temporarily to avoid churn?

---

## Acceptance Criteria

- Redundant modules removed or consolidated without behavior changes.
- Tests pass.

---

## Definition of Done

- WBS complete and checked.
- `ade test` passes.
