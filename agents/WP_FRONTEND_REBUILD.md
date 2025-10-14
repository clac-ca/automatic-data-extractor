# Work Package: Frontend Rebuild

## Status
- **Owner:** Experience Squad
- **Last Reviewed:** 2025-10-10
- **State:** _Execution_
- **Notes:** Fresh Vite scaffold, shell layout, login/setup flows, and API client are in place. Next focus: design system primitives, authenticated workspace surfaces, navigation redesign (header tabs + document rail), end-user login polish, `/auth/callback` handling, and test coverage.

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

## Implementation Guidance
- Anchor UI tokens in `tailwind.config.ts` (color palette, spacing, radius) and consume them through utility classes; avoid inline style drift across features.
- House reusable primitives under `frontend/src/ui/` with prop-driven variants rather than bespoke screen-level styling; keep accessibility baked in (focus traps, ARIA labels).
- Route-level data should come from TanStack Query hooks that wrap `frontend/src/shared/api/client.ts`; mutations must reuse the shared CSRF-aware client helpers.
- Prefer composition over global state: let React Router loaders/queries drive layout state, and keep session/workspace context limited to providers already defined in `AppProviders`.
- When extending auth/setup flows, mirror backend schemas in `frontend/src/shared/api/types.ts` and add Vitest + Testing Library coverage alongside the change.
- Follow AGENTS.md heuristics—clarity over cleverness, deterministic behaviour, and boring abstractions—before introducing new dependencies or optimisations.
- Keep workspace-level navigation in the shell header (active workspace selector, overview/documents tabs) and reserve the left rail for document-centric context (recent uploads, presence indicators) to reinforce workspace scoping.
- Ensure SSO surfaces include a `/auth/callback` route that completes the redirect flow and feeds back into session hydration.

## Progress Snapshot
- Rebuilt `frontend/` from scratch (archived legacy app in `frontend.old/`), configured Tailwind 3.x, React Router, React Query, and updated developer docs.
- Implemented `AppProviders`, `AppRouter`, `ShellLayout`, and `RequireSession`, providing authenticated chrome plus placeholder routes for admin, workspaces, jobs, documents, and settings.
- Delivered initial auth/setup flows (session query, login with SSO discovery, setup status + provisioning mutation) and wired logout redirect handling.
- Updated backend asset pipeline: `ade start --rebuild-frontend` now publishes bundles to `ade/web/static/`; Docker/CLI/docs reflect the new location.
- Shared UI primitives ( `src/ui`) now expose buttons, inputs, alerts, and form helpers to keep feature screens consistent. 
- Workspace shell now persists active selection, shows breadcrumbs, and provides placeholder routes for per-section views.
- Header navigation now surfaces workspace-scoped tabs (overview/documents) with a document rail scaffold in the sidebar ready for real-time presence indicators.
- Added an `AppShell` wrapper so `/workspaces`, `/workspaces/new`, and `/workspaces/{id}/…` all share the same header/profile chrome; the workspace layout now passes tabs, sidebar content, and workspace switcher into that shell.
- Outstanding work includes expanding workspace-specific UI, introducing data visualisations, wiring document/job routes, enriching the document rail with live data, completing `/auth/callback` backend wiring, and covering flows with Vitest.

### Layout & Navigation Progress (2025-10-18)
- Canonicalised workspace routing with a React Router loader that resolves slugs to IDs, writes the active workspace to storage, and primes the React Query cache for nested routes.
- Centralised workspace section metadata in `frontend/src/app/workspaces/sections.ts`, eliminating duplicated label/path constants across the router, shell layout, and placeholder routes.
- Refactored `WorkspaceLayout` to consume loader data through a dedicated `WorkspaceProvider`, ensuring breadcrumbs, navigation tabs, and profile menus derive from a single workspace context.
- Replaced the mock document drawer with `frontend/src/features/documents/components/WorkspaceDocumentRail.tsx`, powered by a TanStack Query hook and per-workspace pin persistence.
- Introduced `WorkspaceDirectoryLayout` so index and detail routes share consistent AppShell composition and admin profile menu wiring.

