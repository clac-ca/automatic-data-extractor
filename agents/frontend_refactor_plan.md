# Work Package: ADE Frontend v3 — Future‑Ready React Router Design
## 1) Business context

**Problem.** The legacy SPA shows inconsistent routing/layout/state patterns. This slows delivery, hurts a11y/testability, and increases bundle bloat.

**Desired outcomes (measurable):**

* **30-40% faster lead‑time** to add a feature view via route‑module scaffolds and shared app‑shell patterns.
* **UX consistency:** One shell everywhere; uniform navigation interactions; zero one‑off layouts.
* **Reliability:** green CI (lint/type/test/build) on every PR; e2e smoke on `main`.
* **A11y:** WCAG 2.2 AA baseline, keyboard‑complete navigation. ([W3C][6])
* **Performance:** unauthenticated shell **p75 LCP <= 2.5s** on “Fast 3G/Slow 4G” simulated; unauth JS <= 300 KB gz (route code‑split by default). ([reactrouter.com][7])

---

## 2) Scope

**In-scope**

* New **React Router Framework Mode SPA** built with Vite and file-based routes (no SSR/pre-render on day one). ([reactrouter.com][8])
* Lean **App Shell** with Header, Sidebar, and Content regions plus shared providers.
* Static navigation config with a simple `canSee()` capability helper.
* Data layer: **TanStack Query** for all data fetching; loaders limited to auth/workspace guards and param validation. ([reactrouter.com][3])
* Auth/session flows, workspaces, documents list/canvas skeleton, configurations skeleton, jobs, settings.
* Test harness (Vitest + Testing Library) and a single Playwright smoke path.
* Docker build; served as static files via FastAPI (HTML fallback for SPA routes). ([reactrouter.com][8])

**Out‑of‑scope**

* Domain UX re‑imagining beyond shell contracts.
* Backend API/RBAC changes.
* Full design system library & visual regression (follow‑on).

**Assumptions**

* Stable backend OpenAPI; static hosting via FastAPI; existing session/tenancy semantics.

**Constraints**

* Keep CI green; non‑disruptive releases.
* RFC for heavy deps.

---

## 3) Principles & guardrails

* **Ship SPA first.** Framework Mode SPA without SSR or pre-render; revisit only if metrics demand it. ([reactrouter.com][8])
* **Keep the shell lean.** A single AppShell with Header, Sidebar, and Content—features own any extra UI they need.
* **Query-first data.** Fetch via TanStack Query; use loaders solely for auth/workspace guards and parameter validation. ([reactrouter.com][3])
* **File routes only.** Co-locate route modules with their components for discoverability and boring maintenance. ([reactrouter.com][12])
* **Accessibility basics.** Landmarks, skip link, and focus restoration; add richer patterns when real requirements appear. ([reactrouter.com][4])
* **Small surface area.** Prefer standard library / existing deps; defer speculative abstractions, tokens, and perf tooling.
* **Deterministic tests.** Lint, typecheck, unit tests, and one Playwright smoke path keep confidence without slowing delivery.
* **Boring error handling.** Start with a root error boundary and explicit 404 route; add feature-specific boundaries later if needed.
---

## 4) Solution overview

### Why Framework Mode SPA?

* React Router's Framework Mode delivers file-based routing, code-splitting, and dev tooling with minimal glue code—perfect for a focused SPA. ([reactrouter.com][1])
* Staying SPA-only keeps the stack simple while leaving room to revisit SSR later if metrics demand it.

### Stack & key deps

* **React Router v7 (Framework Mode)** + `@react-router/dev` (Vite plugin, typegen). ([reactrouter.com][1])
* Vite + React 18/19 + TypeScript.
* TanStack Query, Tailwind CSS (with a minimal shared palette), Zod, Testing Library + Vitest, MSW, Playwright, OpenAPI generator.

---

## 5) Target folder structure (Framework Mode, SPA)

