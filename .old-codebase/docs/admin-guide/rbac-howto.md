# RBAC How-to Recipes

Use these runbooks when you need to grant administrative access or delegate
workspace responsibilities. Every step relies on the unified RBAC endpoints in
`/api/v1` so the OpenAPI documentation and admin UI stay in sync.

## Make a site administrator

1. List the global role catalog and locate the `global-administrator` role to
   confirm its identifier. The API returns the numeric `role_id` alongside the
   slug and permission set.【F:ade/features/roles/router.py†L76-L173】
2. Convert the target user into a principal. Supplying `user_id` in the role
   assignment payload automatically resolves the principal and creates one if it
   does not already exist.【F:ade/features/roles/router.py†L538-L613】
3. Assign the global administrator role by posting to
   `POST /api/v1/role-assignments` with the `role_id` from step 1. The handler is
   idempotent, so repeated calls simply return the existing binding.【F:ade/features/roles/router.py†L538-L613】
4. Verify the grant through `GET /api/v1/me/permissions` while authenticated as
   the user. The response lists the effective global permissions so you can
   confirm `Roles.ReadWrite.All` and the other administrator keys are present.【F:ade/features/roles/router.py†L200-L291】

> **CLI shortcut:** `ade users create` (or `ade users grant-role` when it lands)
> maps the friendly `--role admin` switch to `global-administrator` and syncs the
> permission registry before the assignment runs.【F:ade/cli/commands/users.py†L1-L122】

## Grant an editor role in a workspace

1. Review the permission registry to decide which workspace capabilities the
   editor should own. The registry enumerates every key, label, and description so
   you can choose combinations such as `Workspace.Documents.ReadWrite` and
   `Workspace.Jobs.ReadWrite`.【F:ade/features/roles/registry.py†L1-L132】
2. Create a workspace-scoped role by posting to
   `POST /api/v1/workspaces/{workspace_id}/roles` with a unique slug (for example
   `workspace-editor`) and the selected permission keys. The router enforces that
   only callers with `Workspace.Roles.ReadWrite` can create custom roles and
   persists the definition for future reuse.【F:ade/features/roles/router.py†L180-L398】
3. Assign the editor role to a user by calling
   `POST /api/v1/workspaces/{workspace_id}/role-assignments` with either the
   `principal_id` or `user_id`. The endpoint verifies workspace membership
   permissions, ensures the workspace exists, and returns the assignment record in
   a stable shape for auditing.【F:ade/features/roles/router.py†L651-L760】
4. Confirm the assignment via the workspace role-assignment list or by querying
   the user's effective workspace permissions (`GET /api/v1/me/permissions?workspace_id=...`). The
   workspace-specific response includes the union of all assigned roles so you can
   validate the editor capabilities.【F:ade/features/roles/router.py†L651-L760】【F:ade/features/roles/router.py†L200-L291】

Keep these recipes alongside the API docs so administrators can self-serve
without scanning the implementation. Update the steps whenever role endpoints or
permission slugs evolve.