### Patterns to Carry Forward
- `frontend/src/app/AppProviders.tsx` centralises React Query defaults (limited retries, dev-only devtools) and must wrap the router.
- `frontend/src/shared/api/client.ts` handles CSRF, base URLs, and Problem Details—use it for all HTTP interactions.
- `frontend/src/app/AppRouter.tsx` separates public and authenticated routes; keep guard logic (`RequireSession`) near the top-level router.
- `frontend/src/app/layouts/ShellLayout.tsx` will host the header-level workspace tabs and the document rail; evolve it rather than replacing it wholesale.
- Add future shared components under `frontend/src/ui/` to keep feature code lean and consistent.

### Architecture Review (2025-02-14)
**Current layout**
- `AppRouter` wraps the private tree in `RequireSession`, then fans into the workspace router where placeholders stand in for unfinished surfaces while a loader resolves the active workspace.【F:frontend/src/app/AppRouter.tsx†L1-L59】
- `WorkspaceLayout` currently couples loader data priming, preferred-workspace persistence, permission gating, navigation composition, and the document rail wiring inside a single component.【F:frontend/src/app/layouts/WorkspaceLayout.tsx†L22-L140】
- `AppShell` fetches the session internally to build the profile menu, so every layout that renders it subscribes to `useSessionQuery` instead of receiving session data from above.【F:frontend/src/app/layouts/AppShell.tsx†L1-L164】
- `WorkspaceDirectoryLayout` and the index route re-run session permission checks and recreate shell chrome outside the workspace loader stack.【F:frontend/src/app/layouts/WorkspaceDirectoryLayout.tsx†L13-L34】【F:frontend/src/app/routes/WorkspacesIndexRoute.tsx†L12-L101】
- The document rail owns persistence effects and fetching logic rather than consuming workspace data supplied by the router or context.【F:frontend/src/features/documents/components/WorkspaceDocumentRail.tsx†L28-L94】

**Gaps vs. playbook / simplification opportunities**
- `/login`, `/setup`, and workspace creation screens still manage form state with `useState` instead of the React Hook Form + Zod stack called for in the design guardrails.【F:frontend/src/app/routes/LoginRoute.tsx†L12-L118】【F:frontend/src/app/routes/SetupRoute.tsx†L22-L166】【F:frontend/src/app/routes/WorkspaceCreateRoute.tsx†L33-L220】【F:agents/FRONTEND_DESIGN.md†L56-L140】
- Session data is fetched repeatedly in `AppShell`, `WorkspaceLayout`, `WorkspaceDirectoryLayout`, and the workspaces index, leading to multiple query subscribers and scattered permission checks.【F:frontend/src/app/layouts/AppShell.tsx†L50-L65】【F:frontend/src/app/layouts/WorkspaceLayout.tsx†L53-L138】【F:frontend/src/app/layouts/WorkspaceDirectoryLayout.tsx†L13-L34】【F:frontend/src/app/routes/WorkspacesIndexRoute.tsx†L12-L101】
- Document rail state (pins, collapse) lives in component-local effects, making it harder to share across future surfaces or to hydrate from loader data aligned with `workspaceSections` descriptors.【F:frontend/src/features/documents/components/WorkspaceDocumentRail.tsx†L28-L94】【F:frontend/src/app/workspaces/sections.ts†L21-L136】

### Sustainability & Maintainability Review (2025-02-20)
- Layout modules mix data orchestration, provider wiring, and presentation in one file, making reuse and testing harder. `WorkspaceLayout` defines nested layout components, mutates React Query caches, and persists preferred workspace IDs inside the component body instead of delegating those responsibilities to route loaders and dedicated UI primitives.【F:frontend/src/app/layouts/WorkspaceLayout.tsx†L22-L140】
- `AppShell` remains stateful, invoking the session query and logout mutation directly. That prevents Storybook or test harnesses from rendering the shell without live hooks and forces every consumer to pay an extra network call.【F:frontend/src/app/layouts/AppShell.tsx†L50-L164】
- Directory-level screens still reconstruct shell chrome and permission logic locally rather than consuming a shared authenticated layout contract, which risks drift in navigation labels and profile menus as features expand.【F:frontend/src/app/layouts/WorkspaceDirectoryLayout.tsx†L13-L34】【F:frontend/src/app/routes/WorkspacesIndexRoute.tsx†L12-L101】
- Route components and loaders follow mixed naming conventions (`WorkspaceLayout`, `WorkspacePlaceholderRoute`, `workspaceLoader`) and live in separate directories, so adding suspense or error boundaries requires broad imports rather than encapsulated route folders.【F:frontend/src/app/AppRouter.tsx†L23-L48】【F:frontend/src/app/workspaces/loader.ts†L1-L60】
- Form routes rely on mutable React state instead of shared schema-driven helpers, so validation rules, default values, and submission behaviour are duplicated and harder to internationalise or audit.【F:frontend/src/app/routes/LoginRoute.tsx†L12-L118】【F:frontend/src/app/routes/SetupRoute.tsx†L22-L166】【F:frontend/src/app/routes/WorkspaceCreateRoute.tsx†L33-L220】

