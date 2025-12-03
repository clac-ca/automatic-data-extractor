# 010-WORK-PACKAGE – ADE Web

> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * When you make a design/architecture decision, **update this document first**, then the relevant supporting doc, then the code.
> * Prefer small, incremental commits aligned to checklist items.
> * Do not introduce new navigation/streaming/auth patterns outside the ones defined here and in the supporting specs.

---

## Related Documents (read alongside this workpackage)

These documents live in the same folder as this workpackage:

- `020-ARCHITECTURE.md` – High-level architecture, folder structure, data layer, and diagrams.
- `030-UX-FLOWS.md` – UX goals and detailed flows for Workspace, Documents, Run Detail, and Config Builder.
- `040-DESIGN-SYSTEM.md` – Design tokens, visual language, and component guidelines.
- `050-RUN-STREAMING-SPEC.md` – Run streaming behavior, `RunStreamState`, SSE/NDJSON handling, and replay rules.
- `060-NAVIGATION.md` – Custom navigation/router design (vanilla React + history), route definitions, and URL patterns.
- `070-TEST-PLAN.md` – Test strategy, coverage expectations, and concrete test cases.
- `080-MIGRATION-AND-ROLLOUT.md` – Archive strategy, parity checklist, and go-live plan vs `apps/ade-web-legacy`.
- `090-FUTURE-WORKSPACES.md` – Workspaces UX & architecture; **Phase 1 workspace selector + create flows are now in scope** for this workpackage.
- `100-CONFIG-BUILDER-EDITOR.md` – Detailed specification for the **VS Code–style Config Builder workbench** (Explorer, editor tabs, bottom console panel, run integration).
- `110-BACKEND-API.md` – Backend API surface, route groupings, and frontend integration conventions (including OpenAPI-generated types).
- `120-AUTH-AND-SESSIONS.md` – Auth/session/SSO model, bootstrap flow, and `AuthProvider` state machine.
- `130-DOCUMENTS-UX-AND-API.md` – Documents list/detail UX and corresponding API integration.
- `140-RUNS-AND-OUTPUTS.md` – Runs, outputs, logs, summaries, and how they map to UI.
- `150-CONFIGURATIONS-API.md` – Configurations API: metadata, file tree, validation, builds.

If a section here feels too high-level, check the corresponding document for details.

---

## Work Package Checklist

> **Agent note:**  
> Add brief status notes inline when helpful, e.g.  
> `- [x] Login screen wired to /auth/session (2025-12-02)`  

This checklist is ordered in the **sequence we design and implement things**:  
1) **Auth & bootstrap**, 2) **Workspaces**, 3) **Shell & navigation**, 4) **Design system**, 5) **API wiring**, 6) **Screens & streaming**, 7) **Tests & migration**, 8) **UX polish**.

---

### 1. Planning, terminology & doc alignment

- [ ] Confirm core terminology and keep it consistent across all docs:
  - Workspace, Configuration, Document, Run, Build, Sheet, Output, Session, Login.
- [ ] Update `020-ARCHITECTURE.md` to reflect auth + workspace selector as first-class concerns (AuthProvider, WorkspaceProvider, workspace-aware routes).
- [ ] Update `030-UX-FLOWS.md` with end-to-end flows starting at **login → workspace → Documents/Configs**.
- [ ] Update `090-FUTURE-WORKSPACES.md` to:
  - [ ] Mark **Phase 1** workspace selector + create workspace flows as **in scope** for this workpackage.
  - [ ] Keep advanced workspace UX/features (activity feed, cross-workspace analytics) as **future work**.
- [ ] Update `100-CONFIG-BUILDER-EDITOR.md` to match the VS Code–style workbench described here (Explorer, editor tabs, bottom console).
- [ ] Confirm `110-BACKEND-API.md` and `120-AUTH-AND-SESSIONS.md` match the actual OpenAPI surface in the repo.

---

### 2. App scaffolding & architecture (vanilla React)

- [ ] Create new `apps/ade-web` Vite+React+TS app (strict mode) with **vanilla React navigation** (no React Router).
- [ ] Configure base folder structure with aliases (matching `020-ARCHITECTURE.md`):

