# Work Package: ADE Frontend Rebuild

## Summary
- Rebuild the ADE operator console in `frontend/` so it satisfies the scope and UX contract in `agents/FRONTEND_DESIGN.md`.
- Carry forward the proven patterns from `frontend.old/` while addressing gaps in test coverage, modularity, and placeholder flows.
- Deliver a production-ready, type-safe React/Vite application that pairs cleanly with the FastAPI v1 surface.

## Goals
- Ship the initial route set (`/setup`, `/login`, authenticated workspace shell, configuration detail/drawer, `/logout`) with deterministic behaviour.
- Preserve the feature-first directory layout (`src/app`, `src/features/<feature>`, `src/shared`, `src/ui`) and the API boundary patterns that kept the legacy client maintainable.
- Ensure forms, navigation, and data-fetching respect the accessibility, validation, and telemetry guidance in the design doc.
- Stand up fast, reliable tooling (Vite, Vitest, Testing Library, ESLint, Tailwind) with CI-friendly scripts and consistent developer ergonomics.

## Non-Goals
- Adding analytics, history, document upload workflows, or admin consoles beyond what `agents/FRONTEND_DESIGN.md` lists as release scope.
- Replacing backend authentication or API contracts (coordinate with backend owners if gaps are discovered).
- Migrating or deleting `frontend.old/` during this work package; keep it intact as a historical reference until the new shell is stable.

## Legacy Frontend Lessons

### Strengths to Preserve
- `frontend.old/src/app/AppProviders.tsx` demonstrates a stable `QueryClient` factory with tuned defaults (retry=1, 30s stale, no focus refetch). Mirror this so network behaviour stays predictable.
- The API client in `frontend.old/src/shared/api/client.ts` normalises CSRF tokens, default headers, and Problem+JSON errors; keep the same ergonomics and error surfaces.
- Session and workspace contexts (`frontend.old/src/features/auth/context/SessionContext.tsx`, `frontend.old/src/features/workspaces/context/WorkspaceContext.tsx`) gave components a clean way to read identity and permissions—recreate them with the same hooks and test seams.
- Local storage helpers (`frontend.old/src/shared/lib/storage.ts`, `frontend.old/src/app/workspaces/useWorkspaceRailState.ts`) already guard against SSR and JSON failures; reuse the pattern for persisted UI state.
- Shared UI primitives (`frontend.old/src/ui`) encapsulate focus styles, button loading states, and FormField accessibility; port and expand them instead of scattering Tailwind classes.
- Query key factories (e.g., `frontend.old/src/features/auth/sessionKeys.ts`) and lightweight normalisers (e.g., `frontend.old/src/features/workspaces/api.ts`) kept server interactions deterministic—continue organising network calls this way.

### Gaps to Address
- Placeholder routes and stubs (documents/jobs/configurations) stopped short of the experience promised in `agents/FRONTEND_DESIGN.md`. The rebuild must wire real data flows and UX polish for the configuration detail/drawer and document rail.
- Complex components such as `frontend.old/src/features/documents/components/DocumentDrawer.tsx` grew large and lightly tested. Plan for smaller subcomponents and behavioural tests that exercise filtering, pinning, and empty/error states.
- Auth and setup flows currently share minimal integration coverage (only component-level tests). Introduce feature-level tests that mock API responses, include SSO callback paths, and verify redirect logic.
- Telemetry and logging hooks are absent. The redesign calls for instrumenting key events (setup completion, login success/failure, workspace switch); add a shared telemetry helper so events can be piped to the backend later.
- Linting relies on a single config with few project rules. We should extend ESLint/TypeScript settings to enforce import boundaries (feature-first) and ensure consistent quote/casing options caught by the old code review comments.

