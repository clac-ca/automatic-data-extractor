# ADE Web

ADE Web is the browser-based front-end for the **Automatic Data Extractor (ADE)** platform.

It serves two main personas:

- **Workspace owners / engineers** – design and evolve **Configurations** (backed by Python configuration packages / `ade_config` projects), manage Safe mode, and administer workspaces, SSO, roles, and members using the **Configuration Builder** workbench.
- **End users / analysts / operators** – upload documents, run extractions, monitor progress, inspect logs and telemetry, and download structured outputs.

ADE Web is intentionally **backend-agnostic**. This README describes **what** the app does and the behaviour it expects from any compatible backend. For deep technical details, see the numbered docs in `./docs` (listed at the end).

---

## 0. If you’re about to change something…

Use these as your “don’t break the mental model” guardrails:

- **Name things after the domain**  
  Use `Workspace`, `Run`, `Configuration`, `Document`, and keep routes/sections aligned (`/documents`, `/runs`, `/config-builder`, `/settings`) and mirrored under `screens/workspace-shell/sections`.  
  See: [`docs/01-domain-model-and-naming.md`](./docs/01-domain-model-and-naming.md)

- **Use canonical routes & URL helpers**  
  Build URLs via `@shared/nav/routes`; keep query params consistent with the filter helpers for Documents/Runs and the builder URL helpers.  
  See: [`docs/03-routing-navigation-and-url-state.md`](./docs/03-routing-navigation-and-url-state.md), [`docs/06-workspace-layout-and-sections.md`](./docs/06-workspace-layout-and-sections.md), [`docs/07-documents-and-runs.md`](./docs/07-documents-and-runs.md)

- **Respect layer boundaries**  
  Do not import “upwards”: `shared/` and `ui/` must not depend on `screens/` or `app/`. ESLint enforces this.  
  See: [`docs/02-architecture-and-project-structure.md`](./docs/02-architecture-and-project-structure.md)

- **Reuse existing patterns**  
  New list/detail flows should copy Documents/Runs; NDJSON streaming should use the shared helper and `ade.event/v1` model; permissions should go through `@schema/permissions` + helpers in `@shared/permissions`.  
  See: [`docs/04-data-layer-and-backend-contracts.md`](./docs/04-data-layer-and-backend-contracts.md), [`docs/07-documents-and-runs.md`](./docs/07-documents-and-runs.md)

- **Check RBAC & Safe mode rules**  
  All run/build/activation actions must be permission-aware and Safe-mode-aware.  
  See: [`docs/05-auth-session-rbac-and-safe-mode.md`](./docs/05-auth-session-rbac-and-safe-mode.md)

For contribution workflow, linting, scripts, and local dev setup, see `CONTRIBUTING.md` plus the docs referenced above.

---

## 1. High-level UX & layout

ADE Web has two major UX layers:

1. **Workspace directory** (`/workspaces`) – where users discover and create workspaces.
2. **Workspace shell** (`/workspaces/:workspaceId/...`) – where users operate *inside* a workspace (Documents, Runs, Configuration Builder, Settings, optional Overview).

Both layers share:

- A top bar (`GlobalTopBar`) with brand/context, search, and a profile menu.
- A main content area that adapts to desktop and mobile.
- A consistent approach to **navigation**, **URL state**, **Safe mode banners**, and **notifications**.

### Workspace directory (`/workspaces`)

After sign-in, users land on the **Workspace directory**:

- Shows all workspaces the user can access (cards).
- Provides workspace search with a global shortcut (`⌘K` / `Ctrl+K`).
- Gated “Create workspace” action (requires `Workspaces.Create`).
- Good empty states for “no workspaces but can create” vs “no workspaces and cannot create”.

