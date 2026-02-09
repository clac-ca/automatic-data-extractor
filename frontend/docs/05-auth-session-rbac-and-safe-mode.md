# 05 – Auth, Session, RBAC, and Safe Mode

ADE Web relies on the backend for:

- **Authentication** (setup, login, logout, SSO),
- The current **session** (who is the signed‑in user),
- **Roles & permissions** (RBAC),
- A global **Safe mode** kill switch that blocks new runs.

This document describes how the frontend models these concepts and how they are used to shape the UI.

For domain terminology (Workspace, Document, Run, Configuration, etc.), see  
[`01-domain-model-and-naming.md`](./01-domain-model-and-naming.md).

---

## 1. Goals and scope

**Goals**

- One clear, consistent mental model for auth, session, RBAC, and Safe mode.
- Make it obvious where to fetch identity and permissions, and how to check them.
- Ensure Safe mode behaviour is consistent everywhere runs can be started.
- Keep the frontend thin: permission decisions are made on the backend; the UI only consumes them.

**Non‑goals**

- Describing the backend’s full auth/RBAC implementation.
- Enumerating every possible permission key.

Only frontend‑relevant behaviour and contracts are covered here.

---

## 2. Core frontend models

### 2.1 Session (who is signed in)

The **Session** describes the current principal (signed‑in user) and their high‑level context. It mirrors the backend’s `MeContext` shape returned by `GET /api/v1/me/bootstrap`:

```ts
export type SessionEnvelope = {
  user: {
    id: string;
    email: string;
    display_name: string | null;
    is_service_account: boolean;
    created_at: string;
    updated_at: string | null;
    roles: string[];        // global role slugs
    permissions: string[];  // global permission keys
    preferred_workspace_id: string | null;
  };
  workspaces: WorkspaceMembershipSummary[];
  roles: string[];
  permissions: string[];
  return_to: string | null;
};

export interface WorkspaceMembershipSummary {
  readonly id: string;
  readonly name: string;
  readonly slug: string | null;
  readonly is_default: boolean;
  readonly joined_at: string | null;
}
```

Characteristics:

* Fetched via `GET /api/v1/me/bootstrap` using the session cookie.
* Normalised in `shared/auth/api.ts` from the generated OpenAPI types.
* Cached with React Query.
* Treated as the **single source of truth** for “who am I?”; we do not duplicate user identity elsewhere.
* Sessions are cookie-only; no access tokens are persisted in `localStorage`.
* Default workspace is server‑backed (`is_default` on memberships) and set via `PUT /api/v1/workspaces/{workspaceId}/default`.

### 2.2 Effective permissions

The frontend does not recompute permission graphs. Instead it consumes a pre‑computed set of permission keys from the backend.

```ts
export interface EffectivePermissions {
  /** Global permissions that apply regardless of workspace. */
  readonly global: readonly string[];

  /** Optional: per‑workspace permission keys. */
  readonly workspaces?: Record<string, readonly string[]>;
}
```

This is fetched via:

* `GET /api/v1/me/permissions`, optionally accompanied by:
* `POST /api/v1/me/permissions/check` for specific “does the caller have X?” questions.

Permissions are **string keys** like:

* `Workspaces.Create`
* `Workspace.Runs.Read`
* `Workspace.Runs.Run`
* `Workspace.Settings.ReadWrite`
* `System.SafeMode.Read`
* `System.SafeMode.ReadWrite`

The exact catalog is backend‑defined and discoverable via `GET /api/v1/permissions` for settings UIs.

### 2.3 Safe mode status

Safe mode is represented as:

```ts
export interface SafeModeStatus {
  readonly enabled: boolean;
  readonly detail: string | null;  // human-readable explanation
}
```

* Fetched from `GET /api/v1/system/safeMode`.
* Cached via React Query with a moderate `staleTime`.
* Drives:

  * A persistent banner inside the workspace shell.
* Disabling all **run‑invoking** actions (starting new runs, validations, activations that trigger runs).
* Status is **system‑wide**; the toggle lives on a system‑level Settings screen that only appears for users with `System.SafeMode.*`.

### 2.4 Default workspace selection

**What drives defaults**