**Proposed improvements**
- Introduce an `AuthenticatedApp` router layout that runs a loader to hydrate the session and workspace directory once, exposes them via context providers, and renders `AppShell` as a pure presentational component so nested routes inherit consistent chrome without re-querying.【F:frontend/src/app/AppRouter.tsx†L23-L59】【F:frontend/src/app/layouts/AppShell.tsx†L50-L164】
- Split `WorkspaceLayout` into a route module that handles loader data, query priming, and preferred-workspace persistence, and a `WorkspaceChrome` component that only accepts props for navigation, permissions, and sidebar config. This keeps context logic aligned with `workspaceSections` while making it easier to add real documents/configurations routes.【F:frontend/src/app/layouts/WorkspaceLayout.tsx†L22-L140】【F:frontend/src/app/workspaces/sections.ts†L21-L136】
- Refactor login, setup, and workspace creation to use shared React Hook Form + Zod schemas, mapping backend validation errors through consistent helpers and unlocking richer inline validation and accessibility messaging per the design spec.【F:frontend/src/app/routes/LoginRoute.tsx†L12-L118】【F:frontend/src/app/routes/SetupRoute.tsx†L22-L166】【F:frontend/src/app/routes/WorkspaceCreateRoute.tsx†L33-L220】【F:agents/FRONTEND_DESIGN.md†L56-L140】
- Extract a `useDocumentRailState` helper (persisted via `createScopedStorage`) and allow the rail to accept preloaded document summaries so loaders or future real-time sources can hydrate pins and collapse state without reimplementing effects in each layout.【F:frontend/src/features/documents/components/WorkspaceDocumentRail.tsx†L35-L94】
- Pass profile metadata and actions into `AppShell` via props to decouple it from `useSessionQuery`, which simplifies testing, Storybook usage, and eventual multi-tenant profile menus while avoiding redundant network calls.【F:frontend/src/app/layouts/AppShell.tsx†L50-L164】
- Add explicit `errorElement`/`pendingElement` components for the workspace route so loader failures render actionable messaging instead of falling back to blank screens or generic router errors.【F:frontend/src/app/AppRouter.tsx†L23-L46】
- Co-locate each routed surface under a directory that bundles the route component, loader, and error boundary (for example, `frontend/src/app/routes/workspaces/detail/`) to follow React Router best practices and keep naming predictable.【F:frontend/src/app/AppRouter.tsx†L23-L59】
- Promote `AppShell` into a prop-driven layout under `frontend/src/ui/layouts/` so it can be composed by Storybook stories, tests, and nested routers without importing query hooks by default.【F:frontend/src/app/layouts/AppShell.tsx†L50-L164】
- Introduce shared form utilities (React Hook Form adapters, schema exports under `frontend/src/shared/validation/`, and an error-mapping helper) and migrate existing forms to them, reducing bespoke state and improving maintainability.【F:frontend/src/app/routes/LoginRoute.tsx†L12-L118】【F:frontend/src/app/routes/SetupRoute.tsx†L22-L166】【F:frontend/src/app/routes/WorkspaceCreateRoute.tsx†L33-L220】

### Environment & Build Hooks
- `VITE_API_BASE_URL` drives the HTTP base URL (defaults to `/api/v1`); the backend serves the SPA from `ade.main.start(rebuild_frontend=True|False)`.
- `VITE_SESSION_CSRF_COOKIE_NAME` overrides the cookie the `ApiClient` reads when sending `X-CSRF-Token`. Leave it unset to use `ade_csrf`.
- Development workflow remains `npm install`, `npm run dev`, `npm run build`, and `npm test -- --watch=false`. Keep those scripts intact in the regenerated project.

