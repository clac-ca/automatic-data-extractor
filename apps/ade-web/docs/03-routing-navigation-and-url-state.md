# 03 – Routing, navigation, and URL state

This document describes how ADE Web maps URLs to screens, how navigation is implemented without a third‑party router, and how we use query parameters to encode shareable UI state.

It assumes you’re familiar with the domain model in `01-domain-model-and-naming.md` and the project structure in `02-architecture-and-project-structure.md`.

---

## 1. Goals and design principles

Our routing and navigation layer is designed around a few simple rules:

1. **The URL is the source of truth** for “where am I?”  
   Reloading the page must reconstruct the same screen and key view state.

2. **Single‑page app, browser‑native navigation.**  
   We use the History API directly (`pushState` / `replaceState` / `popstate`) instead of a third‑party router.

3. **Predictable back/forward behaviour.**  
   All navigation (programmatic and link clicks) goes through the same code path as `popstate`, so blockers and side‑effects behave the same.

4. **URLs are safe to share.**  
   The pathname and query string encode enough to re‑open a view (documents list filters, config builder layout, settings tab, etc.).

5. **Minimal custom primitives.**  
   One provider (`NavProvider`), one hook to read (`useLocation()`), one hook to navigate (`useNavigate()`), and one hook to block navigation (`useNavigationBlocker()`).

---

## 2. Runtime stack

The routing stack is composed in `main.tsx` and `App.tsx`:

```tsx
// main.tsx
ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
````

```tsx
// App.tsx (conceptual)
export function App() {
  return (
    <NavProvider>
      <AppProviders>
        <ScreenSwitch />
      </AppProviders>
    </NavProvider>
  );
}
```

* **`NavProvider`** owns the current `location` and wires up the browser History API.
* **`AppProviders`** configures React Query and other cross‑cutting providers.
* **`ScreenSwitch`** looks at `location.pathname` and chooses the top‑level screen.

All routing, navigation, and URL state flows are built on top of this stack.

---

## 3. Path routing

### 3.1 Normalisation and invariants

Before we do any routing:

* Pathnames are normalised to **remove trailing slashes**
  (e.g. `/workspaces/123/` → `/workspaces/123`).

* The `location` we expose always has:

  * `pathname` – slash‑prefixed path without query/hash.
  * `search` – raw `?q=...` query string (or `""`).
  * `hash` – raw `#...` fragment (or `""`).

Consumers should treat `pathname` as immutable within a render.

### 3.2 Top‑level routes

`ScreenSwitch` is a simple “router switch” on `pathname` (pseudo‑code):

```ts
switch (true) {
  case path === "/":                return <HomeOrEntryScreen />;
  case path === "/login":           return <LoginScreen />;
  case path === "/auth/callback":   return <AuthCallbackScreen />;
  case path === "/setup":           return <SetupScreen />;
  case path === "/logout":          return <LogoutScreen />;

  case path === "/workspaces":      return <WorkspaceDirectoryScreen />;
  case path === "/workspaces/new":  return <CreateWorkspaceScreen />;

  case path.startsWith("/workspaces/"):
    return <WorkspaceShellScreen />;

  default:
    return <NotFoundScreen />;
}
```

Top‑level routes are:

| Path                           | Purpose                                      |
| ------------------------------ | -------------------------------------------- |
| `/`                            | Entry strategy (redirect to login/setup/app) |
| `/login`                       | Sign‑in                                      |
| `/auth/callback`               | Auth provider callback                       |
| `/setup`                       | First‑time admin setup                       |
| `/logout`                      | Logout and session cleanup                   |
| `/workspaces`                  | Workspace directory                          |
| `/workspaces/new`              | Create workspace                             |
| `/workspaces/:workspaceId/...` | Workspace shell + sections                   |

### 3.3 Workspace shell routes

The **Workspace shell** handles all paths under `/workspaces/:workspaceId`. The path segment immediately after the workspace ID selects the section:

* `/workspaces/:workspaceId/documents`
* `/workspaces/:workspaceId/jobs`
* `/workspaces/:workspaceId/config-builder`
* `/workspaces/:workspaceId/settings`
* `/workspaces/:workspaceId/overview` (optional)