See: [`docs/06-workspace-layout-and-sections.md`](./docs/06-workspace-layout-and-sections.md#3-workspace-directory-workspaces)

### Workspace shell (`/workspaces/:workspaceId/...`)

Inside a workspace, the **workspace shell** provides:

- **Left nav (desktop)**  
  Workspace identity + primary sections:
  - Documents  
  - Runs  
  - Configurations (**Configuration Builder**)  
  - Settings  
  (and optional Overview)

- **Top bar**  
  Workspace name, optional environment label (`Production`, `Staging`), section-aware search (`GlobalSearchField`), and `ProfileDropdown`.

- **Mobile nav**  
  Left nav becomes a slide-in drawer opened via a menu button and closed on navigation, outside click, or Esc.

- **Safe mode banner**  
  Persistent when Safe mode is enabled, explaining why new runs/builds/activations are blocked.

- **Notifications**  
  Toasts for transient success/error; banners for cross-cutting issues (Safe mode, connectivity, console auto-collapse, etc).

Some routes (notably the **Configuration Builder workbench**) can temporarily hide or dim parts of the shell for an immersive editing layout.

See: [`docs/06-workspace-layout-and-sections.md`](./docs/06-workspace-layout-and-sections.md)

---

## 2. Core concepts (domain model)

ADE Web’s domain language is shared across UI copy, types, and routes:

- **Workspace**  
  Primary unit of organisation and isolation. Owns documents, runs, configurations, membership/roles, and settings (name, slug, environment labels, Safe mode status).  
  See: [`docs/01-domain-model-and-naming.md`](./docs/01-domain-model-and-naming.md#32-workspace)

- **Document**  
  Immutable input file (Excel, CSV, PDF, etc.) uploaded into a workspace. Tracks status (`uploaded`, `processing`, `processed`, `failed`, `archived`) and the last run status. Multi-sheet spreadsheets expose worksheet metadata via a document-sheets endpoint.  
  See: [`docs/07-documents-and-runs.md`](./docs/07-documents-and-runs.md#2-documents)

- **Run**  
  Single execution of ADE against one or more documents using a particular configuration. The UI concept is **Run** with `runId`; the HTTP API uses `/runs` routes.  
  Supports `RunOptions` (camelCase in the UI; snake_case in the API) for `dryRun`, `validateOnly`, `forceRebuild`, and `inputSheetNames`, with an optional `mode` view-model helper (`"normal" | "validation" | "test"`).  
  See: [`docs/07-documents-and-runs.md`](./docs/07-documents-and-runs.md#3-runs)

- **Configuration & configuration package**  
  Workspace concept that describes how ADE interprets and transforms documents. Backed by an installable Python `ade_config` package; versions are exposed as **Configuration versions** with a simple lifecycle: **Draft → Active → Archived**.  
  See: [`docs/01-domain-model-and-naming.md`](./docs/01-domain-model-and-naming.md#33-configuration), [`docs/08-configurations-and-config-builder.md`](./docs/08-configurations-and-config-builder.md)

- **Build**  
  Environment build for a given configuration (virtualenv with `ade_engine` + configuration). Builds are backend entities; ADE Web mostly interacts with them indirectly via runs and streaming events.  
  See: [`docs/01-domain-model-and-naming.md`](./docs/01-domain-model-and-naming.md#34-build), [`docs/04-data-layer-and-backend-contracts.md`](./docs/04-data-layer-and-backend-contracts.md#47-configurations--builds-configurationsapi-buildsapi)

- **Manifest & schema**  
  Structured description of expected outputs (tables, columns, transforms, validators) surfaced in the Configuration Builder. ADE Web patches the manifest without dropping unknown fields so the backend can evolve independently.  
  See: [`docs/08-configurations-and-config-builder.md`](./docs/08-configurations-and-config-builder.md#7-manifest-and-schema-integration)

- **Safe mode**  
  Global kill switch for engine execution. When enabled, new runs, builds, validations, and activations are blocked; read-only operations continue to work. Safe mode is toggled from a system-level Settings surface (permission-gated), and ADE Web shows a workspace banner and disables run/build controls with explanatory tooltips.  
  See: [`docs/05-auth-session-rbac-and-safe-mode.md`](./docs/05-auth-session-rbac-and-safe-mode.md#6-safe-mode)

- **Roles & permissions (RBAC)**  
  Users hold roles per workspace; roles map to permission strings such as `Workspace.Runs.Run`, `Workspace.Configurations.ReadWrite`, or `System.SafeMode.ReadWrite`. The backend enforces RBAC; the frontend hides/disables controls based on effective permissions.  
  See: [`docs/05-auth-session-rbac-and-safe-mode.md`](./docs/05-auth-session-rbac-and-safe-mode.md#5-rbac-model-and-permission-checks)

For a complete domain index and naming contract (IDs, routes, folder layout), start with  
[`docs/01-domain-model-and-naming.md`](./docs/01-domain-model-and-naming.md).

---

## 3. Routing, navigation, and URL state

ADE Web is a single-page React app with a small custom navigation layer built on `window.history`.

### Top-level routes

Handled by `App` + `ScreenSwitch`:

- `/` – entry strategy (decide login vs setup vs app).
- `/login`, `/auth/callback`, `/logout`, `/setup` – auth and first-run setup.
- `/workspaces`, `/workspaces/new` – workspace directory & creation.
- `/workspaces/:workspaceId/...` – workspace shell.
- Anything else – global “Not found” screen.

Workspace sections live under:

- `/workspaces/:workspaceId/documents`
- `/workspaces/:workspaceId/runs`
- `/workspaces/:workspaceId/config-builder`
- `/workspaces/:workspaceId/settings`
- Optional `/workspaces/:workspaceId/overview`

Route builders live in `@shared/nav/routes.ts` and are the **only** place strings like `/workspaces/${id}/runs` should appear.

See: [`docs/03-routing-navigation-and-url-state.md`](./docs/03-routing-navigation-and-url-state.md)

### Navigation primitives

- `NavProvider` – owns `location`, listens to `popstate`, coordinates blockers.
- `useLocation()` – read current `{ pathname, search, hash }`.
- `useNavigate()` – programmatic SPA navigation (`push`/`replace`).
- `useNavigationBlocker()` – opt-in blockers (e.g. workbench unsaved changes).
- `Link` / `NavLink` – SPA links that preserve normal browser behaviours (right-click, modifier-click, etc.).

### URL-encoded state

Important UI state is encoded in **query parameters**, not local component state, so views are shareable and refresh-safe. Examples:

- Documents filters: `q`, `status`, `sort`, `view`  
  (See [`docs/07`](./docs/07-documents-and-runs.md#31-documents-screen-architecture))
- Runs filters: `status`, `configurationId`, `initiator`, `from`, `to`  
  (See [`docs/07`](./docs/07-documents-and-runs.md#6-runs-ledger-screen))
- Workspace Settings tab: `view=general|members|roles`  
  (See [`docs/06`](./docs/06-workspace-layout-and-sections.md#9-guidelines-for-new-sections))
- Configuration Builder workbench layout: `file`, `pane`, `console`, `view`  
  (See [`docs/09-workbench-editor-and-scripting.md`](./docs/09-workbench-editor-and-scripting.md#5-workbench-url-state))

Utilities for this live in `@shared/url-state`: `useSearchParams`, `toURLSearchParams`, `setParams`, and the builder-specific helpers.

---

## 4. Documents & Runs

The workspace shell exposes two key operational sections:

### Documents section

**Route:** `/workspaces/:workspaceId/documents`  

Responsibilities:

- List and filter documents in the workspace.
- Upload new documents (`⌘U` / `Ctrl+U`).
- Show status (`uploaded`, `processing`, `processed`, `failed`, `archived`) and the last run status.
- Trigger runs for a selected configuration, optionally per-document run preferences (preferred configuration and sheet selection).

See: [`docs/07-documents-and-runs.md`](./docs/07-documents-and-runs.md#3-documents-screen-architecture)

### Runs section

**Route:** `/workspaces/:workspaceId/runs`  

Responsibilities:

- Workspace-wide ledger of runs (REST `/runs` on the backend).
- Filter by status, configuration, timeframe, and initiator.
- Link to run detail, logs (via NDJSON replay), event downloads, and outputs (artifact and per-file downloads).

Run creation, options (`RunOptions`), and event streaming (`ade.event/v1`) are described in detail in:  

- [`docs/07-documents-and-runs.md`](./docs/07-documents-and-runs.md)  
- [`docs/04-data-layer-and-backend-contracts.md`](./docs/04-data-layer-and-backend-contracts.md#6-streaming-ndjson-events)

---

## 5. Configuration Builder & workbench

The **Configurations** section (Configuration Builder) is where workspace owners and engineers manage configuration packages.

**Route:** `/workspaces/:workspaceId/config-builder`  
**Folder:** `screens/workspace-shell/sections/config-builder`  
**Nav label:** “Configuration Builder”

Responsibilities:

- Show configurations per workspace and their active/draft/archived versions.
- Provide actions: create, clone, export, duplicate, make active, and archive configurations.
- Launch the **Configuration Builder workbench** for editing a specific configuration (file tree + Monaco editor + console + validation).

### Workbench

The workbench is a dedicated editing window with:

- File tree (`WorkbenchFileNode`) built from backend listings.
- Tabbed Monaco editor (`CodeEditor`) with ADE-specific Python helpers.
- Bottom console/validation panel for streaming build/run logs and validation issues.
- Inspector panel for file metadata.
- Window states: restored, maximised, docked; plus navigation blockers for unsaved changes.
- URL-driven layout (`file`, `pane`, `console`, `view`) and persisted layout/theme preferences.

Environment readiness is handled automatically when runs start:

- **Validation run** – run validators only (`RunOptions.validateOnly: true`).
- **Test run** – run against a sample document; the **Test** split button offers “Test” vs “Force build and test” (the latter sets `RunOptions.forceRebuild`, backend rebuilds inline before running).

See:

- [`docs/08-configurations-and-config-builder.md`](./docs/08-configurations-and-config-builder.md)
- [`docs/09-workbench-editor-and-scripting.md`](./docs/09-workbench-editor-and-scripting.md)

---

## 6. Auth, session, RBAC & Safe mode

ADE Web delegates authentication and authorisation to the backend and treats permissions as data.

Frontend responsibilities:

- Drive login/setup/logout flows.
- Fetch **Session** (current user, workspace memberships, default workspace).
- Fetch **effective permissions** (global + per-workspace).
- Toggle UI based on permissions and Safe mode.

Key concepts:

- Email/password and SSO login, with safe `redirectTo` handling.
- Separate global vs workspace-scoped roles and role assignments.
- `useEffectivePermissionsQuery` + helpers like `useCanInWorkspace` / `useCanStartRuns`.
- Safe mode status (`enabled`, `detail`) from `/system/safe-mode` with a workspace banner and disabled run/build/activation controls.

See: [`docs/05-auth-session-rbac-and-safe-mode.md`](./docs/05-auth-session-rbac-and-safe-mode.md)

---

## 7. Front-end architecture & tooling

ADE Web is a React + TypeScript SPA built with Vite and React Query.

High-level layout (under `apps/ade-web/src`):

- `app/` – application shell, providers, and top-level routing.
- `screens/` (aliased as `@screens`) – feature/screen slices (auth, workspace directory, workspace shell, sections).
- `ui/` – presentational component library (buttons, forms, top bar, search, tabs, context menus, code editor).
- `shared/` – cross-cutting utilities and API modules (HTTP client, nav helpers, URL state, NDJSON streaming, permissions).
- `schema/` – handwritten domain models and mapping from generated types.
- `generated-types/` – OpenAPI-generated types.
- `test/` – Vitest setup and helpers.

Data layer:

- Shared HTTP client → domain API modules (`workspacesApi`, `documentsApi`, `runsApi`, `configurationsApi`, `buildsApi`, `systemApi`, `authApi`, `permissionsApi`, `rolesApi`, `apiKeysApi`) → feature-local React Query hooks.

Tooling highlights:

- Vite dev server with `/api` proxy → local backend.
- React Query with conservative defaults (`retry: 1`, `staleTime: 30s`).
- Vitest + Testing Library, jsdom, and a11y tooling.

See:  

- [`docs/02-architecture-and-project-structure.md`](./docs/02-architecture-and-project-structure.md)  
- [`docs/04-data-layer-and-backend-contracts.md`](./docs/04-data-layer-and-backend-contracts.md)  
- [`docs/10-ui-components-a11y-and-testing.md`](./docs/10-ui-components-a11y-and-testing.md)

---

## 8. Backend expectations (contracts)

ADE Web is backend-agnostic but assumes a set of HTTP APIs and behaviours under `/api/v1/...`:

- **Auth & session** – setup status, login/logout/refresh, auth providers, session endpoint exposing identity + membership; consistent `401` vs `403` semantics.
- **Workspaces** – list/create/update/delete, default workspace, membership and workspace-scoped roles.
- **Documents** – upload, list with filters, download, optional worksheet metadata.
- **Runs** – workspace run ledger (`/workspaces/{workspace_id}/runs` for list/create), run detail/outputs/logs (`/runs/{run_id}/...`), streaming NDJSON event streams using the `ade.event/v1` envelope.
- **Configurations & Configuration Builder** – configuration metadata, version lifecycle, file listing and content APIs, validation endpoint, configuration-scoped runs.
- **Builds** – build entities and logs (used primarily by admin/specialised flows; day-to-day workbench flows rely on run creation with auto-rebuilds and `force_rebuild`).
- **Safe mode** – status and toggle endpoints, permission-gated.
- **Security** – strict tenant isolation, safe `redirectTo` handling, and compatible CORS/CSRF for browser SPAs.

As long as these contracts are honoured, ADE Web can be reused with different backend implementations without changing the user experience described here.

See: [`docs/04-data-layer-and-backend-contracts.md`](./docs/04-data-layer-and-backend-contracts.md)

---

## 9. Reference: docs index

The numbered docs under `apps/ade-web/docs` are the **source of truth** for ADE Web’s behaviour:

1. [`01-domain-model-and-naming.md`](./docs/01-domain-model-and-naming.md)  
   Domain concepts and naming contract (Workspace, Document, Run, Configuration, Build, Artifact, etc.).

2. [`02-architecture-and-project-structure.md`](./docs/02-architecture-and-project-structure.md)  
   On-disk layout, layers, and dependency rules.

3. [`03-routing-navigation-and-url-state.md`](./docs/03-routing-navigation-and-url-state.md)  
   Routes, `NavProvider`, SPA links, and URL query conventions.

4. [`04-data-layer-and-backend-contracts.md`](./docs/04-data-layer-and-backend-contracts.md)  
   HTTP client, API modules, React Query, and backend `/api/v1/...` expectations (including NDJSON streams).

5. [`05-auth-session-rbac-and-safe-mode.md`](./docs/05-auth-session-rbac-and-safe-mode.md)  
   Auth flows, session model, RBAC, and Safe mode semantics.

6. [`06-workspace-layout-and-sections.md`](./docs/06-workspace-layout-and-sections.md)  
   Workspace directory, workspace shell, and main sections.

7. [`07-documents-and-runs.md`](./docs/07-documents-and-runs.md)  
   Document model, runs model, Documents & Runs sections, run options, and per-document run preferences.

8. [`08-configurations-and-config-builder.md`](./docs/08-configurations-and-config-builder.md)  
   Configuration domain model and the Configurations section (Configuration Builder).

9. [`09-workbench-editor-and-scripting.md`](./docs/09-workbench-editor-and-scripting.md)  
   Configuration Builder workbench, file tree, tabs, console, validation, URL state, and ADE scripting helpers.

10. [`10-ui-components-a11y-and-testing.md`](./docs/10-ui-components-a11y-and-testing.md)  
    UI component library, accessibility conventions, keyboard shortcuts, preferences, and testing philosophy.