```text
  apps/ade-web/src/
    app/          # AppShell, nav, providers
    screens/      # Login, Setup, WorkspaceList, WorkspaceHome, Documents, RunDetail, ConfigBuilder
    features/     # auth, workspaces, documents, runs, configs, ui, etc.
    ui/           # design system
    shared/       # api-client, hooks, storage, errors
    schema/       # curated OpenAPI exports + view models
    test/         # testing setup & helpers
```

* [ ] Wire TypeScript strict mode, ESLint, Prettier, and Vitest (per `070-TEST-PLAN.md`).
* [ ] Implement `shared/api-client/client.ts`:

  * [ ] Uses `fetch` with `credentials: "include"` and base URL from env.
  * [ ] Normalizes errors to a typed `ApiError`.
  * [ ] Hooks in 401-handling (lazy `session/refresh`, see `120-AUTH-AND-SESSIONS.md`).

---

### 3. Auth, setup, login & bootstrap (Day-one API wiring)

> **Goal:** On day one, the app should boot into a real **login / SSO / setup** flow backed by the actual API — no fake auth.

* [ ] Implement `features/auth/api/authApi.ts` (per `120-AUTH-AND-SESSIONS.md`):

  * [ ] `getSetupStatus() → /setup/status`
  * [ ] `runSetup() → /setup`
  * [ ] `getSession() → /auth/session`
  * [ ] `loginWithPassword() → /auth/session (POST)`
  * [ ] `logout() → /auth/session (DELETE)`
  * [ ] `refreshSession() → /auth/session/refresh`
  * [ ] `getProviders() → /auth/providers`
  * [ ] `getBootstrap() → /bootstrap`

* [ ] Implement `AuthProvider` with state machine:

  States: `unknown` → `setup-required` → `unauthenticated` → `authenticating` → `authenticated` → `error`.

  * [ ] On mount: `setup/status` → `auth/session` → `bootstrap`.
  * [ ] Lazy refresh on 401 (call `refreshSession`, then retry once).
  * [ ] Expose `useAuth()` with:

    * `state`, `user`, `bootstrap`, `permissions`.
    * `loginWithPassword(credentials)`.
    * `beginSso(provider)` → redirect to `provider.start_url`.
    * `logout()`.

* [ ] Implement **Setup screen** (`screens/Auth/SetupScreen.tsx`):

  * [ ] Shown when `authState === "setup-required"`.
  * [ ] Supports initial admin creation via `/setup`.
  * [ ] Handles `force_sso` case (SSO-based setup only).

* [ ] Implement **Login screen** (`screens/Auth/LoginScreen.tsx`):

  * [ ] Uses `authApi.getProviders()` to discover SSO providers + `force_sso`.
  * [ ] If `force_sso`, show only SSO buttons.
  * [ ] Else show:

    * Email/password form (password login).
    * SSO provider buttons (with labels/icons).
  * [ ] Error UX:

    * Friendly messages for invalid credentials, rate limiting, generic errors.
    * No raw error codes.

* [ ] Integrate auth into `AppShell`:

  * [ ] While `state === "unknown"` → show centered loading/splash.
  * [ ] `setup-required` → Setup screen.
  * [ ] `unauthenticated` → Login screen.
  * [ ] `authenticated` → main app (Workspace routes).

---

### 4. Workspaces: selector, creation & current workspace context

> **Goal:** After login, users choose or create a workspace, and the rest of the app runs **inside that workspace context**.

* [ ] Implement `features/workspaces/api/workspacesApi.ts`:

  * [ ] `listWorkspaces() → GET /workspaces`
  * [ ] `getWorkspace(workspaceId) → GET /workspaces/{id}`
  * [ ] `createWorkspace(payload) → POST /workspaces`
  * [ ] `setDefaultWorkspace(workspaceId) → POST /workspaces/{id}/default`
  * [ ] (Optional) membership/roles endpoints for later UI.