### Data Shapes to Honour
- `SessionEnvelope` → `{ user, expires_at, refresh_expires_at, return_to? }`; `user` matches `SessionUser` (`user_id`, `email`, status flags, roles, permissions, `preferred_workspace_id`).
- `AuthProvider` → used for SSO tiles (`id`, `label`, `icon_url`, `start_url`) plus `force_sso` flag from `/auth/providers`.
- `WorkspaceProfile` → supplies navigation: `id`, `name`, `slug`, `roles`, `permissions`, `is_default`.
- `WorkspaceMember`, `RoleDefinition`, `DocumentTypeDetailResponse`, `ConfigurationSummary`, and `JobRecord` fuel the planned feature screens; keep their field names aligned with backend responses in `frontend/src/shared/api/types.ts`.
- Successful setup (`POST /setup`) and login return `SessionEnvelope` and set `ade_session`/`ade_refresh` cookies. CSRF enforcement applies to every mutating route except setup and initial session creation.

## Backend API Contracts (`/api/v1`)
All paths below already apply the API prefix (`/api/v1`). Mutating routes require `X-CSRF-Token` unless noted. Workspace-scoped endpoints inherit `require_workspace` permission checks.

### Setup & Session
| Method | Path | Purpose | Notes |
| --- | --- | --- | --- |
| GET | `/setup/status` | Determine whether first-run setup is still required | Public; returns `{ requires_setup, completed_at, force_sso }` |
| POST | `/setup` | Create the inaugural administrator and start a session | Public; returns `SessionEnvelope`; sets session cookies |
| GET | `/auth/providers` | List interactive auth providers | Public; returns `{ providers, force_sso }` |
| POST | `/auth/session` | Email/password login | Public; body `LoginRequest`; issues cookies |
| GET | `/auth/session` | Read current session envelope | Requires session cookie |
| POST | `/auth/session/refresh` | Rotate access/refresh cookies | Requires refresh cookie + CSRF header |
| DELETE | `/auth/session` | Log out and clear cookies | Requires session + CSRF |
| GET | `/auth/sso/login` | Start the SSO redirect challenge | Public; accepts optional `next` |
| GET | `/auth/sso/callback` | Finish SSO login and establish session | Public; expects `code`, `state`, and SSO state cookie |
| GET | `/auth/me` | Fetch authenticated user profile | Mirrors `SessionEnvelope.user` |

### API Keys (optional admin UI)
| Method | Path | Purpose | Notes |
| --- | --- | --- | --- |
| GET | `/auth/api-keys` | List issued API keys | Requires `System.Settings.ReadWrite` |
| POST | `/auth/api-keys` | Issue a new API key | Requires `System.Settings.ReadWrite` + CSRF |
| DELETE | `/auth/api-keys/{api_key_id}` | Revoke an API key | Requires `System.Settings.ReadWrite` + CSRF |

### Workspaces & Membership
| Method | Path | Purpose | Notes |
| --- | --- | --- | --- |
| GET | `/workspaces` | List workspaces visible to the caller | Respects global/workspace roles |
| POST | `/workspaces` | Create a workspace | Requires `Workspaces.Create` + CSRF |
| GET | `/workspaces/{workspace_id}` | Retrieve workspace profile | Requires `Workspace.Read` |
| PATCH | `/workspaces/{workspace_id}` | Update name/slug/settings | Requires `Workspace.Settings.ReadWrite` + CSRF |
| DELETE | `/workspaces/{workspace_id}` | Delete a workspace | Requires `Workspace.Delete` + CSRF |
| POST | `/workspaces/{workspace_id}/default` | Mark workspace as caller’s default | Requires membership + CSRF |
| GET | `/workspaces/{workspace_id}/members` | List members | Requires `Workspace.Members.Read` |
| POST | `/workspaces/{workspace_id}/members` | Invite/add member | Requires `Workspace.Members.ReadWrite` + CSRF |
| PUT | `/workspaces/{workspace_id}/members/{membership_id}/roles` | Replace member roles | Requires `Workspace.Members.ReadWrite` + CSRF |
| DELETE | `/workspaces/{workspace_id}/members/{membership_id}` | Remove member | Requires `Workspace.Members.ReadWrite` + CSRF |
| GET | `/workspaces/{workspace_id}/roles` | List workspace-scoped roles | Requires `Workspace.Roles.Read` |
| POST | `/workspaces/{workspace_id}/roles` | Create workspace role | Requires `Workspace.Roles.ReadWrite` + CSRF |
| PUT | `/workspaces/{workspace_id}/roles/{role_id}` | Update workspace role | Requires `Workspace.Roles.ReadWrite` + CSRF |
| DELETE | `/workspaces/{workspace_id}/roles/{role_id}` | Delete workspace role | Requires `Workspace.Roles.ReadWrite` + CSRF |

