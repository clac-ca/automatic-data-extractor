# Work Package: DB Layer Cleanup

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Make ade-db the single source of truth for DB engine/session helpers, schema checks, and migrations. Remove redundant DB utilities in ade-api and ade-worker while preserving behavior.

### Scope

- In:
  - Remove duplicate engine/session helpers in ade-api/ade-worker.
  - Centralize migration entrypoints and schema checks in ade-db.
  - Update imports to ade_db.* consistently.
- Out:
  - Changing migration history or schema contents.

### Work Breakdown Structure (WBS)

1.0 Inventory and Consolidation
  1.1 Identify DB helpers duplicated in ade-api/ade-worker
    - [x] Inventory ade-api db modules for redundant helpers
    - [x] Inventory ade-worker db modules for redundant helpers
  1.2 Define ade-db authoritative helpers
    - [x] Ensure ade-db exposes required engine/session/migration helpers
    - [x] Document intended import surface
2.0 Refactor ade-api
  2.1 Replace local DB helper usage
    - [x] Update ade-api imports to ade_db.*
    - [x] Remove unused/duplicate ade-api db helpers
3.0 Refactor ade-worker
  3.1 Replace local DB helper usage
    - [x] Update ade-worker imports to ade_db.*
    - [x] Remove unused/duplicate ade-worker db helpers
4.0 Validation
  4.1 Tests and runtime checks
    - [x] Run ade test
    - [x] Verify migrations still run via ade db migrate

### Open Questions

- Are there any DB helpers that must remain in ade-api or ade-worker for now?

---

## Acceptance Criteria

- ade-api and ade-worker use ade-db for all DB engine/session/schema access.
- No duplicated DB helpers remain in ade-api/ade-worker.
- Tests pass.

---

## Definition of Done

- WBS complete and checked.
- `ade test` passes.
