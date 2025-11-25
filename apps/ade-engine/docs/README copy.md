Here’s the series I’d recommend for `docs/` for **ade-web**, modeled after your engine docs but tuned for frontend concerns, naming consistency, and “obvious architecture”.

I’ll assume the existing `README.md` is the **00‑overview** and start numbering from `01`.

---

## 01-domain-model-and-terminology.md

**Goal:** Lock down the *names* of things and how they map to both the backend and the UI so humans and AI agents don’t have to guess.

**Scope:**

* Canonical terms and how we use them in code:

  * `Workspace`
  * `Document`
  * `Run` (canonical execution term; maps to `/runs` endpoints).
  * `Config` / `Configuration`
  * `ConfigVersion` / `Build` / `Draft` / `Active` / `Inactive`
  * `User`, `Member`, `Role`, `Permission`
  * `SafeMode`
* How these terms appear in:

  * URLs (`/workspaces/:workspaceId/runs`)
  * Components (`WorkspaceShell`, `DocumentsScreen`, `RunsScreen`, etc.)
  * Backend routes (mapping table to `/api/v1/...`).
* Rules like:

  * “In the UI and React code we say *Run* to mirror the engine and `/runs` API.”
  * “We say *Config* for user‑facing configs, *ConfigVersion* for specific versions.”
* Short glossary section for contributors.

> This doc becomes the single source of truth for naming decisions and should be the first thing new devs read.

---

## 02-project-structure-and-module-boundaries.md

**Goal:** Explain the physical layout of the repo for ade-web and the logical “areas” of the app.

**Scope:**

* High‑level folder structure (suggested):

  ```text
  apps/ade-web/
    src/
      app/           # App shell, providers, routing, entry points
      features/      # Feature slices (documents, runs, configs, settings, auth, etc.)
      ui/            # Reusable UI components and primitives
      shared/        # Cross-cutting utilities (hooks, urlState, storage, logging)
      schema/        # Shared types / zod schemas / generated types
      generated-types/
      test/          # Test helpers, mocks, setup
  ```

* How existing aliases (`@app`, `@screens`, `@ui`, `@shared`, `@schema`, `@generated-types`) map into that structure and whether any should be renamed for clarity (e.g. `@screens` → `@features`).

* Naming conventions for modules:

  * `FeatureNameScreen.tsx`, `FeatureNamePanel.tsx`, `FeatureNameList.tsx`
  * `useXxxQuery.ts`, `useXxxMutation.ts`, `xxxApi.ts`.

* Boundaries:

  * What lives in `app/` vs `features/` vs `ui/` vs `shared/`.
  * “Feature-first” vs “layer-first” guidance (I’d lean feature-first: `features/workspaces`, `features/documents`, etc.).

* Guidance on co-location:

  * Components + hooks + tests per feature folder.
  * Where to put “router-aware” components vs “pure” ones.

---

## 03-app-runtime-routing-and-navigation.md

**Goal:** Describe how the SPA spins up, how routing works, and how screens are chosen.

**Scope:**

* `main.tsx` → `App` → `ScreenSwitch` flow.
* `NavProvider`:

  * How it wraps the app.
  * How it tracks and updates `location`.
  * How it uses `window.history` and `popstate`.
* Top-level route map:

  * `/`, `/login`, `/auth/callback`, `/setup`, `/logout`,
  * `/workspaces`, `/workspaces/new`,
  * `/workspaces/:workspaceId/<section>`.
* `ScreenSwitch`:

  * How it chooses a screen from `location.pathname`.
  * Where 404 / “section not found” behavior is defined.
* Conventions for screen components:

  * Naming (`WorkspacesDirectoryScreen`, `WorkspaceShellScreen`, etc.).
  * Props (typically none; data via hooks).
* How “immersive” screens (Config Builder workbench) can temporarily hide parts of the shell.

---

## 04-navigation-intents-and-url-state.md

**Goal:** Make the custom navigation layer and URL query state completely obvious.

**Scope:**

* `NavProvider` in detail:

  * `NavigationIntent` shape.
  * `NavigationBlocker` and when to use `useNavigationBlocker`.
  * How unsaved‑changes guards work and common patterns for editors.
* `Link` and `NavLink`:

  * Click interception rules (unmodified left‑click vs modified).
  * `NavLink`’s `isActive` calculation and how to apply active styles.
* URL search helpers (`urlState.ts`):

  * `toURLSearchParams`, `getParam`, `setParams`.
* `useSearchParams` hook:

  * API and recommended usage.
  * The `replace` vs `push` semantics.
* `SearchParamsOverrideProvider`:

  * When you’re allowed to use it and when you shouldn’t.
  * Example patterns (e.g. dialogs with local search params).

---

## 05-data-layer-api-clients-and-backend-contracts.md

**Goal:** Explain how ade-web talks to `/api/v1/...` and how we structure data fetching.

**Scope:**

