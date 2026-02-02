# Work Package: Backend Cleanup (ade-db + ade-storage adoption)

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Standardize ade-api and ade-worker around the shared ade-db and ade-storage packages, removing redundant helpers and simplifying configuration paths. Do this in staged subpackages to minimize risk and keep behavior stable.

### Scope

- In:
  - Consolidate DB engine/session helpers and schema/migrations under ade-db.
  - Consolidate blob storage adapters and path/layout logic under ade-storage.
  - Simplify CLI/env handling across api/worker where it duplicates shared logic.
  - Remove redundant modules and legacy helpers after consolidation.
- Out:
  - Changing database schema or migration history.
  - Changing blob storage behavior beyond standardizing paths/adapters.
  - Any feature changes unrelated to cleanup.

### Work Breakdown Structure (WBS)

1.0 DB Layer Cleanup
  1.1 Subpackage: db-cleanup
    - [x] Execute db-cleanup workpackage
2.0 Storage Cleanup
  2.1 Subpackage: storage-cleanup
    - [x] Execute storage-cleanup workpackage
3.0 CLI + Settings Cleanup
  3.1 Subpackage: cli-settings-cleanup
    - [x] Execute cli-settings-cleanup workpackage
4.0 Module Layout Cleanup
  4.1 Subpackage: module-cleanup
    - [x] Execute module-cleanup workpackage
5.0 Connection Alignment Pass
  5.1 Subpackage: connection-alignment
    - [x] Execute connection-alignment workpackage
6.0 Storage Layout + Runtime Alignment
  6.1 Subpackage: layout-alignment
    - [x] Execute layout-alignment workpackage
7.0 Startup + Docs Alignment
  7.1 Subpackage: startup-docs-alignment
    - [x] Execute startup-docs-alignment workpackage
8.0 Simplification Sweep
  8.1 Subpackage: simplification-sweep
    - [x] Execute simplification-sweep workpackage

### Open Questions

- Are there any legacy helpers that must remain temporarily for backward compatibility?
- Do we want a deprecation window for renamed env vars or CLI flags?

---

## Acceptance Criteria

- ade-api and ade-worker use ade-db for all DB engine/session/schema/migrations.
- ade-api and ade-worker use ade-storage for all blob adapter + path/layout concerns.
- Worker runtime/layout paths are derived from ade-storage layout helpers with minimal local glue.
- API and worker use shared storage-root creation.
- Docs include storage layout guidance.
- Remove unused helpers/settings where safe.
- CLI/env handling is consistent and minimal across services.
- Redundant modules removed with no loss of functionality; tests pass.

---

## Definition of Done

- All subpackages completed and checked off.
- `ade test` passes.
- Docs updated where behavior or configuration changed.
