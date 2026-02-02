# Work Package: Startup + Docs Alignment

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Make API startup use shared storage-root creation and document the new worker run layout. Skip legacy cleanup helpers (greenfield install).

### Scope

- In:
  - Ensure API startup calls ade-storage root creation helper.
  - Update docs with the workspace-scoped run layout.
- Out:
  - Changing runtime behavior beyond directory creation.
  - Legacy cleanup helpers (not needed for greenfield).

### Work Breakdown Structure (WBS)

1.0 API Startup Alignment
  1.1 Shared root creation
    - [x] Update API startup to call ade-storage ensure_storage_roots
2.0 Documentation
  2.1 Update docs/runbook
    - [x] Document workspace-scoped run layout
3.0 Validation
  3.1 Tests and runtime checks
    - [x] Run ade test

---

## Acceptance Criteria

- API uses shared storage root creation at startup.
- Docs describe run layout.
- Tests pass.

---

## Definition of Done

- WBS complete and checked.
- `ade test` passes.
