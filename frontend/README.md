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
│  ├─ AppProviders.tsx        # React Query providers (used by the root route)
│  ├─ root.tsx                # Root route wrapping the router <Outlet />
│  ├─ entry.server.tsx        # SSR entry so the plugin can build
│  └─ routes/                 # File-based route modules (auth, workspaces, documents…)
│     ├─ app/route.tsx        # Session gate → renders <Outlet /> on success
│     ├─ workspaces/          # Workspace directory + helpers
│     │  ├─ route.tsx         # Parent route (<Outlet />)
│     │  ├─ WorkspaceDirectoryLayout.tsx
│     │  ├─ new/route.tsx
│     │  └─ $workspaceId/
│     │     ├─ route.tsx      # Workspace layout + provider + nav
│     │     ├─ loader.ts      # Workspace prefetch/redirect logic
│     │     ├─ GlobalTopBar.tsx / WorkspaceNav.tsx / ProfileDropdown.tsx
│     │     ├─ configurations/_index/route.tsx
│     │     ├─ documents/route.tsx + nested index/detail routes
│     │     └─ settings/_index/route.tsx
├─ features/                  # Feature-specific APIs, hooks, models
├─ shared/                    # Reusable helpers (API client, telemetry, storage)
├─ ui/                        # Headless UI primitives (Button, Input, Alert…)
└─ test/                      # Vitest helpers and setup
```

The workspace layout (see `src/app/routes/workspaces/$workspaceId/WorkspaceLayout.tsx`) follows a four-part hierarchy:

1. **Top bar** — global controls (workspace switcher, search, help, profile) plus toggles for the left rail and focus mode.
2. **Left rail** — primary navigation between workspace sections. Collapsible/overlay and persists state per workspace.
3. **Main content** — primary work surface (documents list, configuration summary, etc.). Tabs are reserved for alternate views within the same page.
4. **Right inspector** — contextual detail panel that opens on demand (documents and configurations today). Closes via ESC, header button, or focus mode.

Focus mode hides both rails so the main surface runs edge-to-edge. Navigation state is persisted in `localStorage` on a per-workspace basis.

### Command palette & shortcuts

- Press `⌘K` / `Ctrl+K` or use the search chip in the top bar to open the command palette for fast navigation and actions.
- Toggle focus mode with `Shift+F` (or the toolbar buttons) to collapse chrome around the primary work surface.
- `Esc` closes overlays such as the inspector, command palette, or mobile navigation.
- The left rail footer mirrors quick actions (focus mode, collapse/expand) so keyboard and pointer workflows stay in sync.
- The top bar becomes sticky with a soft shadow once you scroll, and overlays lock background scrolling to keep the focus on the active surface.
- A workspace summary card anchors the left rail with badge status and a quick "Manage workspace" action, mirroring established best-in-class admin consoles.
- Document navigation lives entirely in the left rail (All, Recent, Pinned, Archived), while workspace/admin settings move into the profile menu — a layout similar to SharePoint and other modern hubs.

## Routing

The frontend uses React Router 7 “framework mode” (file-based routing):

- `react-router.config.ts` points the plugin at `src/app` and leaves SSR enabled for builds.
- `src/app/routes.ts` mirrors the file tree so the React Router Vite plugin can resolve routes during builds (keep it in sync with `src/app/routes/**`).
- Each file under `src/app/routes/**/route.tsx` is a route module. Folders map to nested segments, `_index/route.tsx` handles default children, and `$param` directories capture dynamic segments.
- Keep feature logic inside `src/features/**`; route modules stitch features together and host page-level state. The legacy `AppRouter.tsx` has been removed—do not reintroduce it.
- `src/app/root.tsx` wraps the router `Outlet` with `AppProviders`, and `src/app/entry.server.tsx` satisfies the build-time SSR entry that the plugin expects.
- Workspace chrome (nav, top bar, loader) lives beside the dynamic route under `src/app/routes/workspaces/$workspaceId/` so every workspace screen shares the same boundary.

When adding a new screen:

1. Create the matching directory structure under `src/app/routes/`.
2. Compose feature hooks/components inside the new route module.
3. If the page should appear in the workspace nav, update `src/app/routes/workspaces/$workspaceId/sections.ts`.

## Scripts

| Command            | Description                                   |
| ------------------ | --------------------------------------------- |
| `npm run dev`      | Start the Vite dev server with HMR             |
| `npm run build`    | Type-check and create the production bundle   |
| `npm run preview`  | Preview the production build locally          |
| `npm run lint`     | Run ESLint with the project rules              |
| `npm test`         | Execute the Vitest suite (jsdom environment)  |
| `npm run test:watch` | Watch mode for Vitest                       |
| `npm run test:coverage` | Generate coverage metrics                |

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
