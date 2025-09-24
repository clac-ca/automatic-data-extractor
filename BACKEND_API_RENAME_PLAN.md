# Backend API Rename Plan

## Status
- ✅ Completed: the FastAPI package now lives under `backend/api`.
- ✅ All repository references were updated to import `backend.api`.
- ✅ Alembic, test fixtures, and documentation reflect the new path.

Use this document as the reference playbook if we need to repeat the rename pattern in downstream services.

## Rationale
- Clarify intent: the package exposes the HTTP surface only; `api` highlights that responsibility while other runtimes (processors, CLI) sit beside it.
- Avoid ambiguity: contributors previously misread `app` as "the entire backend". The new name scopes imports to the FastAPI layer.
- Align with roadmap: upcoming CLI and Dynaconf work can now target `backend/api` without another round of churn.

## Completed Steps
1. **Inventory & preparation**
   - Captured the previous `backend/app/` tree to ensure parity after the move.
   - Searched for external tooling that might hard-code `backend.app` imports or module strings.
2. **Apply rename**
   - Renamed the directory with `git mv backend/app backend/api` to preserve history.
   - Verified package exports so `backend.api.main:create_app` stays the application entry point.
3. **Reference sweep**
   - Replaced `backend.app` with `backend.api` across Python code, tests, Alembic configuration, and Markdown docs.
   - Updated shell snippets (`uvicorn backend.api.main:app`, `python -m backend.api …`) used in onboarding and ops guides.
4. **Validation**
   - Ran `ruff`, `pytest`, and `mypy` to confirm imports resolve end-to-end.
   - Started `uvicorn backend.api.main:app` locally to ensure the service boots with the new module path.

## Downstream Follow-ups
- Notify teams running private scripts to swap to `backend.api` imports.
- Update any deployment manifests outside this repo (e.g., Terraform, GitHub Actions secrets) that referenced the old path.
- Confirm the developer wiki and runbooks reference the renamed package.

## Future Reference
If we add new runtime packages (CLI, background workers), follow the same approach: move directories with `git mv`, sweep imports with automated tooling, and validate via `ruff` + `pytest` before shipping.