* [ ] Add workspace-aware routes (update `060-NAVIGATION.md` + code):

  ```ts
  type Route =
    | { name: 'workspaceList' }
    | { name: 'workspaceCreate' }
    | { name: 'workspaceHome'; params: { workspaceId: string } }
    | { name: 'documents'; params: { workspaceId: string } }
    | { name: 'documentDetail'; params: { workspaceId: string; documentId: string } }
    | { name: 'runDetail'; params: { workspaceId: string; runId: string; sequence?: number | null } }
    | { name: 'configBuilder'; params: { workspaceId: string; configId: string } }
    | { name: 'notFound' };
  ```

* [ ] Implement **Workspace context provider** (`WorkspaceProvider`):

  * [ ] Tracks `currentWorkspaceId` + `currentWorkspace` object.
  * [ ] Derives initial workspace from:

    * `BootstrapEnvelope.workspaces` + `user.preferred_workspace_id`.
    * URL route params.
  * [ ] Exposes `useWorkspace()` + `setCurrentWorkspaceId()`.

* [ ] Implement **Workspace list screen** (`screens/Workspace/WorkspaceListScreen.tsx`):

  * [ ] Shows list of workspaces (`listWorkspaces()`).
  * [ ] Primary action: “Create workspace” → `workspaceCreate` route.
  * [ ] Selecting a workspace navigates to `workspaceHome` (Documents or Home, depending on UX choice in `030-UX-FLOWS.md`).

* [ ] Implement **Workspace create screen** (`screens/Workspace/WorkspaceCreateScreen.tsx`):

  * [ ] Form: workspace name + optional description.
  * [ ] On success → mark as default + navigate to its `workspaceHome`.

* [ ] Implement **Workspace switcher** in app header:

  * [ ] Shows current workspace name.
  * [ ] Dropdown list of accessible workspaces.
  * [ ] “Create workspace…” option at the bottom.
  * [ ] Switch updates workspace context and navigates to that workspace’s home route.

* [ ] Update `030-UX-FLOWS.md` to document:

  * [ ] First-login flow when 0, 1, or >1 workspaces exist.
  * [ ] Guidelines for invalid workspace IDs (friendly error and redirect to workspace list).

---

### 5. Navigation, shell & layout

* [ ] Implement `NavigationProvider` and `useNavigation()` per `060-NAVIGATION.md` (no React Router):

  * [ ] `parseLocation(location) → Route`.
  * [ ] `buildUrl(route) → string`.
  * [ ] `navigate(route)` / `replace(route)`.
  * [ ] `Link` component that respects middle-click / new tab.
* [ ] Implement `AppShell` layout:

  * [ ] Global providers: Auth, Workspace, Query, Theme, Toast, RunStreamRoot.
  * [ ] Header with:

    * Brand, workspace switcher, user menu (profile, logout).
  * [ ] Main content switching on `route.name`.
* [ ] Add skeleton screens (rendered once auth+workspace are wired) for:

  * [ ] `WorkspaceHomeScreen`
  * [ ] `DocumentsScreen`
  * [ ] `RunDetailScreen`
  * [ ] `ConfigBuilderScreen`
  * [ ] Each starting with real data fetch hooks (no stub data).

---

### 6. Design system & first-class UX details

> **Goal:** Small details (empty states, loading, focus, microcopy) are planned, not bolted on last-minute.

* [ ] Implement design tokens + theme provider per `040-DESIGN-SYSTEM.md`:

  * [ ] Colors, status tokens, typography, spacing, radii.
  * [ ] Light theme default; dark theme optional.
* [ ] Implement UI primitives (`ui/components`):

  * [ ] Button, IconButton, Input, Select, Checkbox, Radio, Switch.
  * [ ] Tabs, Dialog, Tooltip, Toast, StatusPill.
  * [ ] Table, EmptyState, Skeleton.
* [ ] Implement layout primitives (`ui/layout`):

  * [ ] `Page`, `PageHeader`.
  * [ ] `SplitPane`, `Panel`, `Sidebar`, `ScrollArea`.
  * [ ] `SplitPane` behavior:

    * [ ] Drag-to-resize handles (horizontal + vertical).
    * [ ] Double-click to reset to default ratio.
    * [ ] Programmatic collapse/expand of panes.
    * [ ] Persisted sizes per user + per screen (esp. Config Builder) via local storage.