```
frontend/
  app/                         # Framework Mode app root
    root.tsx                   # App shell layout, <Scripts/>, <ScrollRestoration/>
    routes/                    # Route modules (file-route conventions)
      _index.tsx               # Public landing route
      login.tsx
      setup.tsx
      workspaces.$wsId.tsx             # parent route module (acts as layout)
      workspaces.$wsId.documents._index.tsx
      workspaces.$wsId.documents.$docId.tsx
      workspaces.$wsId.configurations._index.tsx
      workspaces.$wsId.jobs._index.tsx
      workspaces.$wsId.settings._index.tsx
    features/                  # Feature internals reused across routes
      auth/
      navigation/
      documents/
      configurations/
      jobs/
      settings/
    shared/
      api/                     # apiClient, OpenAPI types, error mapping
      components/              # primitives (Button, Input, Card) shared across routes
      hooks/                   # shared hooks (e.g., useCanSee, focus helpers)
      providers/               # QueryClient and other global providers
      styles/                  # tailwind.css and minimal shared palette
      testing/                 # test utils
  public/
  vite.config.ts
  react-router.config.ts
  tsconfig.json
  tailwind.config.ts
```

*Notes*

* **File-route conventions are required.** Every route lives in `app/routes/**`; no alternate router entrypoint is maintained.
* `root.tsx` holds **landmarks**, app providers, and the **app shell** with `<Outlet/>`.
* Authenticated sections nest under `workspaces.$wsId.tsx`, which acts as the parent layout route without a separate `_layout` file.
* Route filenames encode **URL params** (e.g., `$wsId`, `$docId`) and nest under workspace.

---

## 6) Routing & data strategy

**Routing**

* The root route hosts the AppShell and shared providers; mount `/login`, `/setup`, and the authenticated parent route (`workspaces.$wsId.tsx`) beneath it.
* Stick to file-based routes only—no alternate router configuration paths.
* Keep `react-router.config.ts` minimal and SPA-focused:

```ts
// react-router.config.ts
import type { Config } from "@react-router/dev/config";

export default {
  ssr: false,
  appDirectory: "app",
  buildDirectory: "build",
} satisfies Config;
```

**Data loading & mutation**

* Loaders guard access (auth, workspace existence) and normalize params; they do **not** fetch page payloads.
* Screen data flows through TanStack Query hooks inside components to avoid duplicate fetch logic. ([reactrouter.com][3])
* Mutations rely on Query invalidation/optimistic updates; prefer `useMutation` patterns over loader-side side effects.

**Concurrency & revalidation**

* Query caching plus React Router request cancellation keeps stale data at bay without extra wiring. ([reactrouter.com][13])

**Type safety**

* Enable **route-module typegen** (`react-router typegen`) and include `.react-router/types` in `tsconfig`; wire typegen to CI before `tsc`. ([reactrouter.com][2])
---

## 7) App Shell & navigation

* AppShell provides `header`, `nav`, and `main` landmarks with a skip link and focus restoration; features supply any extra UI such as inspectors or banners. ([reactrouter.com][4])
* Navigation starts from a static route list plus a simple `canSee(route)` helper sourced from session claims; breadcrumbs still derive from route matches.
* Defer view transitions and keyboard shortcuts until a concrete requirement emerges.
---

## 8) Data & API layer

* **OpenAPI types** generated at build (`api:gen`) into `shared/api/types.ts`, sourced from a pinned `frontend/app/shared/api/openapi.json` artifact checked into the repo and rotated alongside backend releases (no live HTTP fetch in CI).
* Lightweight `apiClient` wrapper (base URL, JSON, auth interceptors, error mapping).
* **TanStack Query**:
  * Provide `QueryClient` defaults (documented below) tuned for API volatility.
  * **In loaders:** use `queryClient.ensureQueryData` to warm cache (blocking) and `prefetchQuery` for non-blocking background data. ([TanStack][14])
* **State Management:** favor **URL/route data** over global stores; most apps can skip additional global state if they lean on route data + fetchers. ([reactrouter.com][15])
## 9) Authentication, security & session

* **Auth flows:** login/logout, token/CSRF handling consistent with backend; 401 → forced logout + Query cache reset.
* **Route guards** via loaders: bounce unauthenticated users to `/login` and ensure **workspace** is present (`/workspaces/:wsId`).
* **Security:**

  * Prepare for **CSP nonces** (`<Scripts nonce>`) if a strict CSP is applied. ([reactrouter.com][16])
  * **Error sanitization** is handled for server‑side errors when SSR is enabled later; still implement client‑side boundaries now. ([reactrouter.com][9])

