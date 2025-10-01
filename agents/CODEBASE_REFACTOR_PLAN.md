# ADE Backend + Frontend Co-location Refactor — One-Pass Migration Plan

> **Status (implemented):** The repository now uses the feature-first `app/` package. FastAPI serves `/api/*` routes alongside the compiled React assets in `app/static/`, the CLI lives under `app/cli`, migrations moved to `app/alembic`, and tests relocated to the top-level `tests/` package. The guidance below remains as historical context for the migration.

**Objective**: Execute a single, tightly-scripted pass that migrates the current ADE backend, CLI, and build assets into the target `app/` package while serving the compiled React SPA from FastAPI. The plan below focuses on sequencing, automation, and safety nets so that the full move happens quickly without piecemeal follow-up work while respecting today’s operational surfaces (CLI tooling, migrations, and packaging contracts).

## Target end-state tree
```
monorepo/
├── app/
│   ├── __init__.py
│   ├── py.typed
│   ├── main.py                   # FastAPI app + start()
│   ├── core/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── db.py                 # engine/session helpers
│   │   ├── logging.py
│   │   ├── middleware.py
│   │   ├── responses.py
│   │   ├── message_hub.py
│   │   └── task_queue.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   ├── schemas.py
│   │   ├── dependencies.py
│   │   └── security.py
│   ├── users/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   ├── schemas.py
│   │   └── dependencies.py
│   ├── workspaces/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   ├── schemas.py
│   │   └── dependencies.py
│   ├── configurations/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   ├── schemas.py
│   │   └── dependencies.py
│   ├── documents/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   ├── schemas.py
│   │   ├── storage.py
│   │   └── dependencies.py
│   ├── jobs/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   ├── schemas.py
│   │   └── dependencies.py
│   ├── results/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   ├── schemas.py
│   │   └── dependencies.py
│   ├── health/
│   │   ├── __init__.py
│   │   └── router.py
│   ├── events/
│   │   ├── __init__.py
│   │   ├── recorder.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   ├── dependencies.py
│   │   └── schemas.py
│   ├── system/
│   │   ├── __init__.py
│   │   ├── repository.py
│   │   └── models.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── mixins.py
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── documents.py
│   │   ├── workspaces.py
│   │   ├── configurations.py
│   │   ├── jobs.py
│   │   ├── results.py
│   │   └── events.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── shared.py
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── static/
│   │   └── … (React build output)
│   └── cli/
│       ├── __init__.py
│       ├── __main__.py
│       ├── main.py              # argparse entry that dispatches to commands
│       ├── app.py               # builds argparse CLI surface
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── start.py
│       │   ├── users.py
│       │   ├── api_keys.py
│       │   ├── reset.py
│       │   └── settings.py      # representative existing commands retained
│       └── core/
│           ├── __init__.py
│           ├── output.py
│           └── runtime.py
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.js
├── scripts/
│   └── build_frontend.py
├── tests/
│   └── … (mirrors feature layout)
├── var/
├── alembic.ini
├── .env.example
└── pyproject.toml
```

---

## 1. Repo analysis & inventory
1. **Backend & entrypoint**
   - FastAPI now lives entirely in `app/main.py`, which mounts feature routers directly without the old `app/api.py` aggregator.【F:app/main.py†L1-L95】
   - Lifespan, middleware, and dependency injection are provided by modules in `app/core/` and each feature package's `dependencies.py`.
2. **Core services & configuration**
   - Settings live in `app/settings.py` using `pydantic-settings` and `.env` support.【F:app/settings.py†L49-L200】
   - Database helpers (`engine.py`, `session.py`, `bootstrap.py`, `mixins.py`) sit in `app/core/db/` alongside SQLAlchemy base definitions.