* [ ] Define micro UX patterns in `040-DESIGN-SYSTEM.md`:

  * [ ] Loading skeleton standards (for lists, details, console).
  * [ ] Empty state patterns (icon + title + body + CTA).
  * [ ] Error display patterns (inline vs toast).
  * [ ] Focus & keyboard behavior (tabs, dialogs, lists).

---

### 7. API integration: backend wiring (no local mocks in production code)

* [ ] Wire `schema/` to re-export OpenAPI-generated types (`openapi.d.ts`) per `110-BACKEND-API.md`.
* [ ] Implement feature API modules:

  * [ ] `features/auth/api/authApi.ts` (already above).
  * [ ] `features/workspaces/api/workspacesApi.ts`.
  * [ ] `features/documents/api/documentsApi.ts` (per `130-DOCUMENTS-UX-AND-API.md`).
  * [ ] `features/runs/api/runsApi.ts` (per `140-RUNS-AND-OUTPUTS.md`).
  * [ ] `features/configs/api/configsApi.ts` (per `150-CONFIGURATIONS-API.md`).
* [ ] Ensure **no screen** calls `fetch` directly; everything goes through feature API modules.
* [ ] Ensure all feature APIs use OpenAPI types for inputs/outputs and convert only to small view models at the edges.

---

### 8. Screens & UX flows – implementation order

We build screens in this order, each time **hooked to real backend data**:

#### 8.1 Workspace Home

* [ ] Implement `WorkspaceHomeScreen` as launchpad:

  * [ ] Top-level page showing:

    * “Documents” card with shortcut to Documents list + some recent docs.
    * “Configurations” card with shortcut to Config Builder + some recent configs.
    * “Recent runs” list (from `workspaces/{id}/runs`).
  * [ ] Uses design system components.

#### 8.2 Documents

* [ ] Implement document list & detail per `030-UX-FLOWS.md` + `130-DOCUMENTS-UX-AND-API.md`:

  * [ ] `DocumentList`:

    * Columns: name, status, last run, uploader, size, expires.
    * Sorting wired to `sort` query param.
  * [ ] `UploadPanel`:

    * Real `POST /documents` with metadata + `expires_at`.
    * Progress, error states (413, 400, etc.).
  * [ ] `DocumentDetail`:

    * Uses `GET /documents/{id}` + `/sheets` + `listWorkspaceRuns(..., input_document_id)`.
    * Header with name + status + last run summary.
    * Tabs: Overview, Runs, Outputs (Outputs via runs outputs).
  * [ ] “Start run” from document:

    * Creates run via configs endpoint (user picks config if multiple).
    * Immediately connects streaming via `useRunStream`.

#### 8.3 Run Detail

* [ ] Implement `RunDetailScreen` per `030-UX-FLOWS.md` + `050-RUN-STREAMING-SPEC.md` + `140-RUNS-AND-OUTPUTS.md`:

  * [ ] Load `RunResource` and `RunSummaryV1`.
  * [ ] Use `useRunStream` and `useRunTelemetry` for live/replay.
  * [ ] Show:

    * Header (run ID, status, config, document link).
    * `RunTimeline`, `RunSummaryPanel`.
    * Console tab (`RunConsole`) with filters + follow-tail + “jump to first error”.
    * Validation tab (table summaries) linking back to Config Builder when possible.
    * Outputs panel listing `RunOutputFile` with download actions.
  * [ ] Support `sequence` query param deep links (replay to a specific event).

#### 8.4 Config Builder (VS Code–style workbench)

> **Goal:** The Config Builder should **look and feel like VS Code**.
> Left: collapsible **Explorer** with configuration files.
> Center: tabbed **code editor** that dominates the layout.
> Bottom: resizable **console panel** for runs/validation.
> Everything is draggable, resizable, and collapsible; the emphasis is always on the code.

