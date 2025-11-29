# 160-WORKSPACES-AND-RBAC.md  
**ADE Web – Workspaces, Workspace Selection & Permissions**

---

## 0. Purpose

This doc covers the **workspace** and **RBAC** (roles/permissions) related parts of the API:

- Workspaces (list/create/read/update/delete)
- Default workspace
- Workspace members & roles
- Permissions & effective permissions
- How frontend should **consume** this (not a full admin UI yet)

It complements:

- `090-WORKSPACE-FUTURE.md` (multi-workspace selector future plan, if present).
- `120-AUTH-AND-SESSIONS.md` (session, bootstrap, auth).
- `020-ARCHITECTURE.md` (how workspace context is wired).

---

## 1. Workspace Model (from OpenAPI)

### 1.1 `WorkspaceOut` & `WorkspacePage`

```ts
/**
 * WorkspaceOut
 * @description Workspace information decorated with membership metadata.
 */
WorkspaceOut: {
  id: string;        // ULID
  name: string;
  slug: string;
  roles: string[];   // Roles for current user in this workspace
  // (additional fields may exist: created_at, settings, etc – we only rely on what we need)
};

/**
 * WorkspacePage
 * @description Paginated list of workspaces for current user.
 */
WorkspacePage: {
  items: WorkspaceOut[];
  page: number;
  page_size: number;
  has_next: boolean;
  has_previous: boolean;
  total?: number | null;
};
````

**UI usage:**

* **Workspace switcher**:

  * List of `WorkspaceOut` from bootstrap or `/workspaces`.
  * Show `name`, maybe `slug`.
* **Workspace context**:

  * Persist “current workspace id” in app state & URL.
  * Use `roles` to toggle workspace-level admin actions (e.g. managing members/roles).

---

## 2. Workspace Endpoints

### 2.1 List workspaces

**Path:** `GET /api/v1/workspaces`
**Op:** `list_workspaces_api_v1_workspaces_get`

Parameters:

```ts
query?: {
  page?: number;
  page_size?: number;
  include_total?: boolean;
};
```

Response: `WorkspacePage`.

Usually, we’ll get workspaces via `bootstrap`, but this endpoint is useful for workspace management UI.

---

### 2.2 Create workspace

**Path:** `POST /api/v1/workspaces`
**Op:** `create_workspace_api_v1_workspaces_post`

Request body (from OpenAPI; effectively a `WorkspaceCreate` style payload):

* Likely includes `name`, optional `slug`, and/or settings.

Response: `WorkspaceOut`.

Frontend:

* “Create workspace” dialog:

  * Name (+ optional slug).
  * After success, switch context to the new workspace.

---

### 2.3 Read / update / delete workspace

**Read**

* Path: `GET /api/v1/workspaces/{workspace_id}`
* Op: `read_workspace_api_v1_workspaces__workspace_id__get`
* Response: `WorkspaceOut`.

**Update**

* Path: `PATCH /api/v1/workspaces/{workspace_id}`

* Op: `update_workspace_api_v1_workspaces__workspace_id__patch`

* Request: `WorkspaceUpdate`:

  ```ts
  WorkspaceUpdate: {
    name?: string | null;
    slug?: string | null;
    settings?: { [key: string]: unknown } | null;
  };
  ```

* Response: `WorkspaceOut`.

**Delete**

* Path: `DELETE /api/v1/workspaces/{workspace_id}`
* Op: `delete_workspace_api_v1_workspaces__workspace_id__delete`
* Response: `200` (likely with workspace metadata) or `204` depending on impl.

Current workpackage doesn’t require full workspace admin UI, but we keep these documented.

---

### 2.4 Set default workspace

**Path:** `POST /api/v1/workspaces/{workspace_id}/default`
**Op:** `set_default_workspace_api_v1_workspaces__workspace_id__default_post`

Response: likely a simple confirmation or updated workspace context.

Frontend usage:

* “Make default” action inside workspace selector.
* Bootstrapping can use backend’s default workspace if user reloads.

---

## 3. Workspace Members & Roles

These endpoints are **important but not first‑phase** for ade‑web UX. We mainly need them to:

* Understand whether current user is an admin in a workspace.
* Implement minimal membership UI later.

### 3.1 Members

Paths:

* `GET /api/v1/workspaces/{workspace_id}/members`

  * Op: `list_members_api_v1_workspaces__workspace_id__members_get`
  * Response: list of member records (OpenAPI schemas include user id, email, roles).

* `POST /api/v1/workspaces/{workspace_id}/members`

  * Op: `add_member_api_v1_workspaces__workspace_id__members_post`
  * Request: payload with user identifier + workspace roles.

* `DELETE /api/v1/workspaces/{workspace_id}/members/{membership_id}`

  * Op: `remove_member_api_v1_workspaces__workspace_id__members__membership_id__delete`

* `PUT /api/v1/workspaces/{workspace_id}/members/{membership_id}/roles`

  * Op: `update_member_api_v1_workspaces__workspace_id__members__membership_id__roles_put`
  * Request: new set of role ids.

**Near-term usage:**

* Not required for initial refactor.
* We only need to **represent** membership count / roles if backend includes them in `WorkspaceOut` or `bootstrap`.

---

### 3.2 Workspace roles & role assignments

Paths:

* `GET /api/v1/workspaces/{workspace_id}/roles`

  * Op: `list_workspace_roles_api_v1_workspaces__workspace_id__roles_get`
* `POST /api/v1/workspaces/{workspace_id}/roles`

  * Op: `create_workspace_role_api_v1_workspaces__workspace_id__roles_post`
* `PUT /api/v1/workspaces/{workspace_id}/roles/{role_id}`

  * Op: `update_workspace_role_api_v1_workspaces__workspace_id__roles__role_id__put`
* `DELETE /api/v1/workspaces/{workspace_id}/roles/{role_id}`

  * Op: `delete_workspace_role_api_v1_workspaces__workspace_id__roles__role_id__delete`

Role assignment:

* `GET /api/v1/workspaces/{workspace_id}/role-assignments`

  * Op: `list_workspace_role_assignments_api_v1_workspaces__workspace_id__role_assignments_get`
  * Query filters: `principal_id`, `user_id`, `role_id`, pagination.
* `POST /api/v1/workspaces/{workspace_id}/role-assignments`

  * Op: `create_workspace_role_assignment_api_v1_workspaces__workspace_id__role_assignments_post`
* `DELETE /api/v1/workspaces/{workspace_id}/role-assignments/{assignment_id}`

  * Op: `delete_workspace_role_assignment_api_v1_workspaces__workspace_id__role_assignments__assignment_id__delete`

**Current plan:**

* **Do not** build a full workspace-role admin UI in this workpackage.
* Use role & permission information only to:

  * Toggle visibility of admin actions (e.g. “Create workspace”, “Manage members”).
  * Provide helpful “You don’t have permission for this action” messaging.

---

## 4. Permissions & Effective Permissions

We already cover Authentication in `120-AUTH-AND-SESSIONS.md`. Here we document the key permission responses.

### 4.1 Effective permissions

```ts
/**
 * EffectivePermissionsResponse
 * @description Effective permissions for the authenticated principal.
 */
