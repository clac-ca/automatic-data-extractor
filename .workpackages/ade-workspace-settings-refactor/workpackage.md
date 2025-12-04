> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

* [ ] Replace the legacy Workspace Settings route + views with a **new settings shell** (no query-param “view” routing)
* [ ] Implement **General** settings v2 (workspace identity + environment label + default workspace)
* [ ] Implement **Members** v2 (list/add/remove + role assignment) wired to `/workspaces/{id}/members`
* [ ] Implement **Roles** v2 (tenant role definitions + permission editor) wired to `/rbac/roles` + `/rbac/permissions`
* [ ] Implement **Danger Zone** v2 (delete workspace) wired to `DELETE /workspaces/{id}`
* [ ] Add shared UI primitives: permission gating, skeleton states, error boundary, save bar, confirm modals
* [ ] Update global workspace UI to display `environment_label` consistently (workspace switcher + header)
* [ ] Delete old settings code paths and update all internal links + docs + tests

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, e.g.:
> `- [x] Implement General v2 — commit 3a9c1e2`

---

# ADE Web — Workspace Settings Complete Refactor (No Backwards Compatibility)

## 1. Objective

**Goal:**
Rebuild Workspace Settings from scratch so it’s:

* **obvious**: clear information architecture, consistent UX patterns
* **correct**: matches ADE API routes + permission semantics
* **scalable**: new workspace-level settings can be added without rewriting the page
* **separated by scope**: Workspace settings vs System settings are not mixed

You will:

* Replace the existing settings route/view system with a new nested settings router.
* Define a new “Workspace Settings” surface composed of:

  * General (workspace identity + preferences)
  * Members (workspace access)
  * Roles (tenant role definitions and permissions)
  * Danger Zone (delete workspace)
* Use workspace `settings` as the extensible store for workspace-specific preferences (e.g. `environment_label`).
* Ensure all actions map cleanly to the backend routes listed (workspaces + members + RBAC + system safe mode).
* Remove any legacy UI patterns entirely (no compatibility layer; update navigational links across the app).

The result should:

* Let a developer read the page components and instantly understand:

  * which backend endpoints each section uses
  * which permissions gate each action
  * what data is stored on the workspace vs globally
* Provide reliable behavior: loading states, optimistic updates when safe, strong confirmation flows for destructive actions.

---

## 2. Context (What you are starting from)

You provided the definitive list of ADE API routes. Workspace Settings primarily depends on:

### Workspace routes

* `GET /api/v1/workspaces/{workspace_id}` — load workspace context
* `PATCH /api/v1/workspaces/{workspace_id}` — update workspace metadata (name/slug/settings)
* `DELETE /api/v1/workspaces/{workspace_id}` — delete workspace
* `PUT /api/v1/workspaces/{workspace_id}/default` — set default workspace
* `GET /api/v1/workspaces` — list workspaces for workspace switcher

### Members routes

* `GET /api/v1/workspaces/{workspace_id}/members` — list members
* `POST /api/v1/workspaces/{workspace_id}/members` — add member (+ roles)
* `PUT /api/v1/workspaces/{workspace_id}/members/{user_id}` — replace member roles
* `DELETE /api/v1/workspaces/{workspace_id}/members/{user_id}` — remove member

### RBAC routes (tenant-wide)

* `GET /api/v1/rbac/roles` — list role definitions
* `POST /api/v1/rbac/roles` — create role
* `GET /api/v1/rbac/roles/{role_id}` — read role
* `PATCH /api/v1/rbac/roles/{role_id}` — update role
* `DELETE /api/v1/rbac/roles/{role_id}` — delete role
* `GET /api/v1/rbac/permissions` — list permissions (to build role permission editor)

### Session/bootstrap routes used for permissions and workspace nav

* `GET /api/v1/me/bootstrap` — profile + roles + permissions + workspaces
* `GET /api/v1/me/permissions` — effective permissions
* `POST /api/v1/me/permissions/check` — permission checks (optional)

### System safe mode (global; not workspace scoped)

* `GET /api/v1/system/safe-mode`
* `PUT /api/v1/system/safe-mode`

**Known pain to resolve with a hard refactor**

* Settings often becomes a dumping ground. We must explicitly define what “Workspace Settings” contains and what it does not.
* RBAC role definitions are tenant-level, but role assignment for workspace members is workspace-level. The UI must make that distinction crystal clear.

---

## 3. Target architecture / structure (ideal)

**IA / UX target:**