* React Query setup (`AppProviders`, `QueryClient` defaults).
* Where API clients live (e.g. `features/*/api.ts` or `shared/api/*`).
* Standard patterns for hooks:

  * `useWorkspacesQuery`, `useJobsQuery`, `useCreateJobMutation`, etc.
  * Using `workspaceId` as part of query keys.
* Mapping of main domain operations to backend routes:

  * Workspaces (`/api/v1/workspaces...`)
  * Documents (`/api/v1/workspaces/{workspace_id}/documents...`)
  * Runs (`/api/v1/workspaces/{workspace_id}/runs...`)
  * Configs/builds (`/api/v1/workspaces/{workspace_id}/configurations...`, `/builds`, `/runs`)
  * Safe mode (`/api/v1/system/safe-mode`)
  * Roles/permissions (`/api/v1/me/permissions`, `/api/v1/workspaces/{workspace_id}/roles...`, etc.)
* How streaming NDJSON endpoints are wrapped:

  * Build logs (`/api/v1/builds/{build_id}/logs`)
  * Run logs (`/api/v1/runs/{run_id}/logs`).
* Error handling conventions:

  * Common error type or normalisation step.
  * Where global error handling lives (e.g. response interceptors or React Query `onError` handlers).

---

## 06-auth-session-and-rbac-integration.md

**Goal:** Document the full auth story once so nobody has to reverse-engineer it again.

**Scope:**

* Auth flows:

  * Setup (`/setup`, `/api/v1/setup`).
  * Email/password session (`/api/v1/auth/session`).
  * SSO login (`/api/v1/auth/sso/login`, `/api/v1/auth/sso/callback`).
* Session model:

  * `/api/v1/auth/session` / `/api/v1/users/me` / `/api/v1/auth/me`.
  * What fields the frontend relies on (id, name, email, global permissions).
* Workspace membership and roles:

  * `/api/v1/workspaces/{workspace_id}` and `members`, `roles`.
  * `/api/v1/me/permissions` and `/permissions/check`.
* How permissions show up in the UI:

  * Checking specific permission strings before showing actions.
  * Pattern for “hide vs disable with tooltip”.
  * How Settings, Config activation, and Safe Mode are permission-gated.
* Sign-out behavior:

  * `/api/v1/auth/session` `DELETE` and what the SPA does afterwards.
* Security notes:

  * `redirectTo` validation (client-side & server-side expectations).
  * Handling 401/403 globally (e.g. redirect to login, show “no access”).

---

## 07-global-layout-workspaces-and-sections.md

**Goal:** Capture the layout system and the main workspace surfaces (directory + shell) in one place.

**Scope:**

* `GlobalTopBar`:

  * Slots (`brand`, `leading`, `actions`, `trailing`, `secondaryContent`).
  * Where it’s composed and how it adapts per screen.
* Workspace directory (`/workspaces`):

  * Search behavior, keyboard shortcuts, empty states.
  * Workspace cards (default workspace marker, roles summary).
* Workspace shell (`/workspaces/:workspaceId/...`):

  * Left nav structure and persistence of collapse per workspace.
  * Top bar contents (name, environment label, search within workspace).
  * Mobile nav (slide-in, scroll locking).
* Safe mode banner behavior inside the shell.
* Notification locations:

  * Toast container placement.
  * Section-level banners vs global banners.
* How special layouts (e.g. fullscreen Config Builder) integrate with and/or override the shell.

---

## 08-documents-and-runs-ui-flows.md

**Goal:** Describe the core operational flows: uploading docs, running configs, viewing run history.

**Scope:**

* Documents screen:

  * Listing, filters (`q`, `status`, `sort`, `view` query params).
  * Upload flow (keyboard shortcut, drag & drop, API used).
  * Status mapping (`uploaded`, `processing`, `processed`, `failed`, `archived`) to chips and icons.
  * Per-document last run summary and quick actions.
* Document-level run options:

  * Run dialog (select config, config version, sheet selection, dry-run, validate-only).
  * Remembering per-document run preferences (and how/where stored).
* Runs screen:

  * Workspace-wide run history, filters (status, config, initiator, date range).
  * How run status maps to UI states.
  * Links to logs, telemetry, outputs/artifacts.
* Relationship between runs in the UI and backend:

  * Clear mapping back to the terminology in **01-domain-model-and-terminology.md**.

---

## 09-config-builder-workbench-architecture.md

**Goal:** Capture everything about the Config Builder workbench as a coherent subsystem.

**Scope:**

* Workbench window states:

  * Restored / Maximized / Docked.
  * How state is stored and persisted.
* Layout:

  * Activity bar, explorer, editor area, bottom console, right inspector.
  * Resizable panels and persistence of sizes.
* File tree model:

  * `WorkbenchFileNode`, `WorkbenchFileMetadata`.
  * How we build the tree from the backend file listing.
  * How language is inferred from file extension.