EffectivePermissionsResponse: {
  global_permissions?: string[];
  workspace_id?: string | null;
  workspace_permissions?: string[];
};
```

Endpoints:

* `GET /api/v1/me/permissions`

  * Op: `read_effective_permissions_api_v1_me_permissions_get`
  * Returns `EffectivePermissionsResponse`.

* `POST /api/v1/me/permissions/check`

  * Op: `check_permissions_api_v1_me_permissions_check_post`
  * Request: list of permission strings; response: indicates which are granted.

Frontend usage:

* On app bootstrap (via `/api/v1/bootstrap`) we should already receive effective permissions.

* Provide a simple hook:

  ```ts
  usePermission(permission: string): boolean;
  ```

  backed by `EffectivePermissionsResponse` (no need to call `/me/permissions/check` in normal flows).

* Use `workspace_permissions` to gate:

  * Upload document.
  * Run configs.
  * Edit configurations.
  * Manage workspace settings (in future).

---

### 4.2 Permissions catalog & roles (global)

Global-level endpoints (mostly for admin console):

* `GET /api/v1/permissions` – list permission catalog entries.
* `GET /api/v1/roles` / `POST /api/v1/roles` / `PATCH` / `DELETE` – global roles.
* `GET /api/v1/role-assignments` / `POST` / `DELETE` – global role assignments.

Current workpackage:

* We **do not** build a UI for these.
* We only need to know:

  * That permission strings are stable and match values in `EffectivePermissionsResponse`.
  * That we can point power users to CLI/other UI for full role management.

---

## 5. System Safe Mode (for completeness)

Endpoint:

* `GET /api/v1/system/safe-mode`

  * Op: `read_safe_mode_api_v1_system_safe_mode_get`
  * Response: `SafeModeStatus`:

    ```ts
    SafeModeStatus: {
      enabled: boolean;
      detail?: string | null; // user-visible explanation
    };
    ```

* `PUT /api/v1/system/safe-mode`

  * Op: `update_safe_mode_api_v1_system_safe_mode_put`
  * Admin-only.

Bootstrap envelope also includes `safe_mode: SafeModeStatus`.

Frontend usage:

* Always show a **Safe mode banner** when `enabled = true`:

  * Message from `detail` or a default message.
  * Optionally disable “Run” actions or show extra confirmation.

---

## 6. Frontend Wiring

* `AuthProvider` / `Bootstrap` should provide:

  ```ts
  {
    user: UserProfile | null;
    workspaces: WorkspaceOut[];
    defaultWorkspaceId: string | null;
    safeMode: SafeModeStatus;
    effectivePermissions: EffectivePermissionsResponse;
  }
  ```

* `WorkspaceProvider` (or equivalent) tracks current workspace:

  * Derived from URL param, local storage, or default workspace id.

* Hooks:

  ```ts
  useCurrentWorkspace(): WorkspaceOut | null;
  useWorkspaces(): WorkspaceOut[];
  usePermission(perm: string): boolean;
  useWorkspacePermission(perm: string): boolean;
  ```

Used everywhere to avoid hard-coding workspace ids and permission checks.

---

## 7. Definition of Done – Workspaces & RBAC

From the perspective of this workpackage, we’re “done” when:

1. App bootstrap consumes workspace + permission info (from `/bootstrap` + these APIs).
2. We can:

   * Select a workspace (even if it’s a minimal selector at first).
   * Correctly scope Documents/Configs/Runs calls using `workspace_id`.
3. Permissions are enforced in UI:

   * Actions requiring specific permissions are hidden/disabled appropriately.
   * Safe mode state is surfaced and respected.
4. We’re **not** leaking admin-only APIs into the normal UX, but the docs make it clear how we’d build that later.