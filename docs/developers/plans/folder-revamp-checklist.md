# Backend & Frontend Folder Revamp Plan

This document inventories the work needed to migrate from the current `backend/` + `frontend/` layout to the structure described in `docs/developers/README.md`. It focuses on filesystem moves, tooling fallout, and validation checkpoints so we can execute the refactor in a single, predictable sequence.

## 1. Goals
- Relocate the FastAPI application under `apps/api/app/**` with the supporting assets outlined in the developer guide.
- Relocate the React Router project to `apps/web/**`.
- Stand up the `packages/ade-engine/` scaffold that will eventually house the runtime and provide a real install target for build/run flows.
- Keep local development (`npm run dev`), CI, Docker, and documentation working throughout the move.

## 2. Current Layout Snapshot
- `backend/app/**` — FastAPI code, migrations, shared libs, static web bundle, scripts.
- `backend/tests/**` — pytest suites.
- `frontend/**` — React Router app, node_modules, build artifacts.
- `engine/` — empty placeholder for future engine code.
- Node tooling (`scripts/*.mjs`) hard-codes `backend/app` & `frontend`.
- Dockerfile copies `backend/...` and `frontend/...` into the image.
- Docs across `docs/**` reference `backend/app/...` and `frontend/...`.
- Alembic configuration (`alembic.ini`, `backend/app/shared/db/migrations/env.py`) and tests (`backend/tests/services/db/test_migrations.py`) assume migrations under `backend/app/shared/db/migrations`.
- Root `.env.example`, `.gitignore`, and various docs reference `backend/app/web/static`.
- CI / scripts expect Python package name `backend.app`.

## 3. Target Layout
The ADE monorepo brings together four cooperating layers:

* **Frontend (React Router)** — web app where workspace owners create and manage config packages, edit code, and trigger builds and runs.
* **Backend (Python FastAPI)** — API service that stores metadata, builds isolated Python environments, and orchestrates job execution.
* **Engine (Python `ade_engine`)** — runtime module that executes inside the worker process, reading spreadsheets, applying detectors and hooks, and producing normalized outputs with full audit trails.
* **Config package (Python `ade_config`)** — built and managed in the frontend; defines the business logic that tells ADE how to detect, map, and transform data. Versioned for draft, testing, rollback, and extension through a flexible Python interface.

```text
automatic-data-extractor/
├─ apps/                                   # Deployable applications (things you run/ship)
│  ├─ api/                                 # FastAPI service (serves /api + static SPA)
│  │  ├─ app/
│  │  │  ├─ main.py                        # mounts: /api routers; serves / from ./web/static
│  │  │  ├─ api/                           # route modules (FastAPI routers)
│  │  │  ├─ core/                          # settings, logging, lifespan, security
│  │  │  ├─ services/                      # build/run orchestration, queues
│  │  │  ├─ repositories/                  # DB access & persistence layer
│  │  │  ├─ schemas/                       # Pydantic models (request/response/DB)
│  │  │  ├─ workers/                       # subprocess/worker orchestration
│  │  │  ├─ web/static/                    # ← SPA build copied here at image build time (DO NOT COMMIT)
│  │  │  └─ templates/                     # optional: server-rendered templates/emails
│  │  ├─ migrations/                       # Alembic migration scripts
│  │  ├─ pyproject.toml                    # Python project for the API app
│  │  └─ tests/                            # API service tests
│  │
│  └─ web/                                 # React SPA (Vite)
│     ├─ src/                              # routes, components, features
│     ├─ public/                           # static public assets
│     ├─ package.json
│     └─ vite.config.ts
│
├─ packages/                               # Reusable libraries (imported by apps)
│  └─ ade-engine/                          # installable Python package: ade_engine
│     ├─ pyproject.toml
│     ├─ src/ade_engine/                   # engine runtime, IO, pipeline, hooks integration
│     └─ tests/                            # engine unit tests
│
├─ templates/                              # Starter content templates (user-facing seeds)
│  └─ config-packages/
│     ├─ default/
│     │  ├─ template.manifest.json         # catalog metadata (name/description/tags/min engine)
│     │  └─ src/ade_config/                # detectors/hooks + runtime manifest/env
│     │     ├─ manifest.json               # read via importlib.resources
│     │     ├─ config.env                  # optional env vars for this config
│     │     ├─ column_detectors/           # detect → transform (opt) → validate (opt)
│     │     ├─ row_detectors/              # header/data row heuristics
│     │     └─ hooks/                      # on_job_start/after_mapping/before_save/on_job_end
│     └─ <other-template>/
│        ├─ template.manifest.json
│        └─ src/ade_config/...
│
├─ specs/                                   # JSON Schemas & other formal specs
│  ├─ config-manifest.v1.json               # config package manifest schema
│  └─ template-manifest.v1.json             # template catalog schema
│
├─ examples/                                # sample inputs/outputs for docs/tests
├─ docs/                                    # Developer Guide, HOWTOs, operations runbooks
├─ scripts/                                 # helper scripts (seed data, local tools, etc.)
│
├─ infra/                                   # deployment infra (container, compose, k8s, IaC)
│  ├─ docker/
│  │  └─ api.Dockerfile                     # multi-stage: build web → copy dist → apps/api/app/web/static
│  ├─ compose.yaml                          # optional: local prod-style run
│  └─ k8s/                                  # optional: manifests/helm when needed
│
├─ Makefile                                 # friendly entrypoints (setup/dev/build/run)
├─ .env.example                             # documented env vars for local/dev
├─ .editorconfig
├─ .pre-commit-config.yaml
├─ .gitignore
└─ .github/workflows/                       # CI: lint, test, build, publish
```

