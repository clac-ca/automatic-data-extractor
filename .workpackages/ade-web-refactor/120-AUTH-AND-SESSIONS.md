# 120-AUTH-AND-SESSIONS.md  
**ADE Web – Auth, Sessions, and SSO Handling**

---

## 0. Purpose

This document defines how the **ade-web** frontend should handle:

- Authentication (password + SSO).
- Session lifecycle (login, refresh, logout).
- Initial setup (first admin).
- Bootstrap and permissions loading.
- Integration with the backend FastAPI routes and **OpenAPI-generated types**.

It is based on the OpenAPI definitions in:

- `apps/ade-web/src/generated-types/openapi.d.ts`

and the auth-related routes in the backend:

- `/api/v1/setup`, `/api/v1/setup/status`
- `/api/v1/bootstrap`
- `/api/v1/auth/session`, `/api/v1/auth/session/refresh`
- `/api/v1/auth/providers`
- `/api/v1/me`
- `/api/v1/auth/sso/login`, `/api/v1/auth/sso/callback`
- `/api/v1/auth/api-keys`
- `/api/v1/me/permissions`, `/api/v1/me/permissions/check`
- plus related schemas:
  - `SetupStatus`, `SetupRequest`
  - `ProviderDiscoveryResponse`, `AuthProvider`
  - `LoginRequest`, `SessionEnvelope`
  - `UserProfile`, `BootstrapEnvelope`, `SafeModeStatus`

---

## 1. Backend Auth Model (From OpenAPI)

### 1.1 Session & Login

**Password login**

- `POST /api/v1/auth/session`
  - Request body: `components["schemas"]["LoginRequest"]`
    - `email: unknown` (string-ish; treat as string in UI)
    - `password: string` (format: password)
  - Response on success: `components["schemas"]["SessionEnvelope"]`
    - `user: UserProfile`
    - `expires_at?: string | null`
    - `refresh_expires_at?: string | null`
    - `return_to?: string | null`
  - Side effects:
    - Backend sets session cookies (access + refresh) – **we should not store tokens ourselves**.

**Read active session**

- `GET /api/v1/auth/session`
  - Response: `SessionEnvelope`
  - 401 if not authenticated.

**Refresh session**

- `POST /api/v1/auth/session/refresh`
  - No body.
  - Response: `SessionEnvelope`
  - Uses refresh cookie to rotate session cookies.

**Logout**

- `DELETE /api/v1/auth/session`
  - Terminates active session; clears auth cookies.

### 1.2 Bootstrap

- `GET /api/v1/bootstrap`
  - Response: `components["schemas"]["BootstrapEnvelope"]`:
    - `user: UserProfile`
    - `global_roles: string[]`
    - `global_permissions: string[]`
    - `workspaces: WorkspacePage`
    - `safe_mode: SafeModeStatus`
- Used for **one-shot SPA bootstrap** once we have a valid session.

### 1.3 Setup (First Admin)

- `GET /api/v1/setup/status`
  - Response: `SetupStatus`:
    - `requires_setup: boolean`
    - `completed_at?: string | null`
    - `force_sso: boolean` (if true, initial setup must go through SSO).

- `POST /api/v1/setup`
  - Request: `SetupRequest`:
    - `email`
    - `password`
    - `display_name?`
  - Response: `SetupStatus`

### 1.4 Provider Discovery & SSO

- `GET /api/v1/auth/providers`
  - Response: `ProviderDiscoveryResponse`:
    - `providers: AuthProvider[]`
    - `force_sso: boolean`

- `AuthProvider` schema:
  - `id: string`
  - `label: string` (e.g., “Google”, “Okta”)
  - `start_url: string` (where to send the browser to initiate login)
  - `icon_url?: string | null`

- SSO endpoints:
  - `GET /api/v1/auth/sso/login`
    - “Initiate the SSO login flow.”
    - In practice, we’ll redirect the browser to `provider.start_url` from `/auth/providers`.
  - `GET /api/v1/auth/sso/callback`
    - Handles callback and establishes session cookies.

### 1.5 User & Permissions

- `GET /api/v1/me`
  - Response: `UserProfile`:
    - `id`, `email`, `is_active`, `is_service_account`
    - `display_name?`
    - `preferred_workspace_id?`
    - `roles?: string[]`
    - `permissions?: string[]`

- `GET /api/v1/me/permissions`
  - Returns effective permission set.

- `POST /api/v1/me/permissions/check`
  - Batch permission check.