**Workspace Settings** (scoped to current workspace)

* General

  * Name / Slug
  * Environment label (workspace.settings)
  * Default workspace (per-user preference)
* Members

  * Add user
  * Assign roles
  * Remove user
* Roles (Tenant-wide)

  * Create/edit/delete role definitions
  * Select permissions per role
  * Clear messaging: “Changing a role affects all workspaces.”
* Danger Zone

  * Delete workspace (with typed confirmation)

**System Settings** (global, separate route, not “inside workspace settings”)

* Safe mode toggle
* Other future global toggles

> ✅ This is a deliberate separation. Workspace settings should not include global system toggles. If you *want* a status banner in workspace settings, it can be informational and link to System Settings.

### Proposed route structure (breaking, by design)

```text
/workspaces/:workspaceId/settings
  /general
  /members
  /roles
  /danger
/system/settings
  /safe-mode
```

### Proposed file tree (frontend)

```text
apps/ade-web/
  src/
    app/
      routes/
        workspaceSettingsRoutes.tsx      # route definitions (RR v6)
        systemSettingsRoutes.tsx
    features/
      workspaces/
        api/
          workspaces.ts                 # GET/PATCH/DELETE, list, default
          members.ts                    # members CRUD
        hooks/
          useWorkspace.ts
          useUpdateWorkspace.ts
          useDeleteWorkspace.ts
          useSetDefaultWorkspace.ts
          useWorkspaceMembers.ts
          useAddWorkspaceMember.ts
          useUpdateWorkspaceMember.ts
          useRemoveWorkspaceMember.ts
        model/
          workspaceSettings.ts          # typed settings keys + helpers
      rbac/
        api/
          roles.ts                      # role defs CRUD
          permissions.ts                # list permissions
        hooks/
          useRoles.ts
          useRole.ts
          useCreateRole.ts
          useUpdateRole.ts
          useDeleteRole.ts
          usePermissions.ts
      settings/
        workspace/
          WorkspaceSettingsShell.tsx     # left nav + header + outlet
          nav.ts                         # view registry + labels
          views/
            GeneralSettingsView.tsx
            MembersSettingsView.tsx
            RolesSettingsView.tsx
            DangerZoneSettingsView.tsx
          components/
            SettingsHeader.tsx
            SettingsNav.tsx
            SettingsCard.tsx
            SaveBar.tsx
            ConfirmModal.tsx
            PermissionGate.tsx
        system/
          SystemSettingsShell.tsx
          views/
            SafeModeView.tsx
    shared/
      ui/
        Toast.tsx
        Skeleton.tsx
        EmptyState.tsx
        ErrorState.tsx
```

---

## 4. Design (for this workpackage)

### 4.1 Design goals

* **Zero backwards compatibility:** remove old views and old route wiring entirely.
* **Single obvious route:** settings are nested routes, not query params.
* **Hard scope separation:** workspace vs system.
* **Permission-first UI:** no “press button then get 403.” Buttons are disabled/hidden appropriately, and read-only states are explicit.
* **Developer clarity:** every page indicates (in code and in UI text) which endpoint it talks to.

### 4.2 Key components / modules

* `WorkspaceSettingsShell`

  * Loads workspace + permissions once
  * Provides consistent header/nav layout
  * Hosts nested route `<Outlet />`
* `GeneralSettingsView`

  * Workspace metadata form (PATCH workspace)
  * Environment label field stored in `workspace.settings`
  * Default workspace action (PUT /default)
* `MembersSettingsView`

  * Member list (GET members)
  * Add member (POST members)
  * Update roles (PUT member)
  * Remove member (DELETE member)
* `RolesSettingsView` (Tenant-wide)

  * Manage role definitions (RBAC endpoints)
  * Permission checklist (GET permissions)
  * Clear UI copy about tenant-wide effects
* `DangerZoneSettingsView`

  * Delete workspace flow (DELETE workspace)
* Shared UI primitives:

  * `PermissionGate` (show/lock sections by required perms)
  * `SaveBar` (dirty state + save/cancel)
  * `ConfirmModal` (typed confirmation)

### 4.3 Key flows / pipelines

#### Flow A — Enter Workspace Settings

1. Route loads `workspaceId`
2. Fetch:

   * `GET /api/v1/workspaces/{workspaceId}`
   * `GET /api/v1/me/permissions` (or use cached bootstrap)
3. Render settings shell with nav items filtered by permissions
4. Default to `/general`

