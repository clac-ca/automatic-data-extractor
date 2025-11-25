## Frontend Structure (Routerless, Screen-First)

```
apps/ade-web/
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
   ├─ schema/                      # Curated, app-facing type exports
   ├─ generated-types/             # Raw OpenAPI-derived types (openapi.d.ts)
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
npm run build      # Vite build output (copied into apps/ade-api/src/ade_api/web/static by ade build)
npm run test       # Vitest test suite
npm run lint       # ESLint (frontend)
ade openapi-types  # regenerate TS types from the FastAPI schema
```

### Notes

* Co-locate screen-specific components under the owning screen. Promote to `shared/` or `ui/` only when reuse emerges.
* Keep OpenAPI types in `generated-types/`. Run `ade openapi-types` after backend schema changes.
* Import API contracts from `@schema` instead of the raw generated file. Extend `src/schema/` when new types are needed.
* Prefer the shared API client and generated types for HTTP interactions.

---

## Agent Guidelines (apps/ade-web)

This app is a **Vite + React + TypeScript SPA** built to be boringly predictable. Follow these guidelines to keep it easy to understand and extend.

### 1. Mental model

Think in three layers:

1. **App shell** – global providers, layout, navigation wiring (`src/app`).
2. **Screens** – URL-addressable pages and big experiences (`src/screens`).
3. **Primitives & shared helpers** – reusable UI and utilities (`src/ui`, `src/shared`).

Screens are thin: they **compose** things, they don’t invent new infra.

---

### 2. Folder contracts

- `src/app/`
  - Bootstrapping and global wiring only: React root, providers, layout shell, navigation utilities.
- `src/screens/`
  - One folder per **screen** (page), with an `index.tsx`.
  - Subfolders like `sections/` and `components/` are allowed, but keep them screen-specific.
  - Put **screen-specific logic and UI** here.
- `src/ui/`
  - Small, reusable, **a11y-correct** UI primitives (e.g., Tabs, Button, Dialog, PageState).
  - No business logic, no data fetching.
- `src/shared/`
  - Cross-cutting non-UI helpers: HTTP client, auth context, storage helpers, env, tiny utilities.
- `src/schema/`
  - Human-authored, app-facing types (and curated re-exports from generated types).
- `src/generated-types/`
  - Auto-generated types (e.g., OpenAPI). **Never edit manually.**

If you’re not sure where something goes: default to co-locating it under the **screen** that uses it.

---

### 3. Navigation

- We use a **router-less model** based on the History API:
  - A `NavProvider` exposes `useLocation` and `useNavigate`.
  - A pure `ScreenSwitch` turns `location.pathname` (and sometimes query params) into “which screen/section to render”.
- When you add or change screens:
  - Update the central switch logic explicitly.
  - Keep path → screen mapping **simple and obvious** (no hidden routing magic).
- Deep links must work:
  - Direct navigation + browser refresh should always land on the correct screen/section.
  - Prefer keeping important view state (like selected workspace section or builder tab) in the URL.

---

### 4. State model

- **Server state** (data from the backend):
  - Use the established data layer (e.g., React Query + HTTP helpers in `shared/api`).
  - Don’t copy server data into local state unless absolutely necessary.
- **UI state** (tabs, selection, filters, open/closed panels):
  - Use local React state or small reducers **inside the relevant screen/section**.
  - For larger experiences (like the Config Builder), keep their UI state in a small `state/` module under that section.
- **Derived state**:
  - Compute on the fly from server + UI state.
  - Avoid storing the same value in multiple places.

---

### 5. Types

- Prefer importing app types from **`@schema`**.
- Generated types live in **`@generated-types`**; treat them as low-level building blocks, not the main API.
- It’s normal to define small domain types for UI and derived models (e.g., editor file, workspace section enum, dirty state). Put those in `schema/` or in a local `types/` under the relevant screen/section.

---

### 6. UI primitives

- Use `src/ui` primitives for:
  - Tabs, Dialogs, Buttons, Inputs, generic layout components, etc.
- Tabs and other primitives should already handle:
  - Correct ARIA roles, keyboard behavior, and focus management.
- Do **not** create ad-hoc tab strips or modals; improve the shared primitive instead.

---

### 7. How to extend the app

When you add new functionality:

1. **New page or major experience**  
   - Create a folder under `src/screens/YourScreen` with `index.tsx`.
   - Wire it into the central screen switch.
2. **New sub-area inside a screen**  
   - Create `sections/SubArea/index.tsx` under the relevant screen.
3. **Reusable pieces**  
   - If you reuse a UI widget in multiple places, move it into `src/ui/`.  
   - If you reuse a non-UI helper, move it into `src/shared/`.
4. **Types**  
   - Add or refine app-facing types in `src/schema/`, not next to generated types.

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