> For most UI gating, we can rely on:
> - `BootstrapEnvelope.global_permissions` (for global scope).
> - `UserProfile.permissions` if populated.
> - Workspace-specific role/permission endpoints for advanced UI (see `110-BACKEND-API.md`).

---

## 2. Auth State Model (Frontend)

We model auth in a small state machine inside an `AuthProvider` (React context), plus a bootstrap step.

### 2.1 States

Suggested `AuthState`:

- `unknown` – app just loaded, no checks performed yet.
- `setup-required` – platform has no admin yet; show setup wizard.
- `unauthenticated` – login required (show login screen).
- `authenticating` – currently performing login/refresh.
- `authenticated` – session established, `BootstrapEnvelope` loaded.
- `error` – irrecoverable auth error (e.g. misconfigured backend).

### 2.2 Transitions

1. **App start**  
   - → `unknown`
   - Call `GET /api/v1/setup/status`:
     - If `requires_setup == true` → `setup-required`
     - Else → call `GET /api/v1/auth/session`
       - 200 → `authenticated?` (with minimal info) → then `GET /api/v1/bootstrap` → `authenticated`
       - 401 → `unauthenticated`

2. **Setup flow** (first admin):
   - From `setup-required`:
     - User submits setup form → `POST /api/v1/setup` (SetupRequest).
     - If success → treat as:`requires_setup=false` now.
     - Then:
       - Either treat user as logged-in (if backend does that), or
       - Redirect to login flow (`unauthenticated`).

3. **Login (password)**:
   - From `unauthenticated`:
     - `auth.loginWithPassword(credentials)` → `POST /auth/session`.
     - On 200:
       - Update local state with `SessionEnvelope.user`.
       - Call `GET /api/v1/bootstrap`.
       - → `authenticated`.

4. **Login (SSO)**:
   - From `unauthenticated`:
     - `GET /auth/providers` → build login options.
     - If `force_sso == true`, hide password UI.
     - User clicks provider:
       - Redirect browser to `AuthProvider.start_url`.
       - Backend handles `/auth/sso/callback` & sets cookies.
       - Post-SSO return:
         - We re-run the bootstrap path (read session → bootstrap) → `authenticated`.

5. **Refresh**:
   - From `authenticated`:
     - `POST /auth/session/refresh` (optional periodic or on 401 handling).
     - On 200: update `SessionEnvelope` timestamps; remain `authenticated`.
     - On 401/403: treat as logout → `unauthenticated`.

6. **Logout**:
   - From `authenticated`:
     - `DELETE /auth/session`
     - Clear cached user/bootstrap state.
     - → `unauthenticated`.

---

## 3. Bootstrapping Strategy

We want a **single, canonical boot flow** in `AuthProvider`:

1. **Check setup status**  
   `GET /api/v1/setup/status → SetupStatus`
   - If `requires_setup == true`:
     - Set `authState = "setup-required"`.
     - Render Setup screen; nothing else loads.
   - Else:
     - Continue.

2. **Check session**  
   `GET /api/v1/auth/session → SessionEnvelope`
   - 200 → we have a session (user + expiry); continue.
   - 401 → `authState = "unauthenticated"`; show login.

3. **Bootstrap**  
   `GET /api/v1/bootstrap → BootstrapEnvelope`
   - Store:
     - `user: UserProfile`
     - `global_roles`
     - `global_permissions`
     - `workspaces`
     - `safe_mode`
   - Initialize:
     - `CurrentWorkspaceContext` using `preferred_workspace_id` or first workspace.
   - Set `authState = "authenticated"`.

4. **Handle `auth_disabled` (dev)**  
   - If backend is running with auth disabled (as indicated by logs / safe environment), `GET /bootstrap` may succeed without a session.
   - We don’t need special UI logic; we just treat the returned user as “dev user”.
   - Optional: show subtle banner “Auth disabled (dev mode)”.

> **Implementation note:**  
> `AppShell` should render a small auth gate:  
> - If `authState === "unknown"` → show splash/loading.  
> - If `setup-required` → show Setup.  
> - If `unauthenticated` → show Login.  
> - If `authenticated` → render the main app.

---

## 4. Login Flows & UI

### 4.1 Provider Discovery & Login Screen Layout

Login screen should:

1. Call `GET /api/v1/auth/providers` to get:
   - `ProviderDiscoveryResponse.providers: AuthProvider[]`
   - `ProviderDiscoveryResponse.force_sso: boolean`

