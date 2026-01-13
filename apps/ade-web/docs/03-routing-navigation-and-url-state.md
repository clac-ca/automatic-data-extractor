# 03 – Routing, navigation, and URL state

This document describes how ADE Web turns URLs into screens, how navigation works in our single‑page app, and how we use query parameters to store shareable UI state.

Use this as the reference for anything that:

- Reads or writes the browser location.
- Navigates between screens.
- Encodes view state (filters, tabs, layout) in the URL.

It assumes you’ve read:

- `01-domain-model-and-naming.md` for core terms (workspace, document, run, configuration).
- `02-architecture-and-project-structure.md` for where code lives.

---

## 1. Goals and principles

The routing and navigation layer is designed to be:

- **Predictable** – the URL always tells you “where you are” and “what you’re looking at”.
- **Shareable** – copying the URL should reopen the same view with the same filters/layout.
- **Small** – keep the route table explicit and avoid over‑abstracting navigation.
- **Guardable** – editors can block navigation when there are unsaved changes.

We follow a few rules:

1. The **location bar is authoritative**. A reload should land you back on the same screen with the same view state.
2. All navigation goes through **React Router** (`useNavigate` / `Link` / `NavLink`), not raw `history.pushState`.
3. **Query parameters** are the standard way to represent view‑level state that should survive refresh and be shareable.
4. Navigation blockers are **opt‑in and local** to the features that need them (e.g. the Configuration Builder workbench).

### Canonical sources and names

- Build workspace routes via helpers in `@app/navigation` instead of hand‑rolled strings so the route map below and the code stay in sync.
- Query parameter names for workspace sections are defined in the Documents/Runs filter helpers (`parseDocumentFilters` / `buildDocumentSearchParams`, `parseRunFilters` / `buildRunSearchParams`) described in `docs/06` and `docs/07`; add new keys there to keep deep links consistent.
- Permission checks referenced in navigation (e.g. showing nav items) should use the keys from `@schema` and the workspace context helpers, not ad‑hoc strings.

---

## 2. Routing stack overview

The high‑level stack looks like this:

