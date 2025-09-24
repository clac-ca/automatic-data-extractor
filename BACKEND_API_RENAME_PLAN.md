# Backend API Rename Plan

## Why rename `backend/app` to `backend/api`?
- Clarify intent: the package exposes the FastAPI surface only; `api` makes that role explicit while `processor` and other runtimes live alongside it.
- Avoid ambiguity: new contributors misread `app` as the whole backend; `api` distinguishes the HTTP layer from background runtimes such as `backend/processor`.
- Align with roadmap: future CLI/worker components can live under `backend/` without overloading "app".
- Minimal churn point: perform the rename now before the jobs rewrite adds more modules.

## Scope Overview
Rename the `backend/app` package to `backend/api` and update every direct or indirect reference to the old path across code, tooling, and documentation. No behavioural changes expected.

## Implementation Steps
1. **Inventory & Preparation**
   - Capture current tree under `backend/app/` and note modules (core, modules, extensions, etc.).
   - Confirm no external tooling depends on the literal `backend.app` string (container manifests, deployment scripts, etc.).
2. **Apply Rename**
   - Move directory: `backend/app` → `backend/api` while preserving file permissions and `__init__.py` markers.
   - Update package exports if the top-level `backend/__init__.py` re-exports `app` symbols.
3. **Search & Replace Imports**
   - Replace `backend.app.` with `backend.api.` across the repository (Python, tests, scripts, docs).
   - Update string references (e.g., `uvicorn backend.app.main:app`, CLI scripts, env variables).
   - Pay special attention to dynamic import strings or JSON/YAML config.
4. **Refactor Tooling & Config**
   - Update `pyproject.toml`, Ruff config, coverage, Alembic env, and any task runners referencing `backend.app`.
   - Adjust test fixtures or utilities that import the old path.
5. **Documentation & Plans**
   - Revise `BACKEND_REWRITE_PLAN.md`, `CURRENT_TASK.md`, onboarding docs, CI scripts, and READMEs to reflect the new path.
   - Mention the rename in `PREVIOUS_TASK.md` once executed to keep the rotation log accurate.
6. **Validation**
   - Run `python -m compileall backend/api` to catch import mistakes quickly.
   - Execute `ruff`, `pytest`, and `mypy` (if configured) to ensure no broken imports remain.
   - Launch the dev server (`uvicorn backend.api.main:app`) to confirm startup.
7. **Follow-up & Communication**
   - Note in the PR summary that the rename is purely structural.
   - Encourage downstream teams to update any private scripts that import `backend.app`.

## Risk Mitigation
- Perform the rename in a dedicated PR to isolate a potentially large diff.
- Use automated search-and-replace to avoid partial updates; review carefully for multiline strings or comments referencing `backend.app` intentionally.
- Run full CI to surface missed references.

## Out of Scope
- No behavioural or configuration changes beyond package rename.
- No concurrent dependency upgrades or refactors.
