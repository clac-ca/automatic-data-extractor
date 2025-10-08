# Work Package: Frontend Rebuild

## Status
- **Owner:** Experience Squad
- **Last Reviewed:** 2025-10-08
- **State:** _Execution_
- **Notes:** SPA scaffold, setup wizard, authentication loop, workspace shell,
  and document type detail are now implemented with baseline tests. Remaining
  hardening tasks cover configuration mutations and analytics surfaces.

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
- The legacy SPA centralises authentication, setup, and bootstrap logic inside a
  bespoke context. The rebuild will replace it with feature hooks backed by
  TanStack Query.
- Login UI mixes setup, credentials, and lockout behaviour with custom
  validation. The new plan separates setup at `/setup` and keeps `/login`
  focused on sessions and SSO.
- Auth API naming must switch from `/auth/me`, `/auth/login`, `/auth/logout`,
  `/auth/refresh` to the standard session resource used in the design doc.
- First-admin creation remains required; the new `/setup` wizard must create the
  inaugural administrator before exposing `/login`.

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
