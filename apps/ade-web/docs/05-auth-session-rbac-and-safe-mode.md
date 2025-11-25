# 05 – Auth, session, RBAC, and safe mode

This document explains how ADE Web handles:

- **Authentication** (setup, login, logout, SSO),
- The **session model** on the frontend,
- **Roles & permissions** (RBAC) at global and workspace scope,
- The **safe mode** kill‑switch and how it affects the UI.

It is written from the frontend’s point of view: how we consume the backend APIs and how we structure the code so that auth, permissions, and safe mode are predictable and easy to work with.

For domain terminology (Workspace, Job, Configuration, etc.), see  
[`01-domain-model-and-naming.md`](./01-domain-model-and-naming.md).

---

## 1. Goals and principles

Auth/RBAC/safe mode in ADE Web should:

1. **Feel transparent to users**  
   - Permissions are enforced without surprises.  
   - If you can’t do something, you either don’t see it or you see it clearly disabled with an explanation.

2. **Be simple to reason about in code**  
   - One **canonical session shape** and one **effective permissions shape**.  
   - Thin, well‑named hooks for permission checks.

3. **Avoid duplication of policy**  
   - Backend remains the source of truth for permissions and safe mode.  
   - Frontend never tries to “re‑implement RBAC”; it only checks booleans.

4. **Stay secure by default**  
   - No secrets in localStorage.  
   - No open redirects.  
   - No accidental access to workspaces a user doesn’t belong to.

---

## 2. High‑level architecture

On the backend, auth and RBAC are exposed via:

- **Auth & session** endpoints:
  - `GET /api/v1/auth/session` – active session profile  
  - `POST /api/v1/auth/session` – create session (email/password)  
  - `DELETE /api/v1/auth/session` – terminate session  
  - `POST /api/v1/auth/session/refresh` – refresh session  
  - `GET /api/v1/auth/providers` – auth provider list  
  - `GET /api/v1/auth/sso/login` / `GET /api/v1/auth/sso/callback` – SSO roundtrip  
  - `GET /api/v1/setup/status` / `POST /api/v1/setup` – initial admin setup

- **Identity, roles, permissions**:
  - `GET  /api/v1/users/me` – authenticated user profile  
  - `GET  /api/v1/me/permissions` – effective permissions for the caller  
  - `POST /api/v1/me/permissions/check` – check specific permissions  
  - `GET/POST/PATCH/DELETE /api/v1/roles` – global roles  
  - `GET/POST/DELETE /api/v1/role-assignments` – global role assignments  
  - `GET /api/v1/workspaces/{workspace_id}/roles` – workspace roles  
  - `GET/POST/DELETE /api/v1/workspaces/{workspace_id}/role-assignments` – workspace role assignments  
  - `GET/POST/DELETE /api/v1/workspaces/{workspace_id}/members` – workspace members and their roles

- **Safe mode**:
  - `GET /api/v1/system/safe-mode` – current safe mode status  
  - `PUT /api/v1/system/safe-mode` – toggle safe mode and update message

On the frontend we model this as three main concepts:

1. A **Session** query – “who am I and am I logged in?”
2. An **EffectivePermissions** query – “what am I allowed to do?”
3. A **SafeModeStatus** query – “is engine execution currently blocked?”

Screens then compose these three pieces using small, predictable hooks.

---

## 3. Initial setup flow

When ADE is first deployed, **no users exist**. ADE Web must detect this and prompt for initial administrator setup.

### 3.1 Setup detection

On app start, the entry strategy does:

1. Call `GET /api/v1/setup/status`.
2. If the API responds “setup required”:
   - Navigate to `/setup`.
3. Otherwise:
   - Continue with normal auth/session checks.

The **Setup screen** at `/setup`:

- Collects the details for the first admin user (email, name, password).
- Calls `POST /api/v1/setup`.
- On success:
  - Redirects to `/login` with a success message, or directly signs in (depending on backend behaviour).

Setup endpoints are **public**, but can only be called when the backend says setup is required. All subsequent requests should see “setup not required” and be rejected if someone tries to hit `/setup` again.

---

## 4. Authentication flows

ADE Web supports:

- Email/password login.
- SSO login.
- Session refresh and logout.

### 4.1 Email/password login

The **Login screen** (`/login`) is responsible for:

- Rendering the list of auth providers (from `GET /api/v1/auth/providers`).
- Rendering an email/password form when local auth is enabled.

Flow:

