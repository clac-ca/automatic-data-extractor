# Work Package: ADE Frontend v2 — Greenfield Rebuild

## Status

* **Owner:** Frontend Experience Squad
* **Sponsor:** Justin Kropp
* **State:** Ready for execution
* **Last Reviewed:** 2025-10-14
* **Notes:** This WP directs an AI agent to deliver a clean, feature-first React application that replaces the current SPA without disrupting backend APIs or release cadence.

---

## 1) Business context

**Problem.** The current SPA has grown organically; layout, navigation, and state patterns vary by feature, slowing delivery and complicating accessibility and testing.

**Desired outcomes (measurable):**

* **Lead time to add a new feature view** reduced by ≥30%.
* **UX consistency:** app-shell + navigation patterns shared across features; zero “one-off” layouts.
* **Reliability:** green CI (lint/type/test/build) on every PR; e2e smoke on main.
* **A11y:** AA-level baseline; keyboard-complete navigation.
* **Performance:** p75 LCP ≤ 2.5s on “Fast 3G/Slow 4G” simulated, total JS ≤ 300 KB gz for unauth shell.

---

## 2) Scope

**In-scope**

* New React + TypeScript app from scratch (Vite).
* Deterministic **App Shell** with named slots (Header, Sidebar, Content, optional Inspector, ModalPortal, Banner).
* Unified navigation (rail + contextual panels) driven by a typed config and capability checks.
* Standardized data layer (TanStack Query) and typed API client from backend OpenAPI.
* Styling tokens + Tailwind (gradual tokenization).
* Auth/session flows, workspaces, documents list/canvas skeleton, configurations skeleton, jobs, settings.
* Test harness (Vitest + Testing Library) and CI gates; minimal Playwright smoke later.
* Deployment via Docker and FastAPI static mount.

**Out-of-scope**

* Redesigning domain UX beyond the shell/contract.
* Changing backend endpoints or RBAC semantics.
* Full Storybook and visual regression (can be a follow-on WP).

**Assumptions**

* Backend serves OpenAPI; endpoints remain stable.
* Static assets are hosted by FastAPI; Docker multi-stage build available.
* RBAC/tenancy logic already defined server-side.

**Constraints**

* Keep CI green; no disruption to production deploys.
* Avoid adding heavyweight dependencies without a mini-RFC.

---

## 3) Principles & guardrails

* **KISS, feature-first.** Co-locate UI, hooks, tests under `src/features/<domain>`.
* **One shell everywhere.** No page renders outside `AppShell`.
* **Server state with TanStack Query.** Local UI state stays inside features.
* **Typed IO.** Generate types from OpenAPI; validate risky inputs with Zod.
* **Accessible by default.** Landmarks, skip link, focus ring, reduced-motion, keyboard parity.
* **Tokens first.** Shared CSS variables for color/spacing/typography; Tailwind maps tokens.
* **Deterministic routing.** React Router v7 data APIs, layout nesting, error boundaries.
* **Test what matters.** Shell smoke, route guards, critical flows; avoid brittle snapshots.

---

## 4) Deliverables

1. **New repo subtree** `frontend/` with Vite React TS scaffold and project scripts.
2. **App Shell** module with slots + responsive sidebar + optional inspector.
3. **Navigation** feature: typed tree, capability filtering, rail + panels, breadcrumbs.
4. **Auth/Session**: login, logout, refresh, guards, workspace switcher.
5. **Documents**: list + canvas skeleton (placeholders), filters and empty/skeleton states.
6. **Configurations & Jobs**: landing pages with stubs wired to real endpoints later.
7. **Settings**: profile/admin placeholders.
8. **Typed API client** generated from OpenAPI + fetch wrapper with interceptors.
9. **Styling tokens** + global styles + light/dark hooks.
10. **Test suite** (Vitest) + **CI pipeline** (lint/type/test/build) + minimal e2e smoke (deferred).
11. **Docs**: `frontend/README.md`, architecture notes, dev guide, migration checklist.

---

## 5) Non-functional requirements

* **A11y:** WCAG 2.2 AA baseline; keyboard path for all interactive elements; visible focus; ARIA for nav/menus/dialogs.
* **Perf:** p75 LCP ≤ 2.5s, FCP ≤ 1.8s (simulated); route-level code-splitting; avoid global re-renders.
* **Security:** CSRF/Session cookie usage consistent with backend; XSS-safe render; auth error interception → logout.
* **Internationalization (ready):** strings via a minimal i18n wrapper; English only for MVP but extraction ready.
* **Observability:** console-safe `track()` helper emitting basic UX events; error boundary hooks to client logger.

---

## 6) Solution overview

**Stack & key deps**

* Vite + React 18 + TypeScript
* React Router **v7** (data routers)
* TanStack Query
* Tailwind CSS + CSS variables
* Zod (validation) + zod-resolver (for forms)
* Testing Library + Vitest (unit/integration)
* Playwright (smoke, later)
* OpenAPI types generator (e.g., openapi-typescript) + lightweight fetch (native fetch or `ky`)

