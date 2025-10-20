## frontend/AGENTS.md

### Frontend Structure

```
frontend/
├─ src/
│  ├─ app/
│  │  ├─ AppProviders.tsx        # shared React Query providers
│  │  ├─ root.tsx                # <Layout/><Outlet/> shell
│  │  ├─ entry.client.tsx        # HydratedRouter entry
│  │  ├─ entry.server.tsx        # SSR entry (disabled in SPA mode but kept for parity)
│  │  ├─ routes.ts               # flatRoutes() → file-based discovery
│  │  └─ routes/
│  │     ├─ _index.tsx           # /
│  │     ├─ login.tsx            # /login
│  │     ├─ auth.callback.tsx    # /auth/callback
│  │     ├─ setup._index.tsx     # /setup
│  │     ├─ workspaces._index.tsx
│  │     ├─ workspaces.new.tsx
│  │     ├─ workspaces.$workspaceId._index.tsx
│  │     ├─ workspaces.$workspaceId.configurations._index.tsx
│  │     ├─ workspaces.$workspaceId.documents._index.tsx
│  │     ├─ workspaces.$workspaceId.documents.$documentId._index.tsx
│  │     ├─ workspaces.$workspaceId.jobs._index.tsx
│  │     ├─ workspaces.$workspaceId.settings._index.tsx
│  │     └─ $.tsx                # catch-all 404
│  ├─ features/                  # feature-driven modules (auth, documents, jobs, …)
│  ├─ shared/                    # cross-feature helpers (api client, config, storage, hooks)
│  │  └─ types/                  # shared TS types (OpenAPI output lands here)
│  ├─ test/                      # vitest setup + helpers
│  └─ ui/                        # reusable presentational components
├─ react-router.config.ts        # { appDirectory: "src/app", ssr: false }
├─ vite.config.ts                # plugin + dev proxy (/api → :8000)
├─ package.json
└─ .env.example                  # VITE_* variables only
```

### Commands

```bash
# from repo root
npm run dev       # runs React Router dev (:5173) and backend if present
npm run test      # runs frontend tests if present
npm run build     # react-router build → copied into backend/app/web/static by root build
npm run openapi-typescript   # refresh backend schema + regenerate src/shared/types/api.d.ts
```

### Routing & naming rules (framework mode)

* **Index route:** `_index.tsx` → `/segment` index.
* **Dynamic params:** `$id` → `:id` in URL.
* **Nested segments:** `parent.child.tsx` → `/parent/child`.
* **Pathless layout:** leading `_` segment is layout-only.
* **Catch-all:** `$.tsx`.
* Use `clientLoader` / `clientAction` in SPA mode for data/mutations.

### Data & API calls

* Use **relative** paths (`/api/v1/...`); dev proxy forwards to backend.
* Centralize fetch logic in `src/shared/api.ts`.
* Regenerate backend client types with `npm run openapi-typescript` → writes `src/shared/types/api.d.ts`.

### Tests

* Unit tests via `vitest`.
* Prefer co-locating tests near features/routes where helpful; use `src/test/test-utils.tsx` for shared providers.

### Do / Don’t

* **Do** keep page UI in `src/app/routes/**`; extract shared UI to `src/ui/**`.
* **Do** keep cross-route logic in `src/features/**` or `src/shared/**`.
* **Don’t** hand-roll route discovery—use `react-router routes --json`.
* **Don’t** hardcode absolute API origins; use relative `/api` paths.