---

## 10) Accessibility

* WCAG 2.2 AA baseline: focus management after navigation, live‑region announcements for route changes, visible focus, skip link, ARIA for menus/dialogs, reduced motion. ([reactrouter.com][4])

---

## 11) Performance approach & budgets

* Route-level code splitting (built into Framework Mode) keeps the initial bundle slim. ([reactrouter.com][7])
* Skip pre-render until metrics show a need—serve everything via SPA today and revisit later.
* Enforce the unauthenticated shell <= 300 KB gz with `npx size-limit --why` and avoid heavy dependencies in the AppShell path.
## 12) Testing & CI

* **Unit/integration:** Vitest + Testing Library; use `createRoutesStub` when components need router context. ([reactrouter.com][10])
* **MSW** for API mocks shared by unit and e2e.
* **Playwright smoke**: `/login` -> auth redirect -> `/workspaces/:wsId/documents` -> open a document details view.
* **Bundle budget:** enforce unauth shell size <= 300 KB gz with `npx size-limit --why` (fails CI on regression).
* **CI gates:** `lint`, **`react-router typegen`**, `typecheck`, `test --run`, `size-limit`, `build`. ([reactrouter.com][2])
## 13) Observability

* Console log key UX events during MVP; add structured tracking/Sentry once usage warrants it.

---

## 14) Deliverables

1. **Framework Mode SPA scaffold** (`frontend/app`, Vite, `@react-router/dev`, file routes, typegen wired). ([reactrouter.com][8])
2. **Lean App Shell** with Header, Sidebar, Content regions plus skip link and focus restoration. ([reactrouter.com][4])
3. **Navigation** via a static config and `canSee()` helper, with breadcrumbs derived from route matches.
4. **Auth/Session** flows (login/logout/refresh) with workspace guard loaders and Query cache reset on 401s.
5. **Feature skeletons** for Documents, Configurations, Jobs, and Settings (lists/placeholders powered by Query hooks).
6. **Typed API client** generated from pinned `frontend/app/shared/api/openapi.json` with a documented rotation process.
7. **Tailwind styling** with a minimal shared palette and component primitives.
8. **Performance guardrail**: unauth shell <= 300 KB gz enforced by `size-limit`.
9. **Quality gates**: Vitest/MSW, one Playwright smoke, lint/typecheck/typegen/build/size-limit. ([reactrouter.com][10])
10. **Docs** (`README`, architecture notes, migration checklist).
## 15) Non‑functional requirements

* **A11y:** WCAG 2.2 AA via skip link, landmarks, focus restoration, and keyboard parity for the main shell. ([reactrouter.com][4])
* **Perf:** Route-level code splitting plus the 300 KB gz shell budget keep load times predictable; LCP targets are monitored but not hard-gated until real data arrives. ([reactrouter.com][7])
* **Security:** CSP-nonce ready, XSS-safe rendering, and 401 interception → logout remain mandatory. ([reactrouter.com][16])
* **Observability:** Console logging for key UX events; expand to structured telemetry/Sentry later.

------

## 16) Phased execution plan

### Phase 0 — Project bootstrap

* Scaffold the Framework Mode SPA with `@react-router/dev` and Vite.
* Add scripts: `dev`, `build`, `preview`, `lint`, `typegen`, `typecheck`, `test`, `format`, `api:gen`, `size-limit`.
* Configure ESLint/Prettier, Tailwind base styles, and QueryClient provider in `root.tsx`.
  **Exit:** `vite build` and Vitest pass; root route renders with landmarks. ([reactrouter.com][8])

### Phase 1 — Routing & shell

* Implement the lean AppShell (Header, Sidebar, Content) with skip link and focus restoration.
* Add file routes for `/login`, `/setup`, and `/workspaces/:wsId/*`; wire loaders for auth/workspace guards only. ([reactrouter.com][9])
  **Exit:** Keyboard-only smoke confirms navigation across header → sidebar → content.

### Phase 2 — Data & API