**Folder structure**

```
frontend/
  src/
    app/              # AppShell, routes, providers, error/suspense
    features/
      auth/
      navigation/
      documents/
      configurations/
      jobs/
      settings/
      setup/
    shared/
      api/            # apiClient, typed endpoints, error mapping
      components/     # primitives (Button, Dialog, Sheet...), no feature logic
      hooks/          # usePreference, useHotkeys, useScreenSize
      providers/      # QueryClient, Theme, Router, Toaster
      styles/         # tokens.css, global.css, tailwind base
      testing/        # test utils
    index.css
    main.tsx
  public/
  vite.config.ts, tailwind.config.ts, tsconfig.json, ...
```

---

## 7) Phased execution plan (what the AI agent should do)

### Phase 0 — Project bootstrap (Day 0)

* Initialize Vite React TS template under `frontend/`.
* Add scripts: `dev`, `build`, `preview`, `lint`, `test`, `typecheck`, `format`.
* Configure ESLint + Prettier; set path alias `@/*` → `src/*`.
* Add Tailwind + PostCSS; create `src/shared/styles/tokens.css` and `global.css`.
* Add Providers scaffold (`AppProviders`) with QueryClient, Theme, Router.

**Exit criteria:** `npm run build` and `npm run test -- --run` succeed; empty page renders.

---

### Phase 1 — App Shell & routing

* Create `AppShell` with slots: `Header`, `Sidebar`, `Content`, `Inspector`, `ModalPortal`, `Banner`.
* Implement skip-link, landmarks (`header`, `nav[aria-label="Primary"]`, `main`, `aside[aria-label="Inspector"]`), reduced-motion utilities.
* Add keyboard shortcuts: toggle sidebar (`[`/`]` or `Shift+S`), focus cycle through regions.
* Configure Router v7 with layouts:

  * `/login`, `/setup` (public)
  * `/workspaces/:workspaceId/*` (protected shell)
  * Error elements + suspense fallbacks at layout boundaries.

**Exit criteria:** Shell renders; routes mount under shell; a11y smoke (keyboard only) passes.

---

### Phase 2 — Data & API layer

* Generate TypeScript types from backend OpenAPI (script: `npm run api:gen`).
* Implement `apiClient` (fetch wrapper): base URL, JSON, auth interceptors, error mapping; retries for idempotent GETs.
* Establish QueryClient with sane caching/stale times; add `useSession` and `useWorkspace` queries.
* Add `usePreference(namespace, key, initial)` with SSR safety (guards for `window`).

**Exit criteria:** Session/workspace queries run; logout on 401; preferences persist collapse state.

---

### Phase 3 — Navigation (feature)

* Define typed `NavigationSection[]` in `features/navigation/config.ts` with route, icon token, capability requirement, telemetry id.
* Implement `useNavigationTree()` merging config with runtime (workspace, flags, counts).
* Build **rail** (icons) + **contextual panels** (Documents, Configs, Jobs) that overlay/expand the sidebar.
* Add breadcrumbs component for header; highlight active route; persist expanded sections with `usePreference`.

**Exit criteria:** Keyboard traversal on rail/panels; hover/focus open behavior; breadcrumbs update on route change.

---

### Phase 4 — Core features (MVP skeletons)

* **Auth:** Login form (Zod validation), logout route, guard components (`RequireAuth`, `RequireWorkspace`).
* **Documents:** List view (server data), canvas placeholder, empty/skeleton states; route params bind to filters.
* **Configurations:** Landing list + “edit” placeholder using Inspector slot (no heavy forms yet).
* **Jobs:** Simple dashboard using server counts; link to details route.
* **Settings:** Basic profile/admin stubs.

**Exit criteria:** Each feature loads from real endpoints (where available), has testable IDs, and returns sensible empty states.

---

### Phase 5 — Styling tokens & theme

* Populate `tokens.css`: colors (brand, semantic states), spacing scale, radii, shadows, motion.
* Map tokens in `tailwind.config.ts` (`theme.extend`), prefer tokens in new components; allow utilities where tokens don’t exist yet.
* Add light/dark theme toggle (document `data-theme` attr).

**Exit criteria:** Most primitives use tokens; theme switch updates across shell/components.

---

### Phase 6 — Testing & CI hardening

* Unit/integration tests for: AppShell slots/landmarks, nav tree filtering, rail keyboard flows, auth guards.
* Add minimal Playwright smoke (optional in this WP): load `/login`, `/:workspaceId/documents`, toggle sidebar, open inspector.
* CI workflow runs: `lint`, `typecheck`, `test -- --run`, `build` on PRs; cache deps.

**Exit criteria:** All gates pass on PR; smoke passes on main.

---

### Phase 7 — Migration cutover & decommission