## Target Architecture & Conventions
- **Tech stack:** Vite + React 19 + TypeScript 5 + React Router v6.28+ (`createBrowserRouter`), TanStack Query v5, Tailwind CSS, clsx, React Hook Form + Zod, Vitest + Testing Library. Match the dependency versions already vetted in `frontend.old/package.json`.
- **Directory layout:** `src/app` (router, layouts, providers), `src/features/<feature>` (api, hooks, components, tests), `src/shared` (types, api client, config, lib), `src/ui` (headless primitives), `src/test` (render helpers), `src/index.css`.
- **State management:** TanStack Query for server cache, feature hooks wrap mutations/queries, React context only for session/workspace state and UI chrome preferences.
- **Routing:** Route objects with loaders for workspace hydration, guarded layouts via `RequireSession`, and explicit `/setup` vs `/login` gating based on `useSetupStatusQuery`.
- **Styling:** Tailwind theme tokens from `frontend.old/tailwind.config.js` (brand palette, `shadow-soft`, focus styles). Extend only when design doc demands it.
- **Persistence:** Limit `localStorage` usage to workspace/doc drawer state and navigation collapse toggles, reusing the scoped helper.
- **Testing:** Co-locate Vitest specs next to features (`__tests__`). Use `src/test/test-utils.tsx` to wrap providers, add request mocking via MSW (or equivalent) to cover fetch flows, and capture coverage through `npm run test:coverage`.
- **Scripts:** Keep npm scripts (`dev`, `build`, `lint`, `test`, `test:watch`, `test:coverage`, `preview`) aligned with the legacy package.json so CI pipelines stay consistent.

### Layout & Navigation Blueprint
- **Hierarchy:** Enforce a single visual stack—global top bar, primary navigation rail on the left, main work surface, and an optional right-hand detail panel.
- **Top bar (global):** Hosts branding, workspace switcher, search (when ready), session controls, and system-level alerts. Keep the chrome slim so it never steals vertical space from work.
- **Left rail (pages):** Lists first-level destinations (e.g., Documents, Jobs, Configurations, Members, Settings). Provide collapsed and overlay modes so the main canvas expands when the rail is dismissed or on narrow screens.
- **Main content (do work):** Dedicated to the task view. Use secondary tabs within this area to pivot between page-level views (e.g., list vs. activity) without touching the primary navigation.
- **Right panel (details):** Reserved for contextual item details, drawers, or inspectors. It must be optional, closable, and default to overlay/collapsed on smaller breakpoints so focus returns to the main canvas.
- **Responsiveness:** Both side panels collapse or slide over the main content when screen width is constrained. Persist user preferences (expanded/collapsed) in scoped local storage.
- **Predictability:** Avoid nesting navigation levels deeper than necessary—primary nav for pages, tabs for page variants, right panel for object details. No other navigation metaphors unless the design doc expands scope.

### Workspace Navigation Story
- **User story:** As a workspace user, I need a clean, spacious layout with predictable navigation so I can land on Documents, move between sections quickly, and keep work front-and-center.
- **Acceptance criteria:**
  - Top bar stays visible, minimal, and includes workspace switch, search, help, profile, plus a toggle for the left rail.
  - Left rail lists workspace sections with Documents first (default landing page), collapses to icons, and persists the expanded state.
  - Main content owns all remaining real estate and is never obscured by navigation in its default state.
  - Right inspector is closed by default, opens as a slide-in for item details, closes via Esc, and overlays on narrow breakpoints.
  - Sub-items (section groups) live in the left rail; reserve tabs for switching views within the same page.
  - Focus mode hides both panels with one action and expands the main content to full width.
  - Responsive behaviour: left rail becomes a drawer, inspector becomes a full-height overlay, main content remains primary.
  - Keyboard/A11y: provide visible focus states, Escape closes panels, and expose ARIA landmarks for header/nav/main/aside.
- **Happy path:**
  - Landing on a workspace routes to Documents by default.
  - Collapsing the left rail immediately widens main content.
  - Opening a document slides in the inspector; pressing Esc closes it.
  - Enabling focus mode makes the work surface edge-to-edge.

## Delivery Plan

### 1. Foundation & Tooling
- Bootstrap a fresh Vite + React + TypeScript project inside `frontend/` and port over configuration files (`tsconfig*.json`, `vite.config.ts`, Tailwind/PostCSS, ESLint) tuned to the decisions above.
- Recreate the project README with setup instructions; ensure environment variables (`VITE_API_BASE_URL`, `VITE_SESSION_CSRF_COOKIE`) are documented.
- Validate that linting, tests, and builds succeed in isolation.

### 2. Shared Infrastructure
- Implement `AppProviders`, `AppRouter`, and `AppShell` scaffolding with responsive layout, breadcrumbs, and profile menu patterns from `frontend.old/src/app/layouts/AppShell.tsx`.
- Port `ApiClient`, `ApiError`, and verb helpers with unit tests that cover CSRF header injection, JSON parsing, and error propagation.
- Stand up shared telemetry/logging helpers (stubbed to console for now) and a typed event catalogue for future backend ingestion.

