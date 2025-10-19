## frontend/AGENTS.md

### Frontend Structure

```
frontend/
├─ src/
│  ├─ root.tsx                 # <Layout/><Outlet/> shell
│  ├─ entry.client.tsx         # HydratedRouter entry
│  ├─ routes.ts                # flatRoutes() → file-based discovery
│  ├─ routes/
│  │  ├─ _index.tsx            # /
│  │  ├─ login.tsx             # /login
│  │  ├─ auth.callback.tsx     # /auth/callback
│  │  ├─ setup._index.tsx      # /setup
│  │  ├─ workspaces._index.tsx # /workspaces
│  │  ├─ workspaces.new.tsx    # /workspaces/new
│  │  ├─ workspaces.$workspaceId._index.tsx
│  │  ├─ workspaces.$workspaceId.configurations._index.tsx
│  │  ├─ workspaces.$workspaceId.documents._index.tsx
│  │  ├─ workspaces.$workspaceId.documents.$documentId._index.tsx
│  │  ├─ workspaces.$workspaceId.jobs._index.tsx
│  │  ├─ workspaces.$workspaceId.settings._index.tsx
│  │  └─ $.tsx                 # catch‑all 404
│  ├─ lib/                     # shared helpers (no UI)
│  │  ├─ api.ts                # API wrapper / client
│  │  ├─ config.ts             # env-driven config (reads VITE_* vars)
│  │  └─ telemetry.ts
│  ├─ components/              # reusable presentational components
│  └─ types/                   # shared TS types (including OpenAPI‑generated later)
├─ react-router.config.ts      # { appDirectory: "src", ssr: false }
├─ vite.config.ts              # plugin + dev proxy (/api → :8000)
├─ package.json
└─ .env.example                # VITE_* variables only
```

### Commands

```bash
# from repo root
npm run dev       # runs React Router dev (:5173) and backend if present
npm run test      # runs frontend tests if present
npm run build     # react-router build → copied into backend/app/static by root build
```

### Routing & naming rules (framework mode)

* **Index route:** `_index.tsx` → `/segment` index.
* **Dynamic params:** `$id` → `:id` in URL.
* **Nested segments:** `parent.child.tsx` → `/parent/child`.
* **Pathless layout:** leading `_` segment is layout‑only.
* **Catch‑all:** `$.tsx`.
* Use `clientLoader` / `clientAction` in SPA mode for data/mutations.

### Data & API calls

* Use **relative** paths (`/api/v1/...`); dev proxy forwards to backend.
* Centralize fetch logic in `src/lib/api.ts`.
* Later, generate types from `/openapi.json` into `src/types` or `src/lib/api.d.ts`.

### Tests

* Unit tests via `vitest`.
* Prefer co‑locating tests near features/routes where helpful.

### Do / Don’t

* **Do** keep page UI in `src/routes/**`; extract shared UI to `src/components/**`.
* **Do** keep cross‑route logic in `src/features/**` or `src/lib/**`.
* **Don’t** hand‑roll route discovery—use `react-router routes --json`.
* **Don’t** hardcode absolute API origins; use relative `/api` paths.