Inside `WorkspaceShellScreen`, we typically:

1. Parse `workspaceId` from the pathname.
2. Fetch workspace context (name, environment, permissions).
3. Route the **section** based on the next segment.

If the section segment is not recognised, we show a **workspace‑local** “Section not found” state instead of the global 404. This lets users recover by switching sections without losing workspace context.

---

## 4. Navigation layer (`NavProvider`)

We implement a small navigation layer on top of the History API so that all navigation flows share the same code and blocker logic.

### 4.1 Core types

```ts
type LocationLike = {
  pathname: string;
  search: string;
  hash: string;
};

type NavigationKind = "push" | "replace" | "pop";

type NavigationIntent = {
  readonly to: string;        // target URL string (pathname + search + hash)
  readonly location: LocationLike; // resolved URL parts
  readonly kind: NavigationKind;
};

type NavigationBlocker = (intent: NavigationIntent) => boolean;
```

* **`NavigationIntent`** captures a proposed navigation.
* **`NavigationBlocker`** can veto it by returning `false`.

### 4.2 Provider behaviour

`NavProvider` does three things:

1. **Initial state**

   * Reads `window.location` on mount.
   * Normalises `pathname` and builds an initial `LocationLike`.

2. **Back/forward (`popstate`)**

   * Listens for the `popstate` event.
   * On `popstate`, constructs a `NavigationIntent` with `kind: "pop"` and the new location.
   * Runs *all registered blockers*:

     * If any returns `false`, it **restores the previous URL** via `pushState` and **does not** update internal location.
     * Otherwise, it updates its `location` state and notifies consumers.

3. **Programmatic navigation**

   * Exposes `navigate(to, { replace? })` via `useNavigate()` (see below).
   * For programmatic navigations, it:

     1. Resolves the target URL with `new URL(to, window.location.origin)`.
     2. Builds a `NavigationIntent` with `kind: "push"` or `"replace"`.
     3. Runs blockers; if any returns `false`, abort.
     4. Calls `history.pushState` or `history.replaceState`.
     5. Dispatches its own `PopStateEvent` so the rest of the app treats it exactly like a natural navigation.

This “re‑dispatch” pattern ensures that **all** navigation flows (back/forward buttons, links, programmatic navigate) pass through the same logic and blockers.

### 4.3 Hooks

`NavProvider` exposes three hooks:

#### `useLocation()`

* Returns the current `LocationLike`:

  * `{ pathname, search, hash }`
* Updates whenever the provider’s location state changes.
* Treat as read‑only; do not mutate the object.

#### `useNavigate()`

```ts
type NavigateOptions = { replace?: boolean };

type NavigateFn = (to: string, options?: NavigateOptions) => void;
```

* Returns a `navigate` function that:

  * Accepts any `to` that `new URL(to, origin)` understands:

    * Absolute path (`/workspaces`),
    * Relative path (`../jobs`),
    * Same‑page query change (`?view=members`).

  * Uses `replace` when you don’t want to add a history entry (e.g. updating filters).

* Always goes through the blocker mechanism.

#### `useNavigationBlocker(blocker, when = true)`

* Registers a **blocker** while `when` is truthy.
* Typical use:

  * Editors (e.g. Config Builder workbench) use it to prevent losing unsaved changes.
  * Implementation pattern:

    * Allow navigation if `pathname` is unchanged (query/hash‑only changes).
    * Otherwise, prompt the user (“Discard changes?”) and return `true/false` accordingly.

Blockers must be **fast** and side‑effect‑free except for user prompts.

---

## 5. SPA link components

We wrap `<a>` to get SPA behaviour without losing native browser semantics.

### 5.1 `Link`

**Goals:**

* Always render a real `<a href="...">` so:

  * Middle‑click, right‑click → “Open in new tab”, “Copy link” work.
* Intercept plain left‑clicks and navigate via `navigate()`.

**Behaviour:**

* Props (simplified):

  ```ts
  interface LinkProps
    extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
    to: string;
    replace?: boolean;
  }
  ```

