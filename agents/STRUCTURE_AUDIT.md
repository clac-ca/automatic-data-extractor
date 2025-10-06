# Backend Structure Audit

## Current Layout Snapshot
- `app/main.py` now bootstraps the FastAPI instance via the slim `app/api/v1/router` aggregator, wiring the in-process task queue while serving SPA assets from `app/web`. 【F:app/main.py†L15-L170】【F:app/api/v1/router.py†L1-L23】【F:app/services/task_queue.py†L1-L107】
- All active feature slices (auth, users, workspaces, configurations, documents, jobs, health, and system settings) now live under `app/features/<name>/`, keeping routers, schemas, models, repositories, and services co-located with relative imports for cross-feature collaboration. 【F:app/features/auth/router.py†L1-L195】【F:app/features/workspaces/service.py†L1-L287】
- Database bootstrapping now lives exclusively under `app/db/`, while shared async helpers such as the task queue reside in `app/services/` and runtime directory provisioning sits in `app/lifecycles.py`, mirroring the target package split. 【F:app/db/__init__.py†L1-L34】【F:app/lifecycles.py†L1-L54】【F:app/services/task_queue.py†L1-L107】
- Events/results surfaces have been removed—the API router only wires active feature slices and the initial schema seeds no results tables—clearing the way for the feature-first relocation. 【F:app/api/v1/router.py†L5-L22】【F:app/alembic/versions/0001_initial_schema.py†L15-L227】
- Tests now mirror the feature layout (`tests/features/<name>/`) so service and API coverage travels with each slice while continuing to run under the shared `tests/` root. 【F:tests/features/auth/test_auth.py†L1-L212】【F:tests/features/jobs/test_service.py†L1-L210】
- The API shell exposes shared dependency aliases through `app/api/deps.py`, keeping router composition slim while preserving feature-owned implementations. 【F:app/api/deps.py†L1-L36】
- A lightweight worker entry point now lives in `app/workers/run_jobs.py`, providing a structured home for task queue consumers as the job pipeline evolves. 【F:app/workers/run_jobs.py†L1-L87】

## Target Layout Highlights
- The playbook calls for a feature-first package structure with routers, schemas, models, repositories, services, workers, and tests grouped under `app/features/<name>/`, mediated by a slim API shell that exposes versioned routers and shared dependencies. 【F:AGENTS.md†L21-L92】
- Infrastructure should split between `app/core/` (cross-cutting helpers), `app/db/` (SQLAlchemy base/session/migrations), `app/services/` (shared adapters), and `app/web/` for built SPA assets so deployment artifacts remain self-contained. 【F:AGENTS.md†L31-L104】
- The active work package reinforces that phased, low-risk PRs must keep behaviour stable while laying the new structure, using compatibility shims only temporarily. 【F:agents/WP_BACKEND_FEATURE_SLICE_RESTRUCTURE.md†L1-L124】

## Gap Analysis
- **API Shell:** Shared dependencies now live directly inside the feature slices, so the API shell only exposes the versioned router and exception helpers without compatibility layers. 【F:app/api/__init__.py†L1-L5】【F:app/api/errors.py†L1-L5】【F:app/features/auth/dependencies.py†L1-L120】
- **Feature Packaging:** ✅ Completed — Routers, schemas, repositories, services, and helpers for each domain now live under `app/features/<name>/`, eliminating the cross-package imports that complicated refactors. 【F:app/features/auth/service.py†L1-L408】【F:app/features/documents/service.py†L1-L213】
- **Infrastructure Separation:** ✅ Completed — Database helpers now live under `app/db/`, runtime directory setup sits in `app/lifecycles.py`, and shared async utilities moved to `app/services/`; the legacy compatibility shims have been removed. 【F:app/db/__init__.py†L1-L34】【F:app/lifecycles.py†L1-L54】【F:app/services/task_queue.py†L1-L107】
- **Static Assets:** ✅ Completed — SPA bundles now live in `app/web/`, CLI messaging references the new directory, and `app/static/` contains only a README pointer for remaining callers. 【F:app/main.py†L88-L170】【F:app/static/README.md†L1-L5】【F:pyproject.toml†L45-L58】
- **Tests & Tooling:** ✅ Completed — `pyproject.toml` now enumerates each test suite directory to mirror the feature-first layout, keeping discovery explicit as additional slices are added. 【F:pyproject.toml†L61-L69】

## Optimised Migration Plan