#### Flow B — Update workspace metadata (name/slug/settings)

1. User edits fields
2. SaveBar appears
3. Submit triggers `PATCH /api/v1/workspaces/{workspaceId}` payload:

   * `{ name, slug, settings }`
4. On success:

   * toast “Saved”
   * update workspace cache
   * update header/workspace switcher immediately

#### Flow C — Default workspace

1. Click “Make default”
2. `PUT /api/v1/workspaces/{workspaceId}/default`
3. Refresh bootstrap/workspaces list so “default” marker updates

#### Flow D — Manage members

1. List via `GET /api/v1/workspaces/{workspaceId}/members`
2. Add member modal collects:

   * identifier (email or user selection; see Open Question)
   * roles
3. Submit `POST /members`
4. Update roles with `PUT /members/{userId}`
5. Remove with `DELETE /members/{userId}`

#### Flow E — Manage role definitions (tenant-wide)

1. List roles `GET /api/v1/rbac/roles`
2. Create role `POST /api/v1/rbac/roles`
3. Edit role permissions:

   * fetch permissions `GET /api/v1/rbac/permissions`
   * update role `PATCH /api/v1/rbac/roles/{roleId}`
4. Delete role `DELETE /api/v1/rbac/roles/{roleId}`

#### Flow F — Delete workspace

1. “Delete workspace” card warns clearly
2. Typed confirm requires entering workspace slug
3. Submit `DELETE /api/v1/workspaces/{workspaceId}`
4. On success:

   * navigate to first available workspace (or workspace list)
   * refresh bootstrap

---

## 4.4 Open questions / decisions

* **Decision: `environment_label` lives in `workspace.settings.environment_label`.**

  * Rationale: future-proof; no new columns needed; consistent with “settings dict” approach.

* **Decision: Roles view is tenant-wide and is labeled that way.**

  * Rationale: RBAC endpoints are tenant-level; role definition changes impact all workspaces. The UI must say this.

* **Open question: Add member payload**

  * The endpoint is `POST /workspaces/{id}/members`. Confirm whether it accepts:

    * `email` (preferred UX)
    * `user_id`
    * both
  * **Frontend implementation will adapt once request schema is confirmed**, but UX will be “type email/user and assign roles.”

* **Open question: Permissions representation**

  * Confirm how workspace permissions are represented in `GET /me/permissions` vs bootstrap; choose one source of truth.
  * Recommendation: prefer bootstrap cache and only refetch permissions if stale.

---

## 5. Implementation & notes for agents

### 5.1 API mapping table (for dev clarity)

| Settings area                | Primary endpoints                                                                     | Notes                                               |
| ---------------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------- |
| General (workspace identity) | `GET /workspaces/{id}`, `PATCH /workspaces/{id}`                                      | Patch includes `{name, slug, settings}`             |
| Environment label            | `PATCH /workspaces/{id}`                                                              | Stored under `workspace.settings.environment_label` |
| Default workspace            | `PUT /workspaces/{id}/default`                                                        | Per-user preference                                 |
| Members                      | `GET/POST /workspaces/{id}/members`, `PUT/DELETE /workspaces/{id}/members/{user_id}`  | Roles assigned per membership                       |
| Roles (tenant-wide)          | `GET/POST /rbac/roles`, `PATCH/DELETE /rbac/roles/{role_id}`, `GET /rbac/permissions` | Must warn about tenant-wide impact                  |
| Danger zone                  | `DELETE /workspaces/{id}`                                                             | Typed confirmation required                         |
| System safe mode (global)    | `GET/PUT /system/safe-mode`                                                           | Goes on `/system/settings`, not workspace settings  |

---

### 5.2 Data model and helpers

Create a typed helper module for workspace.settings keys:

```ts
// features/workspaces/model/workspaceSettings.ts
export const WORKSPACE_SETTINGS_KEYS = {
  environmentLabel: "environment_label",
} as const;

export type WorkspaceSettings = Record<string, unknown>;

export function readEnvironmentLabel(settings: WorkspaceSettings | null | undefined): string {
  const v = settings?.[WORKSPACE_SETTINGS_KEYS.environmentLabel];
  return typeof v === "string" ? v.trim() : "";
}

export function writeEnvironmentLabel(
  settings: WorkspaceSettings | null | undefined,
  label: string
): WorkspaceSettings {
  const next = { ...(settings ?? {}) };
  const trimmed = label.trim();
  if (!trimmed) delete next[WORKSPACE_SETTINGS_KEYS.environmentLabel];
  else next[WORKSPACE_SETTINGS_KEYS.environmentLabel] = trimmed;
  return next;
}
```

