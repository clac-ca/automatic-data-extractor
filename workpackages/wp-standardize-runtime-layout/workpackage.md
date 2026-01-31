# Work Package: Standardize Runtime Layout and Startup

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Make the container runtime layout and startup behave like a standard Python app: package migrations, avoid repo-layout assumptions, and remove bespoke quickstart init containers. Keep the Docker and Compose files simple, predictable, and easy to read.

### Scope

- In:
  - Package Alembic config + migrations inside the ade-api wheel.
  - Update migration loading to use packaged resources (no repo-relative paths).
  - Make `ade start` work without repo layout on disk.
  - Remove `blob_init` from quickstart Compose and document an explicit storage init option.
  - Make data volume usage explicit and allow optional bind mount in docs.
  - Remove runtime reliance on `apps/ade-*` paths where possible.
- Out:
  - Breaking changes to ADE API or worker behavior unrelated to startup/migrations.
  - Re-architecting storage or database systems.
  - UI or workflow changes outside runtime/deployment paths.

### Work Breakdown Structure (WBS)

1.0 Package migrations inside ade-api
  1.1 Package data changes
    - [x] Add Alembic config + migrations to package data in `apps/ade-api/pyproject.toml`.
    - [x] Ensure package includes migrations for sdist and wheel builds.
  1.2 Migration loader changes
    - [x] Update migration code to resolve Alembic ini + migrations via package resources.
    - [x] Add fallback or clear error if resources are missing.
  1.3 Settings defaults
    - [x] Update `Settings` defaults for Alembic paths to use packaged resources (no repo-relative defaults).
    - [x] Remove or deprecate `api_root` if it is not needed at runtime.

2.0 Remove repo-layout dependency at runtime
  2.1 CLI path resolution
    - [x] Remove or relax `ensure_backend_dir` requirement for production/runtime flows.
    - [x] Ensure `ade start` uses package resources and does not require `apps/` paths.
  2.2 Frontend dist resolution
    - [x] Prefer `ADE_FRONTEND_DIST_DIR` when set; avoid implicit repo paths in production.
    - [x] Add a packaged/static fallback or a clean opt-out when dist assets are not present.
  2.3 Dockerfile/runtime env cleanup
    - [x] Remove `PYTHONPATH` and repo-source copies once runtime no longer needs them.
    - [x] Set explicit `ADE_FRONTEND_DIST_DIR` in the production image if needed.

3.0 Simplify quickstart storage init
  3.1 Remove `blob_init`
    - [x] Remove `blob_init` service from `docker-compose.yaml`.
    - [x] Update `depends_on` in `docker-compose.yaml` accordingly.
  3.2 Document storage init options
    - [x] Add a simple manual step (CLI or script) to create the container.
    - [x] Document manual container creation (no auto-create option).

4.0 Data volume clarity
  4.1 Compose defaults
    - [x] Keep named volume as default for data dir in compose files.
    - [x] Add commented bind-mount example for host-visible data.
  4.2 Docs
    - [x] Document how to switch between named volume and bind mount.
    - [x] Call out permissions considerations for bind mounts.

### Open Questions

- Do we want to add an explicit `ade storage init` command, or keep manual container creation only?

---

## Acceptance Criteria

- `ade start` runs in the production image without any repo layout copied into the container.
- Alembic migrations run successfully using packaged resources.
- `docker-compose.yaml` quickstart works without `blob_init` and provides a clear manual or CLI option for container creation.
- Docs explain named volume defaults and how to switch to bind mounts.
- All changes are simple, explicit, and easy to follow in code.

---

## Definition of Done

- WBS tasks completed and checked.
- Updated docs reflect new behavior and commands.
- Quickstart compose validated locally.
- No hidden abstractions or bespoke runtime dependencies remain.
