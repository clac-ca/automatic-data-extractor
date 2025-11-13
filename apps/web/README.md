# ADE Web SPA (apps/web)

The ADE web client is a Vite-powered React single-page application that uses a lightweight history provider instead of React Router. Screens own their sections, hooks, and components so engineers (or AI agents) can find everything a surface needs in one folder.

## Key commands

```bash
npm install          # install dependencies
npm run dev          # start the Vite dev server on http://localhost:5173
npm run build        # create a production bundle copied into the FastAPI image
npm run test         # run Vitest + Testing Library
npm run openapi-typescript  # regenerate TypeScript types from the FastAPI schema
```

## Project layout

```
src/
├─ main.tsx                  # Vite bootstrap → renders <App />
├─ app/                      # Providers, navigation, and global shell chrome
│  ├─ App.tsx                # Wraps providers + <ScreenSwitch />
│  ├─ AppProviders.tsx       # React Query + shared providers
│  └─ nav/                   # History API helpers (NavProvider, Link, urlState)
├─ screens/                  # Screen-first folders (Home, Login, Workspace, …)
│  └─ Workspace/             # Sections + Config Builder module, co-located widgets
├─ shared/                   # Cross-cutting utilities (auth, API, storage, etc.)
├─ ui/                       # Presentational primitives (Button, Tabs, Dialog, …)
├─ schema/                   # Curated, stable type re-exports for UI code
├─ generated-types/          # Raw OpenAPI output (do not import directly)
└─ test/                     # Vitest setup + helpers
```

### Navigation & URL helpers

* React Router has been removed. `NavProvider` in `src/app/nav/history.tsx` exposes `useLocation`, `useNavigate`, and `<Link/NavLink>` wrappers that rely on the browser History API.
* `ScreenSwitch` inside `src/app/App.tsx` matches `window.location.pathname` and selects the right screen. Add new surfaces by extending that switch statement.
* URL query helpers live in `src/app/nav/urlState.ts` and power shareable Config Builder links.
* Config Builder deep links rely on `file`, `view`, `console`, and `pane` query parameters (e.g. `?file=/src/ade_config/hooks.py&view=split&console=open&pane=problems`). Use the helpers in `urlState.ts` to parse/merge them.

### Type layering

* Run `npm run openapi-typescript` whenever the FastAPI schema changes; it overwrites `src/generated-types/openapi.d.ts`.
* UI code imports API shapes from `@schema` (see `src/schema/index.ts`). The generated file is implementation detail guarded by ESLint so we can evolve curated types safely.

### Testing & QA

* `@test/test-utils` wraps renders with `NavProvider` and `AppProviders` so most tests can call `render(<Component />)` directly.
* Add navigation or section tests under `src/app/nav/__tests__` and `src/screens/<Screen>/__tests__/` to exercise the routerless behavior.
* Before committing, run `npm run test`. The full CI pipeline (`npm run ci`) runs lint, type-checks, tests, and the production build.