Everything ADE produces (config_packages, venvs, jobs, logs, cache, etc..) is persisted under `ADE_DATA_DIR` (default `./data`). In production, this folder is typically mounted to an external file share so it persists across restarts.

```text
${ADE_DATA_DIR}/
├─ workspaces/
│  └─ <workspace_id>/
│     ├─ config_packages/           # GUI-managed installable config projects (source of truth)
│     │  └─ <config_id>/
│     │     ├─ pyproject.toml       # Distribution metadata (ade-config)
│     │     ├─ requirements.txt     # Optional overlay pins (editable in GUI)
│     │     └─ src/ade_config/
│     │        ├─ column_detectors/ # detect → transform (opt) → validate (opt)
│     │        ├─ row_detectors/    # header/data row heuristics
│     │        ├─ hooks/            # on_job_start/after_mapping/before_save/on_job_end
│     │        ├─ manifest.json     # read via importlib.resources
│     │        └─ config.env        # optional env vars
│     ├─ venvs/                     # One Python virtualenv per config_id
│     │  └─ <config_id>/
│     │     ├─ bin/python
│     │     ├─ ade-runtime/
│     │     │  ├─ packages.txt      # pip freeze
│     │     │  └─ build.json        # {config_version, engine_version, python_version, built_at}
│     │     └─ <site-packages>/
│     │        ├─ ade_engine/...    # Installed ADE engine
│     │        └─ ade_config/...    # Installed config package
│     ├─ jobs/                      # One working directory per job (inputs, outputs, audit)
│     │  └─ <job_id>/
│     │     ├─ input/               # Uploaded files
│     │     ├─ output/              # Generated output files
│     │     └─ logs/
│     │        ├─ artifact.json     # human/audit-readable narrative
│     │        └─ events.ndjson     # append-only timeline
│     └─ documents/
│        └─ <document_id>.<ext>     # optional shared document store
│
├─ db/
│  └─ app.sqlite                    # SQLite in dev (or DSN for prod)
├─ cache/
│  └─ pip/                          # pip download/build cache (safe to delete)
└─ logs/                            # optional: centralized service logs
```

## 4. Migration Steps

### 4.1 Scaffolding & Moves
1. Create destination directories: `apps/api/{app,migrations,tests}`, `apps/web`, and `packages/ade-engine`.
2. Move Python modules from `backend/app/**` into `apps/api/app/**`, preserving the internal structure for now (`features` can be re-homed later, but ensure imports still resolve).
3. Relocate `backend/app/shared/db/migrations` to `apps/api/migrations` and adjust package imports accordingly.
4. Move `backend/tests/**` into `apps/api/tests/**`; update any relative fixtures that assume `tests/` lives under `backend/`.
5. Relocate the React project (`frontend/**`) into `apps/web/**`, including hidden files like `.eslintrc`, `.npmrc`, etc. Ensure `apps/web/node_modules` remains ignored.
6. If any tooling expects a `backend/app/web/static/README.md`, move it alongside the static directory under `apps/api/app/web`.
7. Drop the empty `backend/` and `frontend/` directories after verifying all references point to the new locations.

### 4.2 Python Packaging & Tooling
1. Update `pyproject.toml`:
   - Adjust `tool.setuptools.packages.find` include pattern to `["apps.api.app*"]` (or maintain a shim for `backend.app` if we expose a namespace).
   - Refresh `tool.setuptools.package-data` glob paths (static assets, migrations under `apps/api/migrations`).
   - Update pytest, coverage, and mypy configuration paths (`apps/api/tests`, `apps/api/app`).
2. Update imports across Python modules and tests. Options:
   - Keep `backend.app` as a namespace package by adding a thin shim (e.g., `backend/app/__init__.py` inside a compatibility package under `apps/api`) to avoid touching every import immediately.
   - Or rename to `apps.api.app` and run a bulk `sed`/editor replace for `backend.app` → `apps.api.app`.
3. Update Alembic:
   - `alembic.ini` `script_location` to `apps/api/migrations`.
   - `apps/api/migrations/env.py` (moved from `backend/app/shared/db/migrations/env.py`) to import the new settings module path.
   - Any direct references in migration scripts (e.g., relative imports) to the new package path.
4. Ensure `backend/tests/services/db/test_migrations.py` (now under `apps/api/tests/...`) looks for the new tables without referencing old paths.
5. Update `Dockerfile`:
   - COPY backend files from `apps/api`.
   - Copy SPA bundle into `apps/api/app/web/static`.
   - Adjust CMD to `uvicorn apps.api.app.main:create_app` (or the shim path).
