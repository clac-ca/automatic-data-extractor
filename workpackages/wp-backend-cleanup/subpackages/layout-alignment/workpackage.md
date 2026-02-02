# Work Package: Layout + Runtime Alignment

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Align ade-worker runtime path management with ade-storage layout helpers, and centralize creation of shared storage root directories.

### Scope

- In:
  - Add computed layout properties to ade-worker settings (workspaces/configs/documents/runs/venvs/pip cache).
  - Rework ade-worker PathManager to use ade-storage layout helpers for workspace roots.
  - Centralize storage root directory creation in ade-storage and reuse in ade-worker startup.
- Out:
  - Changing storage semantics or retention policies.
  - Renaming environment variables.

### Work Breakdown Structure (WBS)

1.0 Settings Alignment
  1.1 Add layout properties to ade-worker settings
    - [x] Add workspaces_dir/configs_dir/documents_dir/runs_dir/venvs_dir/pip_cache_dir properties
2.0 Layout Refactor
  2.1 Use ade-storage layout helpers in PathManager
    - [x] Update PathManager to derive workspace/config/venv/run roots via ade-storage layout
    - [x] Keep safe path joins for user-controlled identifiers
3.0 Runtime Directory Creation
  3.1 Centralize storage root directory creation
    - [x] Add ade-storage helper to ensure layout root directories exist
    - [x] Update worker startup to use shared helper + pip cache dir
4.0 Validation
  4.1 Tests and runtime checks
    - [x] Run ade test

### Open Questions

- Decision: use workspace-scoped run directories via ade-storage's `workspace_run_root`.

---

## Acceptance Criteria

- ade-worker settings expose StorageLayoutSettings-compatible properties.
- PathManager uses ade-storage layout helpers for workspace/config/venv/run roots.
- Worker startup uses shared directory creation helper.
- Tests pass.

---

## Definition of Done

- WBS complete and checked.
- `ade test` passes.