* Generate OpenAPI types from the pinned schema; flesh out the shared `apiClient`.
* Establish TanStack Query defaults (`staleTime`, `gcTime`, retry policy) and shared hooks (`useSession`, `useWorkspaces`).
  **Exit:** Documents list screen reads data purely via Query with no duplicate fetches.

### Phase 3 — Navigation & auth polish

* Build the static navigation config + `canSee()` helper sourced from session claims.
* Add breadcrumbs from route matches and ensure 401s trigger logout + Query reset.
  **Exit:** Capability changes update nav visibility after a session refetch.

### Phase 4 — Feature skeletons

* Documents, Configurations, Jobs, Settings routes render list/placeholder UIs backed by Query hooks.
* Provide sensible empty/error states; keep Inspector/secondary UI local to routes.
  **Exit:** Loading, empty, and error states verified for each skeleton.

### Phase 5 — Testing & CI hardening

* Add Vitest coverage for AppShell landmarks, auth guard behaviour, and nav visibility.
* Wire MSW fixtures and a single Playwright smoke (login → documents list → open doc).
* CI order: `lint` → `react-router typegen` → `typecheck` → `test --run` → `size-limit` → `build`. ([reactrouter.com][2])
  **Exit:** CI pipeline green end-to-end; Playwright smoke runs in CI.

### Phase 6 — Cutover readiness

* Validate SPA fallback by deep-linking into `/workspaces/:id/documents` (FastAPI serves `index.html`).
* Compare new routes with `frontend.old` for parity; prepare migration checklist.
  **Exit:** Smoke tests pass against FastAPI fallback; go/no-go checklist signed.
## 17) Acceptance criteria (DoD)

* CI passes: `lint`, **typegen**, `typecheck`, `test --run`, `size-limit`, `build`. ([reactrouter.com][2])
* FastAPI serves `index.html` for every non-`/api/*` GET (`GET /{path:path}` fallback) so deep links hydrate in the SPA.
* AppShell across all authenticated routes; sidebar collapse persists.
* A11y: skip link; focus management after navigation; visible focus; landmarks. ([reactrouter.com][4])
* Navigation rail/panels: keyboard traversal; breadcrumbs reflect route changes.
* Auth/session: 401 → forced logout + QueryClient reset; workspace guard works.
* Feature skeletons use real data (where available) or sensible placeholders.
* Perf budget enforced via `size-limit` (unauth shell <= 300 KB gz) with spot Lighthouse checks as follow-up.
* README/architecture docs updated; commands/envs documented.
---

## 18) Risk register & mitigations

| Risk                       | Impact           | Likelihood | Mitigation                                                                                |
| -------------------------- | ---------------- | ---------: | ----------------------------------------------------------------------------------------- |
| API drift                  | Broken pages     |     Medium | OpenAPI types per build; narrow surface early; smoke tests.                               |
| Route‑module unfamiliarity | Onboarding delay |     Medium | Templates + examples; doc links; enforce typegen CI. ([reactrouter.com][2])               |
| A11y regressions           | Compliance       |     Medium | Shell a11y tests; keyboard‑only QA on nav changes. ([reactrouter.com][4])                 |
| Bundle bloat               | Perf             |     Medium | Route code‑split; analyze chunks; keep heavy libs off shell path. ([reactrouter.com][7])  |
| Concurrency edge cases     | Stale data       |        Low | Depend on router cancellation & revalidation; test fetcher flows. ([reactrouter.com][13]) |

---

## 19) Roles & RACI (lean)

* **Sponsor (Justin):** Accountable for scope, priorities, sign‑off.
* **Frontend Squad Lead:** Responsible for delivery & technical decisions.
* **AI Agent(s):** Implement phases; write tests; keep docs in sync.
* **Backend Lead:** Consulted for API/auth nuances.
* **QA/UX Reviewer:** Consulted for a11y/usability; informed on milestones.

---

## 20) Environment & configuration

* Envs: `VITE_API_BASE_URL`, `VITE_ENV_NAME`, `VITE_SESSION_CSRF_COOKIE_NAME` (if applicable), `VITE_SENTRY_DSN` (optional).
* Build targets: dev/staging/prod (base URLs per env).
* Docker: multi‑stage build; output static files served by FastAPI with **SPA 200 fallback** for route URLs (per SPA mode guidance). ([reactrouter.com][8])

