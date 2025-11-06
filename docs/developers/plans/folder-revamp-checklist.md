# Backend & Frontend Folder Revamp Plan

This document inventories the work needed to migrate from the current `backend/` + `frontend/` layout to the structure described in `docs/developers/README.md`. It focuses on filesystem moves, tooling fallout, and validation checkpoints so we can execute the refactor in a single, predictable sequence.

## 1. Goals
- Relocate the FastAPI application under `apps/api/app/**` with the supporting assets outlined in the developer guide.
- Relocate the React Router project to `apps/web/**`.
- Stand up the `packages/ade-engine/` scaffold that will eventually house the runtime.
- Keep local development (`npm run dev`), CI, Docker, and documentation working throughout the move.

## 2. Current Layout Snapshot
- `backend/app/**` — FastAPI code, migrations, shared libs, static web bundle.
- `backend/tests/**` — pytest suites.
- `frontend/**` — React Router app, node_modules, build artifacts.
- `engine/` — empty placeholder for future engine code.
- Node tooling (`scripts/*.mjs`) hard-codes `backend/app` & `frontend`.
- Dockerfile copies `backend/...` and `frontend/...` into the image.
- Docs across `docs/**` reference `backend/app/...` and `frontend/...`.

## 3. Target Layout
```
apps/
  api/
    app/
      main.py
      api/
      core/
      services/
      repositories/
      schemas/
      workers/
      web/static/
      templates/
    migrations/
    pyproject.toml
    tests/
  web/
    package.json
    vite.config.ts
    src/
    public/
packages/
  ade-engine/
    pyproject.toml
    src/ade_engine/
    tests/
```

## 4. Migration Steps

### 4.1 Scaffolding & Moves
1. Create `apps/api/app/`, `apps/api/migrations/`, `apps/api/tests/`, `apps/web/`, and `packages/ade-engine/`.
2. Move Python modules from `backend/app/**` into `apps/api/app/**`, preserving relative structure for `api`, `core`, `features` (→ interim `services`/`repositories`/`schemas`/`workers` split), `shared`, `scripts`, and `web`.
3. Move `backend/tests/**` into `apps/api/tests/**`.
4. Relocate the React project (`frontend/**`) into `apps/web/**`.
5. Delete the now-empty `backend/` and `frontend/` directories once all references are updated.

### 4.2 Python Packaging & Tooling
1. Update `pyproject.toml`:
   - Adjust `tool.setuptools.packages.find` include pattern to `["apps.api.app*"]`.
   - Refresh `tool.setuptools.package-data` paths (static assets, migrations).
   - Update pytest, coverage, mypy paths (`apps/api/tests`, `apps/api/app`).
2. Update import paths throughout the codebase (`backend.app...` → new package name). Decide whether to keep `backend.app` as the canonical module (via namespace package) or rename to `apps.api.app`. If renaming, update every `from backend.app...` import, Alembic env, etc.
3. Adjust `alembic.ini` and `backend/app/shared/db/...` modules to the new package paths and migration location (`apps/api/migrations`).
4. Update `Dockerfile` COPY instructions, `CMD`, and static copy target to match `apps/api/app/web/static`.
5. Update `compose.yaml` or other infra scripts if they reference the old module path.

### 4.3 Node Tooling & Scripts
1. Update all `.mjs` helpers in `scripts/` to look for `apps/api/app` and `apps/web`.
2. Revise root `package.json` scripts (`dev`, `build`, `test`, `lint`, etc.) to invoke npm/yarn in `apps/web` and python tooling in `apps/api`.
3. Update generated file destinations (OpenAPI types) to `apps/web/src/generated`.
4. Confirm `npm run workpackage`, `routes:*`, and `ade` helper still function with the new paths.

### 4.4 Environment & Config
1. Ensure `.env.example` keys align with the new directory expectations (already partially updated).
2. Update any Python settings defaults (e.g., `DEFAULT_DATA_DIR`) if path normalization changes.
3. Review `.gitignore` and cleanup entries referencing `backend/app/web/static` or `frontend/build`.

### 4.5 Documentation & Metadata
1. Search/replace doc references under `docs/**`, `AGENTS.md`, `README.md`, etc., to the new paths (e.g., `apps/api/app/...`, `apps/web/...`).
2. Update architecture diagrams or ASCII trees that still show `backend/` or `frontend/`.
3. Refresh changelog entries if they describe the old structure.

### 4.6 Engine Package Scaffold
1. Move (or delete) the empty `engine/` directory.
2. Create `packages/ade-engine/pyproject.toml`, `src/ade_engine/__init__.py`, and placeholder tests to unblock future engine work.
3. Wire the backend build process (`npm run build`, Dockerfile, docs) to expect the engine package in `packages/ade-engine`.

## 5. Validation Checklist
- `npm run setup` installs dependencies in the new locations.
- `npm run dev`, `npm run dev:backend`, and `npm run dev:frontend` (or their future equivalents) launch correctly.
- `npm run build` writes the SPA bundle to `apps/api/app/web/static`.
- `npm run test` executes both pytest and Vitest with updated paths.
- `npm run ci` passes end-to-end.
- `docker compose build` succeeds and the container serves the API from the new module path.
- Alembic `command upgrade head` works with migrations in `apps/api/migrations`.

## 6. Open Questions / Decisions
- **Package name retention:** keep `backend.app` as an import alias via `src/backend/app/__init__.py` shim or fully rename to `apps.api.app`? Decide before bulk renames.
- **Feature → Services breakdown:** immediate re-homing of `features/**` into `services/`, `repositories/`, `schemas/`, `workers/`, or defer until after the move?
- **Future queue implementation:** if queue primitives are reintroduced, confirm where they live (`app/services` vs. separate package).
- **Node package manager strategy:** remain on npm with `--prefix` or adopt workspace tooling (pnpm/npm workspaces) once layout stabilises.

Document updates and further refinements can append to this checklist as new requirements surface.