3. **Modules to migrate in this pass**
   - Router-backed features (`auth`, `users`, `workspaces`, `configurations`, `documents`, `jobs`, `results`, `health`) now sit under `app/<feature>` and are imported directly by `app/main.py`.【F:app/auth/router.py†L1-L37】【F:app/users/router.py†L1-L40】【F:app/workspaces/router.py†L1-L49】【F:app/configurations/router.py†L1-L40】【F:app/documents/router.py†L1-L40】【F:app/jobs/router.py†L1-L52】【F:app/results/router.py†L1-L47】【F:app/health/router.py†L1-L27】
   - Supporting packages without routers (`events`, `system`) supply persistence and services that other modules import and therefore moved alongside the feature-first layout.【F:app/events/service.py†L1-L48】【F:app/system/repository.py†L1-L42】
4. **Alembic & migrations**
   - Migration environment relocated to `app/alembic/`; repository-level `alembic.ini` points there.【F:app/alembic/env.py†L1-L48】
5. **CLI**
   - `[project.scripts] ade` in `pyproject.toml` points to `cli.main:main`; command set lives in `cli/commands/` with `start.py` orchestrating the API process.
6. **Frontend/static**
   - React SPA under `frontend/` built via Vite. `scripts/build_frontend.py` copies the compiled assets into `app/static/` so FastAPI can serve them.
7. **Tests & tooling**
   - Tests live under `tests/` and import the feature packages from `app.*`; lint/type tooling in `pyproject.toml` already targets the new layout.

---

## 2. Move map (source → target)
Execute via an automated relocation script (Python or shell) to guarantee a one-pass move while preserving history through `git mv`.

### 2.1 Package skeleton and shared utilities
- `app/__init__.py` retains the re-export of `Settings` helpers.
- `app/main.py` now handles router registration and exposes `start()` so the CLI can launch uvicorn directly.【F:app/main.py†L1-L96】
- The aggregator `app/api.py` was deleted during the move; routes live entirely in `app/main.py`.
- Core utilities remain under `app/core/` with middleware consolidated into `app/core/middleware.py`.
- Database helpers stay organised as `app/core/db/{bootstrap.py,engine.py,session.py}` with a new `__init__.py` exposing the public API.【F:app/core/db/__init__.py†L1-L26】
- ORM mixins continue under `app/models/mixins.py`; shared schema helpers sit in `app/schemas/`.
- Migrations moved from `app/migrations/` to `app/alembic/`, and `alembic.ini` was updated accordingly.【F:app/alembic/env.py†L1-L48】【F:alembic.ini†L1-L8】
- `app/py.typed` marks the package for typing, and `app/static/` now ships with the compiled frontend.

### 2.2 Feature and supporting modules
- `app/auth/*` → `app/auth/*` (router, dependencies, service, repository, schemas, security)
- `app/users/*` → `app/users/*`
- `app/workspaces/*` → `app/workspaces/*` (retain `routing.py` helper)
- `app/configurations/*` → `app/configurations/*`
- `app/documents/*` → `app/documents/*`
- `app/jobs/*` → `app/jobs/*`
- `app/results/*` → `app/results/*`
- `app/health/*` → `app/health/*`
- `app/events/*` → `app/events/*`
- `app/system/*` → `app/system/*`
- Move module-specific ORM models (currently alongside each module) into domain-specific files under `app/models/` and adjust imports (e.g., `app/users/models.py` → `app/models/users.py`).
- Keep shared schema utilities under `app/schemas/` and ensure each feature re-exports its public schemas through its own `__all__` declarations.

### 2.3 CLI & scripts
- `cli/{__init__.py,__main__.py,main.py}` → `app/cli/`
- `cli/app.py` → `app/cli/app.py`
- `cli/commands/**` → `app/cli/commands/**` (preserve every existing command module so current automation keeps working)
- `cli/core/**` → `app/cli/core/**`
- Update imports inside CLI modules from `cli.*` → `app.cli.*`
- Add `scripts/build_frontend.py` (new)

### 2.4 Tests and fixtures
- `tests/**` → `tests/**`
- Confirm fixtures import from `app.*` and drop references to the legacy `backend.api.*` modules.
- Ensure `tests/__init__.py` created if namespace packages require it

