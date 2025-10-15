# Work Package: ADE Frontend v3 - Angular 19 Migration Plan

## 1. Product & delivery goals

**Problem**
- The legacy SPA mixes patterns, has no shared navigation contract, and slows feature work.

**Target outcomes**
- Deliver a **workspace-first Angular 19 SPA** with predictable routing, theming, and state.
- Hit **WCAG 2.2 AA** and keep bundle p75 LCP <= 2.5s on a simulated slow 4G profile.
- Achieve **green CI** (lint, unit, e2e, build) on every pull request.
- Provide a first-run `/setup` wizard for seeding the initial admin before exposing workspaces.

## 2. Scope boundaries

**In scope**
- Fresh Angular 19 CLI workspace rooted in `frontend/` using standalone components, Angular signals, and CLI-managed configuration.
- Application shell with header, collapsible workspace sidebar, content area, and skip links.
- Workspace navigation that defaults to the Documents view and exposes a toggleable document list in the sidebar.
- Distinct areas for **workspace settings** (scoped to a workspace) and **admin settings** (global) with their own routes and guards.
- `/setup` first-run flow that creates the initial administrator and locks the rest of the app until completion.
- Type-safe API access via HttpClient, interceptors, and generated typings.
- Testing stack based on Angular CLI defaults: ESLint, strict template/type checks, Karma + Jasmine unit tests, and Playwright smoke tests introduced once the navigation shell is stable.

**Out of scope**
- Backend contract changes or RBAC overhaul.
- Redesigning feature UX beyond layout/navigation.
- Replacing FastAPI static hosting or deployment pipeline.

**Assumptions & constraints**
- Node 20.x and npm 10.x baseline.
- Serving through FastAPI with HTML5 history fallback.
- Feature work must keep the repository deployable; no half-configured tools left enabled in `main`.

## 3. Guiding principles
- **Angular-first conventions**: prefer CLI defaults, standalone components, typed forms, Angular CDK utilities, and v19 control flow (`@if`, `@for`).
- **Workspace-first UX**: every workspace route lands on the Documents page with a collapsible document panel. Sidebar hides on mobile but remains discoverable.
- **Separation of concerns**: core services/guards are singleton; feature directories own their UI and state.
- **Progressive enhancement**: default experience works without JS bells/whistles; enhance with CDK overlays and animations as needed.
- **Deterministic tests**: lean on Angular CLI defaults (TestBed + Karma) for fast feedback; reserve Playwright for essential end-to-end journeys.
- **Incremental documentation**: keep `frontend/README.md` and per-feature READMEs updated as features land.

## 4. Roadmap & milestones

Track progress with the checklist below. Update statuses as work completes.

| Phase | Status | Focus | Key deliverables | Dependencies |
| --- | --- | --- | --- | --- |
| **Phase 0 - Tooling & workspace** | ✅ Completed | Establish Angular 19 workspace, linting, testing, CI hooks | Angular CLI scaffold with strict TS/HTML templates, ESLint config, headless Karma setup, npm scripts, `/setup` guard placeholder | Node/npm toolchain |
| **Phase 1 - Shell & navigation** | ⧗ In progress | Layout, responsive chrome, navigation contracts | `AppShellComponent` with header/sidebar/content, collapsible document list, workspace switcher placeholder, skip links, focus management, default workspace documents route | Phase 0 |
| **Phase 2 - Identity & setup** | ☐ Not started | `/setup` wizard and authentication scaffolding | Setup flow screens + guard, API adapters for admin bootstrap, auth interceptor + login/logout stubs, workspace context service | Phase 1, backend auth endpoints |
| **Phase 3 - Data & API layer** | ☐ Not started | Typed API clients and error handling | `ng-openapi-gen` pipeline, Http interceptors (auth, error, loading), typed ProblemDetails mapper, optimistic mutation helpers | Phase 2 |
| **Phase 4 - Feature skeletons** | ☐ Not started | Workspace feature scaffolds | Documents list/canvas shell (default landing), configurations, jobs, workspace settings, admin settings, shared empty/error/loading states | Phase 3 |
| **Phase 5 - Quality hardening** | ☐ Not started | Accessibility, performance, docs | Playwright smoke coverage for setup/workspace flows, axe checks on core pages, basic bundle budgets, docs & runbooks updated | Phases 0-4 |

### Critical-first focus
1. **Phase 0** unlocks tooling and ensures we can iterate safely.
2. **Phase 1** establishes the navigation and default workspace landing pattern demanded by stakeholders.
3. **Phase 2** protects setup and tenancy boundaries.
4. **Phase 3** provides the type-safe API layer required by downstream features.
5. **Phase 4** delivers visible progress in workspace modules.
6. **Phase 5** locks in quality, accessibility, and release confidence.

