## Frontend Structure (Routerless, Screen-First)

```
apps/web/
├─ package.json
├─ package-lock.json
├─ vite.config.ts
├─ index.html
└─ src/
   ├─ main.tsx                     # Vite entry point → renders <App />
   ├─ app/
   │  ├─ App.tsx                   # Providers + <ScreenSwitch />
   │  ├─ AppProviders.tsx          # React Query + shared providers
   │  ├─ nav/                      # History-based navigation helpers
   │  └─ shell/                    # Global chrome (top bar, profile menu, etc.)
   ├─ screens/                     # Screen-first layout (Home, Login, Workspace, …)
   ├─ shared/                      # Cross-cutting utilities (auth, API, storage, …)
   ├─ ui/                          # Reusable presentational primitives
   ├─ generated/                   # OpenAPI-derived types (openapi.d.ts)
   └─ test/                        # Vitest setup + helpers
```

### Navigation & URL helpers

* The app no longer uses React Router. A lightweight history provider powers navigation.
* Use the helpers from `@app/nav`:
  * `NavProvider`, `useNavigate`, `useLocation`, `useSearchParams`
  * `Link`/`NavLink` render `<a>` tags with history-aware click handling.
* Screen selection happens inside `App.tsx` – add new screens by extending the switch logic there.

### Commands

```
npm run dev        # Vite dev server
npm run build      # Vite build output
npm run test       # Vitest test suite
npm run lint       # Ruff (backend) + ESLint (frontend)
```

### Notes

* Co-locate screen-specific components under the owning screen. Promote to `shared/` or `ui/` only when reuse emerges.
* Keep OpenAPI types in `generated/`. Run `npm run openapi-typescript` after backend schema changes.
* Prefer the shared API client and generated types for HTTP interactions.
