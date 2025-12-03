# ADE Web – Navigation & Routing (060-NAVIGATION.md)

## 1. Purpose & Scope

This document defines the navigation and routing model for the new `apps/ade-web`:

- How we represent routes as **typed objects**.
- How we map routes to **canonical URLs** and back.
- How the **custom history-based router** works (no React Router).
- How deep links (e.g. “open this specific run at this event sequence”) are expressed and consumed.
- How screens integrate with navigation (Workspace, Documents, Run Detail, Config Builder).

This spec is the single source of truth for navigation. If you introduce a new screen or change a URL shape, **update this document first**, then the code.

---

## 2. Constraints & Goals

### 2.1 Constraints

- **No React Router or other routing library.**
- Application is a **single-page app** using the browser History API (`pushState`, `popstate`).
- URLs must be:
  - Stable & shareable (deep links work across sessions).
  - Human-readable and roughly REST-like.
- Navigation must work with:
  - Browser back/forward.
  - Programmatic navigation from components.
  - Server-side 404 if the path is completely unknown.

### 2.2 Goals

- Typed route model that makes illegal states hard to represent.
- Clear **separation of concerns**:
  - Parsing/building URLs (pure functions).
  - Imperative history integration.
  - React hook (`useNavigation`) for components.
- Easy-to-use APIs for screens:
  - `navigateToDocuments(workspaceId)`
  - `navigateToRunDetail(workspaceId, runId, sequence?)` etc.
- First-class **deep links** for Run Detail and Documents.

---

## 3. Design Overview

We use a simple architecture:

1. **Route model** – a TypeScript union describing all valid app routes.
2. **URL mappers** – functions to convert between `Route` and URL (`string`).
3. **Navigation store** – small module that:
   - Tracks current `Route`.
   - Integrates with `window.history` and `popstate`.
4. **React hook (`useNavigation`)** – reads current route and exposes navigation helpers.
5. **AppShell** – central component that renders the correct screen based on `route.name`.

This gives us all the advantages of a router, without pulling in a 3rd-party dependency.

---

## 4. Route Model

### 4.1 Route Types

We model routes as a discriminated union:

```ts
// src/app/nav/routes.ts
export type Route =
  | { name: 'workspaceHome' }
  | { name: 'documents'; params: { workspaceId: string } }
  | { name: 'documentDetail'; params: { workspaceId: string; documentId: string } }
  | {
      name: 'runDetail';
      params: { workspaceId: string; runId: string; sequence?: number | null };
    }
  | { name: 'configBuilder'; params: { workspaceId: string; configId: string } }
  | { name: 'notFound' };
````

Notes:

* `workspaceHome` is a simple landing view (workspace selector + “go to Documents / Configs”).
* `documents` is the list view for a given workspace.
* `documentDetail` shows runs & outputs for a specific document.
* `runDetail` supports an optional `sequence` param for replay/deep linking.
* `configBuilder` opens a specific config in the builder.
* `notFound` is a local catch-all for malformed/unknown URLs (we still treat invalid IDs as screen-level 404s, see below).

### 4.2 Canonical URLs

We aim for clear, hierarchical URLs:

* Workspace Home

  * Route: `{ name: 'workspaceHome' }`
  * URL: `/`
* Documents list

  * Route: `{ name: 'documents', params: { workspaceId } }`
  * URL: `/workspaces/:workspaceId/documents`
* Document detail

  * Route: `{ name: 'documentDetail', params: { workspaceId, documentId } }`
  * URL: `/workspaces/:workspaceId/documents/:documentId`
* Run detail

  * Route: `{ name: 'runDetail', params: { workspaceId, runId, sequence? } }`
  * URL: `/workspaces/:workspaceId/runs/:runId`
  * With sequence: `/workspaces/:workspaceId/runs/:runId?sequence=123`
* Config Builder

  * Route: `{ name: 'configBuilder', params: { workspaceId, configId } }`
  * URL: `/workspaces/:workspaceId/configs/:configId`

These mappings are **canonical**. We should not emit multiple different URLs for the same `Route`.

---

## 5. URL <-> Route Mapping

### 5.1 Parsing Location → Route

We define a pure function:

```ts
export function parseLocation(location: Location): Route;
```

Responsibilities:

* Inspect `location.pathname` and `location.search`.
* Match known patterns in order of specificity (e.g. `/workspaces/:workspaceId/runs/:runId` before generic fallbacks).
* Parse query parameters (e.g. `sequence`) where relevant.
* Return a valid `Route` or `{ name: 'notFound' }`.

Example (simplified):

```ts
function parseLocation(location: Location): Route {
  const path = location.pathname;
  const searchParams = new URLSearchParams(location.search);

  if (path === '/') {
    return { name: 'workspaceHome' };
  }

  const parts = path.split('/').filter(Boolean);
  // e.g., ['workspaces', 'abc', 'documents', '123']

  if (parts[0] === 'workspaces') {
    const workspaceId = parts[1];

    if (parts[2] === 'documents') {
      if (!parts[3]) {
        return { name: 'documents', params: { workspaceId } };
      }
      const documentId = parts[3];
      return { name: 'documentDetail', params: { workspaceId, documentId } };
    }

    if (parts[2] === 'runs' && parts[3]) {
      const runId = parts[3];
      const sequenceParam = searchParams.get('sequence');
      const sequence =
        sequenceParam != null ? Number.parseInt(sequenceParam, 10) : undefined;

      return { name: 'runDetail', params: { workspaceId, runId, sequence } };
    }

    if (parts[2] === 'configs' && parts[3]) {
      const configId = parts[3];
      return { name: 'configBuilder', params: { workspaceId, configId } };
    }
  }

  return { name: 'notFound' };
}
```

Parsing should be tolerant to trailing slashes and ignore unknown query params.

### 5.2 Building URL from Route

The inverse function:

```ts
export function buildUrl(route: Route): string;
```

Example:

```ts
function buildUrl(route: Route): string {
  switch (route.name) {
    case 'workspaceHome':
      return '/';
    case 'documents':
      return `/workspaces/${encodeURIComponent(route.params.workspaceId)}/documents`;
    case 'documentDetail':
      return `/workspaces/${encodeURIComponent(
        route.params.workspaceId
      )}/documents/${encodeURIComponent(route.params.documentId)}`;
    case 'runDetail': {
      const { workspaceId, runId, sequence } = route.params;
      const base = `/workspaces/${encodeURIComponent(
        workspaceId
      )}/runs/${encodeURIComponent(runId)}`;
      if (sequence != null) {
        return `${base}?sequence=${sequence}`;
      }
      return base;
    }
    case 'configBuilder':
      return `/workspaces/${encodeURIComponent(
        route.params.workspaceId
      )}/configs/${encodeURIComponent(route.params.configId)}`;
    case 'notFound':
      return '/404';
  }
}
```

All navigation inside the app should go through `buildUrl(route)` to guarantee canonical URLs.

---

## 6. Navigation Store & Provider

### 6.1 navigation.ts – Core Store

We maintain a tiny store (no external state library) that:

* Holds `currentRoute`.
* Allows `navigate(route)` / `replace(route)`.
* Subscribes to `window.onpopstate` and updates subscribers.

Pseudo-API:

```ts
type RouteListener = (route: Route) => void;