1. User submits email/password.
2. Frontend calls `POST /api/v1/auth/session` with credentials.
3. On success:
   - Session cookie is set by the backend (http‑only).
   - We invalidate and refetch the **Session** and **EffectivePermissions** queries.
   - We redirect:
     - To `redirectTo` query param if present and valid.
     - Otherwise to the workspace directory (`/workspaces`) or default workspace.

Errors:

- Invalid credentials → inline form error, no redirect.
- Other errors → generic error message.

We do **not** store the session token in localStorage; we rely on the backend’s cookie/session implementation.

### 4.2 SSO login

If SSO providers are configured:

- The Login screen shows provider buttons based on `GET /api/v1/auth/providers`.
- Clicking a provider:
  - Navigates to `GET /api/v1/auth/sso/login?provider=<id>&redirectTo=<path>`.
  - Backend immediately responds with `302` to the IdP.

On successful IdP authentication:

- IdP redirects to `GET /api/v1/auth/sso/callback?...`.
- Backend validates the result, creates the session and sets cookies.
- Backend then redirects back to ADE Web (e.g. `/auth/callback`).

On the **Auth callback screen** (`/auth/callback`):

1. Optionally show a short “Signing you in…” state.
2. Invalidate and refetch Session & permissions.
3. Redirect to:
   - `redirectTo` from the callback URL (if valid and same‑origin).
   - Otherwise workspace directory or default workspace.

### 4.3 Session refresh

Sessions can expire. To provide a smooth experience:

- A refresh mechanism calls `POST /api/v1/auth/session/refresh` when:
  - Certain errors indicate an expiring session, or
  - A background job refresh timer runs (if implemented).

On successful refresh:

- Backend extends cookies.
- We refetch Session & permissions if needed.

On failure:

- We treat the user as logged out:
  - Clear any in‑memory session state.
  - Redirect to `/login` with a “session expired” message.

### 4.4 Logout

From the **Profile dropdown**, “Sign out”:

1. Calls `DELETE /api/v1/auth/session`.
2. Regardless of success/failure:
   - Clears React Query cache and any in‑memory auth state.
   - Navigates to `/login`.

While logout is in progress:

- Disable the sign‑out button.
- Optionally show “Signing out…” text.

---

## 5. Session model on the frontend

We treat **“who am I?”** as a single canonical object.

### 5.1 Session query

`useSessionQuery()` (in `shared/auth`):

- Calls `GET /api/v1/auth/session`.
- Returns:

  ```ts
  interface Session {
    user: {
      id: string;
      email: string;
      name: string;
      avatarUrl?: string | null;
    };
    // Optionally:
    defaultWorkspaceId?: string | null;
    globalPermissions?: string[];
    // Any other flags the backend chooses to expose.
  }
````

* If the request returns 401/403:

  * Treat as “not authenticated”.
  * Screens that require auth redirect to `/login`.

### 5.2 User profile

`GET /api/v1/users/me` may provide more detailed profile information (e.g. extra fields).

We normally:

* Use `Session.user` for most UI (display name, email).
* Use `/users/me` only for areas that need extended info (e.g. profile management screen).

To keep things simple:

* `useSessionQuery` is considered the **one true source** of “current user” for the rest of the app.
* If we need more fields, we add them to the backend’s session shape and the `Session` interface.

---

## 6. Roles & permissions (RBAC)

RBAC provides:

* **Global roles & assignments** for system‑level capabilities.
* **Workspace roles & assignments** for per‑workspace capabilities.
* **Effective permissions** for answering yes/no permission checks.

### 6.1 Effective permissions

We centralise permission evaluation in the backend, and the frontend only asks for effective results.

`useEffectivePermissionsQuery()`:

* Calls `GET /api/v1/me/permissions`.
* Returns:

  ```ts
  interface EffectivePermissions {
    // Flattened set of permission keys the user has globally.
    global: string[];

    // Optionally: per-workspace map.
    workspaces?: Record<string, string[]>; // workspaceId -> permissions
  }
  ```

When we need to check a specific set of permissions **for one action** and don’t want to transfer all of them, we can use:

* `POST /api/v1/me/permissions/check` with a list of permission keys.
* The corresponding helper: `checkPermissions(keys)` – returns a boolean or per‑key result.

However, the **preferred pattern** is to fetch effective permissions once and reuse them.

### 6.2 Global roles & assignments

Frontend exposure:

* Screens to list and manage global roles and assignments are usually restricted to high‑privilege users.

Endpoints:

* `GET /api/v1/roles` – list global roles.
* `POST /api/v1/roles` – create role.
* `PATCH /api/v1/roles/{role_id}` – update role.
* `DELETE /api/v1/roles/{role_id}` – delete role.
* `GET /api/v1/role-assignments` – list global assignments.
* `POST /api/v1/role-assignments` – assign a role to a principal.
* `DELETE /api/v1/role-assignments/{assignment_id}` – remove assignment.

The UI:

* May have an “Admin” section for system‑wide role management.
* Will be permission‑gated by a global permission (e.g. `System.Roles.ReadWrite`).

### 6.3 Workspace roles & assignments

A workspace defines its own roles that aggregate permissions.

Endpoints:

* `GET /api/v1/workspaces/{workspace_id}/roles` – list workspace roles.
* `GET /api/v1/workspaces/{workspace_id}/role-assignments` – list role assignments.
* `POST /api/v1/workspaces/{workspace_id}/role-assignments` – assign a workspace role to a principal.
* `DELETE /api/v1/workspaces/{workspace_id}/role-assignments/{assignment_id}` – remove an assignment.
* `GET /api/v1/workspaces/{workspace_id}/members` – list workspace members and their roles.
* `POST /api/v1/workspaces/{workspace_id}/members` – add a member.
* `DELETE /api/v1/workspaces/{workspace_id}/members/{membership_id}` – remove a member.
* `PUT /api/v1/workspaces/{workspace_id}/members/{membership_id}/roles` – replace roles for a member.

The **Settings → Members** and **Settings → Roles** tabs (see `06-workspace-layout-and-sections.md`) use these endpoints.

### 6.4 Permission helpers

To make permission checks uniform, we expose a small set of helpers in `shared/permissions`:

```ts
function hasPermission(
  permissions: EffectivePermissions,
  key: string,
  workspaceId?: string,
): boolean;