### Configurations (per workspace)
| Method | Path | Purpose | Notes |
| --- | --- | --- | --- |
| GET | `/workspaces/{workspace_id}/configurations` | List configurations | Query by `document_type`/`is_active` |
| GET | `/workspaces/{workspace_id}/configurations/active` | List active configurations | Read-only |
| GET | `/workspaces/{workspace_id}/configurations/{configuration_id}` | Fetch configuration | Raises 404 if missing |
| POST | `/workspaces/{workspace_id}/configurations` | Create configuration | Requires `Workspace.Configurations.ReadWrite` + CSRF |
| PUT | `/workspaces/{workspace_id}/configurations/{configuration_id}` | Update configuration | Requires `Workspace.Configurations.ReadWrite` + CSRF |
| POST | `/workspaces/{workspace_id}/configurations/{configuration_id}/activate` | Mark configuration active | Requires `Workspace.Configurations.ReadWrite` + CSRF |
| DELETE | `/workspaces/{workspace_id}/configurations/{configuration_id}` | Delete configuration | Requires `Workspace.Configurations.ReadWrite` + CSRF |

### Documents & Jobs (per workspace)
| Method | Path | Purpose | Notes |
| --- | --- | --- | --- |
| GET | `/workspaces/{workspace_id}/documents` | List documents | Supports pagination via `limit` and `offset` |
| POST | `/workspaces/{workspace_id}/documents` | Upload document | Multipart form (`file`, `metadata`, `expires_at`) |
| GET | `/workspaces/{workspace_id}/documents/{document_id}` | Read document metadata | Requires `Workspace.Documents.Read` |
| GET | `/workspaces/{workspace_id}/documents/{document_id}/download` | Download document | Streams file |
| DELETE | `/workspaces/{workspace_id}/documents/{document_id}` | Soft-delete document | Requires `Workspace.Documents.ReadWrite` + CSRF |
| GET | `/workspaces/{workspace_id}/jobs` | List jobs | Query by `status`, `input_document_id` |
| GET | `/workspaces/{workspace_id}/jobs/{job_id}` | Fetch job detail | Requires `Workspace.Jobs.Read` |
| POST | `/workspaces/{workspace_id}/jobs` | Submit extraction job | Body `JobSubmissionRequest`; requires `Workspace.Jobs.ReadWrite` + CSRF |

### Roles & Permissions (global scope)
| Method | Path | Purpose | Notes |
| --- | --- | --- | --- |
| GET | `/roles` | List global roles | Requires global read |
| POST | `/roles` | Create global role | Requires `Roles.ReadWrite.All` + CSRF |
| GET | `/roles/{role_id}` | Read role definition | Requires matching read permission |
| PATCH | `/roles/{role_id}` | Update role | Requires matching write permission + CSRF |
| DELETE | `/roles/{role_id}` | Delete role | Requires matching write permission + CSRF |
| GET | `/role-assignments` | List global assignments | Requires `Roles.Read.All` |
| POST | `/role-assignments` | Assign global role | Requires `Roles.ReadWrite.All` + CSRF |
| DELETE | `/role-assignments/{assignment_id}` | Remove global assignment | Requires `Roles.ReadWrite.All` + CSRF |
| GET | `/workspaces/{workspace_id}/role-assignments` | List workspace role assignments | Requires `Workspace.Roles.Read` |
| POST | `/workspaces/{workspace_id}/role-assignments` | Assign workspace role | Requires `Workspace.Roles.ReadWrite` + CSRF |
| DELETE | `/workspaces/{workspace_id}/role-assignments/{assignment_id}` | Remove workspace assignment | Requires `Workspace.Roles.ReadWrite` + CSRF |
| GET | `/permissions` | Retrieve permission catalogue | Supports `scope` filter |
| GET | `/me/permissions` | Read caller’s effective permissions | Useful for client RBAC bootstrapping |
| POST | `/me/permissions/check` | Batch permission check | Public endpoint (no CSRF) used for gating UI |