let currentRoute: Route = parseLocation(window.location);
const listeners = new Set<RouteListener>();

export function getCurrentRoute(): Route {
  return currentRoute;
}

export function navigate(route: Route) {
  const url = buildUrl(route);
  if (url === window.location.pathname + window.location.search) return;
  window.history.pushState({}, '', url);
  setRouteFromLocation();
}

export function replace(route: Route) {
  const url = buildUrl(route);
  window.history.replaceState({}, '', url);
  setRouteFromLocation();
}

function setRouteFromLocation() {
  currentRoute = parseLocation(window.location);
  for (const listener of listeners) {
    listener(currentRoute);
  }
}

export function subscribe(listener: RouteListener) {
  listeners.add(listener);
  listener(currentRoute);
  return () => listeners.delete(listener);
}

// setup popstate listener once
window.addEventListener('popstate', () => {
  setRouteFromLocation();
});
```

### 6.2 NavigationProvider & useNavigation

`NavigationProvider` glues this store into React.

```tsx
// src/app/nav/NavigationProvider.tsx
const NavigationContext = React.createContext<NavigationValue | null>(null);

export function NavigationProvider({ children }: { children: React.ReactNode }) {
  const [route, setRoute] = React.useState<Route>(getCurrentRoute);

  React.useEffect(() => {
    return subscribe(setRoute);
  }, []);

  const value = React.useMemo(
    () => ({
      route,
      navigate,
      replace,
    }),
    [route]
  );

  return (
    <NavigationContext.Provider value={value}>
      {children}
    </NavigationContext.Provider>
  );
}

export function useNavigation() {
  const ctx = React.useContext(NavigationContext);
  if (!ctx) throw new Error('useNavigation must be used within NavigationProvider');
  return ctx;
}
```

Screens call:

```ts
const { route, navigate } = useNavigation();
```

`AppShell` uses `route` to decide which screen to render.

---

## 7. Link Component

To avoid sprinkling `navigate` everywhere, we provide a simple `Link` component:

```tsx
// src/app/nav/Link.tsx
interface LinkProps extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
  route: Route;
  replace?: boolean;
}

export function Link({ route, replace, onClick, ...rest }: LinkProps) {
  const { navigate, replace: replaceNav } = useNavigation();
  const href = buildUrl(route);

  const handleClick = (event: React.MouseEvent<HTMLAnchorElement>) => {
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.altKey ||
      event.ctrlKey ||
      event.shiftKey
    ) {
      return;
    }
    event.preventDefault();
    if (replace) replaceNav(route);
    else navigate(route);
    onClick?.(event);
  };

  return <a href={href} onClick={handleClick} {...rest} />;
}
```

Usage:

```tsx
<Link
  route={{ name: 'runDetail', params: { workspaceId, runId } }}