* On click:

  1. Call any `onClick` handler.
  2. If `event.defaultPrevented` → do nothing else.
  3. If any modifier key is pressed (`meta`, `ctrl`, `shift`, `alt`) → let the browser handle it.
  4. If it’s a plain left‑click:

     * `preventDefault()`.
     * Call `navigate(to, { replace })`.

Use `Link` for all internal navigation within the app.

### 5.2 `NavLink`

`NavLink` extends `Link` with an **active** state:

* It computes `isActive` from the current `pathname` and the `to` prop:

  ```ts
  const isActive = end
    ? pathname === to
    : pathname === to || pathname.startsWith(`${to}/`);
  ```

* API:

  ```ts
  interface NavLinkProps extends LinkProps {
    end?: boolean;
    className?: string | ((args: { isActive: boolean }) => string);
    children:
      | React.ReactNode
      | ((args: { isActive: boolean }) => React.ReactNode);
  }
  ```

* Use cases:

  * Left nav items in the workspace shell.
  * Tabs that are backed by routes.

This pattern allows conditional classes (`isActive` → bold, different background) without duplicating active logic in many places.

---

## 6. Query strings and URL helpers

We centralise low‑level query string operations in `shared/urlState.ts`.

### 6.1 Basic helpers

#### `toURLSearchParams(init)`

Accepts a **SearchParamsInit** and returns a `URLSearchParams`. Supported inputs:

* String (`"q=foo&status=processed"`),
* `string[][]`,
* `URLSearchParams`,
* A record `{ [key: string]: string | string[] | null | undefined }`.

Null/undefined values are omitted.

#### `getParam(search, key)`

* `search`: raw `location.search` string (with or without leading `?`).
* Returns the first value for `key` or `null` if not present.

#### `setParams(url, patch)`

* `url`: `URL` instance.
* `patch`: same shape as `toURLSearchParams` init.
* Returns a string of the updated `path + search + hash`.
* Typically used internally by `useSearchParams`.

### 6.2 Conventions

* Treat query strings as **view state**, not data storage.
* Keep parameter names short and stable (`q`, `view`, `status`, `sort`).
* Avoid encoding large or sensitive payloads into the URL.

---

## 7. `useSearchParams` hook

`useSearchParams()` is the standard way to read and update query parameters inside a screen.

### 7.1 API

```ts
const [params, setSearchParams] = useSearchParams();

// params: URLSearchParams (current query string)
// setSearchParams: (init, options?) => void
```

Where:

```ts
type SearchParamsInit =
  | string
  | string[][]
  | URLSearchParams
  | Record<string, string | string[] | null | undefined>
  | ((prev: URLSearchParams) => SearchParamsInit);

interface SetSearchParamsOptions {
  replace?: boolean; // default false
}
```

### 7.2 Behaviour

* Reads the current query string from `useLocation().search`.
* `setSearchParams(init, options)`:

  1. Resolves `init` (if it’s a function, call it with the current `URLSearchParams`).
  2. Uses `toURLSearchParams` to build a new `URLSearchParams`.
  3. Combines it with the current `pathname` and `hash` to get a target URL.
  4. Calls `navigate(target, { replace })` internally.

This ensures:

* The URL in the address bar always reflects the current query string.
* Back/forward navigation works as expected when toggling filters or tabs.

### 7.3 Guidelines

* Use `replace: true` for **ephemeral view tweaks** (filters, tabs) to avoid bloating history.
* Use `replace: false` for **logical navigation steps** (wizard pages, major mode switches).
* Always use this hook instead of manually writing to `window.location.search`.

---

## 8. `SearchParamsOverrideProvider`

Most screens should use the real URL search parameters.

`SearchParamsOverrideProvider` exists for rare cases where a subtree needs **local query‑like state** that behaves like `useSearchParams` but shouldn’t touch the browser’s address bar.

### 8.1 API (conceptual)

```ts
interface SearchParamsOverrideValue {
  readonly params: URLSearchParams;
  readonly setSearchParams: (
    init: SearchParamsInit,
    options?: SetSearchParamsOptions,
  ) => void;
}
```

