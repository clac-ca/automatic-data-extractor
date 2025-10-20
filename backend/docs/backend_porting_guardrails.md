# Backend Porting Guardrails

## Context Snapshot
- `.old-codebase/ade/app.py` wires FastAPI with global `TaskQueue`, middleware, and serves bundled SPA assets.
- Feature domains live under `ade/features/*` following a router → service → repository pattern with Pydantic schemas and tests.
- Cross-cutting infrastructure sits in `ade/platform/*` (config, logging, security, middleware) and `ade/db/*` (SQLAlchemy engine/session, Alembic migrations).
- Background jobs mount through `ade/workers/*` and queue adapters under `ade/adapters/queue`.
- Storage abstractions (`adapters/storage`) and API surface (`ade/v1/router.py`) are tightly coupled to runtime settings and global state.

This organisation delivers useful separation of concerns, but it also brings implicit dependencies and legacy conventions that should be reconsidered when migrating into `backend/app`.

## Guiding Principles
- **Keep the surface area lean**: only migrate behaviour that is required for the new product scope; treat every module as opt-in.
- **Prefer explicit dependency wiring**: rely on FastAPI dependency injection or constructor injection instead of global singletons (`app.state.*`, module-level caches).
- **Leverage existing shared packages**: consolidate new helpers under `backend/app/shared/*` before adding new cross-cutting modules.
- **Ensure async compatibility**: favour async database and background patterns; avoid blocking calls in request paths without `run_in_executor`.
- **Tests drive acceptance**: mirror or write tests in `backend/tests/` before or alongside feature ports to lock behaviour.

## Anti-Patterns to Avoid
- Re-importing the legacy `Settings` complexity from `ade/platform/config.py`; align with the simplified `backend/app/shared/core/config.py`.
- Recreating repository/service layers that only wrap single ORM calls—keep persistence thin or colocate with feature routers when complexity is low.
- Coupling features to global task queues; background work should flow through well-defined interfaces registered during application start-up.
- Duplicating bespoke middleware and logging stacks unless the behaviour is demonstrably required.
- Porting synchronous filesystem/database adapters without first validating concurrency needs (e.g. the SQLite polling queue).

## Migration Checklist
For every candidate module, confirm:
1. Clear business capability aligns with planned backend surface.
2. Dependencies are understood and either already exist in `backend/app` or have a migration plan.
3. Configuration needs are covered by the new Settings model (extend intentionally if gaps exist).
4. Tests from `.old-codebase/ade/tests/...` are mapped to new pytest modules—or new tests are written—to preserve critical behaviour.
5. Background tasks, storage, or external integrations have documented contracts and failure handling.

## Initial Targets & Notes
- **Keep/Adapt**: authentication scaffolding (`features/auth`), workspace management (`features/workspaces`), job task definitions (`features/jobs/tasks`), shared pagination utilities.
- **Re-evaluate/Refactor**: database session management (`db/session.py`), legacy queue adapters, filesystem storage abstractions, platform middleware stack, legacy CLI wrappers.
- **Exclude for now**: anything under `ade/web` (frontend build system), dev-only convenience scripts, Docker-specific bootstrapping.

## Working Practices
- Record migration decisions beside the relevant modules (docstring or README) and update this guardrail file as ground truth evolves.
- Run `npm run test` after each meaningful port; plan to wire new behaviour into `npm run ci` thresholds.
- When in doubt, spike code in isolation rather than copying and pruning; the goal is to design-forwards, not clone backwards.