2. Based on this + `SetupStatus.force_sso`:

   - If either `force_sso` flag is true:
     - **Hide** password login UI.
     - Show only SSO options (buttons per `AuthProvider`).
   - Otherwise:
     - Show:
       - Email/password form.
       - SSO buttons (if any providers).

**Use of `AuthProvider`:**

- Display `label` and optionally `icon_url` on button:
  - “Continue with Google”
  - “Continue with Okta”
- On click:
  - `window.location.href = provider.start_url`
  - Don’t attempt to fetch via XHR – this is a full redirect.

### 4.2 Password Login Flow

1. User fills email + password.
2. UI calls `POST /api/v1/auth/session` with `LoginRequest`.
3. On success:
   - Backend sets session cookies.
   - Response: `SessionEnvelope` with `user` and expiry info.
   - Optionally use `SessionEnvelope.return_to`:
     - If provided, we can navigate there after bootstrap.
4. After session creation:
   - Call `GET /api/v1/bootstrap`.
   - Transition to `authenticated` state.

### 4.3 Error Handling

- 401 → show “Invalid email or password.”
- 429 → show “Too many attempts, please wait and try again.”
- 500 → generic backend issue.

All errors should be displayed using the design system (e.g., `Alert` or inline error text under the form).

---

## 5. Session Refresh & Lifetime

### 5.1 Strategy

We **do not** manage raw tokens in the frontend. We rely on:

- HttpOnly session cookies set by the backend.
- `POST /auth/session/refresh` to rotate sessions when needed.

Possible strategies:

1. **Lazy refresh (simple, recommended initially)**

   - On 401 from a protected API call:
     - Try `POST /auth/session/refresh`.
       - If success: retry original request once.
       - If 401/403 again: treat as logout; `authState = "unauthenticated"`.

2. **Proactive refresh (optional optimization)**

   - Use `SessionEnvelope.expires_at` / `refresh_expires_at` from:
     - `GET /auth/session`
     - `POST /auth/session`
     - `POST /auth/session/refresh`
   - Keep these timestamps in `AuthContext`.
   - Periodically (e.g., every N minutes) check:
     - If `now` is close to `expires_at`, call refresh.
   - If refresh fails, drop to `unauthenticated`.

Initially, we can implement **lazy refresh** only; proactive is a future improvement.

### 5.2 Impact on React Query

- API client should be configured such that:
  - For each request:
    - If it receives 401:
      - Run the lazy refresh logic.
      - If refresh succeeds, retry.
      - If not, clear queries and go to login.
- This can be implemented via:
  - A fetch wrapper that raises custom “UnauthenticatedError”.
  - A global `onError` handler in React Query that calls auth refresh logic.

---

## 6. Logout Flow

1. User clicks “Logout”.
2. UI calls `DELETE /api/v1/auth/session`.
3. On success (or even on any response, conservatively):
   - Clear:
     - `AuthContext` user, permissions, bootstrap data.
     - Any workspace-specific context.
   - Reset React Query caches (or at least auth-sensitive queries).
   - Navigate to login screen (`authState = "unauthenticated"`).

We should also consider:

- CSRF handling (backend may use CSRF cookies/headers; our API client should attach CSRF header if required).
- 403 on logout due to CSRF failure (rare; we can still clear local state).

---

## 7. Setup & Force SSO

### 7.1 Setup Status-Driven UX

Use `GET /api/v1/setup/status → SetupStatus` to drive:

- If `requires_setup === true`:
  - Render **Setup screen** (first admin creation) instead of login.
  - Setup form uses:
    - `POST /api/v1/setup` with `SetupRequest`.
  - On success:
    - Setup is complete; we can either:
      - Immediately treat the admin as authenticated (if backend does that), or
      - Redirect admin to login screen and go through the normal flow.

### 7.2 `force_sso` when Setup is required

- `SetupStatus.force_sso` indicates initial admin must go through SSO (no password).
- In this case:
  - Setup screen may:
    - Show SSO-only onboarding (“Sign in with your IdP to become the first admin”).
    - Use `/auth/providers` + SSO flow.

### 7.3 `force_sso` when Setup is complete

There are two `force_sso` sources:

- `SetupStatus.force_sso` (initial setup stance).
- `ProviderDiscoveryResponse.force_sso` (login-time stance).

We should treat `ProviderDiscoveryResponse.force_sso` as the **live truth** when rendering login, but setup’s `force_sso` gives hints for the first run.

---

## 8. API Keys & Service Accounts (Future UI)

The OpenAPI shows:

