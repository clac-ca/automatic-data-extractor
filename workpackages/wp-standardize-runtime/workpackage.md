# Work Package: Standardize Runtime, Deployment, and Repo Layout

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Move ADE toward standard, straightforward deployment and layout patterns. Use a single `apps/` root for all services (no root `/src`), keep API and worker fully standalone, and serve the web app via a conventional nginx config. Retain the single-image goal while running services as separate containers/commands.

### Scope

- In:
  - Standardize runtime roles (api, worker, web) with the same image.
  - Make nginx configuration standard (static config file in nginx paths).
  - Make database migrations explicit (separate command/job).
  - Remove dynamic port-switching defaults in favor of fixed, explicit ports.
  - Collapse repo layout to a single top-level `apps/` (remove root `/src`).
  - Ensure API and worker are standalone (no shared Python modules).
  - Update docs and compose files to reflect the standard approach.
- Out:
  - Changing ADE runtime behavior beyond startup/serving (engine logic, API routes).
  - Re-architecting frontend build system (Vite stays).
  - Changing data model or storage backends.

### Work Breakdown Structure (WBS)

1.0 Target Architecture Definition
  1.1 Decide standard runtime model
    - [x] Confirm desired default: split containers by role (same image).
    - [x] Confirm fixed port policy for API and web.
    - [x] Confirm migration strategy (explicit command).
  1.2 Document standard runtime contract
    - [x] Define required env vars for API, worker, and web roles.
    - [x] Define nginx proxy target behavior for split mode.

2.0 nginx Standardization
  2.1 Add standard nginx config
    - [x] Add `default.conf` (or template) in a standard nginx path.
    - [x] Use a standard env-substitution path (or static upstream) for /api.
  2.2 Remove bespoke nginx runtime
    - [x] Remove Python-generated nginx config and runtime wrapper.

3.0 Process and Port Standardization
  3.1 Make migrations explicit
    - [x] Add/confirm a migration command or container entrypoint.
    - [x] Remove automatic migrations from the default start flow.
  3.2 Fix ports
    - [x] Set API port to a fixed default (e.g., 8000).
    - [x] Set web port to a fixed default (e.g., 8080 or 8000) and update nginx config.
    - [x] Update CLI help text and env var docs accordingly.

4.0 Repo Layout + Packaging
  4.1 Remove root `/src` and root distribution
    - [x] Delete root `src/` package.
    - [x] Remove root `pyproject.toml` and `uv.lock`.
  4.2 Restore per-service packaging
    - [x] Restore `apps/ade-api/pyproject.toml` with only `ade-api` CLI.
    - [x] Restore `apps/ade-worker/pyproject.toml`.
    - [x] Ensure no shared Python modules between API and worker.
  4.3 Update local setup
    - [x] Update `setup.sh` to sync per-service deps into a shared venv.
    - [x] Update developer docs for new setup/commands.

5.0 Deployment and Docs
  5.1 Compose files
    - [x] Make split-mode compose the default (single image, multi-container).
    - [x] Remove all-in-one commands from default docs.
  5.2 Documentation
    - [x] Update README and docs to reflect standard layout and commands.
    - [x] Document migration step and role-based commands.

6.0 Verification
  6.1 Local validation
    - [x] Build the image and run split-mode compose.
    - [x] Confirm web serves SPA and proxies /api correctly.
    - [x] Confirm migrations run explicitly and API starts without auto-migrate.

Notes:
- Local validation used `ADE_BLOB_CONTAINER=ade` to satisfy azurite init.

### Open Questions

- None. Decisions: split containers are the default; no root `/src`; no shared Python modules between API and worker.
- Fixed ports: API defaults to 8000; web defaults to 8080.
- Migrations are explicit via CLI (`ade-api migrate`).

---

## Acceptance Criteria

- A single image can run api, worker, and web roles separately using standard commands.
- Repo layout uses a single top-level `apps/` (no root `src/`).
- API and worker are standalone (no shared Python modules).
- nginx uses a standard config file (or template) in nginx paths.
- Migrations are explicit and no longer run on every default start.
- Ports are fixed and documented; no dynamic port swapping.
- Docs and compose files reflect the standard, split-first deployment model.

---

## Definition of Done

- All WBS tasks are checked off.
- Docs updated and consistent with runtime behavior.
- Basic local validation completed for split-mode deployment.
