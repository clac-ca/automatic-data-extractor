# 05-auth-session-rbac-and-safe-mode

**Purpose:** All auth, identity, permissions, and safe mode behaviour in one place.

### 1. Overview

* Relationship to backend auth system.
* High-level flow: setup → login → workspace selection.

### 2. Initial setup flow

* `/api/v1/setup/status`, `/api/v1/setup`:

  * When we show the first-run setup screen.
  * Only first admin can complete it.

### 3. Authentication flows

* **Email/password**

  * `/api/v1/auth/session` POST/DELETE/refresh.
  * How login form works, where errors are shown.

* **SSO**

  * `/api/v1/auth/sso/login` and `/auth/sso/callback`.
  * “Choose provider” screen if multiple providers exist.

* **Redirects**

  * Use of `redirectTo` query param.
  * Validation rules (no external redirect).

### 4. Session & identity

* Canonical “who am I?” endpoint(s):

  * `/api/v1/auth/session` and/or `/users/me`.

* What the session data contains:

  * User id, name, email.
  * Global permissions.
  * Possibly workspace memberships with roles.

* Where session is cached:

  * In React Query as a `session` query.
  * Short-term in memory; no long-term storage of tokens in localStorage.

### 5. Roles & permissions model

* **Global roles & assignments**

  * `/roles`, `/role-assignments`.
  * Used for system-wide capabilities (like listing all users).

* **Workspace roles & assignments**

  * `/workspaces/{workspace_id}/roles`.
  * `/workspaces/{workspace_id}/role-assignments`.
  * Membership list and role editing in Settings.

* **Permissions**

  * Catalog (`/permissions`) and effective permissions (`/me/permissions`).
  * Permission key naming convention (e.g. `Workspace.Members.ReadWrite`, `Workspaces.Create`).

### 6. Permission checks in the UI

* Helpers in `shared/permissions`:

  * `hasPermission(permissions, key)`.
  * `hasAnyPermission(permissions, keys)`.

* Guidelines:

  * Hide vs disable:

    * Hide controls for actions the user should not be aware of.
    * Disable with tooltip for actions the user *knows* exist but cannot use (e.g. safe mode toggle).

* Examples:

  * Create workspace button.
  * Settings tabs.
  * Config activate/deactivate buttons.

### 7. Safe mode behaviour

* Reading `/api/v1/system/safe-mode`:

  * Polling or refetch triggers.

* Exactly what is blocked:

  * New jobs/runs.
  * Config builds/validations.
  * Activate/publish actions.

* UI treatment:

  * Global banner inside workspace shell.
  * Disabled buttons with informative tooltips (“Safe mode is enabled: <message>”).

* Permissions:

  * Which permission is required to toggle safe mode.
  * How the Safe mode controls are shown only to authorised users.

### 8. Security considerations

* CSRF/credentials model:

  * E.g. cookie-based sessions with `sameSite` and CSRF token if applicable.

* CORS:

  * Mention reliance on Vite `/api` proxy in dev.

* Sensitive data:

  * Never store secrets or tokens in localStorage.
  * State persistence keys only hold preferences.