* Route-by-route cutover plan (documents → configurations → jobs → settings).
* When a route reaches parity: flip feature flag, retire legacy route, update docs.
* Remove legacy SPA only after final smoke is green and stakeholders sign-off.

**Exit criteria:** Legacy removed; single SPA deployed; migration log archived.

---

## 8) Acceptance criteria (DoD)

* `npm run lint`, `npm run typecheck`, `npm run test -- --run`, `npm run build` all succeed on CI.
* AppShell present on all authenticated routes; sidebar collapse persistently remembered.
* A11y checks: skip link works; all interactive elements are keyboard-reachable; focus visible; landmarks present.
* Navigation rail + panels: keyboard traversal and hover/focus behavior; breadcrumbs reflect route.
* Auth/session flows: 401 → logout, login persists across refresh; workspace guard works.
* Documents/Configurations/Jobs/Settings skeletons render with real data (where endpoints exist) or sensible placeholders.
* Perf budgets met on a simulated slow network for the unauth shell.
* README and architectural notes updated; commands and env vars documented.

---

## 9) Risk register & mitigations

| Risk                              | Impact           | Likelihood | Mitigation                                                               |
| --------------------------------- | ---------------- | ---------- | ------------------------------------------------------------------------ |
| API drift during rebuild          | Broken pages     | Medium     | Generate types from OpenAPI per build; narrow surface area early.        |
| Over-engineering the token system | Delays           | Medium     | Phase tokens; enforce in new code only; add lint rule later.             |
| A11y regressions                  | Compliance risk  | Medium     | Add shell a11y smoke tests; run keyboard-only QA per PR for nav changes. |
| Navigation complexity             | User confusion   | Medium     | Start with rail + one panel; expand after usability checks.              |
| Bundle bloat                      | Perf regressions | Medium     | Route-level code splitting; avoid heavy libs; monitor bundle analyzer.   |

---

## 10) Roles & RACI (lean)

* **Sponsor (Justin):** Accountable for scope, priorities, sign-off.
* **Frontend Squad Lead:** Responsible for delivery & technical decisions.
* **AI Agent(s):** Responsible for implementing phases, writing tests, updating docs.
* **Backend Lead:** Consulted on API and auth/session nuances.
* **QA/UX Reviewer:** Consulted for a11y and usability; Informed on milestones.

---

## 11) Environment & configuration

* Envs: `VITE_API_BASE_URL`, `VITE_ENV_NAME`, `VITE_SESSION_CSRF_COOKIE_NAME` (if applicable), `VITE_SENTRY_DSN` (optional).
* Build targets: dev, staging, prod (env-specific base URLs).
* Docker: multi-stage, SPA built into `dist/`, copied to backend’s static dir.

---

## 12) Documentation plan

* `frontend/README.md`: quickstart, scripts, envs, folder map, troubleshooting.
* `docs/frontend-architecture.md`: shell, routing, state, tokens, testing, decisions.
* `docs/migration-checklist.md`: per-feature steps to move from legacy.
* Inline JSDoc/TSdoc for shared utilities and hooks.

---

## 13) Quality gates (CI)

* **Static:** ESLint (TS/React), typecheck (`tsc --noEmit`).
* **Unit/Integration:** Vitest with `@testing-library/react`, `userEvent`.
* **Build:** `vite build` with chunk size warnings enforced.
* **(Optional) E2E smoke:** Playwright minimal flow on main.

---

## 14) “Definition of Ready” for each phase

* Dependencies identified and version-pinned.
* API contracts known (or typed stubs with TODO).
* Acceptance criteria enumerated in the phase ticket.
* Rollback plan defined (feature flag or route switch).

---

## 15) Agent execution checklist (copy-paste to the PR description)

* [ ] Create `frontend/` scaffold and scripts; commit baseline.
* [ ] Add Tailwind + tokens + global styles.
* [ ] Implement `AppProviders` + `AppShell` with slots and landmarks.
* [ ] Configure Router v7 layouts and error/suspense elements.
* [ ] Generate OpenAPI types; add `apiClient` with interceptors.
* [ ] Implement `usePreference`; persist sidebar collapse.
* [ ] Build Navigation rail + panel; add breadcrumbs.
* [ ] Add Auth (login/logout/guards) and Workspace guard.
* [ ] Ship Documents/Configurations/Jobs/Settings skeletons.
* [ ] Write shell/nav/auth tests; wire CI (lint/type/test/build).
* [ ] Update README + architecture docs.
* [ ] Record perf metrics; verify a11y smokes.
* [ ] Prepare migration checklist; plan first cutover.

---

### Appendix A — Recommended npm scripts

```
dev         : vite
build       : vite build
preview     : vite preview
lint        : eslint . --max-warnings=0
typecheck   : tsc -p tsconfig.json --noEmit
test        : vitest
test:run    : vitest run
format      : prettier --write .
api:gen     : openapi-typescript http://localhost:8000/openapi.json -o src/shared/api/types.ts
analyze     : vite build --mode analyze
```
