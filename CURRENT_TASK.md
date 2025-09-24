# 🚧 ADE Backend Rewrite – Next Focus

## Status Snapshot
- Jobs service/router restored with synchronous processor integration and green end-to-end tests.
- Processor runner packaged as standalone stub; jobs now emit metrics/logs for results module.
- Documentation updated with jobs architecture and backlog notes for retention/timeline work.

## Goal for This Iteration
Rename the FastAPI package from `backend/app` to `backend/api` following `BACKEND_API_RENAME_PLAN.md` so future work (CLI, Dynaconf) builds on the clarified structure without extra churn.

## Scope
1. **Inventory & preparation**
   - Confirm no external tooling hard-codes `backend.app` (deployment scripts, Procfiles, Docker configs).
   - Capture the existing tree so we can double-check nothing is dropped during the move.
2. **Apply rename**
   - Use `git mv backend/app backend/api` to preserve history.
   - Adjust any top-level exports or namespace packages that referenced `backend.app`.
3. **Reference sweep**
   - Replace `backend.app` imports/strings with `backend.api` across code, tests, scripts, and docs.
   - Update tooling files (`pyproject.toml`, coverage config, pytest/mypy settings, make/nox tasks, deployment manifests) that point at the old path.
4. **Docs & task rotation**
   - Refresh plans (`BACKEND_REWRITE_PLAN.md`, `BACKEND_API_RENAME_PLAN.md`, `CURRENT_TASK.md` → `PREVIOUS_TASK.md`) and README snippets to reflect the new package name.
   - Note any downstream follow-ups (e.g., developer wiki, CI secrets) that external teams must adjust.

## Definition of Done
- Repository tree contains `backend/api` with all previous modules intact; `backend/app` no longer exists.
- `rg "backend\\.app"` returns no matches outside historical notes.
- `uvicorn backend.api.main:app` starts successfully; `ruff`, `pytest`, and `mypy` (if configured) pass without import errors.
- Documentation and task tracking reference `backend/api`, and follow-up items for external consumers are recorded.