Key rule: **never clobber unknown settings keys**.

---

### 5.3 UX spec (what the new page should feel like)

**WorkspaceSettingsShell**

* Left nav, sticky
* Right content area with consistent max-width
* Header:

  * “Workspace Settings”
  * Workspace name + environment label badge
  * Quick link to “System Settings” for admins

**General**

* Card: “Workspace identity”

  * Name (text)
  * Slug (text)
  * Workspace ID (read-only)
* Card: “Workspace preferences”

  * Environment label
  * “Make default workspace” plus status (“This is your default”)
* SaveBar appears when identity/preferences changed

**Members**

* Table list: Name, Email, Roles, Actions
* “Add member” modal:

  * email/user
  * role multi-select (from roles list)
* Inline role editing per row + Save
* Remove member confirm

**Roles**

* Warning banner: “Roles are tenant-wide. Changes affect all workspaces.”
* Role list with “Create role”
* Role editor:

  * Name, description
  * Permissions checklist grouped by domain (workspace.*, runs.*, configs.*, system.*)
  * Save, Delete

**Danger Zone**

* Card: “Delete workspace”
* Typed confirm requires workspace slug
* explicit warning about loss of configurations, documents, runs, etc.

---

### 5.4 Permission gating strategy (no 403-driven UX)

Implement a single `PermissionGate` component:

```tsx
type PermissionGateProps = {
  require: { workspace?: string[]; global?: string[] };
  fallback?: React.ReactNode; // read-only message or null
  children: React.ReactNode;
};

function PermissionGate(...) { ... }
```

Rules:

* If user lacks read access for a view, hide it from nav and redirect.
* If user can read but cannot manage, show view in read-only mode and disable actions with tooltip.

Source of truth:

* `GET /api/v1/me/bootstrap` and/or `GET /api/v1/me/permissions`

---

### 5.5 Networking / state management

Standardize API files per feature domain:

* `features/workspaces/api/workspaces.ts`
* `features/workspaces/api/members.ts`
* `features/rbac/api/roles.ts`
* `features/rbac/api/permissions.ts`

And expose hooks that wrap them (React Query recommended):

* `useWorkspace(workspaceId)`
* `useUpdateWorkspace(workspaceId)`
* `useWorkspaceMembers(workspaceId)`
* `useAddWorkspaceMember(workspaceId)`
* `useUpdateWorkspaceMember(workspaceId)`
* `useRemoveWorkspaceMember(workspaceId)`
* `useRoles()`, `usePermissions()`, `useCreateRole()`, etc.

Key: one “mutation style” across the app:

* show toasts on success/failure
* map backend validation errors to fields
* invalidate relevant queries

---

### 5.6 Delete the old system completely

Since you want no compatibility:

* Remove the old workspace settings components and routing logic.
* Remove any query-param `view=` navigation.
* Update all internal links that pointed to old syntax.

Deliverable: a single new entry route:

* `/workspaces/:workspaceId/settings/*`

And a new system settings route:

* `/system/settings/*`

---

### 5.7 Tests (required)

Add/Update tests:

1. **Routing**

* entering `/workspaces/:id/settings` redirects to `/general`
* permission missing redirects to first available section

2. **General**

* PATCH payload includes merged settings
* default workspace button calls correct endpoint and updates UI

3. **Members**

* add member calls POST and refreshes list
* role update calls PUT and refreshes list
* remove calls DELETE and refreshes list

4. **Roles**

* create role calls POST
* edit role calls PATCH
* delete role calls DELETE
* permissions list is fetched and rendered

5. **Danger zone**

* delete button disabled until slug matches
* on success navigates away and workspace disappears

---

### 5.8 Documentation + developer friendliness (DoD)

* Update frontend docs (where workspace layout/settings are described) to match the new route structure and section breakdown.
* Add a short README near `features/settings/workspace` explaining:

  * the scope separation
  * the endpoints used per section
  * how settings keys are stored in workspace.settings

---

## Summary: What the new Workspace Settings contains

**Workspace Settings**

* Identity (name/slug)
* Preferences (environment label, default workspace)
* Members (access control)
* Roles (tenant-wide definitions)
* Danger zone (delete workspace)

**NOT in Workspace Settings**

* System safe mode toggle (global) → goes to System Settings route