### 3. Authentication Core
- Recreate session hooks (`useSessionQuery`, `useLoginMutation`, `useLogoutMutation`, `useAuthProviders`), session context/provider, and route guard (`RequireSession`), including tests for loading/error/redirect paths.
- Implement SSO callback handling with robust error cases and unit tests mirroring `frontend.old/src/app/routes/AuthCallbackRoute.tsx`.
- Ensure session invalidation clears provider queries and cached workspace data.

### 4. Setup Experience
- Build the `/setup` wizard per `FRONTEND_DESIGN.md` using React Hook Form + Zod, inline errors, and `PageState` loading/error shells.
- Coordinate API payloads with backend specs (`POST /setup`, `GET /setup/status`); add tests that cover successful completion, validation errors, 409 conflicts, and `force_sso` messaging.

### 5. Login Flow
- Implement `/login` with provider tiles, SSO enforcement, credential form, and redirect handling (`return_to` + `?next=`). Ensure state is restored post-login.
- Add telemetry for login success/failure and provider selection.
- Write tests covering force-SSO, provider fetch failure, and error messaging.

### 6. Workspace Shell & Navigation
- Implement workspace loader, layout, and switcher, persisting preferred workspace and nav collapse state per workspace.
- Build the navigation rail using `workspaceSections` metadata aligned with the design doc, including placeholder content where APIs are still pending.
- Wire `WorkspaceDocumentRail` with pinning/filtering and ensure it hydrates from TanStack Query + local storage.
- Add tests for loader redirects, permissions gating, profile menu items, and rail state persistence.

### 7. Configuration Detail & Drawer
- Deliver the configuration status strip, context cards, and primary/secondary actions described in Section 6.4–6.5 of the design doc.
- Build the right-anchored drawer with focus trap, revision breadcrumbs, and unsaved-change confirmation.
- Integrate data hooks (`useConfigurationQuery`, `useConfigurationHistoryQuery`) with optimistic updates for publish actions once backend endpoints arrive.
- Cover rendering, telemetry, and focus control with component tests.

### 8. Quality, Telemetry & Handoff
- Implement global error boundaries and idle/logout handling (session expiry refresh) to match backend expectations.
- Instrument telemetry events (setup complete, login, workspace switch, configuration selected/published) and add unit tests to confirm payload composition.
- Execute accessibility audits (keyboard traversal, aria-live regions, colour contrast) and write regression tests for critical flows.
- Update docs (`README.md`, `agents/FRONTEND_DESIGN.md` if adjustments arise) and capture CHANGELOG notes under `## [Unreleased]`.
- Schedule removal/archive plan for `frontend.old/` once parity is confirmed (outside this work package).

## Dependencies & Coordination
- Confirm authentication endpoints, CSRF cookie naming, and SSO callback parameters with backend owners (`ade/core/auth_backends.py`, `docs/authentication.md`).
- Ensure workspace/document/configuration API contracts are available or stubbed in FastAPI before wiring UI hooks.
- Coordinate telemetry schema with whoever owns observability so event payloads land in an agreed queue.

## Risks & Mitigations
- **API drift:** Backend contracts may evolve during the rebuild. Mitigate with TypeScript interfaces + Zod parsing at the boundary and early backend alignment.
- **Large component complexity:** Recreating advanced UI (document rail, configuration drawer) could bloat components. Mitigate by carving subcomponents, writing stateful hooks, and enforcing size limits in review.
- **Auth edge cases:** SSO/credential fallbacks are sensitive; build automated tests with MSW mocks to guard against regressions.
- **Timeline pressure:** Implementing every feature at once risks context switching. Follow the phased workstreams above and land incremental PRs with feature flags when possible.

## Acceptance Checklist
- [ ] All routes described in `agents/FRONTEND_DESIGN.md` render with production-ready UX and real API integrations.
- [ ] Shared infrastructure (API client, providers, contexts, telemetry) is covered by unit tests.
- [ ] Feature flows (setup, login, workspace shell, configuration drawer) have Vitest + Testing Library coverage exercising success, empty, error, and retry states.
- [ ] `npm run build`, `npm run lint`, and `npm test` succeed locally and in CI.
- [ ] Documentation (`frontend/README.md`, CHANGELOG entry) reflects the new stack and any required environment variables.
- [ ] Sign-off obtained from design/ops stakeholders on layout fidelity and accessibility.

## Open Questions
- Do we need an interim mock server (MSW or FastAPI stub) to develop before backend endpoints are final?
- Should telemetry events be queued locally (e.g., batching) or fire-and-forget via API calls?
- Are we adopting Playwright/Cypress end-to-end coverage in this rebuild, or deferring to a later task?