* Tab model:

  * `WorkbenchFileTab` fields, “dirty” calculation.
  * Pinned tabs, MRU order, keyboard shortcuts.
* Persistence:

  * `PersistedWorkbenchTabs` in localStorage keyed by `workspaceId` + `configId`.
  * Console state storage (`ConsolePanelPreferences`).
  * Editor theme preference (tie-in to next doc).
* Build & validation integration:

  * How the split `Build` button works.
  * How build/validation events are streamed to the console and to the Validation panel.
* “Run extraction” from the workbench:

  * Document picker, sheet list, and how we stream run output into the console.

---

## 10-code-editor-theme-and-ade-scripting.md

**Goal:** Explain the code editing experience and ADE-specific affordances.

**Scope:**

* `CodeEditor` component:

  * Props, lazy Monaco loading, `CodeEditorHandle`.
  * Save shortcuts (`⌘S` / `Ctrl+S`) and how they integrate with workbench tabs.
* Editor theme:

  * `EditorThemePreference` & `EditorThemeId`.
  * How we derive theme from system preference.
  * Where `ade-dark` is defined and what it tweaks.
* ADE script helpers:

  * `registerAdeScriptHelpers` and when it runs.
  * Scope detection (which paths/files get ADE helpers).
  * Types of helpers: hovers, completions, signature help.
* Script API reference (frontend perspective):

  * Summary of expected signatures for row detectors, column detectors/transforms/validators, hooks.
  * Emphasis that this is a “developer aid”, not an enforcement layer.

---

## 11-state-persistence-and-user-preferences.md

**Goal:** Centralise all the “we store this in localStorage / workspace-scoped storage” behavior.

**Scope:**

* Storage strategy:

  * Namespacing by `workspaceId` and sometimes `configId`.
  * Common prefix pattern: `ade.ui.workspace.<workspaceId>...`.
* Items to document:

  * Default workspace selection (if any).
  * Left nav collapsed state per workspace.
  * Workbench tabs, console state, editor theme (link back to doc 09/10).
  * Workbench “return path”.
  * Per-document run preferences.
* Implementation helpers:

  * Any shared `useStoredState` / `storage` utilities.
* Rules:

  * When it’s okay to introduce a new stored preference.
  * How to handle versioning or format changes (e.g. `version: 2` in console preferences).

---

## 12-ui-component-library-and-interaction-patterns.md

**Goal:** Document the UI building blocks and how to use them consistently.

**Scope:**

* Component categories & naming:

  * Buttons (`Button`, `SplitButton`).
  * Form controls (`Input`, `TextArea`, `Select`, `FormField`).
  * Feedback components (`Alert`, toast primitives).
  * Identity (`Avatar`, `ProfileDropdown`).
  * Navigation (`Tabs*`, `ContextMenu`).
  * Search (`GlobalSearchField`, how it connects to screen-level search).
  * Layout primitives (any shared `PageHeader`, `PageBody`, etc., if you add them).
* Props conventions:

  * Variant names (`primary`, `secondary`, `ghost`, `danger`).
  * Size names (`sm`, `md`, `lg`).
  * `tone` / `status` fields (`info`, `success`, `warning`, `danger`).
* Accessibility patterns:

  * ARIA practices for tabs, dropdowns, context menus.
  * Focus management, keyboard navigation.
* Keyboard shortcuts:

  * Global shortcuts and where they’re wired up.
  * Workbench-specific shortcuts and how conflicts with browser defaults are avoided.

---

## 13-testing-debugging-and-development-workflow.md

**Goal:** Make it easy for new devs (or agents) to run, test, and change ade-web safely.

**Scope:**

* Vite dev server config:

  * Ports, host, `/api` proxy behavior.
* Vitest config:

  * JSDOM environment, setup file, coverage.
* Recommended testing layers:

  * Unit tests for utilities (`urlState`, storage helpers).
  * Component tests for screens and complex components.
  * Integration-style tests for navigation behavior and workbench flows (where practical).
* Testing patterns:

  * How to mock React Query calls.
  * How to mock the custom router / NavProvider.
  * How to test streaming endpoints (if you simulate them).
* Debugging tips:

  * Using React Query devtools.
  * Common gotchas (e.g. remembering `replace` vs `push` when asserting history).
* CI hooks and expectations (if you have them or plan to).

---

### How this hangs together

* **01** and **02** give people the *mental model* and *physical layout*.
* **03–04** cover the **routing & URL** spine of the app.
* **05–06** cover the **data and auth/RBAC** spine.
* **07–08** describe the core **user‑facing surfaces**.
* **09–10** go deep on the **Config Builder subsystem**.
* **11–12** capture cross‑cutting concerns: persistence, UI primitives, shortcuts.
* **13** closes the loop with **testing & workflow**.

If you’d like, next step I can:

* Refine this list (merge or split items).
* Propose concrete filenames and section headings inside one or two of these docs to set the pattern.
* Or start drafting 01 + 02, including a more opinionated project folder structure and naming rules.