```tsx
// main.tsx
ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
);
````

```tsx
// app/App.tsx
export function AppShell() {
  return (
    <NuqsAdapter>
      <AppProviders>
        <Outlet />
      </AppProviders>
    </NuqsAdapter>
  );
}
```

```tsx
// app/routes.tsx
export const appRoutes = [
  {
    element: <AppShell />,
    children: [
      { path: "login", element: <LoginScreen /> },
      { element: <ProtectedLayout />, children: [/* ... */] },
    ],
  },
];
```

* **`RouterProvider`**
  Owns the router state and coordinates navigation.

* **`AppShell`**
  Wraps the app with global providers (React Query, Nuqs).

* **`ProtectedLayout`**
  Gates authenticated routes (`RequireSession`).

* **`routes.tsx`**
  Central route table mapping paths to pages.

Everything below the route table (workspaces, documents, runs, Configuration Builder) uses URL‑encoded view state and query parameters.

---

## 3. Route map

### 3.1 Top‑level routes

Route mapping lives in `app/routes.tsx` (simplified):

```ts
export const appRoutes = [
  {
    element: <AppShell />,
    children: [
      { path: "login", element: <LoginScreen /> },
      { path: "logout", element: <LogoutScreen /> },
      { path: "setup", element: <SetupScreen /> },
      {
        element: <ProtectedLayout />,
        children: [
          { index: true, element: <HomeScreen /> },
          { path: "workspaces", element: <WorkspacesScreen /> },
          { path: "workspaces/new", element: <WorkspaceCreateScreen /> },
          { path: "workspaces/:workspaceId/*", element: <WorkspaceScreen /> },
          { path: "*", element: <NotFoundScreen /> },
        ],
      },
    ],
  },
];
```

Supported top‑level routes:

| Path                         | Responsibility                              |
| ---------------------------- | ------------------------------------------- |
| `/`                          | Entry strategy (decide login/setup/app).    |
| `/login`                     | Login form & auth provider selection.       |
| `/setup`                     | First‑time administrator setup.             |
| `/logout`                    | Logout and session teardown.                |
| `/workspaces`                | Workspace directory.                        |
| `/workspaces/new`            | Create a workspace.                         |
| `/workspaces/:workspaceId/*` | Workspace shell and all workspace sections. |
| `*`                          | Global “Not found” screen.                  |

We **normalize trailing slashes**:

* `/foo/` → `/foo`
* `/workspaces/123/runs/` → `/workspaces/123/runs`

This avoids subtle “same page, different URL” duplication.

### 3.2 Workspace shell routes

Inside `/workspaces/:workspaceId`, the next path segment selects the section:

| Segment          | Example path                     | Section                       |
| ---------------- | -------------------------------- | ----------------------------- |
| `documents`      | `/workspaces/123/documents`      | Documents list & run triggers |
| `runs`           | `/workspaces/123/runs`           | Runs ledger (workspace run history) |
| `config-builder` | `/workspaces/123/config-builder` | Configuration Builder (configurations list + workbench) |
| `settings`       | `/workspaces/123/settings`       | Workspace settings            |

Naming stays 1:1: the nav item reads **“Configuration Builder”**, the route segment is `config-builder`, and the feature folder is `pages/Workspace/sections/ConfigBuilder`. The Configuration Builder section always includes both the configurations list and the workbench editing mode.

If the workspace ID is valid but the section segment is unknown, the shell should render a **workspace‑local “Section not found”** state, not the global 404. This lets the user switch to another section without leaving the workspace.

### 3.3 Route helpers

Workspace routes are derived from:

* `pages/Workspace/components/workspaceNavigation.ts` (section definitions + `getWorkspacePrimaryNavigation`)
* `app/navigation/workspacePaths.ts` (default section path)

Use these helpers for nav links and redirects instead of hand‑rolled strings. Keeping one source of truth helps the tables above stay in sync with the code.

---

## 4. Navigation model (React Router)

React Router v7 owns history, location, and navigation. Use its hooks and components directly.

### 4.1 Reading the current location (`useLocation`)

```ts
const { pathname, search, hash } = useLocation();
```

* Use this in any component that needs to:

  * Match route segments (e.g. active nav items).
  * Parse query parameters (`new URLSearchParams(search)`).

**Do not** read `window.location` directly inside React components.

### 4.2 Programmatic navigation (`useNavigate`)

```ts
const navigate = useNavigate();
navigate("/workspaces");
```

* `to` can be:

  * An absolute path (`/workspaces/123/runs`).
  * A relative path (`../documents`).
  * A query‑only change (`?view=members`).

**Guidelines:**

* Use `replace: true` when you’re **fixing** or **normalising** a URL (e.g. invalid `view` value → `view=general`).
* Use the default (`replace: false`) when you’re taking a **logical step** (navigating to another screen).

### 4.3 Navigation blockers (`useBlocker`)

Use `useBlocker` when a view has **unsaved changes** that shouldn’t be lost silently.

Example pattern for the Configuration Builder editor:

```ts
const blocker = useBlocker(({ currentLocation, nextLocation }) => {
  if (!hasUnsavedChanges) return false;
  if (currentLocation.pathname === nextLocation.pathname) return false;
  return true;
});

useEffect(() => {
  if (blocker.state !== "blocked") return;
  if (window.confirm("You have unsaved changes. Leave without saving?")) {
    blocker.proceed();
  } else {
    blocker.reset();
  }
}, [blocker]);
```

Guidelines:

* Blockers should be **local** to the component that owns the unsaved state.
* Always treat query/hash‑only changes specially (usually allowed even when dirty).

---

## 5. SPA links (`Link` and `NavLink`)

Use React Router’s `Link` and `NavLink` from `react-router-dom`. They render `<a>` tags and preserve normal browser semantics (right‑click, middle‑click, copy link) while keeping navigation client‑side.

### 5.1 `Link`

Use `Link` for all **internal** navigations where you would otherwise use `<a>`:

```tsx
<Link to="/workspaces">Workspaces</Link>
```

### 5.2 `NavLink`

`NavLink` adds an “active” state that you can use for styling:

```tsx
<NavLink
  to="/workspaces/123/runs"
  className={({ isActive }) => clsx("nav-item", isActive && "nav-item--active")}
>
  Runs
</NavLink>
```

Use `NavLink` anywhere you want route‑aware styling, e.g. nav menus or route‑backed tabs.

---

## 6. URL state and search parameters

### 6.1 Why encode state in the URL

We use query parameters for view‑level state that:

* Should survive refresh,
* Should be shareable via URL, and
* Does not need to stay private.

Examples:

* Documents filters and sort order.
* Which settings tab is selected.
* Configuration Builder layout (editor vs split vs zen, which pane is open).

Plain local component state is fine for **purely ephemeral** UI (e.g. whether a dropdown is open). If a user might:

* Bookmark it,
* Share it with a teammate, or
* Expect the browser back button to step through it,

it should live in the URL.

### 6.2 Low‑level helpers

Helpers in `app/navigation/urlState` handle raw query string operations:

* `toURLSearchParams(init)`

  * Accepts strings, `URLSearchParams`, arrays, or plain objects.
  * Produces a `URLSearchParams` instance.

* `getParam(search, key)`

  * Extracts a single value from a `search` string (with or without `?`).

* `setParams(url, patch)`

  * Patches query parameters on a `URL` object and returns the new `path + search + hash`.

You rarely need these directly; they power `useSearchParams()`.

### 6.3 `useSearchParams()`

API:

```ts
const [params, setSearchParams] = useSearchParams();
```

* `params` – current `URLSearchParams` for `location.search`.
* `setSearchParams(init, options?)` – update query parameters:

  ```ts
  type SearchParamsInit =
    | string
    | string[][]
    | URLSearchParams
    | Record<string, string | string[] | null | undefined>
    | ((prev: URLSearchParams) => SearchParamsInit);

  interface SetSearchParamsOptions {
    replace?: boolean;
  }
  ```

When called:

1. We compute the new `URLSearchParams`.
2. Build a full target URL with the current `pathname` and `hash`.
3. Call `navigate(target, { replace })` under the hood.

**Usage patterns:**

* Patch in place:

  ```ts
  setSearchParams(prev => {
    const params = new URLSearchParams(prev);

    if (nextStatus) params.set("status", nextStatus);
    else params.delete("status");

    return params;
  }, { replace: true });
  ```

* Use `replace: true` when tweaking filters or tabs (back button should skip over tiny changes).

* Use `replace: false` if query changes represent a new logical step in a flow (less common).

### 6.4 `SearchParamsOverrideProvider`

Most of the app should talk to the **real** URL. `SearchParamsOverrideProvider` exists for a few niche cases where a subtree needs **query‑like** state but must not mutate `window.location`.

Conceptually:

```ts
interface SearchParamsOverrideValue {
  readonly params: URLSearchParams;
  readonly setSearchParams: (
    init: SetSearchParamsInit,
    options?: SetSearchParamsOptions,
  ) => void;
}
```

Within the provider:

* `useSearchParams()` returns the override instead of the global URL‑backed one.

Use cases:

* Embedded flows that reuse components expecting `useSearchParams`, but where URL changes would be misleading.
* Transitional flows where you cannot yet change the real URL model.

Rules:

* **Do not** wrap whole sections or screens; that defeats deep‑linking.
* Document each usage with a comment explaining why the override is needed.
* Prefer migrating to real URL state over time.

### 6.5 Typed query helpers for filters

For non‑trivial query state (documents filters, run filters), use typed helper pairs instead of scattered strings: `parseDocumentFilters(params: URLSearchParams)` / `buildDocumentSearchParams(filters)` or `parseRunFilters` / `buildRunSearchParams`. Centralising canonical names (`q`, `status`, `view`, etc.) keeps components consistent and deep links predictable. See `07-documents-and-runs.md` for the canonical filter shapes.

---

## 7. Canonical query parameters

This section defines the expected query parameters per view. Having one place to look keeps naming consistent.

### 7.1 Auth

On `/login` and related auth routes:

* `returnTo` (string):

  * Target path after successful login.
  * Must be a **relative**, same-origin path.
  * Examples: `/workspaces`, `/workspaces/123/documents`.

The backend and frontend both validate `returnTo` to avoid open redirects.

### 7.2 Workspace settings

On `/workspaces/:workspaceId/settings`:

* `view` (string):

  * Allowed values: `general`, `members`, `roles`.
  * Controls which tab is active.

Behaviour:

* Invalid or missing `view` is normalised to `general` using `navigate(..., { replace: true })` to keep history clean.

### 7.3 Documents

On `/workspaces/:workspaceId/documents`:

* `q` (string):

  * Free‑text query (document name, source, etc.).

* `status` (string):

  * Comma‑separated document statuses.
  * Example: `status=uploaded,processed,failed`.

* `sort` (string):

  * Sort key and direction.
  * Examples: `sort=-created_at`, `sort=-last_run_at`.

* `view` (string):

  * View preset.
  * Suggested values: `all`, `mine`, `team`, `attention`, `recent`.

These parameters make documents views sharable:

> “Show me all failed documents in workspace X” should be a URL, not just a filter in memory.

### 7.4 Runs

On `/workspaces/:workspaceId/runs`:

* `status` (string, optional):

  * Comma‑separated run statuses.

* `configurationId` (string, optional):

  * Filter by configuration ID.

* `initiator` (string, optional):

  * Filter by user id/email.

* `from`, `to` (string, optional):

  * ISO‑8601 date boundaries for run start time.

These names should be stable so that links from other parts of the UI (e.g. “View runs for this configuration”) can construct correct URLs.

### 7.5 Configuration Builder (summary)

On `/workspaces/:workspaceId/config-builder` with an active workbench:

* `pane` (string):

  * Bottom panel tab: `console` or `validation`.

* `console` (string):

  * Console visibility: `open` or `closed`.

* `view` (string):

  * Layout mode: `editor`, `split`, `zen`.

* `file` (string):

  * ID/path of the active file in the workbench.

The Configuration Builder URL state is documented in detail in `09-workbench-editor-and-scripting.md`. The important rule here: we only write **non‑default** values back into the URL to keep it tidy.

---

## 8. Extending the route map and URL state

When adding new routes or URL‑encoded state, follow this checklist:

1. **Decide the owner and scope**

   * Global (auth, setup, workspace directory) vs workspace‑scoped (`/workspaces/:workspaceId/...`).
   * Which feature folder will own the screen (`pages/Workspace/sections/Runs`, etc.).

2. **Add a page component and wire it into routing**

   * Create `SomethingScreen.tsx` under the appropriate feature folder.
   * Add a route in `app/routes.tsx` (for top‑level) or a branch in `WorkspaceScreen` (for sections).

3. **Define route helpers**

  * Centralise URL construction in `pages/Workspace/components/workspaceNavigation.ts` and `app/navigation/workspacePaths.ts` (see §3.3).
   * Use these helpers in `Link` / `NavLink`, navigation logic, and tests instead of ad‑hoc strings.

4. **Register query parameters here**

   * Add a row/section in §7 for new query parameters.
   * Decide names and allowed values up front; avoid one‑off strings sprinkled in components.

5. **Use `useSearchParams()` in your feature**

   * Do not hand‑parse `location.search`.
   * Prefer `setSearchParams(prev => ...)` with `{ replace: true }` for filters.

6. **Avoid surprises**

   * Don’t override history in unexpected ways.
   * Don’t encode large or sensitive payloads in the URL.

If we follow these patterns, the routing and URL‑state model stays small, obvious, and easy to extend as ADE Web grows.
