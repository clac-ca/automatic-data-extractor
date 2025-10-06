# Work Package: Feature-Sliced Backend Restructure

## Snapshot

- **Goal:** Land the feature-first FastAPI package described in `AGENTS.md`,
  eliminating the legacy `backend/app` scaffolding while keeping behaviour
  stable.
- **Owner:** Backend platform team (AI agents execute individual milestones).
- **Time horizon:** Ship incrementally across several PRs; each phase should be
  mergeable and production-safe.

---

## Context & Motivation

The current backend mixes routers, services, configuration, and CLI utilities
inside shared modules, making feature ownership ambiguous and code moves risky.
We aligned on a modern structure where each vertical slice (auth, workspaces,
documents, etc.) owns its API contract and supporting logic. The new layout also
bundles the SPA for a single deployable container and provides a consistent home
for cross-cutting concerns. This work package turns that blueprint into reality.

---

## Objectives & Success Measures

1. Stand up the `app/` package skeleton and migrate all runtime entrypoints
   (FastAPI app factory, CLI, workers) without regressions.
2. Relocate shared infrastructure (config, DB glue, auth backends) into
   dedicated `core/` and `db/` modules.
3. Move every feature’s router, schemas, models, repositories, services,
   workers, and tests into `app/features/<name>/`, leaving only compatibility
   shims where unavoidable.
4. Serve the compiled SPA from `app/web/` via FastAPI static mounting while
   preserving local dev workflows.

Completion is defined by meeting the acceptance criteria below with green test
suites and updated docs.

---

## Out of Scope

- Rewriting business logic beyond path/import updates needed for the move.
- Renaming external APIs, configuration variables, or environment files.
- Adding new third-party dependencies unless they are required to preserve
  behaviour.

---

## Phased Plan

Each phase should be delivered as one or more self-contained PRs that keep the
main branch deployable.

### Phase 0 – Preparation
- Audit `pyproject.toml`, packaging metadata, and `ade` entry points to confirm
  assumptions.
- Capture baseline test results (`pytest`, `mypy app`, CLI smoke test) for
  regression comparison.

### Phase 1 – Scaffolding & Build Hooks
- Create the `app/` directory layout matching `AGENTS.md` (empty modules and
  `__init__.py` shims as needed).
- Point packaging metadata and CLI entry points at the new package paths.
- Document migration notes in `README.md` and `agents/CURRENT_TASK.md`.

### Phase 2 – Core & Infrastructure Migration
- Move configuration, logging, auth backends, security helpers, lifecycle hooks,
  and DB session/base utilities into `app/core/` and `app/db/`.
- Update imports across the repository and fix tests that reference old paths.
- Verify startup and shutdown hooks run as expected.

### Phase 3 – Feature Vertical Moves
- For each feature (`auth`, `users`, `workspaces`, `documents`,
  `configurations`, `jobs`, `system_settings`):
  - Relocate router, schemas, models, repositories, services, workers, and tests.
  - Provide re-export shims only when consumers cannot be updated in the same PR.
  - Ensure feature-level tests still import relative modules inside the slice.
- Keep PRs focused (e.g., one or two features per PR) to simplify review.

### Phase 4 – API Shell Assembly
- Build `app/api/v1/router.py` to aggregate feature routers.
- Keep shared dependencies inside their owning feature modules so the API shell
  only re-exports versioned routers and exception helpers from
  `app/api/errors.py`.
- Update `app/main.py` to include the versioned router and dependencies.

### Phase 5 – CLI & Worker Relocation
- Move CLI commands into `app/cli/` (e.g., `main.py`, `dev.py`, `admin.py`).
- Re-home worker processes under `app/workers/` and update invocation scripts.
- Confirm `ade start`, database tasks, and worker entry points still run.

### Phase 6 – SPA Bundling & Docs
- Configure FastAPI static mounting to serve built assets from `app/web/`.
- Document the build pipeline (`frontend` → `app/web`) in `README.md` and
  `agents/FRONTEND_DESIGN.md`.
- Ensure deployment scripts copy the SPA artefacts into the container image.

### Phase 7 – Validation & Stabilisation
- Run `pytest`, `ruff check`, and `mypy app`.
- Smoke-test CLI commands (`ade start`, `ade db upgrade`, etc.).
- Update onboarding docs, diagrams, and any scripts referencing old paths.
- Capture lessons learned and follow-ups in `agents/PREVIOUS_TASK.md`.

---

## Acceptance Criteria

- `uvicorn app.main:create_app` (or equivalent factory) boots cleanly and serves
  the SPA assets from `/static` with client-side routing intact.
- Imports resolve without relying on deprecated aliases or legacy package names.
- `pytest`, `ruff check`, and `mypy app` pass on the refactored tree.
- `ade start` launches the API container, and critical CLI helpers (`ade db`,
  `ade dev`) function with the new module paths.
- `README.md`, deployment docs, and agent playbooks describe the new structure.

---

## Risks & Mitigations

- **Hidden runtime imports:** Run the full test suite plus targeted smoke tests
  after each major move to catch missing imports early.
- **Long-lived branches:** Keep PRs small and feature-focused to avoid painful
  rebases. Merge to main frequently.
- **Alembic path expectations:** Decide whether to house migrations inside
  `app/db/migrations` or keep them top-level. Document whichever path we choose
  and update tooling accordingly.

---

## Follow-ups & Open Questions

- Determine whether thin compatibility re-exports inside
  `app/features/*/__init__.py` should remain long term or be removed once
  downstream consumers catch up.
- Evaluate the best long-term location for the Alembic environment (top-level vs
  nested) and communicate any tooling adjustments.
- Revisit test layout once the restructure settles—decide if feature-level tests
  should stay co-located or partially move under `tests/` for integration
  coverage.