> **Status notes**
> - Phase 0: ✅ Angular workspace restored with strict typing, CLI-managed linting, headless Karma, and a placeholder `/setup` guard syncing with the backend build pipeline.
> - Phase 1: ⧗ App shell, navigation scaffold, and workspace stubs in place; next up is wiring real workspace data and interaction states.
> - Phase 2:
> - Phase 3:
> - Phase 4:
> - Phase 5:

## 5. Navigation & information architecture
- `/setup` route owns the first-run wizard. Guard all other routes behind a `SetupCompleteGuard` that checks bootstrap status.
- `/workspaces/:workspaceId` lazy module hosts workspace routes:
  - Default child route redirects to `/documents` so the documents view is the landing experience.
  - Sidebar presents a collapsible panel listing uploaded documents, using Angular CDK for focus trapping and animation.
  - Workspace settings live at `/workspaces/:workspaceId/settings` with tabs for members, quotas, and billing.
- `/admin` route provides global admin settings (system toggles, integrations, user provisioning) and is guarded by a global admin permission distinct from workspace settings.
- A global top bar includes workspace switcher, account menu, and notifications placeholder.
- Error and 404 routes display within the shell while respecting the collapsible sidebar contract.

## 6. First-run `/setup` experience
- Visiting `/setup` when no admin exists displays a multi-step wizard (account info, password, organisation details).
- On completion, persist admin credentials via the backend and mark setup as complete (e.g., `SetupStateService`).
- Subsequent visits redirect to the login screen; `/setup` becomes inaccessible once bootstrap is done.
- Provide resumable progress: if the user refreshes mid-setup, load partial data from backend or local storage.
- After setup, redirect to the default workspace documents view.

## 7. Testing strategy

**Objectives**
- Prevent regressions in routing, guards, and workspace navigation.
- Ensure deterministic coverage for data services and UI state.
- Keep feedback tight (<90s for unit suite, <6m for CI end-to-end smoke).

**Layers**
1. **Unit tests (Karma + Jasmine)** - Stick with the Angular CLI defaults. Co-locate specs (`*.spec.ts`) with components, pipes, and services; rely on TestBed helpers such as `provideHttpClientTesting` and `RouterTestingModule`. Introduce Angular Material Harnesses only when the component uses Material.
2. **Component interaction smoke** - Cover shell behaviours (sidebar collapse, guards, redirects) with focused TestBed specs. Prefer direct DOM queries over custom helper libraries until we hit repeated patterns.
3. **End-to-end (Playwright)** - Enable the CLI-provided Playwright project once the shell and `/setup` flows are stable. Smoke the `/setup` bootstrap, default documents landing, and admin/workspace settings navigation. Run in CI on merges to `main` and nightly.
4. **Accessibility & performance** - During Phase 5, extend Playwright flows with `@axe-core/playwright` on the shell and Documents view and add a lightweight Lighthouse CI script that checks LCP/CLS budgets for the default workspace landing page.

**Practices**
- Write or update tests alongside feature work; every route or service change ships with coverage for the happy path and key guard rails.
- Keep Playwright helpers simple; extract shared navigation utilities only when duplication appears.
- Add builders under `src/app/testing/` when multiple specs share factories; otherwise create fixtures inline to reduce indirection.
- Expose `npm run test:ci` as a thin wrapper over `ng test --configuration ci` so browser flags live in `angular.json`, and document the required Node/Chrome versions in `frontend/README.md`.

## 8. Tooling & environment
- Enforce strict template/type checking (`"strictTemplates": true`).
- Use ESLint (`@angular-eslint`) with Angular 19 recommended rules; add Prettier only if the team needs auto-formatting beyond the CLI defaults.
- Manage environment configs under `src/environments/` with typed tokens.
- Document scripts, environment variables, and testing commands in `frontend/README.md`.
- Wire npm scripts into FastAPI build pipeline to bundle SPA artifacts.

## 9. Risks & mitigations
- **Angular 19 adoption curve** - Leverage official upgrade guide; pin dependencies and run `ng update` for minor releases.
- **Navigation complexity** - Prototype sidebar interactions early (Phase 1) with extensive accessibility tests.
- **Setup flow blocking** - Feature flag the guard in development to avoid locking contributors out; provide CLI to reset setup state.
- **Testing flake** - Keep e2e minimal, rely on harnessed unit/integration tests for most coverage.

## 10. Follow-on enhancements
- Replace Karma with Jest once Angular 19 Jest builder stabilises.
- Introduce Storybook for shared components in Phase 5 for design review.
- Add real-time collaboration affordances (presence, locking) to Documents view after MVP.
- Layer in analytics/telemetry once privacy review completes.