---

## 21) Documentation plan

* `frontend/README.md`: quickstart, scripts, envs, route module primer.
* `docs/frontend-architecture.md`: modes choice, routing, data strategy, tokens, testing, decisions (ADRs).
* `docs/migration-checklist.md`: per‑feature cutover steps.
* `agents/FRONTEND_DESIGN.md`: keep intent in sync.
* Inline TSdoc for shared hooks/components.

---

## 22) Quality gates (CI)

* **Static:** ESLint TS/React, **React Router typegen**, `tsc --noEmit`, and `npx size-limit --why` enforcing the 300 KB gz unauth shell budget. ([reactrouter.com][2])
* **Unit/Integration:** Vitest + Testing Library; use `createRoutesStub` for router-aware units. ([reactrouter.com][10])
* **Build:** `vite build` with chunk size guard (CI uploads bundle stats for regression tracking).
* **E2E smoke:** Playwright minimal flows on `main`.
---

## 23) “Definition of Ready” for each phase

* Dependencies pinned; versions chosen.
* Route contracts known (or typed stubs with TODO).
* Phase acceptance criteria in ticket.
* Rollback plan via feature flag or route switch.

---

## 24) Agent execution checklist (drop into PR)

* [ ] Scaffold Framework Mode SPA with file routes and `@react-router/dev`. ([reactrouter.com][8])
* [ ] Configure Tailwind base styles + minimal palette; wire QueryClient provider in `root.tsx`.
* [ ] Implement lean AppShell (Header/Sidebar/Content), skip link, root error boundary, and 404 route.
* [ ] Add auth/workspace guard loaders and static navigation with `canSee()` helper + breadcrumbs.
* [ ] Generate OpenAPI types from pinned schema; ship shared `apiClient` + Query hooks.
* [ ] Build Documents/Configurations/Jobs/Settings skeleton screens powered by Query data.
* [ ] Implement auth flows (login/logout/refresh) with 401 → logout + Query reset.
* [ ] Add Vitest coverage + one Playwright smoke (login → documents → open doc); ensure CI runs lint → typegen → typecheck → test → size-limit → build. ([reactrouter.com][10])
* [ ] Update README + architecture docs; document OpenAPI rotation and migration checklist.
* [ ] Verify FastAPI SPA fallback (`GET /{path:path}`) handles deep links.

---

## 25) Appendix A — Example route and loader integration with TanStack Query

**`app/routes/workspaces.$wsId.documents.$docId.tsx`**

* `loader`: validate workspace/session access and return `{ wsId, docId }` (no data fetch).
* Component: call `useQuery(docQueryOptions(wsId, docId))`; handle loading/empty/error states locally; invalidate on mutations. ([TanStack][14])

---

## 26) Appendix B — Recommended npm scripts

```
dev         : react-router dev
build       : react-router build
preview     : react-router preview
lint        : eslint . --max-warnings=0
typegen     : react-router typegen
typecheck   : npm run typegen && tsc -p tsconfig.json --noEmit
test        : vitest
test:run    : vitest run
format      : prettier --write .
api:gen     : openapi-typescript app/shared/api/openapi.json -o app/shared/api/types.ts
size-limit  : size-limit
```

---

### References consulted

* **React Router - Picking a Mode, SPA Mode, File Route Conventions, Typegen, Error Boundaries, Testing.** ([reactrouter.com][1])
* **TanStack Query - Query caching, mutations, and invalidation patterns.** ([TanStack][14])
* **React - Starting a new app, CRA sunset (prefer frameworks or modern build tools).** ([React][11])
* **WCAG 2.2 AA (a11y baseline).** ([W3C][6])

---

### Why this sets ADE up for the future

* The app ships as a lightweight SPA with boring file-based routes, keeping the learning curve low while leaving room to add SSR later if business needs change. ([reactrouter.com][1])
* Framework Mode delivers automatic route-level code splitting and predictable error handling without extra tooling. ([reactrouter.com][7])
* A Query-first data model keeps fetching predictable today and can grow into richer caching/optimistic flows as requirements expand. ([reactrouter.com][3])


