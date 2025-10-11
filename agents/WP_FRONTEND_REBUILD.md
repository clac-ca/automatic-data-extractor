# Work Package: Frontend Rebuild

## Status
- **Owner:** Experience Squad
- **Last Reviewed:** 2025-10-10
- **State:** _Execution_
- **Notes:** SPA scaffold, setup wizard, authentication loop, workspace shell,
  and document type detail are in place. Workspace chrome now exposes matching
  "New workspace" entry points from the header, rail, and empty state so the
  creation flow is always discoverable. Feature route registries now live with
  their owning features, leaving `createAppRouter` to stitch the arrays
  together. Session/setup guards now sit under `app/guards`, supplying outlet
  context and redirect helpers so routes stay declarative. Root routing now
  primes session and setup queries through a shared loader so downstream guards
  and layouts can reuse cached data immediately. Shared form primitives and the
  workspace chrome are in place, and the document type detail now relies on the
  reusable drawer shell. The next pass should plug in configuration mutations
  and revision timelines before layering analytics.

## Objective
Rebuild the ADE single-page application with a standard React + TypeScript
stack. Deliver only the flows required for day-to-day operations while aligning
with the updated authentication and setup contracts.

## Deliverables
- Vite + React + TypeScript project initialised with ESLint, Prettier, Vitest,
  and Testing Library using upstream defaults.
- Routing shell with authentication guard, shared layout chrome, and feature
  routes built on React Router v6.
- Shared UI primitives (button, input, card, modal) styled with Tailwind.
- TanStack Query configuration plus a typed `apiClient` for authenticated
  requests and error handling.
- Authentication workflow: session resource (`GET/POST/DELETE /auth/session`,
  `POST /auth/session/refresh`), `/auth/providers` integration, credential form,
  provider redirect, logout, and first-run setup wizard via `/setup`.
- Feature scaffolds for workspace overview and document type detail with typed
  data hooks.
- Frontend README covering scripts, environment configuration, routing map, and
  contribution expectations.
- Baseline tests for routing guard, setup wizard, login validation, and data
  hooks.

## Current State Findings
- **Forms now share a baseline primitive layer, but still need the planned
  schema-driven wrapper.**
  - Files: `frontend/src/shared/forms/`,
    `frontend/src/features/setup/components/SetupWizard.tsx`,
    `frontend/src/features/auth/components/LoginForm.tsx`.
  - Status: 🔄 Implemented first-pass `TextField`, `FormAlert`, and validation
    utilities so login/setup flows use consistent markup, messaging, and
    problem-details handling. Still need to swap the custom state helpers for
    the `react-hook-form` + Zod wrapper once dependency access is cleared.
- **Session and setup state are fetched in multiple surfaces.**
  - Files: `frontend/src/app/loaders/rootLoader.ts`,
    `frontend/src/app/RootRoute.tsx`.
  - Status: ✅ Implemented. The root loader now prefetches both resources and
    exposes cached values to route elements so guards reuse the same data.
- **Workspace shell blends layout, data, and modal focus logic.**
  - File: `frontend/src/features/workspaces/components/WorkspaceLayout.tsx`
    (≈400 lines).
  - Issue: the top bar, workspace rail, navigation tabs, empty state, collapse
    toggle, and create-workspace dialog all live in one module with hand-rolled
    focus capture/restore helpers. As a result the sidebar cannot collapse or
    resize cleanly at tablet breakpoints, and the content area never stretches
    into a true full-width view.
  - Action: split this into primitives (`WorkspaceChrome`, `WorkspaceRail`,
    `WorkspaceHeader`, `WorkspaceDialogs`) and move dialog behaviour onto a
    shared accessible modal primitive before layering analytics panes.
- **Navigation rail lacks responsive/collapsible behaviour.**
  - File: `frontend/src/features/workspaces/components/WorkspaceLayout.tsx`.
  - Issue: the navigation rail is hard-coded at desktop width and hidden on
    narrow screens, which forces the global header to shoulder navigation and
    makes the main canvas feel cramped.
  - Action: introduce a `useWorkspaceChromeState` store that tracks
    `railCollapsed`, `railPinned`, and last viewport width. On desktop the rail
    should animate between 288px expanded and 72px collapsed; on tablet the rail
    should slide over the content with a backdrop and obey reduced-motion
    settings.
- **Workspace navigation is incomplete.**
  - File: `frontend/src/features/workspaces/components/WorkspaceLayout.tsx`.
  - Issue: the sidebar lists only workspaces; the planned document-type rail,
    collapse persistence, and quick links are missing, so deep routes depend on
    the browser location alone.
  - Action: add the secondary rail + persistence hooks once the layout is
    modular, and re-use them on the overview + detail screens.
- **Document type detail now exposes the planned chrome but still needs action
  wiring.**
  - Files: `frontend/src/features/workspaces/routes/DocumentTypeRoute.tsx`,
    `frontend/src/features/workspaces/documentTypes/*`,
    `frontend/src/shared/chrome/RightDrawer.tsx`.
  - Status: 🔄 Introduced the responsive header/status strip composition and a
    shared `RightDrawer` primitive so configuration details live in a dedicated
    panel. The document type layout now flows through a `DocumentTypeDetailProvider`
    that centralises drawer orchestration for upcoming publish/rollback actions.
    Still need to attach mutation hooks for publishing/rollback and feed revision
    timelines into the drawer body.