- One membership per user may be flagged `is_default` by the backend.
- The SPA consumes that flag from `GET /api/v1/me/bootstrap` and from workspace listings.
- We keep a lightweight local hint (`backend.app.active_workspace`), but the server default always wins when present.

**How the UI sets it**

- The Workspace directory shows “Set as default” on non‑default cards.
- That action calls `PUT /api/v1/workspaces/{workspaceId}/default` via a typed helper, then updates cached workspace data and the local hint.
- The endpoint is **idempotent**—repeated calls keep the same default.

**Redirect behaviour**

- After auth, the root route prefers the server default; otherwise it falls back to the first accessible workspace, then `/workspaces` if none exist.

---

## 3. Initial setup and authentication flows

### 3.1 First‑run setup

On first deployment, ADE may require a “first admin” to be created.

The entry strategy:

1. Call `GET /api/v1/auth/setup`.
2. If `setup_required == true`:

   * Navigate to `/setup`.
   * Render the first‑admin setup screen.
3. Otherwise:

   * Proceed to normal login/session checks.

The setup screen:

* Collects the first admin’s information (e.g. name, email, password).
* Calls `POST /api/v1/auth/setup` to create the user and initial session.
* On success, redirects to:

  * The workspace directory (`/workspaces`), or
  * A validated `returnTo` path, if present.

Setup endpoints are public but should be callable only while `setup_required == true`. After setup, this flag becomes false and the `/setup` path should redirect to `/login` or `/workspaces`.

### 3.2 Email/password login

Email/password authentication uses:

* `POST /api/v1/auth/cookie/login` – create a session cookie (public).
* `POST /api/v1/auth/cookie/logout` – terminate the current session (authenticated).
* `POST /api/v1/auth/jwt/login` – issue a bearer token (non-browser clients).

Flow:

1. On `/login`, render the login form.
2. On submit:

   * Call `createSession({ email, password })` (cookie login + bootstrap).
   * On success:

     * Invalidate and refetch the `session` and `effectivePermissions` queries.
     * Redirect to `returnTo` (if safe) or to the default route.
3. On invalid credentials:

   * Show an inline form error.
4. On other errors:

   * Show a generic error and keep the user on `/login`.

Logout:

* Initiated via “Sign out” in the profile menu.
* Calls `POST /api/v1/auth/cookie/logout`.
* Clears the React Query cache and navigates to `/login`.

### 3.3 SSO login

When SSO is enabled, providers are listed via:

* `GET /api/v1/auth/sso/providers`.
* Public auth endpoints (`/auth/providers`, `/auth/sso/providers`, `/auth/setup`, `/auth/cookie/login`, `/auth/jwt/login`, and the SSO redirects) are the only unauthenticated surface area; everything else requires a session cookie, bearer token, or API key.

SSO flow:

1. `/login` renders buttons for each provider.
2. Clicking a provider navigates to `GET /api/v1/auth/sso/{providerId}/authorize?returnTo=<path>`:

   * Backend responds with a redirect to the IdP.
3. After IdP authentication, the user is redirected to `GET /api/v1/auth/sso/{providerId}/callback`.
4. Backend verifies the callback, establishes a session, and redirects directly to the sanitized `returnTo` path.

### 3.4 Redirect handling

`returnTo` is used to send the user back to where they were going, for example:

* After login,
* After SSO callback,
* After first‑run setup.

Redirect safety rules:

* Accept only **relative paths** beginning with `/`, e.g. `/workspaces/123/runs`.
* Reject absolute URLs, protocol-relative URLs (`//...`), or paths with control characters.

We centralize this logic in a helper, e.g.:

```ts
function resolveRedirectParam(raw?: string | null): string;
```

If validation fails or `returnTo` is omitted:

* Fallback to `/` (the app home screen handles workspace routing).

---

## 4. Session lifecycle and caching

### 4.1 Fetching the session

On app startup and after any login/logout, ADE Web fetches the session:

* `GET /api/v1/me/bootstrap` (canonical “who am I?” + roles/permissions/workspaces).

`useSessionQuery()`:

* Wraps the React Query call.
* Treats `401` as “no active session”; `403` is propagated so screens can render a permissions experience (see §4.4).

Behaviour:

* If the user navigates to an authenticated route and `useSessionQuery()` resolves as unauthenticated:

  * Redirect them to `/login` with an optional `returnTo` back to the original path.