function hasAnyPermission(
  permissions: EffectivePermissions,
  keys: string[],
  workspaceId?: string,
): boolean;
```

Usage patterns:

* **Global actions** (creating workspaces, toggling safe mode):

  ```ts
  const canCreateWorkspace = hasPermission(perms, "Workspaces.Create");
  ```

* **Workspace actions** (editing members, running jobs):

  ```ts
  const canManageMembers = hasPermission(
    perms,
    "Workspace.Members.ReadWrite",
    workspaceId,
  );
  ```

These helpers are used in:

* **Nav construction**: decide which nav items to show.
* **Screens**: decide whether to show entire sections.
* **Buttons/forms**: decide whether to show actions and whether to disable them.

We avoid sprinkling raw permission key strings directly throughout screens. Instead:

* Expose small domain helpers when possible, e.g. `canEditWorkspaceMembers(perms, workspaceId)` that calls `hasPermission` under the hood.

---

## 7. Permission UX patterns

Permissions should be visible and predictable in the UI.

### 7.1 Hide vs disable

Guidelines:

* **Hide** actions a user should not know exist:

  * “Create workspace” for non‑admins.
  * “Manage global roles” section for non‑system admins.

* **Disable with explanation** when the user is aware of the concept but not allowed to perform it:

  * Safe mode toggle for non‑admins.
  * “Add member” button when user can see members but cannot edit.

Disable pattern:

* Use the `disabled` prop on buttons and show a tooltip:

  * “You don’t have permission to manage workspace members.”
  * “Safe mode can only be toggled by system administrators.”

### 7.2 Empty states and redirects

If a user navigates directly to a section without permissions:

* Either:

  * Redirect back to a safe default (e.g. Documents), and show a toast/banners explaining they don’t have access, or
  * Render a full‑page `Alert` stating “You do not have permission to access Workspace Settings”.

Which pattern to choose depends on the section:

* Settings → better to show a clear “no access” state.
* Hidden Admin sections → better to route them away.

### 7.3 Navigation and section availability

The **Workspace shell** (left nav) is built based on permissions:

* Only show **Settings** tab if the user has at least read access to any workspace settings.
* Only show **Config Builder** if they have read access to configurations.

If a permission change happens during a session (e.g. admin revokes roles), a refresh or a revalidation of the Session/permissions queries will update the UI accordingly.

---

## 8. Safe mode

Safe mode is a **global kill switch** that stops all engine execution.

From the frontend perspective it is:

* A shared piece of state (fetched via a dedicated query).
* A source of truth for disabling engine‑invoking actions.
* A banner that explains why things are blocked.

### 8.1 Backend contract

Endpoints:

* `GET /api/v1/system/safe-mode`:

  ```json
  {
    "enabled": true,
    "detail": "Maintenance window – engine temporarily paused."
  }
  ```

* `PUT /api/v1/system/safe-mode`:

  * Requires a permission such as `System.Settings.ReadWrite`.
  * Accepts an object with `enabled` and `detail`.

### 8.2 Safe mode query

`useSafeModeQuery()`:

* Calls `GET /api/v1/system/safe-mode`.

* Returns:

  ```ts
  interface SafeModeStatus {
    enabled: boolean;
    detail?: string | null;
  }
  ```

* Refetch strategy:

  * On app focus.
  * When certain stuck states are detected (optional).
  * Or at a modest interval if desired.

### 8.3 UI behaviour when safe mode is enabled

When `enabled === true`:

1. **Banner in workspace shell**

   * Renders below the `GlobalTopBar`.
   * Shows a succinct message, e.g.
     “Safe mode is enabled. New jobs, builds, validations, and activations are temporarily disabled.”
   * Includes the backend’s `detail` message verbatim.

2. **Disable engine‑invoking actions**
   Typical actions to disable:

   * Document‑level “Run extraction”.
   * Workspace Jobs “New job” actions (if any).
   * Config Builder:

     * “Build environment” button.
     * “Run validation” button.
     * “Run extraction” from workbench.
     * “Publish/activate” buttons.

   Disabled controls must:

   * Provide tooltips explaining:
     “Safe mode is enabled: <detail>”

3. **Read‑only behaviour remains**
   Safe mode **does not** block:

   * Viewing documents and jobs.
   * Viewing and downloading logs/outputs.
   * Editing configurations on disk (if backend allows this).
   * Navigating around the UI.

The UI must not silently ignore clicks; every disabled action should be obviously disabled and explain why.

### 8.4 Toggling safe mode

The **System / Settings** area (or equivalent) exposes a small management UI for safe mode:

* Visible only to users with appropriate permission.
* Shows current `enabled` state and `detail` message.
* Allows:

  * Toggle on/off.
  * Editing the detail message.

Flow:

1. User changes the toggle or edits the message.
2. Frontend calls `PUT /api/v1/system/safe-mode`.
3. On success:

   * Refetch `SafeModeStatus`.
   * Show a success toast (“Safe mode disabled” / “Safe mode enabled”).

On 403:

* Show an inline error `Alert` indicating insufficient permission.

---

## 9. Security considerations

### 9.1 Redirect handling

ADE Web uses a `redirectTo` query parameter for post‑login and post‑SSO redirects.

Rules:

* Only allow **same‑origin relative paths**, e.g.:

  * `redirectTo=/workspaces`
  * `redirectTo=/workspaces/123/documents?view=team`

* Reject or ignore:

  * Full URLs (`https://example.com/...`).
  * Protocol‑relative URLs (`//evil.com/...`).
  * Paths with suspicious components (`//`, `\`, etc.).

If `redirectTo` is absent or invalid:

* Fallback to the default route (directory or default workspace).

### 9.2 Storage and secrets

We never store:

* Passwords,
* Tokens,
* Session identifiers,

in localStorage or sessionStorage. Auth is handled via secure cookies and in‑memory state.

LocalStorage is used only for:

* UI preferences (workbench layout, theme),
* Per‑document run defaults,
* Per‑workspace nav collapse and return path.

See `10-ui-components-a11y-and-testing.md` for a full list of keys and patterns.

### 9.3 Workspace isolation

Even though permission enforcement happens server‑side, the frontend must:

* Never construct URLs for workspaces that the user cannot see (based on workspace list and permissions).
* Treat 403s on workspace endpoints explicitly and show a clear “Access denied” state.

This avoids confusing UX even when backend checks are strict.

---

## 10. Summary

* **Auth**: handled via `/auth/session` (email/password) and `/auth/sso/*` (SSO). Setup is a one‑time flow via `/setup`.
* **Session**: `useSessionQuery` is the single source of truth for “who am I”.
* **RBAC**: backend computes effective permissions; frontend calls `useEffectivePermissionsQuery` and uses small `hasPermission` helpers rather than re‑implementing policy.
* **UI gating**: nav, screens, and actions are all driven from the same permission set; we use consistent hide/disable patterns.
* **Safe mode**: read from `/system/safe-mode`, surfaced as a banner, and used to disable all engine‑invoking actions with clear explanations.
* **Security**: no secrets in localStorage, no open redirects, and clear handling of 401/403.

With this structure in place, auth, session, RBAC, and safe mode should be easy to understand for both developers and AI agents, and straightforward to extend as ADE grows.