* [ ] Implement Config Builder as a **VS Code–style workbench**, per `100-CONFIG-BUILDER-EDITOR.md` (update that doc accordingly):

  ##### Layout

  * [ ] Full-screen `ConfigBuilderScreen` organized as:

    ```text
    ┌───────────────────────────────────────────────────────────────┐
    │ Header / Toolbar (Config title, actions, breadcrumbs)        │
    ├───────────────┬───────────────────────────────────────────────┤
    │ Explorer       │ Editor Area (tabs + code editor)             │
    │ (left)         │                                             │
    │                │                                             │
    │                │                                             │
    ├───────────────┴───────────────────────────────────────────────┤
    │ Bottom Panel (Console / Validation / Problems)               │
    └───────────────────────────────────────────────────────────────┘
    ```

  * [ ] **Explorer (left sidebar)**:

    * Default width ~260–280px.
    * Implemented via `SplitPane` so it’s **resizable** and **collapsible**.
    * Contains a single primary view for now: **“Explorer”** showing the configuration file tree.

  * [ ] **Editor Area (center)**:

    * Occupies the majority of the horizontal and vertical space.
    * At top: VS Code–style **tab strip** (`EditorTabs`) showing open files.
    * Below tabs: main **code editor** (Monaco-like) with:

      * Line numbers, syntax highlighting, bracket matching.
      * Search within file (Ctrl+F), optional minimap (future).
      * Error/warning squiggles wired to validation results.
    * Optional secondary “inspector”/form view is:

      * Shown as a **collapsible right-hand panel** or a split inside the editor.
      * Always secondary to the code; code editor stays visible.

  * [ ] **Bottom Panel (console)**:

    * VS Code–style **panel** docked to the bottom.
    * Resizable via horizontal `SplitPane` and **collapsible** with a toggle button in the toolbar.
    * Contains tabs (at least):

      * **Console** – streaming logs and events for the active workbench run.
      * **Validation / Problems** – structured list of config validation issues.
      * (Future) “Runs” or “History”.

  * [ ] **Responsiveness & persistence**:

    * [ ] All splits (Explorer width, bottom panel height, optional inspector width) are resizable.
    * [ ] Each pane (Explorer, bottom panel, inspector) is collapsible via:

      * Clickable icons in the toolbar.
      * Double-click on splitter (optional).
    * [ ] Persist layout settings **per user + config** in local storage:

      * Last Explorer width.
      * Last bottom panel height.
      * Whether panels were collapsed.

  ##### Explorer (file tree)

  * [ ] Implement `ConfigExplorerPane`:

    * [ ] Displays configuration file tree, grouped by logical roots (e.g., `config/`, `schemas/`, `transforms/`, etc.).
    * [ ] Supports:

      * Expand/collapse of folders.
      * Click to open file → focuses or adds tab in `EditorTabs`.
      * Context menu or inline icons for:

        * **New file** (under folder or root).
        * **New folder**.
        * **Rename**.
        * **Delete** (with confirmation).
    * [ ] Visual cues:

      * “Dirty”/unsaved indicator (●) next to file names.
      * Icons per file type (YAML, JSON, script, etc.) using design system icon set.
    * [ ] Keyboard behavior:

      * Arrow keys to navigate tree.
      * Enter to open.
      * Delete to delete (with confirm).

  ##### Editor tabs & code editor

  * [ ] Implement `ConfigEditorTabs`:

    * [ ] Standard VS Code–like tab strip:

      * Shows file name and relative path on hover.
      * Close button on each tab.
      * Unsaved indicator (●) on tab title.
      * Support for reordering tabs via drag-and-drop (stretch goal).
    * [ ] Right-click context menu (stretch):

      * “Close”, “Close Others”, “Close to the Right”, “Reveal in Explorer”.

  * [ ] Code editor behavior:

    * [ ] Use a code editor component (Monaco or similar) configured with:

      * Line numbers, syntax highlight, indent guides.
      * Auto-indent on newline.
      * Config-specific language or YAML/JSON modes.
    * [ ] Integrate validation:

      * Errors/warnings from validation feed into editor diagnostics.
      * Clicking a “Problem” scrolls and focuses the corresponding location in the code.
    * [ ] Emphasis on **code-first**:

      * The code editor is always visible (unless the user explicitly closes all tabs).
      * Any structured inspector or helper UI must be secondary (side panel or overlay).

  ##### Header toolbar

  * [ ] Implement `ConfigHeaderToolbar` across the top:

    * Left:

      * Breadcrumbs: Workspace → Configurations → [Config Name].
      * Config status pill (Draft, Valid, Invalid, Published).
    * Right:

      * Primary actions: **Save**, **Validate**, **Run**.
      * Drop-down to choose run target (document set, sample, etc., as defined in flows).
      * “Open latest run” shortcut when there is a recent workbench run.

  ##### Bottom console & problems

  * [ ] Implement `ConfigRunPanel` anchored in the bottom panel:

    * Tabs (at minimum):

      * **Console**:

        * Stream of log lines from `useRunStream`.
        * Filters (info/warn/error).
        * “Follow tail” toggle.
      * **Validation / Problems**:

        * Table/list of validation issues (severity, message, file, line).
        * Clicking an item focuses file + line in editor.
    * [ ] Connected to shared run streaming (`features/runs/stream`):

      * Reuses `RunConsole` component under the hood.
      * Uses the same `RunStreamState` and replay behavior as Run Detail.

  ##### Workbench run behavior

  * [ ] Implement `useWorkbenchRun` hook:

    * [ ] Creates runs via `createRun(configurationId, { stream: true, options })`.
    * [ ] Attaches to streaming via `useRunStream`.
    * [ ] Exposes:

      * `status` (idle, running, failed, succeeded).
      * `currentRunId`.
      * Start/stop/retry operations.
    * [ ] Used by both:

      * Header toolbar “Run” button.
      * Bottom panel run controls (e.g., “Re-run with same inputs”).

  ##### Keyboard & VS Code affordances (MVP)

  * [ ] Implement basic shortcuts:

    * [ ] `Ctrl+S` / `Cmd+S` → Save.
    * [ ] `Ctrl+Enter` / `Cmd+Enter` → Run.
    * [ ] `Ctrl+`` (backtick) → toggle bottom console panel (optional).
  * [ ] Keep command palette (`Ctrl+Shift+P`) as future work, but design layout so it could be added later without major changes.

---

### 9. Run streaming & shared run UI

> **Goal:** One shared streaming foundation and UI used in Documents, Run Detail, and Config Builder — no per-screen special cases.

* [ ] Implement `features/runs/stream` exactly per `050-RUN-STREAMING-SPEC.md`:

  * [ ] `RunStreamState`, `runStreamReducer`, action types.
  * [ ] `RunStreamProvider` at app root (supports multiple runs in parallel).
  * [ ] `useRunStream(runId, options)` for live SSE + replay controls.
  * [ ] `useRunTelemetry(runId, options)` for NDJSON/historical replay.
  * [ ] Backpressure:

    * Caps on `events` and `consoleLines`.
    * Batched updates to avoid render storms.
* [ ] Implement shared run components (`features/runs/components`):

  * [ ] `RunConsole`
  * [ ] `RunTimeline`
  * [ ] `RunSummaryPanel`
  * [ ] `ValidationSummary`
* [ ] Integrate streaming into all relevant screens:

  * [ ] Documents: live run cards + document detail run panel.
  * [ ] Run Detail: full replay/live experience.
  * [ ] Config Builder: bottom run panel.

---

### 10. Testing, migration & rollout

* [ ] Implement unit tests per `070-TEST-PLAN.md`:

  * [ ] `runStreamReducer` behavior.
  * [ ] Navigation parsing/building round-trips.
  * [ ] Auth state machine (`AuthProvider`).
* [ ] Implement React Testing Library tests for:

  * [ ] Login + SSO flows.
  * [ ] Documents: upload → run → outputs.
  * [ ] Config Builder: open config → edit file → save → run → see console output.
  * [ ] Run Detail: open via URL, deep link with `sequence`.
* [ ] Implement selected E2E (Playwright or similar) for:

  * [ ] Full journey: login → pick workspace → upload doc → run → view run → download outputs.
  * [ ] Config journey: login → pick workspace → open config → edit → run → debug errors in Problems tab.
* [ ] Complete migration tasks per `080-MIGRATION-AND-ROLLOUT.md`:

  * [ ] Move legacy app to `apps/ade-web-legacy`.
  * [ ] Ensure CI builds only new app by default.
  * [ ] Implement rollout + rollback plan.
  * [ ] Validate monitoring dashboards and alerts.

---

### 11. UX polish & “small details that count”

* [ ] Loading & skeletons:

  * [ ] Login & Setup: avoid sudden layout jumps.
  * [ ] Workspace list, Documents list, Run Detail, Config Builder: skeleton states per `040-DESIGN-SYSTEM.md`.
* [ ] Empty states:

  * [ ] No workspaces.
  * [ ] No documents.
  * [ ] No runs yet for a document/config.
* [ ] Error messaging:

  * [ ] Friendly, non-technical messages for common errors (auth, upload failed, run failed).
  * [ ] Clear microcopy for destructive actions (“Archive document”, “Delete config file”).
* [ ] Keyboard accessibility:

  * [ ] Navigation, Tabs, Dialogs, Workspace switcher.
  * [ ] Config Builder: Explorer navigation, tab switching, editor focus, console toggle.
* [ ] Visual polish:

  * [ ] Consistent use of spacing, typography, and color tokens.
  * [ ] Status pills and icons consistent across all screens (runs, documents, configs).
  * [ ] Config Builder theme evokes VS Code (especially in dark mode) while still using our brand tokens.

---

## 1. Objective

Rebuild `apps/ade-web` as a **vanilla React** (no React Router) + TypeScript app that:

1. Starts at a **real login/setup flow** (auth, SSO, sessions).
2. Guides users to a **workspace selector & creator**.
3. Provides first-class experiences for:

   * **Documents**: upload → run → monitor → download.
   * **Configurations**: a **VS Code–style Config Builder** with Explorer, editor tabs, and a bottom console.
   * **Runs**: shared run detail with streaming logs, timeline, validation, and outputs.
4. Is **fully wired to the backend API** from day one (no long-lived mock data in production code).
5. Uses a shared design system and a single streaming foundation across all screens.

We are allowed to archive the current `apps/ade-web` and rebuild as `apps/ade-web` with a clean architecture and UX.

---

## 2. Scope & Non-Goals

### In scope (for this workpackage)

* Auth/session handling with password + SSO (`120-AUTH-AND-SESSIONS.md`).
* Setup/first admin flow.
* Workspace list and creation, workspace switcher (Phase 1 from `090-FUTURE-WORKSPACES.md`).
* Navigation, layout, design system (`020-ARCHITECTURE.md`, `040-DESIGN-SYSTEM.md`, `060-NAVIGATION.md`).
* Documents list/detail, upload, and linkage to runs (`130-DOCUMENTS-UX-AND-API.md`).
* Runs detail, streaming SSE/NDJSON, logs, outputs, and summary (`050-RUN-STREAMING-SPEC.md`, `140-RUNS-AND-OUTPUTS.md`).
* **VS Code–style Config Builder workbench** on top of configuration file APIs (`100-CONFIG-BUILDER-EDITOR.md`, `150-CONFIGURATIONS-API.md`).
* Migration & rollout from the legacy app (`080-MIGRATION-AND-ROLLOUT.md`).
* Baseline accessibility and tests (`070-TEST-PLAN.md`).

### Out of scope (future workpackages)

* Advanced workspace UX (activity feeds, cross-workspace dashboards).
* Full admin UIs for global roles/permissions and workspace member management.
* Rich API key / service-account management UI.
* Run comparison dashboards, regression analytics, and long-term trends.
* Config diffing/version browser UI and **command palette** (nice-to-have for later).

---

## 3. Core Terminology

Keep these terms consistent across code, UX, and docs:

* **Session** – the authenticated browser session (via cookies).
* **User** – logged-in person (not service account).
* **Workspace** – top-level container for documents, configurations, and runs.
* **Configuration** – a config package (files + versions) used to drive runs.
* **Document** – an uploaded file, possibly with multiple sheets.
* **Sheet** – a worksheet within a document (e.g., Excel tab).
* **Run** – an execution of a configuration against input documents.
* **Build** – configuration build step; may precede runs.
* **Output** – files produced by a run (normalized data, reports, logs).
* **Explorer** – the left-hand pane in Config Builder showing the configuration file tree.
* **Bottom Panel** – the console/problems area at the bottom of Config Builder.

When in doubt, prefer these names in code and UI.

---

## 4. User Flows (high-level)

### 4.1 First-time user

1. Visit app → Setup wizard appears (no admin yet).
2. Complete setup (password or SSO, depending on backend).
3. Land on login/auto-login → authenticated.
4. Create first workspace.
5. Enter workspace home:

   * See “Upload documents” CTA.
   * See “Create configuration” CTA.

### 4.2 Returning user with one workspace

1. Visit app → existing session or login.
2. Workspace choice:

   * If a preferred workspace exists → go directly to that workspace.
   * Else → workspace list, pick one.
3. In workspace home, choose:

   * Documents (upload & process files).
   * Config Builder (work on configs).

### 4.3 Document-driven flow

1. Login → choose workspace.
2. Go to Documents.
3. Upload file(s).
4. Select document → start run (select config if multiple).
5. Watch progress (live run card, console tail).
6. When complete:

   * Download normalized outputs.
   * If failed, open Run Detail to debug.

### 4.4 Config-driven flow

1. Login → choose workspace.
2. Go to Config Builder.
3. Choose or create configuration.
4. In VS Code–style workbench:

   * Use Explorer to navigate config files.
   * Open multiple files as tabs.
   * Edit code in central editor.
5. Run config:

   * Observe logs/validation in bottom console & Problems tab.
6. On error:

   * Click validation issue → jump to file + line in editor.
   * Fix config and re-run.
7. Share link to Run Detail for deeper investigation if needed.

---

## 5. Implementation Order (summary)

1. **Scaffold app & tooling** (Vite, TS, lint/test, architecture).
2. **Auth & Setup**:

   * AuthProvider, Setup & Login screens, /bootstrap wiring.
3. **Workspaces**:

   * Workspace list, create, and switcher.
4. **Navigation & Shell**:

   * Route union, parse/build, AppShell, layout.
5. **Design System**:

   * Tokens, primitives, layout (`SplitPane`, `Panel`, etc.).
6. **API integration**:

   * Feature API modules for auth, workspaces, documents, runs, configs.
7. **Screens**:

   * Workspace Home → Documents → Run Detail → **VS Code–style Config Builder**.
8. **Run streaming**:

   * RunStream foundation, shared run UI components, integration.
9. **Tests & migration**:

   * Unit/RTL/E2E, legacy archive, rollout.
10. **UX polish**:

* Loading/empty/error states, microcopy, accessibility.

Each of these is reflected in the checklist above.

---

## 6. Notes for Agents

* **Vanilla React navigation only.** Do not add React Router or other routing libraries. Extend `060-NAVIGATION.md` if you need new routes.
* **Single streaming foundation.** All run streaming logic must live in `features/runs/stream`. Screens consume it via hooks and shared components.
* **Auth first.** Do not implement deep screens without wiring them to real auth/bootstrap and workspace context; avoid persistent local stubs.
* **OpenAPI types only.** When you need API types, import from the generated OpenAPI declarations via `schema/`, not hand-written interfaces.
* **VS Code mental model for Config Builder.**

  * Explorer (left), Editor (center), Bottom Panel (console/problems).
  * Code comes first; inspectors/helpers are secondary.
  * Resizable/collapsible panels with persisted layout.
* **UX details matter.** For each screen you touch, think:

  * What does loading look like?
  * How does it fail?
  * What happens if there’s no data yet?
  * Is it keyboard accessible?
* **Keep docs in sync.** When behavior changes, update:

  1. This workpackage.
  2. The relevant spec (e.g., `030-UX-FLOWS.md`, `050-RUN-STREAMING-SPEC.md`, `100-CONFIG-BUILDER-EDITOR.md`, `120-AUTH-AND-SESSIONS.md`).
  3. Then the code.

When in doubt, document the decision here before implementing it.