### Phase 0 – Preflight & Shims
- [x] Introduce empty packages (`app/api`, `app/api/v1`, `app/db`, `app/features`, `app/services`, `app/web`, `app/workers`) with `__init__.py` markers so imports resolve before we move code. 【F:app/api/__init__.py†L1-L5】【F:app/features/__init__.py†L1-L5】【F:app/services/__init__.py†L1-L9】
- [x] Extract the lifespan helper and runtime directory creation into a new `app/lifecycles.py`, which now owns the startup/shutdown hooks consumed by the factory. 【F:app/lifecycles.py†L1-L54】【F:app/main.py†L30-L63】
- [x] Update packaging metadata (`pyproject.toml`) and CLI status messages to recognise `app/web/` assets while leaving a compatibility note in `app/static/` until the swap is complete. 【F:pyproject.toml†L45-L59】【F:app/cli/commands/start.py†L34-L60】【F:app/static/README.md†L1-L5】

### Phase 1 – API Shell & Static Serving
- [x] Build `app/api/errors.py` and `app/api/v1/router.py` that aggregate feature routers while the factory mounts the versioned router and static assets via the new helper. 【F:app/api/errors.py†L1-L5】【F:app/api/v1/router.py†L1-L23】【F:app/main.py†L15-L118】
- [x] Switch the CLI `start` command to use `uvicorn.run(..., factory=True)` with `app.main:create_app`, which keeps `ade start` aligned with the factory-first design from the playbook. 【F:app/main.py†L75-L117】【F:AGENTS.md†L31-L44】
- [x] Move built SPA files from `app/static/` into `app/web/` (with a README pointer), adjusting `sync_frontend_assets` to copy to the new directory so the deployment artifact matches the target structure. 【F:app/main.py†L52-L119】【F:app/static/README.md†L1-L5】【F:app/web/index.html†L1-L14】

### Phase 2 – Infrastructure Extraction
- [x] Relocate database base/session/bootstrap helpers into `app/db/` (including the SQLAlchemy declarative base previously exported from `app/models`) and drop the interim compatibility shims. 【F:app/db/base.py†L1-L25】【F:app/db/session.py†L1-L78】【F:app/db/mixins.py†L1-L56】
- [x] Move cross-cutting services like the task queue into `app/services/`, updating all call sites to the new namespace. 【F:app/services/task_queue.py†L1-L107】
- [x] Consolidate startup utilities inside `app/lifecycles.py`, letting the factory depend on that module directly. 【F:app/lifecycles.py†L1-L49】【F:app/main.py†L28-L63】

### Phase 3 – Feature Slice Relocation Loop
- [x] Relocate health, jobs, configurations, documents, users, workspaces, auth, and system settings into `app/features/<name>/`, updating `app/api/v1/router.py` and all call sites in the same change. 【F:app/features/auth/router.py†L1-L195】【F:app/api/v1/router.py†L1-L23】
- [x] Mirror the move in tests by relocating corresponding suites under `tests/features/<name>/` so every slice ships with passing coverage. 【F:tests/features/auth/test_auth.py†L1-L212】【F:tests/features/workspaces/test_workspaces.py†L1-L276】
- [x] Inline the API dependency shim once the new imports settle so shared dependencies live inside their owning feature modules. 【F:app/features/auth/dependencies.py†L1-L120】

### Phase 4 – Tooling, Docs, and Cleanup
- [x] Update `pyproject.toml` test paths to mirror the new suite layout so discovery reflects the feature-first structure. 【F:pyproject.toml†L61-L69】
- [x] Refresh `README.md`, `agents/CURRENT_TASK.md`, and related playbooks with the completed milestones, then archive the work package snapshot into `agents/PREVIOUS_TASK.md` once the restructure lands. 【F:README.md†L122-L137】【F:agents/WP_BACKEND_FEATURE_SLICE_RESTRUCTURE.md†L1-L180】
- [x] Run the full quality gate (`pytest`, `ruff check`, `mypy app`) plus `ade start --no-reload` smoke tests as features move to verify parity with the legacy layout. 【c9ddf9†L1-L33】【9f88ad†L1-L2】【4e71ae†L1-L2】【4df542†L1-L11】

## Supporting Checklists
- Maintain a migration log in `agents/CURRENT_TASK.md` noting which features have moved and which shared dependencies still require attention so reviewers can trace state easily. 【F:agents/WP_BACKEND_FEATURE_SLICE_RESTRUCTURE.md†L1-L180】
- Track follow-up questions (Alembic location, long-term re-export policy) in the work package to avoid losing context between PRs. 【F:agents/WP_BACKEND_FEATURE_SLICE_RESTRUCTURE.md†L153-L180】

This refined roadmap keeps the repo deployable at each step while converging on the feature-first layout mandated in the playbook.
