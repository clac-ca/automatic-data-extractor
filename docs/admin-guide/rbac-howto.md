# RBAC How-to Recipes

Use these runbooks when you need to grant administrative access or delegate
workspace responsibilities. Every step relies on the unified RBAC endpoints in
`/api/v1` so the OpenAPI documentation and admin UI stay in sync.

## Make a site administrator

1. List the global role catalog and locate the `global-admin` role to confirm
   its identifier. The API returns the role UUID alongside the slug and
   permission set (`GET /api/v1/rbac/roles?scope=global`).
2. Assign the global administrator role with the user-centric endpoint:
   `PUT /api/v1/users/{user_id}/roles/{role_id}`. The call is idempotent, so
   repeating it leaves the binding unchanged.
3. Verify the grant through `GET /api/v1/me/permissions` while authenticated as
   the user. The response lists the effective global permissions so you can
   confirm `roles.read_all` and the other administrator keys are present.

## Grant an editor role in a workspace

1. Review the permission registry (`GET /api/v1/rbac/permissions`) to decide
   which workspace capabilities the editor should own. Choose combinations such
   as `workspace.documents.manage` and `workspace.runs.manage`.
2. Create a workspace-scoped role by posting to `POST /api/v1/rbac/roles`
   with `scope=workspace`, a unique slug (for example `workspace-editor`), and
   the selected permission keys.
3. Assign the editor role to a user by calling
   `POST /api/v1/workspaces/{workspace_id}/members` with the target `user_id`
   and `role_ids`. The endpoint verifies workspace membership permissions,
   ensures the workspace exists, and returns the assignment record in a stable
   shape for auditing.
4. Confirm the assignment via the workspace member listing or by querying
   the user's effective workspace permissions (`GET /api/v1/me/permissions?workspace_id=...`). The
   workspace-specific response includes the union of all assigned roles so you can
   validate the editor capabilities.

Keep these recipes alongside the API docs so administrators can self-serve
without scanning the implementation. Update the steps whenever role endpoints or
permission slugs evolve.
