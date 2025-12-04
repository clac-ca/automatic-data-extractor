> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

* [ ] Replace the current tabbed workspace settings route with a “standard settings” layout (sidebar + subpages)
* [ ] Fix **all** settings-related API calls to respect backend pagination limits (page_size ≤ 100) and correct scope usage
* [ ] Refactor the Members settings UX (loaders/errors, user directory handling, role assignment flow) and verify end-to-end functionality
* [ ] Refactor the Roles settings UX (permissions scope, create/edit/delete role flows) and verify end-to-end functionality
* [ ] Add/adjust tests, remove old settings code paths, and run a full manual QA pass for Workspace Settings

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, e.g.:
> `- [x] Fix page_size limit — <commit_sha>`

---

# Workspace Settings Refactor (Standard Settings Page + API Call Fixes)

## 1. Objective

**Goal:**
Refactor the **Workspace Settings** experience in `ade-web` into a standard, intuitive settings UI (sidebar navigation + focused subpages), while fixing all settings-related API calls to match the ADE API constraints and eliminating current runtime errors in Members/Roles.

You will:

* Replace the current “tabs + `view` query param” settings UI with a **standard settings layout**.
* Fix Members/Roles (and any other settings page queries) to respect backend pagination limits and correct API contract usage.
* Ensure membership & roles management is functional end-to-end.
* Remove old settings page code paths (no backwards compatibility).

The result should:

* Feel like a conventional settings page: consistent nav, clear section boundaries, “danger zone” patterns, etc.
* Have **zero 422s** from invalid `page_size` and correct permission scoping for permissions/roles.
* Be easy to extend with future settings sections.

---

## 2. Context (What you are starting from)

### Current UI shape

Workspace settings currently render as a route under workspace sections with a **tabbed UI controlled by `view` query param**. 
The workspace section router maps `"settings"` to `WorkspaceSettingsRoute` via `resolveWorkspaceSection`. 

### Known issues / pain points

#### 1) Members list endpoint errors (422)

Frontend requests `page_size=200` but backend enforces `page_size ≤ 100`.

* Backend pagination is capped at 100 (FastAPI validation uses `le=MAX_PAGE_SIZE`). 
* Frontend Members hook hardcodes 200.

#### 2) Roles list endpoint errors (422)

Same pagination cap issue:

* Frontend Roles hook hardcodes 200.
* Permissions query also hardcodes 200 and requests `scope="global"` while later filtering for workspace permissions. 

#### 3) Permissions scope mismatch in Roles UI

Roles UI *filters for workspace permissions* but query requests `scope="global"`, which will not return workspace-scoped permissions when the API filters by scope. The backend endpoint accepts a scope and applies it. 

#### 4) “Standard settings page” expectation

Tabs feel “inside an app page”, not like standard settings. We want:

* left sidebar, nested routes/subpages
* clear separation of General / Members / Roles / Danger Zone
* consistent patterns for save actions, destructive actions, confirmations, permissions gating

### Hard constraints

* Pagination: `page_size` must be ≤ 100 across paginated endpoints. 
* Members endpoints are under `/api/v1/workspaces/{workspace_id}/members` (list/add/update/remove). 
* Roles/Permissions endpoints are under `/api/v1/rbac/roles` and `/api/v1/rbac/permissions`. 

---

## 3. Target architecture / structure (ideal)

**Summary:**
Implement `Workspace Settings v2` as a settings layout with:

* **Left sidebar navigation**
* **Subpages** (General, Members, Roles, Danger Zone)
* Strong API contract alignment (pagination + scope correctness)
* No query-param tab switching

```text
apps/ade-web/
  src/
    screens/
      Workspace/
        sections/
          Settings/
            WorkspaceSettingsRoute.tsx          # NEW: layout + section routing
            settingsNav.ts                      # NEW: canonical sections + permission gates
            pages/
              GeneralSettingsPage.tsx
              MembersSettingsPage.tsx
              RolesSettingsPage.tsx
              DangerSettingsPage.tsx
            components/
              SettingsLayout.tsx                # left nav + content shell
              SettingsSectionHeader.tsx
              SaveBar.tsx
              ConfirmDangerActionModal.tsx
            hooks/
              useWorkspaceMembers.ts            # FIX: page_size + pagination strategy
              useWorkspaceRoles.ts              # FIX: page_size
              usePermissions.ts                 # FIX: scope + page_size
  src/
    api/
      pagination.ts                             # NEW: MAX_PAGE_SIZE + helpers
      workspaces-api.ts                         # FIX: default page sizes (permissions)
  tests/
    screens/Workspace/settings.test.tsx         # update/add tests for new route behavior
```

