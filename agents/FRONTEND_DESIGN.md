# ADE Frontend Design Document

Use this document as the authoritative spec for ADE's web client. When behaviour
drifts, update this text before writing code. The rebuild plan in
`agents/WP_FRONTEND_REBUILD.md` describes the delivery steps; this document locks
the product and UX contract that the app must satisfy.

## 1. Mission
- Deliver a predictable operator console covering setup, authentication,
  workspace navigation, and document configuration.
- Provide ticket-ready direction so work can proceed without additional design
  cycles.

## 2. Personas
- **Operations Lead** — Monitors processing health and resolves errors.
- **Configuration Specialist** — Adjusts extraction rules and publishes
  revisions.
- **Auditor / Reviewer** — Reviews outcomes and configuration history with
  read-only access.

## 3. Design Tenets
- One primary action per screen; defer extras.
- Plain language with verb-first buttons and consistent layout chrome.
- Separate monitoring, editing, and history so each view stays focused.
- Prefer standard, accessible components over custom patterns.

## 4. Release Scope
1. First-run setup wizard (`/setup`) that provisions the inaugural administrator
   before exposing the login surface.
2. Authentication loop (`/login`) with credentials, optional SSO, and redirect
   into the workspace shell.
3. Workspace shell listing accessible workspaces and summarising document types.
4. Document type detail view with status strip and configuration drawer.

## 5. Experience Map
### 5.1 Routes
- `/setup` — Public wizard available only while setup is required.
- `/login` — Public authentication surface once setup completes.
- `/workspaces/:workspaceId` — Default authenticated landing experience.
- `/workspaces/:workspaceId/document-types/:documentTypeId` — Document type
  detail inside the workspace shell.
- `/logout` — Calls `DELETE /auth/session` then redirects to `/login`.

### 5.2 Layout
- Top bar: product logo, workspace selector, user menu, connectivity indicator.
- Navigation rail lists workspaces then document types; collapse below tablet
  widths and persist the preference in `localStorage`.
- Right pane renders the active document type with breadcrumbs.

## 6. Screen Specifications
### 6.1 `/setup`
- Reachable only while `GET /setup/status` returns `requires_setup: true`; otherwise redirect to `/login`.
- Steps: `Welcome` (system readiness summary), `Administrator` (display name,
  email, password + confirm), `Confirmation` (success message and link to
  `/workspaces`).
- Use React Hook Form + Zod validation; enforce password policy and confirmation
  match.
- Submit via `POST /setup`, map validation errors to fields, refresh session via
  `GET /auth/session`, then redirect into the workspace shell.
- On HTTP 409 refresh status, show completion notice, and redirect to `/login`.
- When `force_sso` is true, explain that the inaugural administrator signs in
  with credentials for break-glass access before enabling SSO for everyone else.

### 6.2 `/login`
- Inputs: email and password with inline validation.
- Errors: top-level summary with `aria-live="assertive"` plus inline messages.
- Success path: call `POST /auth/session`, hydrate TanStack Query with
  `GET /auth/session`, redirect to preferred workspace.
- Force SSO: when `force_sso` is true, replace credential form with a single SSO
  CTA and support contact link.
- SSO providers: render tiles when discovery returns entries; respect backend
  ordering and supplied labels/icons.
- Setup handoff: if `GET /setup/status` reports `requires_setup: true`, redirect
  to `/setup` before rendering the login experience.
- Admin provisioning: setup wizard creates the inaugural administrator; document
  CLI fallback (`ade users create --role admin`) for recovery scenarios.

### 6.3 `/workspaces/:workspaceId`
- Workspace selection defaults to `preferred_workspace_id` from
  `GET /auth/session`, otherwise the first `/workspaces` entry.
- Navigation rail persists last selection in `localStorage`.
- Document type cards show name, status badge, and last-run timestamp supplied by
  `useWorkspaceOverviewQuery`.