>
  View run details
</Link>
```

This ensures:

* `href` is set correctly for right-click / open-in-new-tab.
* SPA navigation for normal clicks.
* No dependency on React Router.

---

## 8. Run Detail Deep Links & Sequence Param

### 8.1 URL Shape

Deep link examples:

* Basic run detail:
  `/workspaces/abc/runs/xyz`
* Deep link to a specific event:
  `/workspaces/abc/runs/xyz?sequence=123`

When `sequence` is present:

* `parseLocation` sets `route.params.sequence = 123`.
* `RunDetailScreen` uses this value to drive telemetry replay:

  * E.g. call `useRunTelemetry(runId, { upToSequence: sequence })` and initialize the scrubber position.

### 8.2 Generating “Share this moment” Links

From the console or validation views, we can generate deep links:

```ts
const route: Route = {
  name: 'runDetail',
  params: { workspaceId, runId, sequence: errorSequence },
};

const url = buildUrl(route);
// show in “Copy link” button or use <Link route={route}>...
```

This keeps deep-link logic centralized.

---

## 9. Error Handling & Not Found

### 9.1 Unknown Paths

If `parseLocation` can’t match any known pattern, it returns `{ name: 'notFound' }`.

`AppShell` renders a simple 404-like screen:

* “We couldn’t find that page.”
* Link back to workspace home or last known valid view.

### 9.2 Invalid IDs

If a path matches a known pattern but data doesn’t exist (e.g., `workspaceId` doesn’t belong to current user, or `runId` not found):

* The screen hook (`useRun(runId)`, `useDocument(documentId)`) returns “not found” state.
* Screen shows a domain-specific empty/error state:

  * “This run does not exist or you don’t have access.”
* We do **not** change the route or redirect to `notFound` – the URL pattern is valid, the data isn’t.

---

## 10. Integration With Screens

### 10.1 AppShell

Pseudocode:

```tsx
function AppShell() {
  const { route } = useNavigation();

  switch (route.name) {
    case 'workspaceHome':
      return <WorkspaceScreen />;
    case 'documents':
      return <DocumentsScreen workspaceId={route.params.workspaceId} />;
    case 'documentDetail':
      return (
        <DocumentDetailScreen
          workspaceId={route.params.workspaceId}
          documentId={route.params.documentId}
        />
      );
    case 'runDetail':
      return (
        <RunDetailScreen
          workspaceId={route.params.workspaceId}
          runId={route.params.runId}
          initialSequence={route.params.sequence}
        />
      );
    case 'configBuilder':
      return (
        <ConfigBuilderScreen
          workspaceId={route.params.workspaceId}
          configId={route.params.configId}
        />
      );
    case 'notFound':
    default:
      return <NotFoundScreen />;
  }
}
```

Individual screens should **not** parse the URL directly; they receive plain props typed from the route.

### 10.2 Typical Navigation Calls

Examples:

* From Workspace home → Documents:

  ```ts
  navigate({ name: 'documents', params: { workspaceId } });
  ```

* From Documents list row → Document detail:

  ```tsx
  <Link
    route={{
      name: 'documentDetail',
      params: { workspaceId, documentId },
    }}
  >
    Open
  </Link>
  ```

* From Document run history → Run detail:

  ```tsx
  <Link
    route={{
      name: 'runDetail',
      params: { workspaceId, runId },
    }}
  >
    View run details
  </Link>
  ```

* From Config builder → Run detail of latest run:

  ```ts
  navigate({
    name: 'runDetail',
    params: { workspaceId, runId: latestRunId },
  });
  ```

---

## 11. Advanced Behaviors & Edge Cases (Optional)

These are **nice-to-haves** that can be layered in later.

### 11.1 Scroll Restoration

Basic approach:

* At route change, scroll top of main content.
* Optionally track `scrollY` per route key and restore when user navigates back (if needed).

### 11.2 Unsaved Changes Guard

For screens with unsaved edits (e.g. Config Builder):

* Provide a hook (e.g. `useUnsavedChangesGuard`) that:

  * Registers a callback with navigation store.
  * Confirms with the user before allowing `navigate` away.
  * Hooks into `beforeunload` to warn on tab close.

This should live in `shared/navigation-guards.ts` and be opt-in.

---

## 12. Testing Strategy

* **Unit tests** for:

  * `parseLocation` – given URL, returns correct `Route`.
  * `buildUrl` – given `Route`, returns expected URL.
* **Round-trip tests**:

  * `parseLocation(buildUrl(route))` → original `Route` (for all route variants).
* **Integration tests**:

  * Navigation flows:

    * Workspace → Documents → Document detail → Run detail.
    * Deep link to Run Detail with `sequence`.
    * Back/forward behavior.

If you add a new route, update:

1. `Route` type.
2. `buildUrl` and `parseLocation`.
3. At least one test case covering it.
4. This document.