## Layout Direction After Refactor
- **Shared form primitives:** introduce `src/shared/forms/` with our `Form`,
  `Field`, `ErrorSummary`, and schema helpers so auth/setup flows consume the
  same building blocks.
- **Guard components:** add a `src/app/guards/` directory housing
  `RequireSession`, `RequireNoSession`, and `RequireSetupComplete` variants that
  encapsulate redirects declaratively and can be reused across route modules.
- **Workspace chrome:** refactor the shell into `src/features/workspaces/layout/`
  containing the top bar, navigation rail(s), and modal/drawer orchestration to
  keep feature routes lean. Base the layout on a CSS grid with three named
  areas (`header`, `rail`, `canvas`) so the main document surface can stretch to
  100% width when the rail is collapsed.
- **Feature route registries:** export route arrays from each feature (auth,
  setup, workspaces, admin) so `createAppRouter` only stitches them together.
- **Drawer & panel system:** stand up a shared `RightDrawer` primitive the
  document type detail can use immediately, then extend it to configurations and
  analytics later.
- **Responsive navigation pattern:** add a `WorkspaceChromeContext` that exposes
  `toggleRail`, `isRailCollapsed`, and `isOverlayOpen`, and wire it into the top
  navigation so global actions (e.g. "Collapse navigation") are reachable from
  keyboard shortcuts. Persist the collapsed state per-device with
  `localStorage`, but fall back to viewport detection when no preference exists.

## Milestones & Tasks
### M0 — Backend Alignment & Prep
1. Confirm the new session resource and `/setup` contracts, including problem
   details, before frontend work begins.
2. Introduce shared `apiClient`, session query utilities, and setup status query
  under the legacy code to unblock the rebuild and ease retirement of
  `AuthContext`.
3. Plan the legacy SPA sunset (deployment cutover, archival steps) so the new
  structure can launch cleanly.

### M1 — Foundation
1. Scaffold the Vite React TS project, enable ESLint/Prettier/Tailwind, and write
   the initial README with run scripts.
2. Establish project structure (`src/app`, `src/features`, `src/shared`) and
   placeholder routes for `/login`, `/setup`, and `/workspaces/...`.
3. Implement the shared `apiClient` with credential forwarding and CSRF handling.

### M2 — Initial Setup Flow
1. Build the `/setup` route that reads `GET /setup/status` and denies access once
   an administrator exists.
2. Implement the multi-step wizard collecting administrator profile information
   with React Hook Form + Zod.
3. Call `POST /setup`, handle validation errors and concurrency conflicts, and on
   success bootstrap the session and redirect to `/workspaces`.
4. Pull `/auth/providers` to explain SSO expectations during setup.
5. Cover wizard happy path and "setup already complete" guard with Vitest +
   Testing Library.

### M3 — Authentication Loop
1. Implement `useSessionQuery` backed by `GET /auth/session` and hydrate provider
  discovery alongside session state.
2. Build the login page with credential form, provider tiles, force-SSO handling,
  and redirect logic.
3. Wire logout via `DELETE /auth/session` and guard authenticated routes with a
  `RequireSession` layout.
4. Test login validation and session guard behaviour.

### M4 — Workspace Shell
1. Construct the workspace layout: top bar, navigation rail, and responsive
   behaviour down to tablet widths.
2. Integrate workspace listing query and default-selection logic using TanStack
   Query.
3. Render workspace overview content with placeholders for future analytics.

### M5 — Document Type Detail & Configuration Drawer
1. Implement the document type detail view with status strip and context cards
   tied to backend fields.
2. Build a read-only configuration drawer skeleton with revision metadata.
3. Add placeholder mutation hooks that assert payload shapes.
4. Write tests covering drawer open/close flows and data hook rendering.

### M6 — Hardening & Handover
1. Sweep for accessibility basics (focus management, keyboard navigation,
   aria wiring).
2. Document API dependencies, routing table, and environment requirements in the
   README.
3. Run lint/test suite, update `agents/FRONTEND_DESIGN.md`, and track remaining
   gaps as follow-up issues.

## Dependencies
- `/auth/providers` endpoint (see `WP_AUTH_PROVIDER_DISCOVERY`).
- `/setup/status` + `POST /setup` contract for first-run provisioning.
- Session resource (`GET/POST/DELETE /auth/session`, `POST /auth/session/refresh`).
- `/workspaces` and `/configurations/:id` APIs for data contracts.
- Stable auth cookie/CSRF behaviour from the backend.

## Risks & Mitigations
- **Backend gaps** — Block frontend release until discovery, session, and setup
  routes are live.
- **Contract drift** — Lock schemas early and cover critical flows with tests.
- **Scope creep** — Keep deferred features in the design doc; do not add new
  surfaces during this rebuild.

## Definition of Done
- Milestone tasks complete with reviewed PRs.
- Frontend build passes lint, tests, and produces artefacts served via FastAPI.
- Documentation (`agents/FRONTEND_DESIGN.md`, frontend README) reflects the
  implemented architecture.
- Legacy `AuthContext` and initial-setup flows removed or clearly deprecated.