---

## 4. Design (for this workpackage)

### 4.1 Design goals

* **Clarity / intuition:** Settings should look and behave like settings (sidebar, subpages, “danger zone”).
* **Correctness:** No invalid API calls; pagination and scope must match backend constraints.
* **Maintainability:** One obvious place to add future settings sections; centralized nav/route config.

### 4.2 Key components / modules

* **`SettingsLayout`** — Standard two-column layout (left nav + content), mobile-friendly.
* **`WorkspaceSettingsRoute`** — Owns which settings “section” is active based on path segments.
* **API hooks (`useWorkspaceMembers`, `useWorkspaceRoles`, `usePermissions`)** — Source of truth for data loading, pagination strategy, caching, invalidations.

### 4.3 Key flows / pipelines

#### Flow A — Enter Workspace Settings

1. `resolveWorkspaceSection(workspaceId, ["settings", ...])` routes into settings.
2. `WorkspaceSettingsRoute` parses the “section” segment: `general | members | roles | danger`.
3. Render `SettingsLayout` with sidebar items gated by permissions; render the selected page.

#### Flow B — Members management

1. Load members (paginated correctly).
2. Load available roles (paginated correctly).
3. Optional: load user directory for “Add member” (if the caller can access it; currently `/users` is “administrator only” per OpenAPI docs). 
4. Add/update/remove member triggers mutations; invalidate member list + toast feedback.

#### Flow C — Roles management

1. Load roles for workspace scope.
2. Load workspace-scoped permissions (scope must be `"workspace"`).
3. Create/update/delete role triggers invalidations; show errors cleanly.

### 4.4 Open questions / decisions

* **Decision: environment_label**

  * **Default**: do not add a first-class field; if needed, store it as `workspace.settings.environment_label` and treat it as UI-only metadata. 
  * **Rationale**: reduces domain complexity; workspace name/slug already solve most use cases.

* **Decision: pagination UX**

  * **Preferred**: implement `useInfiniteQuery` (or “Load more” button) for members/roles/permissions when `total > loaded`.
  * **Rationale**: avoids hardcoding large page sizes and stays within limits.

---

## 5. Implementation & notes for agents

### 5.1 Fix the API contract errors first (stop 422s)

Backend enforces `page_size ≤ 100`. 
Frontend currently violates this in multiple places:

* Members hook uses `MEMBERS_PAGE_SIZE = 200`.
* Roles hook uses `ROLES_PAGE_SIZE = 200`.
* Permissions query uses `PAGE_SIZE = 200` and `scope="global"`. 

**Implementation steps:**

1. Add `apps/ade-web/src/api/pagination.ts`:

   ```ts
   export const MAX_PAGE_SIZE = 100; // mirrors ade-api validation
   export const DEFAULT_PAGE_SIZE = 50;

   export function clampPageSize(size?: number): number | undefined {
     if (size == null) return undefined;
     return Math.min(size, MAX_PAGE_SIZE);
   }
   ```
2. Update:

   * `useWorkspaceMembers.ts`: set page size to `MAX_PAGE_SIZE` or `DEFAULT_PAGE_SIZE` (≤ 100), implement pagination.
   * `useWorkspaceRoles.ts`: same.
   * `usePermissions.ts`: page size ≤ 100 **and** request `scope: "workspace"` for workspace role editing.

**Minimum fix** (unblocks UI immediately): change the 200 constants to 100.
**Better fix**: add simple pagination aggregation:

```ts
// Example: pull all pages up to total (simple, safe for small datasets)
async function listAllPages<T>(fetchPage: (page: number) => Promise<{ items: T[]; total?: number }>) {
  const results: T[] = [];
  for (let page = 1; page <= 1000; page += 1) {
    const { items, total } = await fetchPage(page);
    results.push(...items);
    if (!items.length) break;
    if (total != null && results.length >= total) break;
    if (items.length < 100) break; // heuristic
  }
  return results;
}
```

