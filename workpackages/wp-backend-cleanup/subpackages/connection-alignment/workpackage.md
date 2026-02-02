# Work Package: Connection Alignment Pass

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Align how ade-api and ade-worker establish database connections and reuse shared helpers, with a single, consistent path for SQLAlchemy and psycopg connection configuration.

### Scope

- In:
  - Centralize psycopg connection kwargs building in ade-db.
  - Remove duplicate worker-side connection helper logic.
  - Keep API + worker naming and behavior consistent.
- Out:
  - Behavior changes beyond helper alignment.

### Work Breakdown Structure (WBS)

1.0 Inventory
  1.1 Identify duplicate connection setup logic
    - [x] Review worker LISTEN/NOTIFY connection helpers
    - [x] Review API DB engine/session setup for overlap
2.0 Consolidate helpers
  2.1 Add shared helper in ade-db
    - [x] Implement shared psycopg connection kwargs builder
  2.2 Update worker to use shared helper
    - [x] Remove local helper functions and use ade-db helper
3.0 Validation
  3.1 Tests
    - [x] Run ade test

### Open Questions

- None.

---

## Acceptance Criteria

- Worker psycopg connection setup uses ade-db helper.
- No duplicate connection builder remains in worker.
- Tests pass.

---

## Definition of Done

- WBS complete and checked.
- `ade test` passes.
