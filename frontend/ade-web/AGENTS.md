## Frontend Structure (React Router v7, Standard Vite Layout)

```
frontend/ade-web/
├─ package.json
├─ package-lock.json
├─ vite.config.ts
├─ index.html
└─ src/
   ├─ main.tsx                     # Vite entry point → renders <RouterProvider />
   ├─ app/                         # App shell, routing, and layouts
   │  ├─ routes.tsx                # Route definitions
   │  ├─ router.tsx                # createBrowserRouter wiring
   │  └─ layouts/                  # App layouts (AppShell, PublicLayout, WorkspaceLayout, ...)
   ├─ providers/                   # AppProviders + auth/theme/notifications
   ├─ api/                         # HTTP client + domain API calls
   ├─ pages/                       # Route-level pages (Home, Login, Workspace, ...)
   ├─ components/                  # Shared UI + navigation + layout primitives
   │  ├─ topbar/                   # Global top bar + actions
   │  ├─ layout/                   # Reusable layout components (PageState, ...)
   │  ├─ ui/                       # Buttons, inputs, dialogs, etc. (shadcn)
   │  └─ icons.tsx                 # Icon exports
   ├─ hooks/                       # React Query + shared app hooks
   ├─ lib/                         # Cross-cutting utilities (storage, uploads, preferences)
   ├─ types/                       # Human-authored, app-facing type exports
   │  └─ generated/                # Raw OpenAPI-derived types (never edit)
   ├─ test/                        # Vitest setup + helpers
   └─ index.css                    # Global styles + theme tokens
```

### Navigation & URL helpers

* The app uses **React Router v7 (data router)**.
* Route definitions live in `src/app/routes.tsx`; the router is created in `src/app/router.tsx`.
* Use `react-router-dom` hooks/components directly:
  * `useNavigate`, `useLocation`, `useSearchParams`, `Link`, `NavLink`, `generatePath`, `createSearchParams`.

### Commands

```
npm run dev        # Vite dev server
npm run build      # Vite build output in frontend/ade-web/dist (serve via web server or reverse proxy)
npm run test       # Vitest test suite
npm run lint       # ESLint (frontend)
ade api types      # regenerate TS types from the FastAPI schema
```

### Notes

* Co-locate page-specific components under the owning page. Promote to `components/`, `hooks/`, `api/`, or `lib/` only when reuse emerges.
* Keep OpenAPI types in `types/generated/`. Run `ade api types` after backend schema changes.
* Import app types from `@/types` and `@/types/generated` as needed.
* Prefer the shared API client and generated types for HTTP interactions.

---

## Agent Guidelines (frontend/ade-web)

This app is a **Vite + React + TypeScript SPA** built to be boringly predictable. Follow these guidelines to keep it easy to understand and extend.

### 1. Mental model

Think in three layers:

1. **App shell** – global providers, layout, navigation wiring (`src/app/layouts/`, `src/app/routes.tsx`, `src/providers/`).
2. **Pages** – URL-addressable pages and big experiences (`src/pages`).
3. **Shared building blocks** – reusable UI + app infrastructure (`src/components`, `src/api`, `src/hooks`, `src/lib`).

Screens are thin: they **compose** things, they don’t invent new infra.

---

### 2. Folder contracts

- `src/`
  - `app/routes.tsx`, `app/router.tsx`, and `app/layouts/` for routing + layout shells.
- `src/app/layouts/`
  - App-level layouts and shell containers.
- `src/providers/`
  - AppProviders + auth/theme/notifications providers.
- `src/pages/`
  - One folder per **page**, with an `index.tsx`.
  - Subfolders like `sections/` and `components/` are allowed, but keep them page-specific.
- `src/components/`
  - UI primitives under `components/ui/`.
  - Shared top bar chrome under `components/topbar/`.
  - Reusable layout helpers under `components/layout/`.
- `src/api/`
  - HTTP client + domain API calls (no React).
- `src/hooks/`
  - Shared React hooks (React Query hooks, global app hooks).
- `src/lib/`
  - Cross-cutting helpers (storage, uploads, local preferences).
- `src/index.css`
  - Global styles and theme tokens.
- `src/types/`
  - Human-authored, app-facing types (and curated re-exports from generated types).
- `src/types/generated/`
  - Auto-generated types (e.g., OpenAPI). **Never edit manually.**

If you’re not sure where something goes: default to co-locating it under the **page** that uses it.

---

### 3. Navigation

- We use **React Router v7** with a central route config.
- Route wiring lives in `src/routes.tsx` and `src/router.tsx`.
- When you add or change pages:
  - Update the route table explicitly.
  - Keep path → page mapping **simple and obvious** (no hidden routing magic).
- Deep links must work:
  - Direct navigation + browser refresh should always land on the correct screen/section.
  - Prefer keeping important view state (like selected workspace section or builder tab) in the URL.

---

### 4. State model

- **Server state** (data from the backend):
  - Use the established data layer (e.g., React Query + HTTP helpers in `api/`).
  - Don’t copy server data into local state unless absolutely necessary.
- **UI state** (tabs, selection, filters, open/closed panels):
  - Use local React state or small reducers **inside the relevant screen/section**.
  - For larger experiences (like the Config Builder), keep their UI state in a small `state/` module under that section.
- **Derived state**:
  - Compute on the fly from server + UI state.
  - Avoid storing the same value in multiple places.

---

### 5. Types

- Prefer importing app types from `@/types`.
- Generated types live in `@/types/generated`; treat them as low-level building blocks, not the main API.
- It’s normal to define small domain types for UI and derived models (e.g., editor file, workspace section enum, dirty state). Put those in `types/` or in a local `types/` under the relevant page/section.

---

### 6. UI primitives

- Use `src/components/ui` primitives for:
  - Tabs, Dialogs, Buttons, Inputs, generic layout components, etc.
- Tabs and other primitives should already handle:
  - Correct ARIA roles, keyboard behavior, and focus management.
- Do **not** create ad-hoc tab strips or modals; improve the shared primitive instead.

#### UI primitives governance

- `src/components/ui/*` is **generated but owned** code (DiceUI/shadcn). Updates happen by re-running the install commands and reconciling diffs.
- Prefer theme tokens and global styles before editing primitives.
- Editing primitives is allowed, but must be **minimal** and documented:
  - Add a short comment in the file.
  - Record the change in `src/components/ui/README.md`.
- App-specific composite UI must **not** live in `src/components/ui`; keep it under page/feature folders (for example, `src/pages/**/components/`).

---

### 7. How to extend the app

When you add new functionality:

1. **New page or major experience**  
   - Create a folder under `src/pages/YourPage` with `index.tsx`.
   - Wire it into `src/routes.tsx`.
2. **New sub-area inside a page**  
   - Create `sections/SubArea/index.tsx` under the relevant page.
3. **Reusable pieces**  
   - UI widgets → `src/components/ui/` or `src/components/layout/`.  
   - Navigation chrome → `src/components/topbar/`.  
   - API calls → `src/api/`.  
   - Shared React hooks → `src/hooks/`.  
   - Non-React helpers → `src/lib/` (uploads, storage, etc.).  
4. **Types**  
   - Add or refine app-facing types in `src/types/`.

---

### 8. Style & clarity

- Favor clear names over clever ones.
- Keep side-effects (fetching, navigation, subscriptions) near the top of components.
- Break complex screens into:
  - “Data / hooks”
  - “Decision / mapping”
  - “View / JSX”
- If it’s hard to explain what a module does in one sentence, consider splitting it.

The goal is that any agent—or human—can open `src/`, skim the folders, and immediately understand where to look and where to add new code.
