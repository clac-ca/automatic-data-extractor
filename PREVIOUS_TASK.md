## Context
`CURRENT_TASK.md` directed us to let FastAPI inject `WorkspaceMemberCreate`
directly into the `/workspaces/{workspace_id}/members` handler, add a 422
regression test, and document the resolved manual-parsing gap.

## Outcome
- Replaced the `_get_workspace_member_payload` dependency with a `Body`
  parameter so `WorkspaceRoutes.add_member` now receives
  `WorkspaceMemberCreate` directly from FastAPI.
- Added `test_workspace_member_payload_requires_user_id` to prove that posting
  an empty JSON body returns the native FastAPI 422 error highlighting the
  missing `user_id` field.
- Updated `BEST_PRACTICE_VIOLATIONS.md` to record that the workspace member
  endpoint now relies on FastAPI's validation pipeline.

## Next steps
- Harden documentation exposure by defaulting `Settings.enable_docs` to `False`
  and only enabling docs for explicitly allowed environments.
- Update the settings test suite and best-practice log to reflect the new
  behaviour so the security change is exercised automatically.