### 4.2 Session expiry

ADE uses cookie sessions without refresh tokens. When a session expires, the frontend treats the user as signed out and redirects to `/login` after the next bootstrap attempt.

### 4.3 Global vs workspace‑local data

We intentionally separate:

* **Global identity & permissions** (from `Session` and `EffectivePermissions`),
* **Workspace‑local context** (from workspace endpoints).

Workspace context comes from:

* `GET /api/v1/workspaces/{workspaceId}` – workspace metadata and membership summary.
* `GET /api/v1/workspaces/{workspaceId}/members` – detailed list of members and roles.
* `GET /api/v1/roles` – role definitions (filter by scope as needed).

The UI uses:

* Session + membership summaries for top‑level decisions (what workspaces to show).
* Workspace‑specific endpoints for detailed management screens.

### 4.4 HTTP status semantics

Frontends treat auth‑related status codes consistently:

* `401` → **not logged in**. Redirect to `/login` (preserving a safe `returnTo` where appropriate).
* `403` → **logged in but not allowed**. Keep the user on the current screen and surface a permissions experience (hide or disable actions with explanatory copy).

---

## 5. RBAC model and permission checks

### 5.1 Permission keys

Permissions are represented as strings and follow a descriptive pattern:

* `<Scope>.<Area>.<Action>`

Examples:

* `Workspaces.Create`
* `Workspace.Runs.Read` – view runs in a workspace.
* `Workspace.Runs.Run` – start new runs.
* `Workspace.Settings.Read`
* `Workspace.Settings.ReadWrite`
* `Workspace.Members.Read`
* `Workspace.Members.ReadWrite`
* `System.SafeMode.Read`
* `System.SafeMode.ReadWrite`

The full catalog is provided by `GET /api/v1/permissions` and is primarily used by the Roles/Permissions UIs.

### 5.2 Global and workspace roles

Roles are defined and assigned via the API; the frontend treats them as named bundles of permissions.

**Global roles**

* Endpoints:

  * `GET /api/v1/roles`
  * `POST /api/v1/roles`
  * `GET /api/v1/roles/{roleId}`
  * `PATCH /api/v1/roles/{roleId}`
  * `DELETE /api/v1/roles/{roleId}`

* Assignments:

  * `GET /api/v1/roleassignments`
  * `POST /api/v1/roleassignments`
  * `DELETE /api/v1/roleassignments/{assignmentId}`
  * `GET /api/v1/users/{userId}/roles`
  * `PUT /api/v1/users/{userId}/roles/{roleId}`
  * `DELETE /api/v1/users/{userId}/roles/{roleId}`

* Membership:

  * `GET /api/v1/workspaces/{workspaceId}/members`
  * `POST /api/v1/workspaces/{workspaceId}/members`
  * `PUT /api/v1/workspaces/{workspaceId}/members/{userId}`
  * `DELETE /api/v1/workspaces/{workspaceId}/members/{userId}`

The **Roles** and **Members** panels in Settings are thin UIs over these endpoints. The core run/document/configuration flows should not depend on the specifics of role assignment; they only consume effective permission keys.

### 5.3 Effective permissions query

We expose a dedicated query for permissions:

```ts
function useEffectivePermissionsQuery(): {
  data?: EffectivePermissions;
  isLoading: boolean;
  error?: unknown;
}
```

Implementation:

* Calls `GET /api/v1/me/permissions`.
* Returns at least:

  ```ts
  {
    global: string[];
    workspaces?: Record<string, string[]>;
  }
  ```

In many cases the global set is sufficient:

* Global actions like creating workspaces or toggling Safe mode are gated by global permissions.
* Workspace actions can either use `workspaces[workspaceId]` or derive workspace permissions from membership if the backend does not include them in `/me/permissions`.

### 5.4 Permission helpers and usage

Helpers in `shared/permissions` make checks uniform:

```ts
export function hasPermission(
  permissions: readonly string[] | undefined,
  key: string,
): boolean {
  return !!permissions?.includes(key);
}

export function hasAnyPermission(
  permissions: readonly string[] | undefined,
  keys: readonly string[],
): boolean {
  return !!permissions && keys.some((k) => permissions.includes(k));
}
```

Workspace helpers:

