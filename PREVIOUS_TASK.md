## Context
Renamed the FastAPI package from `backend/app` to `backend/api` to make the HTTP
surface explicit before layering on CLI and Dynaconf work.

## Outcome
- Moved the package with `git mv` and confirmed every module (core, db, modules,
  services, migrations) survived the transition.
- Updated imports, Alembic configuration, and test fixtures to reference
  `backend.api`; refreshed README and planning docs to point at the new path.
- Verified startup (`uvicorn backend.api.main:app`), `ruff`, `pytest`, and a
  targeted `mypy` run to ensure no import regressions.

## Next steps
- Announce the rename to consumers maintaining private scripts or deployment
  manifests so they swap to `backend.api` imports.
- Follow the rewrite roadmap: enforce job/results retention policies and seed
  default workspace permissions.
- Proceed with the CLI and Dynaconf milestones now that the package layout is
  settled.