- `GET /api/v1/auth/api-keys` (with query params like `include_revoked`, `page`, `page_size`)
- `POST /api/v1/auth/api-keys` (issue new API key)
- `DELETE /api/v1/auth/api-keys/{api_key_id}` (revoke)

These are useful for:

- CLI integrations
- Service accounts

For this workpackage, we can:

- Implement `authApi.listApiKeys()`, `createApiKey()`, `revokeApiKey()` behind the scenes.
- Defer a full API key management UI to a separate admin workpackage.

Front-end auth/session flows **do not** depend on API keys.

---

## 9. Permissions & Guards

### 9.1 Where to Get Permissions

Sources:

- `BootstrapEnvelope.global_permissions: string[]`
- `UserProfile.permissions?: string[]`
- `/api/v1/me/permissions` (effective permission set)
- Workspace-level roles via other endpoints (see `110-BACKEND-API.md`)

For v1:

- Start with **global permissions** from `BootstrapEnvelope` and **workspace roles** only where absolutely needed.
- Optionally call `/me/permissions` to get a checked, up-to-date permission set if we need more nuance.

### 9.2 Guarding UI

Approach:

- `AuthContext` exposes:
  - `user: UserProfile | null`
  - `permissions: string[]`
  - Small helper:
    - `hasPermission(perm: string): boolean`
    - `hasAnyPermission(perms: string[]): boolean`

Use this to:

- Show/hide admin-only screens (e.g., safe-mode toggle, global roles).
- Disable dangerous actions (delete workspace, toggle safe mode).

We should **not** gate everything client-side only; the backend is authoritative. But front-end guards improve UX.

---

## 10. Implementation Plan (Frontend)

### 10.1 Modules

- `features/auth/api/authApi.ts`
  - Wraps:
    - `/auth/session` (GET/POST/DELETE)
    - `/auth/session/refresh` (POST)
    - `/auth/providers` (GET)
    - `/me` (GET)
    - `/setup/status` (GET)
    - `/setup` (POST)
    - `/bootstrap` (GET)
  - Uses OpenAPI types:
    - `LoginRequest`, `SessionEnvelope`, `BootstrapEnvelope`, `SetupStatus`, `SetupRequest`, `ProviderDiscoveryResponse`.

- `app/providers/AuthProvider.tsx`
  - Implements state machine.
  - Uses `authApi` to drive transitions.
  - Exposes `useAuth()` hook with:
    - `state` (enum above)
    - `user`, `permissions`, `bootstrap`
    - `loginWithPassword(credentials)`
    - `logout()`

- `shared/api-client/client.ts`
  - Adds:
    - `credentials: "include"` to fetch.
    - Intercepts 401 to run refresh logic if `AuthProvider` exposes it.

### 10.2 React Query Integration

- Use React Query for:
  - `useBootstrap` (internal to AuthProvider).
  - Data that depends on `authState === "authenticated"`:
    - workspaces list, documents, configs, runs.

- When user logs out:
  - Clear or invalidate all queries.
- When session refresh fails:
  - Clear queries and set `authState = "unauthenticated"`.

---

## 11. Non-Goals & Later Enhancements

Not required for this workpackage:

- Full admin UI for:
  - Global roles/permissions.
  - Workspace roles/memberships.
  - API keys management.
- Remembering `return_to` in local storage for complex flows; for now, we can:
  - Use `SessionEnvelope.return_to` if backend populates it.
  - Or use simple “redirect back to last route” semantics.

Possible future improvements:

- Full-blown “Account” screen (profile, API keys, workspace membership).
- Rich session management (see active sessions, log out of other devices).
- Command palette integration (“Log out”, “Switch account”, etc.).

---

## 12. Summary

- We have a **session-cookie-based** backend with:
  - Password login, optional SSO providers.
  - A rich `BootstrapEnvelope` for SPA initialization.
  - Setup endpoints (`/setup`, `/setup/status`) for first admin.
- The frontend should:
  - Centralize auth & bootstrap in an `AuthProvider`.
  - Use `setup/status` → `auth/session` → `bootstrap` as canonical boot flow.
  - Use `auth/providers` + `force_sso` flags to decide password vs SSO options.
  - Use `auth/session/refresh` lazily on 401 to keep sessions alive.
  - Use OpenAPI types for all auth-related requests (`LoginRequest`, `SessionEnvelope`, `ProviderDiscoveryResponse`, `SetupStatus`, `BootstrapEnvelope`, etc).

This gives us a clear, predictable auth story that’s aligned with the backend surface and plays nicely with the rest of the ade-web architecture.