6. Update `compose.yaml` and any other scripts invoking the module path (CLI helpers, `Python -m` commands).

### 4.3 Node Tooling & Scripts
1. Update all `.mjs` helpers in `scripts/` (`npm-dev`, `npm-build`, `npm-test`, `npm-ci`, `npm-lint`, `npm-openapi-typescript`, `routes-*`, `npm-clean`, `npm-setup`, `npm-reset`, `npm-start`, `npm-workpackage`, etc.) to look for `apps/api/app` and `apps/web`.
2. Revise root `package.json` scripts to:
   - Use the new backend module path when launching uvicorn (`apps/api/app/main.py`).
   - Pass `--prefix apps/web` (or set `cwd`) for frontend commands.
   - Update `npm run build` to copy `apps/web/build/client` into `apps/api/app/web/static`.
3. Update generated file destinations (OpenAPI types) to `apps/web/src/generated`.
4. Ensure `ade` CLI continues to proxy to the correct npm scripts after rewiring.
5. Verify `npm run workpackage` expectations if it inspects paths under `backend/` (check `.workpackage` attachments).

### 4.4 Environment & Config
1. Ensure `.env.example` keys align with the new directory expectations (already partially updated for ADE data directories).
2. Update `backend/app/shared/core/config.py` (soon under `apps/api/app/shared/core/config.py`) defaults if paths change (e.g., `PROJECT_ROOT` calculation uses relative parents—verify after move).
3. Review `.gitignore`, `.dockerignore`, and lint/test configs for stale references (`backend/app/web/static`, `frontend/build`, etc.).
4. Verify any hard-coded paths in scripts (e.g., `npm-clean.mjs` removing `backend/app/web/static`) point to the new locations.

### 4.5 Documentation & Metadata
1. Global search for `backend/app` and `frontend/` references across:
   - `docs/**` (developer guide, admin guide, glossary, reference, workpackage notes).
   - Root `README.md`, `AGENTS.md`, `CHANGELOG.md`.
   - `docs/developers/_archive` materials (update or annotate with legacy status).
2. Update architecture diagrams and ASCII trees in docs to show the new structure.
3. Refresh command examples (e.g., `npm run build` comment pointing to `backend/app/web/static`) to reference `apps/api/app/web/static`.
4. Update changelog or release notes if they describe the old structure or mention migration steps.

### 4.6 Engine Package Scaffold
1. Remove the empty `engine/` directory.
2. Create `packages/ade-engine/pyproject.toml`, `src/ade_engine/__init__.py`, and placeholder tests to unblock future engine work.
3. Update docs and build scripts to point to `packages/ade-engine` when building the venv (including README snippets and `docs/developers/README.md` example commands).
4. Ensure the engine package is excluded from lint/test scripts until populated (or add stubs so they pass).

### 4.7 Order of Operations (Suggested)
1. Create destination scaffolding (`apps/api`, `apps/web`, `packages/ade-engine`) without moving files yet.
2. Introduce a temporary namespace shim so imports continue to resolve once files move.
3. Move backend files + migrations; update python packaging config; run pytest to confirm.
4. Move frontend project; update npm scripts; run `npm run test` (frontend only).
5. Update toolchain scripts, env files, and docs.
6. Update Dockerfile/compose & rebuild to verify container pathing.
7. Perform final cleanup (`.gitignore`, dead directories) and rerun full CI (`npm run ci`).

## 5. Validation Checklist
- `npm run setup` installs dependencies in the new locations.
- `npm run dev`, `npm run dev:backend`, and `npm run dev:frontend` (or their future equivalents) launch correctly.
- `npm run build` writes the SPA bundle to `apps/api/app/web/static`.
- `npm run test` executes both pytest and Vitest with updated paths.
- `npm run ci` passes end-to-end.
- `docker compose build` succeeds and the container serves the API from the new module path (`apps.api.app.main` or shim).
- Alembic `command upgrade head` works with migrations in `apps/api/migrations`.
- Workpackage tooling (`npm run workpackage`) still operates with updated paths.
- Static path references in docs (e.g., `docs/reference/glossary.md`) reflect the new layout.

## 6. Open Questions / Decisions
- **Package name retention:** keep `backend.app` as an import alias via `src/backend/app/__init__.py` shim or fully rename to `apps.api.app`? Decide before bulk renames.
- **Feature → Services breakdown:** immediate re-homing of `features/**` into `services/`, `repositories/`, `schemas/`, `workers/`, or defer until after the move?
- **Future queue implementation:** if queue primitives are reintroduced, confirm where they live (`app/services` vs. separate package).
- **Node package manager strategy:** remain on npm with `--prefix` or adopt workspace tooling (pnpm/npm workspaces) once layout stabilises.
- **Release packaging:** confirm `pip install` workflow still produces the expected artifacts with the new directory structure (adjust `MANIFEST.in` if we add one for engine package).

Document updates and further refinements can append to this checklist as new requirements surface.
