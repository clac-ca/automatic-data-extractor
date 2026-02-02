# Work Package: Unified Backend Pyproject + Frontend Layout

Guiding Principle:
Make ADE a clean, unified, and easily operable system with one backend distribution, clear shared infrastructure, and a simple default workflow that still allows each service to run independently.


> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Unify the backend into a single Python distribution under `backend/` while keeping separate service packages (`ade_api`, `ade_worker`) and shared internal packages (`ade_db`, `ade_storage`). Move the frontend to `frontend/ade-web`. Provide a root `ade` CLI that starts/dev/tests all services, delegates per-service commands, and exposes shared DB migrations via `ade db`. Simplify Docker builds, normalize paths, and replace outdated docs with a fresh set aligned to the new layout. Update version reporting to a simple, standard shape across API and UI.

Desired folder structure:

```
automatic-data-extractor/
├─ backend/
│  ├─ pyproject.toml
│  ├─ uv.lock
│  ├─ ade-api/
│  │  ├─ src/ade_api/...
│  │  ├─ tests/...
│  │  └─ README.md
│  ├─ ade-worker/
│  │  ├─ src/ade_worker/...
│  │  ├─ tests/...
│  │  └─ README.md
│  ├─ ade-db/
│  │  ├─ src/ade_db/...
│  │  └─ tests/...
│  ├─ ade-storage/
│  │  ├─ src/ade_storage/...
│  │  └─ tests/...
│  └─ scripts/           # optional backend-only scripts
├─ frontend/
│  └─ ade-web/
│     ├─ package.json
│     ├─ src/...
│     └─ nginx/...
├─ Dockerfile
├─ docker-compose.yaml
├─ docker-compose.prod.yaml
├─ setup.sh
├─ README.md
├─ docs/
├─ data/
└─ workpackages/
```

Locked decisions:

- Distribution name: `automatic-data-extractor` (root `ade` CLI).
- Dependencies: single combined backend dependency set + `dev` extra.
- Orchestration: root `ade` CLI spawns api/worker/web processes; use `tini` for signal handling.
- Web entrypoint naming: keep `entrypoint.sh` (most standard) and have `ade web start` execute it.
- CLI structure: root `ade` commands (`start`, `dev`, `test`) plus service delegation via `ade api|worker|web`.
- Shared infra packages: create separate internal packages `ade-db` and `ade-storage` under `backend/`.
- DB migrations: primary command is `ade db migrate` (service CLIs may offer aliases).
- Version response shape: `backend`, `engine`, `web` strings.
- Web version source: generated `version.json` during frontend build; API reads with fallback.

CLI command map (target behavior):

- Root
  - `ade start` -> start api + worker + web (default; supports `ADE_SERVICES` / `--services`).
  - `ade dev` -> api dev (reload) + worker start + web dev (Vite).
  - `ade test` -> run api + worker + web tests.
- DB
  - `ade db migrate` (primary)
  - `ade db history` | `ade db current` | `ade db stamp` (optional)
- API
  - `ade api start` | `ade api dev` | `ade api routes` | `ade api types` | `ade api users` | `ade api test` | `ade api lint`
  - `ade api migrate` (optional alias to `ade db migrate`)
- Worker
  - `ade worker start` | `ade worker dev` | `ade worker gc` | `ade worker test`
- Web
  - `ade web start` (nginx + built assets)
  - `ade web dev` (Vite)
  - `ade web build` | `ade web test` | `ade web test:watch` | `ade web test:coverage` | `ade web lint` | `ade web typecheck` | `ade web preview`

### Scope

- In:
  - New repo layout with `backend/ade-api`, `backend/ade-worker`, `frontend/ade-web`.
  - Shared internal packages `backend/ade-db` + `backend/ade-storage`.
  - Single `pyproject.toml` in `backend/` covering both backend packages.
  - Root `ade` CLI with `start`, `dev`, `test`, plus `ade api|worker|web` delegation.
  - `ade db` migrations command backed by `ade_db`.
  - Dockerfile/compose/setup/docs updates to reflect the new layout and CLI.
  - Simplified Docker build using one backend install step.
  - Unified test orchestration with per-service test targeting preserved.
  - Normalized path references to `backend/` and `frontend/`.
  - Simplified frontend hooks for `ade web` commands.
  - Update version reporting to a standard shape + UI alignment (separate subpackage).
  - Documentation rewrite from scratch (separate subpackage).
- Out:
  - Changes to ade-engine or ade-config repositories.
  - Semantic changes to API/worker runtime behavior beyond process orchestration.

### Subpackages (Suggested Sequencing)

