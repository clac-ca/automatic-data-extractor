# 03-routing-navigation-and-url-state

**Purpose:** Explain how URLs map to screens, how navigation works, and how query parameters encode view state.

### 1. Overview

* SPA on top of `window.history`.
* Custom router (`NavProvider`) instead of React Router.
* URL is the single source of truth for where you are.

### 2. App entry and top-level routes

* `main.tsx` → `<App>` → `NavProvider` → `AppProviders` → `ScreenSwitch`.

* Top-level paths:

  * `/`, `/login`, `/auth/callback`, `/setup`, `/logout`.
  * `/workspaces`, `/workspaces/new`.
  * `/workspaces/:workspaceId/...`.
  * Global not-found.

* Explain trailing slash normalization (`/foo/` → `/foo`).

### 3. Workspace routes

* Structure of workspace URLs:

  * `/workspaces/:workspaceId/documents`
  * `/workspaces/:workspaceId/jobs`
  * `/workspaces/:workspaceId/config-builder`
  * `/workspaces/:workspaceId/settings`
  * `/workspaces/:workspaceId/overview` (optional).

* How “unknown section” in a workspace produces a workspace-local 404 instead of global 404.

### 4. Custom navigation layer

* Types:

  * `LocationLike`
  * `NavigationIntent`
  * `NavigationBlocker`

* `NavProvider`:

  * Tracks `location` from `window.location`.
  * Listens to `popstate`.
  * Runs navigation blockers and can cancel navigation.

* `useLocation()` and `useNavigate()`:

  * How `navigate(to, { replace? })` works.
  * Using `URL` to resolve relative links.

* `useNavigationBlocker()`:

  * How editors like Config Builder prevent losing unsaved changes.
  * Pattern for “save then navigate” flows.

### 5. SPA links

* `Link`:

  * Always renders `<a href={to}>`.
  * Intercepts unmodified left clicks and calls `navigate`.
  * Lets modified clicks (Cmd+Click, Ctrl+Click) behave normally.

* `NavLink`:

  * Active state logic: `end` vs prefix matching.
  * API (`className`, `children` as render function `{ isActive }`).

### 6. URL search parameters

* Helpers:

  * `toURLSearchParams`, `getParam`, `setParams`.

* `useSearchParams()`:

  * Return values and how to update (`setSearchParams(init, { replace })`).
  * When to prefer `replace` to avoid history spam.

### 7. SearchParamsOverrideProvider

* What it is:

  * Provider that intercepts `useSearchParams()` within its subtree.

* When it’s allowed:

  * Embedded flows that need “fake” query state.
  * Migration/legacy cases.

* Rule: Most screens should use real URL search; overrides are advanced/rare.

### 8. Important query parameters (global view)

* **Auth**: `redirectTo`:

  * Only relative paths allowed.
  * Validation rules to avoid open redirects.

* **Settings**: `view`:

  * `general`, `members`, `roles`.

* **Documents**: `q`, `status`, `sort`, `view`.

* **Config Builder**: overview (just names; full details in doc 09):

  * `tab`, `pane`, `console`, `view`, `file`.
