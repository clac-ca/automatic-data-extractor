# Work Package: Shared Backend Infrastructure Packages (DB + Storage)

Guiding Principle:
Make ADE a clean, unified, and easily operable system with one backend distribution, clear shared infrastructure, and a simple default workflow that still allows each service to run independently.


> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Create dedicated internal packages `ade_db` and `ade_storage` under `backend/` to centralize shared database schema/migrations and blob storage helpers. Update API/worker to consume these packages and expose migrations via `ade db` commands.

Targeted folder structure:

```
backend/
  ade-db/
    src/ade_db/
      __init__.py
      metadata.py
      models/
      migrations/
      alembic.ini
      env.py
      types.py          # optional
    tests/...
  ade-storage/
    src/ade_storage/
      __init__.py
      client.py
      settings.py
      paths.py
    tests/...
```

CLI command map (target behavior):

- `ade db migrate` -> apply Alembic migrations (upgrade head).
- `ade db history` -> show migration history (optional).
- `ade db current` -> show current DB revision (optional).
- `ade db stamp <rev>` -> stamp revision without running migrations (optional).
- `ade api migrate` -> alias for `ade db migrate` (optional convenience).

Locked decisions:

- Primary migration command is `ade db migrate`.
- Keep `ade api migrate` as a thin alias to `ade db migrate` (optional, convenience).

### Scope

- In:
  - New packages: `backend/ade-db` and `backend/ade-storage`.
  - Move shared DB schema/models + Alembic migrations to `ade_db`.
  - Move shared blob storage helpers to `ade_storage`.
  - Update API/worker imports to use shared packages.
  - Add `ade db migrate` command in the root CLI.
- Out:
  - Changes to storage provider behavior.
  - Re-architecting DB access patterns beyond shared schema/migrations.

### Work Breakdown Structure (WBS)

1.0 Package layout
  1.1 Create ade-db package
    - [x] Add `backend/ade-db/src/ade_db` with metadata/models/migrations.
    - [x] Add Alembic config (`alembic.ini`, `env.py`) inside ade_db.
    - [x] Wire package data so migrations ship with the backend distribution.
  1.2 Create ade-storage package
    - [x] Add `backend/ade-storage/src/ade_storage` with storage helpers.
    - [x] Define minimal storage client/config/path helpers used by api/worker.

2.0 Integrate services
  2.1 API integration
    - [x] Update ade-api imports to use `ade_db` models/metadata.
    - [x] Update blob storage usage to use `ade_storage` helpers.
  2.2 Worker integration
    - [x] Update ade-worker imports to use `ade_db` models/metadata.
    - [x] Update blob storage usage to use `ade_storage` helpers.

3.0 Migrations and CLI
  3.1 ade db commands
    - [x] Add `ade db migrate` (upgrade head) command to root CLI.
    - [x] Optionally add `ade db history/current/stamp` if needed.
  3.2 Tests
    - [x] Update tests for new package locations.

### Open Questions

- None.

---

## Acceptance Criteria

- Shared DB schema/migrations live in `ade_db` and are used by both services.
- Shared blob helpers live in `ade_storage` and are used by both services.
- `ade db migrate` applies migrations successfully.
- API/worker runtime behavior remains unchanged.

---

## Definition of Done

- No duplicated schema/migration or storage helper code remains in api/worker.
- All imports updated and tests pass.