1) `subpackages/shared-infra` (after layout/packaging foundation)
2) `subpackages/cli` (after shared infra so `ade db` exists)
3) `subpackages/versions` (after CLI + layout; before docs rewrite)
4) `subpackages/docs` (last, once commands and paths are finalized)

### Execution Stages (Suggested)

Stage 1: Repo layout + unified backend packaging (WBS 1.0)
Stage 2: Shared infra packages (WBS 2.0)
Stage 3: Root CLI + service delegation (WBS 3.0)
Stage 4: Test orchestration + frontend hooks (WBS 4.0–5.0)
Stage 5: Container/runtime updates (WBS 6.0)
Stage 6: Version reporting (WBS 7.0)
Stage 7: Docs + release tooling and docs rewrite (WBS 8.0–9.0)

### Work Breakdown Structure (WBS)

1.0 Repo layout + packaging (foundation)
  1.1 Move backend/frontend folders
    - [x] Create `backend/ade-api` and `backend/ade-worker` paths and move code/tests/readmes.
    - [x] Create `backend/ade-db` and `backend/ade-storage` paths.
    - [x] Move `apps/ade-web` to `frontend/ade-web`.
    - [x] Update references to old paths in scripts, docs, and configs.
  1.2 Unified backend pyproject
    - [x] Create `backend/pyproject.toml` with combined metadata, deps, scripts, and package data.
    - [x] Configure package discovery for `backend/ade-api/src` and `backend/ade-worker/src`.
    - [x] Configure package discovery for `backend/ade-db/src` and `backend/ade-storage/src`.
    - [x] Consolidate tooling config (pytest, ruff, mypy, coverage) at backend root.
    - [x] Generate a single `backend/uv.lock` and remove per-service locks.

2.0 Shared infra (subpackage)
  2.1 Centralize DB + storage
    - [x] Complete shared DB/storage packages (see `subpackages/shared-infra/workpackage.md`).

3.0 CLI orchestration
  3.1 CLI subpackage
    - [x] Complete CLI implementation (see `subpackages/cli/workpackage.md`).

4.0 Test orchestration
  4.1 Root + per-service tests
    - [x] Implement `ade test` to run api + worker + web tests.
    - [x] Preserve `ade api test` and `ade worker test` for targeted runs.
    - [x] Keep frontend tests runnable via `ade web test`.

5.0 Frontend hooks
  5.1 Simplify `ade web` commands
    - [x] Centralize npm command invocation and path handling for web subcommands.

6.0 Container + runtime
  6.1 Dockerfile updates
    - [x] Point backend installs to `backend/pyproject.toml`.
    - [x] Build frontend from `frontend/ade-web` and copy dist into nginx.
    - [x] Install `tini` and set ENTRYPOINT for proper signal handling.
    - [x] Set image default CMD to `ade start`.
    - [x] Remove multi-step backend install (single `uv sync` for unified backend).
  6.2 Flexible service composition
    - [x] Add entrypoint/supervisor to start api/worker/web based on `ADE_SERVICES`.
    - [x] Keep single-image, multi-container usage supported (api+web, worker, etc.).

7.0 Version reporting (subpackage)
  7.1 API + frontend update
    - [x] Complete version reporting updates (see `subpackages/versions/workpackage.md`).

8.0 Docs + release tooling
  8.1 Docs and scripts
    - [x] Update `setup.sh` to install backend deps via `backend/pyproject.toml` and frontend via `frontend/ade-web`.
    - [x] Update docs to reference new paths and CLI commands.
    - [x] Normalize all path references from `apps/` to `backend/` + `frontend/`.
  8.2 Release Please config
    - [x] Update release config to the new backend version file location (if needed).
    - [x] Confirm tag/version strategy for unified backend distribution.

9.0 Docs rewrite (subpackage)
  9.1 Replace existing docs set
    - [x] Complete documentation rewrite (see `subpackages/docs/workpackage.md`).

### Open Questions

- None.

---

## Acceptance Criteria

- Backend code lives under `backend/ade-api` + `backend/ade-worker` with one `backend/pyproject.toml`.
- Shared packages `backend/ade-db` + `backend/ade-storage` are integrated by both services.
- Frontend lives under `frontend/ade-web` and builds into the image.
- `ade start` runs api+worker+web by default; `ade api|worker|web ...` run individually.
- Image defaults to `ade start` and supports `ADE_SERVICES` for composition.
- Setup scripts, Dockerfile, and docs reflect the new layout.

---

## Definition of Done

- `ade test` (all services) runs successfully.
- `ade start` works in a single container and services come up.
- API+web and worker-only container scenarios are documented and functional.
- No references to old `apps/` paths remain in scripts/docs.