### 6.4 Document Type Detail
- Status strip surfaces `last_run_at`, `success_rate_7d`, and `pending_jobs`.
- Primary actions: `Review configuration` (primary CTA) and `View history`
  (secondary link, stub until analytics ship).
- Context panels summarise active configuration (version, published by/at) and
  recent alerts when available.
- Component structure: `SummaryHeader`, `StatusStrip`, and `ContextCards`.

### 6.5 Configuration Drawer
- Right-anchored drawer that traps focus until closed.
- Sections: `Overview` (name, description, version metadata, publish status) plus
  read-only `Inputs` and `Publishing` summaries.
- Show revision breadcrumbs (e.g., `v12 • Published by Dana • 2025-03-04`).
- Exit handling: `Done` button returns focus to its trigger and confirms before
  discarding unsaved changes.

## 7. Data Contracts
- `GET /setup/status` → `{ requires_setup: bool, completed_at: datetime | null }`.
- `POST /setup` → accepts `{ display_name, email, password }`, returns
  `SessionEnvelope` and transitions into the authenticated shell.
- `GET /auth/session` → active session profile powering TanStack Query.
- `POST /auth/session` → credential sign-in returning `SessionEnvelope`
  (`user`, `expires_at`, `refresh_expires_at`).
- `DELETE /auth/session` → clears cookies/tokens and redirects to `/login`.
- `POST /auth/session/refresh` → rotates refresh token and returns updated
  `SessionEnvelope`.
- `/auth/providers` → `{ providers: List[Provider], force_sso: bool }` where
  `Provider` includes `id`, `label`, `icon_url`, `start_url`.
- `/workspaces` → each workspace includes `id`, `name`, `status`, and
  `document_types: List[DocumentTypeSummary]`.
- `DocumentTypeSummary` → `id`, `display_name`, `status`,
  `active_configuration_id`, `last_run_at`, `recent_alerts` (optional list).
- `/configurations/:id` → `version`, `published_by`, `published_at`, `draft`
  status, input schema summary, revision notes.

## 8. Accessibility and Telemetry
- Maintain keyboard access with visible focus states; drawers trap focus until
  closed.
- Use `aria-live="assertive"` for error summaries and `aria-describedby` for
  inline errors.
- Emit telemetry for setup completion, login success/failure, workspace switch,
  document type selection, and configuration publish/save events.

## 9. Implementation Guardrails
- Bootstrap with Vite + React + TypeScript, ESLint, Prettier, Vitest, and Testing
  Library using `create-vite` defaults.
- Project layout: `src/app`, `src/features/<feature>`, `src/shared`.
- TanStack Query manages server state; invalidate queries after mutations.
- Persist only workspace/document selections and nav collapse state in
  `localStorage`.
- React Router v6 handles routing; protect authenticated routes with a
  `RequireSession` layout using `useSessionQuery`.
- Tailwind styles shared primitives; reach for CSS Modules only when utilities
  fall short.
- Forms rely on React Hook Form + Zod; API access flows through a single
  `apiClient` helper.
- Expose `useInitialSetupStatus` to gate `/setup` and `/login` appropriately.

## 10. Component Map
- `AppShell` — Routing, query client, and session providers.
- `SetupWizard` — Guides first-run administrator creation and redirects on
  completion.
- `LoginPage` — Fetches provider discovery, renders credential form/SSO tiles.
- `WorkspaceLayout` — Navigation rail and top bar around nested routes.
- `WorkspaceOverviewPage` — Lists document types with status and last-run info.
- `DocumentTypePage` — Renders status strip, context cards, and actions.
- `ConfigurationDrawer` — Handles review flow with focus trap.
- Shared primitives — Button, Input, Select, Card, Drawer, Spinner, Empty State,
  Alert components.

## 11. Deferred Features
- Analytics/history pages.
- Document upload tooling, bulk retry flows, and advanced filtering.
- Multi-tenant admin controls and role management UI.

Keep this document aligned with backend capabilities. Revise sections here before
shipping code that alters the contract.