### Users & Health
| Method | Path | Purpose | Notes |
| --- | --- | --- | --- |
| GET | `/users` | Admin search across users | Requires global admin |
| GET | `/users/me` | Convenience profile endpoint | Mirrors `/auth/me` |
| GET | `/health` | Service health check | Used by uptime monitoring / readiness |

## Testing & Quality Expectations
- Keep `npm run build` and `npm test -- --watch=false` as the default gates before handing off a PR.
- When API contracts change, extend `frontend/src/shared/api/types.ts` alongside backend schemas and cover the new flow with Vitest + Testing Library.
- Backend tests rely on `pytest` with async fixtures from `conftest.py`. The `test_csrf_guards.py` suite will fail if new mutating routes omit `require_csrf`, so ensure the frontend always attaches the CSRF header (the shared `ApiClient` already does this).

## Milestones & Tasks
### M0 — Alignment & Visual Direction
1. Reconfirm requirements across `AGENTS.md`, `docs/authentication.md`, and `agents/FRONTEND_DESIGN.md`; document any deltas in this work package.
2. Define the visual baseline (color system, typography scale, spacing tokens) and capture them in updated Tailwind config notes.
3. Map the primary operator journeys (first-run setup, daily login, workspace triage) so the navigation hierarchy and wayfinding stay grounded in user needs.

### M1 — Foundation & Design System
1. (Done) Refresh the Vite + React + TypeScript scaffold with linting, Tailwind, and developer docs.
2. (Next) Establish reusable design-system primitives (buttons, inputs, alerts, modal scaffolds) with accessible patterns.
3. (Next) Document component usage in `frontend/README.md` and propagate spacing/typography tokens through Tailwind.

### M2 — Application Shell & Navigation
1. (Done) Build the responsive app chrome with top bar, navigation rail, and content container.
2. (Next) Add global loading/empty states and error boundaries for page transitions.
3. (Done) Wire placeholder routes for `/login`, `/setup`, `/workspaces/*`, `/admin/*`, and `/settings`.
4. (Done) Relocate workspace-level navigation into the header (overview/documents tabs + active workspace indicator).
5. (In progress) Convert the left rail into a document list/presence sidebar scaffold ready for real-time updates.

### M3 — Authentication & Session Management
1. (Done) Implement session query + React Query cache hydration, including CSRF-safe login/logout mutations.
2. (Done) Deliver `/login` with credentials + SSO discovery and redirect handling.
3. (Done) Finish `RequireSession` guard and logout control in the shell.
4. (Next) Add Vitest coverage for auth flows (happy path, error states, forced SSO).
5. (Done) Improve login UX: auto-check `/setup/status`, redirect to setup when required, remove redundant setup link, and refresh copy for end users.
6. (Done) Add `/auth/callback` route handling that finalises SSO flows and drops the user back into the shell.

### M4 — First-Run Setup Experience
1. (In progress) Replace the current controlled form with Zod + React Hook Form (status validation, inline errors).
2. (Next) Surface provider discovery/force-SSO messaging during setup.
3. (Done) Ensure successful setup logs the user in and routes into the shell.

### M5 — Workspace Home & Navigation Depth
1. (Done) Implement initial workspace overview route pulling live `/workspaces` data with quick actions and counts.
2. (In progress) Finalise workspace selection logic (preferred workspace, fallbacks) and persist the choice across sessions.
3. (Next) Introduce contextual navigation (breadcrumbs, tab highlights) so users understand their location within a workspace.

### M6 — Documents & Configuration Surfaces
1. Deliver the document list/detail and document-type routes with status, metadata, and action panels.
2. Build the configuration drawer and detail screens, including version history and read-only previews.
3. Provide optimistic or state-aware mutations for configuration activation and document deletion using shared API helpers.

### M7 — Admin & Settings Surfaces
1. Implement the workspace membership and role management views with bulk actions and inline feedback.
2. Build the global admin area (`/admin`) for role catalogues and assignments, reusing list/detail patterns from earlier milestones.
3. Introduce the application settings panel (feature flags, organisational settings, notification preferences) using the design system components.

### M8 — Polish & Handover
1. Sweep for accessibility (focus management, keyboard support, color contrast) and responsive edge cases.
2. Document API dependencies, routing topology, and UI conventions in `frontend/README.md` and relevant agent docs.
3. Run the full lint/test/build pipeline, update `agents/FRONTEND_DESIGN.md` with final state, and capture any follow-up items for post-launch iterations.