* The provider injects a custom `params` and `setSearchParams`.
* Inside the provider, `useSearchParams()` returns the override instead of reading from `location.search`.

### 8.2 When to use

* Embedded dialogs or panels that reuse components expecting `useSearchParams`, but where URL changes would be confusing or undesirable.
* Legacy flows that need to present “virtual” query state while you refactor them to real URLs.

### 8.3 Rules of thumb

* **Do not** wrap entire screens or sections with overrides—this defeats the purpose of shareable URLs.
* Document each usage explicitly with a comment explaining why the override is necessary and temporary if possible.

---

## 9. Conventional query parameters

This section documents the main query parameters used across ADE Web. Exact semantics belong to the feature docs; here we record **names and scopes**.

### 9.1 Auth and setup

* `redirectTo`

  * Used on `/login` and other auth routes.
  * Must be a **relative, same‑origin path** (validated both client and server).
  * Example: `/login?redirectTo=/workspaces`.

### 9.2 Workspace settings

* `view`

  * Used on `/workspaces/:workspaceId/settings`.
  * Values: `general`, `members`, `roles`.
  * Invalid values are normalised back to `general`.

### 9.3 Documents list

On `/workspaces/:workspaceId/documents`:

* `q` – free text search (name, source, etc.).
* `status` – comma‑separated statuses (`uploaded,processing,failed`).
* `sort` – sort key (e.g. `-created_at`, `-last_run_at`).
* `view` – optional preset (`all`, `mine`, `team`, `attention`, `recent`).

These parameters should be considered part of the **shareable URL** for any documents view.

### 9.4 Jobs list

On `/workspaces/:workspaceId/jobs` (if implemented with query parameters):

* Typical parameters:

  * `status` – job status filter.
  * `config` – configuration id filter.
  * `initiator` – user filter.
  * `from`, `to` – date range filters.

Even where these aren’t yet implemented, new filters should follow this pattern.

### 9.5 Config Builder workbench

The Config Builder workbench encodes layout and selection in query parameters. Full semantics live in `09-workbench-editor-and-scripting.md`, but the keys are:

* `tab` – top‑level builder tab (currently `editor`).
* `pane` – bottom panel tab (`console`, `validation`).
* `console` – `open` or `closed`.
* `view` – layout mode (`editor`, `split`, `zen`).
* `file` – currently selected file id/path.

Key properties:

* Defaults are defined in a single place (`DEFAULT_CONFIG_BUILDER_SEARCH`).
* We only write **non‑default** values back into the URL to keep query strings clean.

---

## 10. Patterns and anti‑patterns

### 10.1 Patterns to follow

* **Use route helpers**, not string concatenation:

  * Prefer `routes.workspaceDocuments(workspaceId)` over `"/workspaces/" + workspaceId + "/documents"` sprinkled around.

* **Always navigate via `navigate()` or `Link`/`NavLink`.**

  * Never write to `window.location` directly for internal navigation.

* **Encode meaningful view state in the URL.**

  * Filters, selected settings tab, config builder layout mode—anything users may want to bookmark or share.

* **Use `replace: true` for “tuning”, `replace: false` for “steps”.**

  * Tuning = change filters, hide/show panels.
  * Steps = navigate between logically distinct pages.

### 10.2 Anti‑patterns to avoid

* **Directly reading or writing `window.location`** in screens or components.

  * If you need `pathname`, `search`, or `hash`, use `useLocation()`.

* **Holding a second copy of “where we are” in React state.**

  * The URL + `useLocation()` is the single source of truth.

* **Using `SearchParamsOverrideProvider` as a general solution.**

  * It’s an escape hatch. Prefer real URL state whenever possible.

* **Large or sensitive payloads in the query string.**

  * URLs are logged, cached, and potentially shared. Keep them small and non‑sensitive.

---

By adhering to these conventions, ADE Web’s routing layer remains small, predictable, and easy to reason about. New screens should plug into `ScreenSwitch`, use `NavProvider` primitives, and encode their view state via `useSearchParams` so deep links and navigation remain robust as the app evolves.