### 2.5 Static & packaging assets
- Introduce `app/static/` populated by build script
- Ensure `pyproject.toml` includes `app/static/**/*`, `app/alembic/**/*`, and `app/py.typed` as package data

### 2.6 Out-of-scope items for this pass
- Keep `backend/processor/` in place; the background runner depends on process orchestration that is not yet wired into FastAPI and should move in a later iteration once lifecycle contracts are clearer.【F:backend/processor/runner.py†L1-L81】
- Defer any new feature scaffolding (`ingest`, `rules`, `exports`) until the current API stabilises; note these as follow-up tasks in the work log rather than pre-creating empty packages.

---

## 3. API & routing plan (no aggregator)
1. `app/main.py` builds a single `FastAPI` instance and imports feature routers directly.
2. Mounting strategy under `"/api"`:
   - `app.health.router.router` included with `prefix="/api/health"` to preserve the explicit health endpoint.【F:app/health/router.py†L1-L23】
   - Feature routers with their own prefixes (`auth`) or explicit route paths (`users`, `workspaces`, `documents`) are included via `prefix="/api"` so their existing paths automatically nest under `/api`.【F:app/auth/router.py†L21-L40】【F:app/users/router.py†L1-L40】【F:app/workspaces/router.py†L1-L49】【F:app/documents/router.py†L1-L40】
   - Workspace-scoped routers (`configurations`, `jobs`, `results`) use `workspace_scoped_router` and therefore produce `/api/workspaces/{workspace_id}/…` once mounted with `prefix="/api"`.【F:app/configurations/router.py†L1-L32】【F:app/jobs/router.py†L1-L32】【F:app/results/router.py†L1-L25】
   - Supporting packages without routers (`events`, `system`) remain import-only until dedicated endpoints are required; they are not included in FastAPI routing but stay available to services.
3. Middleware registration handled by `app/core/middleware.py`; include logging, CORS, request ID, and session middlewares previously provided by `app/extensions/middleware.py`.【F:app/core/middleware.py†L1-L96】
4. Provide `GET "/"` returning `FileResponse(Path(__file__).parent / "static" / "index.html")`.
5. Mount `StaticFiles(directory=Path(__file__).parent / "static", html=True)` at `"/static"`.
6. Ensure lifespan or startup hooks now reference `app/core/db` and other relocated utilities.

---

## 4. Static frontend serving plan
1. **Build**: `npm --prefix frontend ci` followed by `npm --prefix frontend run build` creates `frontend/dist`.
2. **Copy**: new `scripts/build_frontend.py` (pure stdlib) performs:
   - validation that `frontend/dist/index.html` exists
   - deletion/recreation of `app/static/`
   - recursive copy of all `frontend/dist/**` files into `app/static/`
3. **Serve**: `app/main.py` handles `/` and `/static/*` as described above.
4. **Package data**: update `pyproject.toml` `[tool.setuptools.package-data]` (or equivalent) so wheels include static and alembic assets.
5. **Developer workflow**: Document that SPA hot reload still uses `npm run dev` with Vite proxying to `http://127.0.0.1:8000/api` while the packaged flow relies on copied assets.

---

## 5. CLI & entrypoint plan
1. Keep the existing multi-command CLI surface while clarifying that `ade start` is the default path for serving the API.
   - `[project.scripts] ade = "app.cli.__main__:main"` still lands in the argparse dispatcher that exposes all subcommands.
   - Ensure `ade --help` continues to list commands such as `start`, `users`, `reset`, `settings`, and `api-keys` so downstream tooling remains stable.
2. `app/cli/commands/start.py` delegates into `app.main.start(host, port, reload)` and is responsible for orchestrating optional SPA builds (via `scripts.build_frontend`) before booting uvicorn when `--reload` is false.
3. Non-start commands (`users`, `api-keys`, `reset`, `settings`, etc.) keep their current behaviour with import-path updates only; verify they still compose correctly with the relocated core utilities.
4. `app/main.start()` wraps `uvicorn.run("app.main:app", host=host, port=port, reload=reload)` and retains settings-driven overrides so other commands that rely on settings stay consistent.
5. Update docs to emphasise `ade start` for serving the combined app while documenting that the other maintained subcommands continue to exist for operations and migration flows.