```ts
export function useWorkspacePermissions(workspaceId: string) {
  const { data: effective } = useEffectivePermissionsQuery();
  const workspacePerms =
    effective?.workspaces?.[workspaceId] ?? ([] as string[]);

  return { permissions: workspacePerms };
}

export function useCanInWorkspace(workspaceId: string, permission: string) {
  const { permissions } = useWorkspacePermissions(workspaceId);
  return hasPermission(permissions, permission);
}
```

Wrap raw permission keys in **domain helpers** to keep feature code declarative:

```ts
export function useCanStartRuns(workspaceId: string) {
  return useCanInWorkspace(workspaceId, "Workspace.Runs.Run");
}

export function useCanManageConfigurations(workspaceId: string) {
  return useCanInWorkspace(workspaceId, "Workspace.Configurations.ReadWrite");
}
```

Typical usage:

* **Navigation construction**

  ```ts
  const canSeeSettings = useCanInWorkspace(workspaceId, "Workspace.Settings.Read");

  const items = [
    { id: "runs", path: "/runs", visible: true },
    { id: "settings", path: "/settings", visible: canSeeSettings },
  ].filter((item) => item.visible);
  ```

* **Action buttons**

  ```tsx
  const canStartRuns = useCanInWorkspace(workspaceId, "Workspace.Runs.Run");

  <Button
    onClick={onStartRun}
    disabled={!canStartRuns || safeModeEnabled}
    title={
      !canStartRuns
        ? "You don't have permission to start runs in this workspace."
        : safeModeEnabled
        ? `Safe mode is enabled: ${safeModeDetail ?? ""}`
        : undefined
    }
  >
    Run
  </Button>;
  ```

### 5.5 Hide vs disable

We use a simple policy:

* **Hide** features that the user should not know exist:

  * Global Admin screens,
  * “Create workspace” action, if they lack `Workspaces.Create`.

* **Disable with explanation** for features the user understands conceptually but cannot execute *right now*:

  * Run buttons for users who can see runs but lack `Workspace.Runs.Run`.
  * Safe mode toggle for users with read but not write access.

Disabled actions should always have a tooltip explaining **why**:

* “You don’t have permission to start runs in this workspace.”
* “Only system administrators can toggle Safe mode.”

---

## 6. Safe mode

Safe mode is a system‑wide switch that stops new engine work from executing (workspace overrides are optional). ADE Web must:

* Reflect its current status to the user.
* Proactively block all run‑invoking actions at the UI layer.

### 6.1 Backend contract

Endpoints:

* `GET /api/v1/system/safeMode`:

  ```json
  {
    "enabled": true,
    "detail": "Maintenance window – new runs are temporarily disabled."
  }
  ```

* `PUT /api/v1/system/safeMode`:

  * Permission‑gated (e.g. requires `System.SafeMode.ReadWrite`).
  * Accepts:

    ```json
    {
      "enabled": true,
      "detail": "Reasonable, user-facing explanation."
    }
    ```

### 6.2 Safe mode hook

Frontend exposes:

```ts
function useSafeModeStatus(): {
  data?: SafeModeStatus;
  isLoading: boolean;
  error?: unknown;
  refetch: () => void;
}
```

Implementation details:

* Wraps `GET /api/v1/system/safeMode` in a React Query query.
* Uses a `staleTime` on the order of tens of seconds (exact value configurable).
* Allows manual refetch (e.g. after toggling Safe mode).

### 6.3 What Safe mode blocks

When Safe mode is enabled (`enabled === true`), ADE Web must block **starting new runs** and any other action that causes the engine to execute.

Examples:

* Starting a new run from:

  * The Documents screen (“Run extraction”),
  * The Runs ledger (“New run”, if present),
  * The Configuration Builder workbench (“Run extraction” within the editor).

* Starting **validate‑only** runs (validation of configurations or manifests).

* Activating/publishing configurations if that triggers background engine work.

UI behaviour:

* All such controls must:

  * Be disabled (not clickable),
  * Show a tooltip like:

    > “Disabled while Safe mode is enabled: Maintenance window – new runs are temporarily disabled.”

The backend may still reject blocked operations; the UI’s run is to make the state obvious and avoid a confusing “click → no‑op” experience.

### 6.4 Safe mode banner

When Safe mode is on:

