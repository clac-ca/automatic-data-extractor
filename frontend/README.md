# ADE Frontend

The `frontend/` package hosts the rebuilt ADE operator console. It is a Vite + React + TypeScript application that implements the navigation model described in `agents/FRONTEND_DESIGN.md` and the workspace story captured in `agents/WP_FRONTEND_REBUILD.md`.

## Getting Started

```bash
cd frontend
npm install
npm run dev
```

The dev server runs on <http://localhost:5173>. Configure `.env` to point at the FastAPI backend when needed (defaults to `/api/v1`).

## Project Layout

```
src/
├─ app/
│  ├─ AppProviders.tsx        # React Query + session providers shared by every route
│  ├─ entry.server.tsx        # Minimal SSR entry so the Vite plugin can bundle correctly
│  ├─ root.tsx                # Root route that wraps the router <Outlet /> with providers
│  └─ routes/                 # File-based route modules (auth, workspaces, documents…)
│     ├─ _index/route.tsx     # Landing page → redirects into the primary workspace
│     ├─ login/route.tsx      # Session entry (email/password or SSO redirect)
│     ├─ setup/route.tsx      # First-run workspace + admin bootstrap
│     ├─ auth/callback/route.tsx
│     ├─ not-found/route.tsx
│     └─ workspaces/
│        ├─ _index/route.tsx              # Workspace directory
│        ├─ _index/DirectoryLayout.tsx    # Shared chrome reused by directory + creation flow
│        ├─ new/route.tsx                 # Workspace creation wizard
│        └─ $workspaceId/                 # Authenticated workspace shell
│           ├─ route.tsx                  # Loader + left nav/top bar chrome + <Outlet />
│           ├─ GlobalTopBar.tsx / ProfileDropdown.tsx / WorkspaceNav.tsx / icons.tsx
│           ├─ sections.ts                # Section metadata consumed by the left rail
│           ├─ _index/route.tsx           # Workspace dashboard surface
│           ├─ documents/
│           │  ├─ route.tsx               # Documents boundary (renders an <Outlet />)
│           │  ├─ _index/route.tsx        # Document list + drawer logic
│           │  └─ $documentId/route.tsx   # Document detail page
│           ├─ configurations/_index/route.tsx
│           ├─ jobs/_index/route.tsx
│           └─ settings/_index/route.tsx
├─ features/                  # Feature-specific APIs, hooks, and UI fragments
├─ shared/                    # Reusable helpers (API client, telemetry, storage)
├─ ui/                        # Headless UI primitives (Button, Input, Alert…)
└─ test/                      # Vitest helpers and setup
```

Workspace chrome (nav, top bar, loader) lives beside the dynamic route under `src/app/routes/workspaces/$workspaceId/` so every workspace screen shares the same boundary.

## Routing

The frontend uses React Router 7 “framework mode” with the official Vite plugin. The setup is intentionally minimal:

- `vite.config.ts` loads `reactRouter()` so the file system under `src/app/routes/**` is the single source of truth.
- `react-router.config.ts` points the plugin at `src/app` and runs in SPA mode (`ssr: false`).
- The plugin auto-discovers `src/app/routes/**` via `src/app/routes.ts` exporting `flatRoutes()`, so no hand-maintained manifest is required.
- Each directory containing a `route.tsx` module becomes a route. Folders map to nested segments, `_index/route.tsx` handles default children, and `$param` directories capture dynamic segments.
- Keep feature logic inside `src/features/**`; route modules stitch features together and host page-level state.
- `src/app/root.tsx` wraps the router `Outlet` with shared providers and adds `ScrollRestoration`.
- `src/app/entry.server.tsx` satisfies the build-time SSR entry that the plugin expects, even though the app currently ships as an SPA.

When adding a new screen:

1. Create the matching directory structure under `src/app/routes/`.
2. Compose feature hooks/components inside the new route module.
3. If the page should appear in the workspace nav, update `src/app/routes/workspaces/$workspaceId/sections.ts`.

## Scripts

| Command               | Description                                     |
| --------------------- | ----------------------------------------------- |
| `npm run dev`         | Start the Vite dev server with HMR              |
| `npm run build`       | Type-check and create the production bundle     |
| `npm run preview`     | Preview the production build locally            |
| `npm run lint`        | Run ESLint with the project rules               |
| `npm test`            | Execute the Vitest suite (jsdom environment)    |
| `npm run test:watch`  | Watch mode for Vitest                           |
| `npm run test:coverage` | Generate coverage metrics                     |

Vitest uses `src/test/setup.ts` to initialise Testing Library and jsdom. Use `src/test/test-utils.tsx` to render hooks/components under the shared providers.

## Telemetry

`src/shared/telemetry/events.ts` exposes a `trackEvent` helper. It currently logs to the console during development and will be wired to the backend telemetry endpoint once available.

## Accessibility & Keyboard Support

- Focus-visible outlines are provided by the shared UI primitives.
- The inspector traps focus when open and closes with <kbd>Esc</kbd>.
- `header`, `nav`, `main`, and `aside` landmarks are present so screen readers understand layout.
- Focus mode can be toggled from the top bar and automatically hides navigation panels.

## Next Steps

- Replace placeholder configuration data with real API integrations.
- Flesh out Jobs, Members, and Settings routes as backend endpoints become available.
- Wire telemetry helper to the backend event stream.