---

## 6. Build/CI & developer flow plan
Use a single scripted pass so that local dev and CI share the exact steps.
1. **Bootstrap**
   - `pip install -e .[dev]`
   - `npm --prefix frontend ci`
2. **Build & copy**
   - `npm --prefix frontend run build`
   - `python -m scripts.build_frontend`
3. **Run app**
   - `ade start --reload` for local work (skips rebuild by default)
   - `ade start` for production (build script runs)
4. **Database migrations**
   - `alembic upgrade head` with updated config referencing `app/alembic`
5. **CI updates**
   - Python job: install deps, run build script, execute `ruff`, `mypy`, `pytest`
   - Frontend job: `npm ci`, `npm run lint`, `npm run test`, `npm run build`
   - Packaging job: `python -m build` then verify wheel contains static/alembic assets
6. **Cross-platform guarantees**
   - Use `pathlib`, `shutil`, `subprocess` with explicit envs (no `rm`/`cp` shell commands)
   - Ensure CLI uses module invocation (`python -m app.cli`) for Windows compatibility

---

## 7. Testing & verification plan
1. Update imports throughout `tests/**` to reference `app.*`.
2. Adjust `pyproject.toml` `tool.pytest.ini_options` to set `testpaths = ["tests"]` and coverage targets to `app`.
3. Validate fixtures that previously targeted the legacy settings module now use `app.settings`.
4. Smoke tests post-migration:
   - `GET /` returns 200 with SPA markup
   - `GET /static/<asset>` serves built JS/CSS
   - `/api/auth/*`, `/api/users/*`, `/api/workspaces/*`, `/api/configurations/*`, `/api/documents/*` respond as before
   - `/api/jobs/*`, `/api/results/*`, and `/api/health` reachable with expected payloads
   - Import-only support packages (`app.events`, `app.system`) remain importable after relocation
   - `ade start --reload` runs without extra processes
   - Representative CLI flows (`ade users list --json`, `ade settings`, `ade api-keys issue`) continue to succeed
   - `alembic upgrade head` executes successfully
5. Add optional integration test using `httpx.AsyncClient` to confirm static serving if time permits.

---

## 8. Risks, rollback, and timeline
1. **Risks**
   - Large one-pass move could hide missed import updates
   - Forgetting to include static/alembic assets in packaging
   - Alembic env import paths breaking
   - Import-only support packages (`events`, `system`) introducing unused dependencies or failing tests after relocation
   - CLI command wiring drifting during import path updates and breaking automation scripts
   - Build script misfiring on Windows paths
2. **Mitigations**
   - Automate refactor with scripted `git mv` + `sed` replacements; run `pytest -q` after script before commit
   - Add CI job to inspect `wheel` contents for static/alembic assets
   - Verify Alembic by running `alembic upgrade head --sql` during migration branch testing
   - Document the support-only packages (`app/events`, `app/system`) and run targeted import checks to ensure they stay lint-clean
   - Add CLI smoke tests (or scripted `ade --help`, `ade users list --json`) in CI to catch regressions
   - Use stdlib path utilities in build script and test on Windows via CI matrix if available
3. **Rollback strategy**
   - Perform migration on dedicated branch with a single squashed commit; revert commit to restore prior tree if issues arise
4. **Proposed execution timeline (single-pass focus)**
   - **Prep (0.5 day)**: draft migration script, dry-run on branch, update docs/tests stubs
   - **Migration day (1 day)**: run script to move packages, adjust imports, update configs/tests, run build script
   - **Verification (0.5 day)**: run full lint/type/test suite, build wheel, smoke-test CLI + SPA serving
   - **Stabilisation (0.5 day)**: polish docs, ensure dormant modules documented, prepare release notes