### 5.2 Refactor the settings UI into a standard layout (no tab query params)

Current settings route uses a `view` query param and tabs. 
We will replace it with path-segment routing:

**New URLs**

* `/workspaces/:id/settings/general`
* `/workspaces/:id/settings/members`
* `/workspaces/:id/settings/roles`
* `/workspaces/:id/settings/danger`

**Implementation steps**

1. Update `resolveWorkspaceSection` so `"settings"` passes the remaining segments to settings:

   * from `settings.tsx` 
   * Accept: `segments: string[]` and determine active section.
2. Rebuild `WorkspaceSettingsRoute`:

   * Owns parsing: second segment defaulting to `general`.
   * Renders `<SettingsLayout active="members" ... />`.
3. Remove:

   * old `TabsRoot` usage
   * old `view` query-param logic
   * old section components if they no longer fit

**Sidebar behavior**

* Show all sections, but disable/hide sections based on permission where appropriate.
* If the user lands on a section they cannot access, show a friendly “You don’t have access” state.

### 5.3 Redesign the content pages (standard sections)

#### General

* Workspace name + slug (existing)
* “Default workspace” toggle (calls `PUT /workspaces/{id}/default`) 
* Optional: “Labels” (store in `workspace.settings`) — include `environment_label` only if you want it

#### Members

* Table with: user, roles, status, actions
* Add member modal (integrate existing `useUsersQuery` but handle non-admin failures gracefully)
* Edit roles inline via role multi-select
* Remove member (confirm modal)

#### Roles

* Table of roles (name, slug, system/custom, permission count, actions)
* Role editor drawer/modal:

  * name/slug/description
  * permissions multi-select (workspace scope)
* **Critical fix**: load permissions with `scope="workspace"`; backend filters by scope. 

#### Danger Zone

* Delete workspace (confirm modal + typed warning)
* Optional: “Leave workspace” if supported later

### 5.4 Review “all API calls” used by workspace settings

At minimum, verify these requests and ensure they match the backend contract:

* Workspace:

  * `GET /workspaces/{workspace_id}`
  * `PATCH /workspaces/{workspace_id}`
  * `PUT /workspaces/{workspace_id}/default` 
  * `DELETE /workspaces/{workspace_id}` 

* Members:

  * `GET /workspaces/{workspace_id}/members` (page_size ≤ 100, include_total optional) 
  * `POST /workspaces/{workspace_id}/members`
  * `PUT /workspaces/{workspace_id}/members/{user_id}`
  * `DELETE /workspaces/{workspace_id}/members/{user_id}` 

* Roles/Permissions:

  * `GET /rbac/roles?scope=workspace` (page_size ≤ 100)
  * `POST /rbac/roles`, `PATCH /rbac/roles/{role_id}`, `DELETE /rbac/roles/{role_id}` 
  * `GET /rbac/permissions?scope=workspace` (page_size ≤ 100) 

**Known current mismatches (must fix)**

* Members fetch uses `page_size=200` in frontend.
* Roles fetch uses `page_size=200` in frontend.
* Permissions fetch uses `page_size=200` and requests `scope="global"` while UI wants workspace. 

### 5.5 Testing requirements

* Update/replace unit tests for workspace route section parsing (settings subroutes).
* Add a small integration-style test for:

  * Members page loads with page_size 100 (or default) and does not throw
  * Roles page loads permissions with `scope=workspace`
* Manual QA checklist:

  * Visit each settings subroute directly (deep links).
  * Members list loads (no 422).
  * Roles list loads (no 422).
  * Create role → appears in list.
  * Add member → shows in list.
  * Update member roles → persists.
  * Delete workspace confirmation behaves correctly.

### 5.6 Performance / security notes

* Do not attempt to “fetch everything” with huge `page_size`; backend caps at 100. 
* Mutations (members add/update/remove) are CSRF-protected on the API side; ensure the existing client/middleware continues to include CSRF headers/cookies.
* If user directory loading (`/users`) fails for non-admins, the Members page should still function for viewing members; only “Add member” should be blocked with a clear explanation.