* Render a **persistent banner** inside the workspace shell:

  * Located just below the global top bar, above section content.
  * Present in all workspace sections (Runs, Documents, Configuration Builder, Settings, etc.).

* Recommended copy:

  ```text
  Safe mode is enabled. New runs and validations are temporarily disabled.
  ```

* If `detail` is provided by the backend, append or incorporate it:

  ```text
  Safe mode is enabled: Maintenance window – new runs are temporarily disabled.
  ```

The banner should be informational only; it does not itself contain primary actions.

### 6.5 Toggling Safe mode

Toggling Safe mode is an administrative action performed on a **system‑level Settings screen** (not per‑workspace). The screen is visible only to users with `System.SafeMode.Read`/`System.SafeMode.ReadWrite`.

UI pattern:

* Show current state (`enabled` / `disabled`) and editable `detail` field.

* Require:

  * `System.SafeMode.Read` to view current status.
  * `System.SafeMode.ReadWrite` to change it.

* The toggle workflow:

  1. User edits the switch and/or message.
  2. UI calls `PUT /api/v1/system/safeMode`.
  3. On success:

     * Refetch Safe mode status.
     * Show a success toast (“Safe mode enabled”/“Safe mode disabled”).
  4. On 403:

     * Show an inline error `Alert` (“You do not have permission to change Safe mode.”).

---

## 7. Security considerations

### 7.1 Redirect safety

Any time `returnTo` is used (login, SSO, setup), we must:

* Accept only relative URLs (starting with `/`).
* Reject:

  * Absolute URLs (`https://…`),
  * Protocol‑relative URLs (`//…`),
  * `javascript:` or similar schemes.

Safe logic belongs in a single helper (`resolveRedirectParam`) that is used by:

* The login flow.
* The SSO callback screen.
* The setup screen.

If `returnTo` is unsafe or missing:

* Redirect to `/` (the app home screen handles workspace routing).

### 7.2 Storage safety

We **never** store:

* Passwords,
* Raw session objects outside the auth helper,

in `localStorage` or `sessionStorage`.

We **do** store:

* UI preferences such as:

  * Left nav collapsed/expanded,
  * Workbench layout,
  * Editor theme,
  * Per‑document run defaults,

under namespaced keys like:

* `ade.ui.workspace.<workspaceId>.nav.collapsed`
* `ade.ui.workspace.<workspaceId>.configuration.<configurationId>.console`
* `ade.ui.workspace.<workspaceId>.document.<documentId>.run-preferences`

All such values are:

* Non‑sensitive,
* Safe to clear at any time,
* Derived from information already visible in URLs or UI.

See `10-ui-components-a11y-and-testing.md` for the full list of persisted preferences.

### 7.3 CSRF and CORS

CSRF and CORS are primarily backend concerns, but ADE Web should:

* Use `credentials: "include"` when the backend uses cookie‑based auth.
* Use the Vite dev server’s `/api` proxy in development to avoid CORS headaches locally.
* Avoid manually setting auth headers unless explicitly required by the backend design.

Cookies should be configured with appropriate `Secure` and `SameSite` attributes; this is out of scope for the frontend but the assumptions should be documented in backend configuration.

---

## 8. Checklist for new features

When adding a feature that touches auth, permissions, or runs:

1. **Define the permission(s)**

   * Which permission key(s) gate the feature?
   * Are they global (`Workspaces.Create`) or workspace‑scoped (`Workspace.Runs.Run`)?

2. **Wire into helpers**

   * Use `hasPermission` / `useCanInWorkspace` instead of checking raw strings in multiple places.
   * Prefer a small domain helper (e.g. `canStartRuns(workspaceId)`).

3. **Respect Safe mode**

  * If the feature starts or schedules new runs, disable it when `SafeModeStatus.enabled === true`.
  * Add an explanatory tooltip mentioning Safe mode.

4. **Handle unauthenticated users**

   * Do not assume `useSessionQuery().data` is always present.
   * Redirect to `/login` when required.

5. **Avoid leaking information**

   * Hide admin‑only sections entirely if the user lacks the relevant read permissions.
   * Disable rather than hide when the existence of the feature is already obvious from the context.

With these patterns, auth, RBAC, and Safe mode remain predictable and easy to extend as ADE evolves.
