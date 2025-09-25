# Let FastAPI Parse JSON Payloads for Key Auth Routes – Implementation Plan

## Objective
Replace helper dependencies that manually inject request bodies with direct
Pydantic parameters so FastAPI emits native 422 responses for bad payloads on
API key issuance, job submission, and workspace membership routes.

## Approach Overview
Simplify each handler signature to accept the relevant schema (`APIKeyIssueRequest`,
`JobSubmissionRequest`, `WorkspaceMemberCreate`) without indirection. Remove the
bespoke `Body(...)` helper functions, adjust dependencies where necessary, and
extend tests to cover new validation behaviour.

## Scope
1. **Auth API key issuance**
   - Drop `_get_api_key_issue_request` from `backend/api/modules/auth/router.py`
     and accept `payload: APIKeyIssueRequest` directly in `create_api_key`.
   - Ensure the route continues to enforce admin access and that tests cover
     validation failures via FastAPI’s response model.
2. **Job submission**
   - Remove `_get_job_submission` from `backend/api/modules/jobs/router.py` and
     depend on `payload: JobSubmissionRequest` in `submit_job`.
   - Update tests to assert 422 responses for malformed JSON submissions.
3. **Workspace membership**
   - Drop `_get_workspace_member_payload` from `backend/api/modules/workspaces/router.py`
     and rely on a direct `WorkspaceMemberCreate` parameter.
   - Confirm workspace membership tests exercise validation and permission
     checks after the refactor.

## Deliverables
- Routes updated to take advantage of FastAPI’s native body parsing.
- Redundant helper dependencies removed.
- Tests demonstrating 422 responses for invalid payloads.
- Documentation refreshed if the best-practice tracker changes.

## Testing
- `pytest backend/tests/modules/auth/test_auth.py`
- `pytest backend/tests/modules/jobs/test_jobs.py`
- `pytest backend/tests/modules/workspaces/test_workspaces.py`
- `ruff check backend`
- `mypy backend`
