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

## Implementation Guidance

### Patterns to Carry Forward
- `frontend/src/app/providers.tsx` centralises the TanStack Query client, disables retries on `401`, caps other retries at two, and only mounts React Query Devtools during development—retain that behaviour in the rebuild.
- `frontend/src/shared/api/client.ts` normalises base URLs, injects the CSRF token from the signed cookie, and surfaces `ApiError` with Problem Details; hook all fetches through this client so mutating requests continue to satisfy `require_csrf`.
- SPA routing (`frontend/src/app/router.tsx`) keeps public routes (`/setup`, `/login`) outside `<RequireSession />` and hides feature paths behind permission guards (`RequirePermission`, `RequireGlobalPermission`). Preserve this layering so route-based protection stays declarative.
- `WorkspaceLayout` is the canonical pattern for picking the active workspace: read the route param, fall back to the preferred workspace, then first membership. It also scopes navigation by permission and restores focus after dialogs; copy these UX details.
- RBAC helpers in `frontend/src/shared/rbac` (permission registry, `can.ts`, guard components) already mirror backend keys and include tests—lift them into the new structure instead of inventing new checks.

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
1. Refresh the Vite + React + TypeScript scaffold with ESLint, Prettier, Vitest, and Tailwind using upstream defaults.
2. Establish the design system primitives (buttons, inputs, form controls, modals, alert banners) with accessibility baked in via Headless UI/ARIA patterns.
3. Capture component usage guidance in `frontend/README.md` and ensure shared spacing/typography tokens flow through Tailwind and component styles.

### M2 — Application Shell & Navigation
1. Build the responsive app chrome: fixed top bar, collapsible workspace navigation rail, and content area with standard padding/breakpoints.
2. Implement the global loading/empty/skeleton states and error boundaries to keep route transitions polished.
3. Wire placeholder routes for `/login`, `/setup`, `/workspaces/*`, `/admin/*`, and `/settings` so the shell mirrors the final sitemap.

### M3 — Authentication & Session Management
1. Implement the session query + React Query cache hydration, including CSRF-safe mutations for login, logout, and refresh.
2. Deliver the `/login` experience with password and SSO entry points, error messaging, and redirect handling using established form primitives.
3. Finish `RequireSession` and related guards so authenticated routes render only when the session cache is populated.

### M4 — First-Run Setup Experience
1. Complete the `/setup` wizard flow (status gate, profile form, password validation) using Zod + React Hook Form.
2. Present provider discovery during setup to prepare administrators for SSO-only deployments.
3. Ensure successful setup logs the user in and routes them into the shell with onboarding messaging.

### M5 — Workspace Home & Navigation Depth
1. Implement the workspace overview route with document/job summaries, recent activity, and clear calls-to-action.
2. Finalise workspace selection logic (preferred workspace, fallbacks) and persist the choice across sessions.
3. Introduce contextual navigation (breadcrumbs, tab highlights) so users understand their location within a workspace.

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

