# 02 – Architecture and project structure

This document describes how `ade-web` is organised on disk, how the main layers depend on each other, and the naming conventions we use for files and modules.

If **01‑domain‑model‑and‑naming** tells you *what* the app talks about (workspaces, documents, runs, configurations), this doc tells you *where* that logic lives and *how* it is wired together.

---

## 1. Goals and principles

The architecture is intentionally boring and predictable:

- **Feature‑first** – code is grouped by user‑facing feature (auth, documents, runs, config builder), not by technical layer.
- **Layered** – app shell → screens → shared utilities & UI primitives → types.
- **One‑way dependencies** – each layer imports “downwards” only, which keeps cycles and hidden couplings out.
- **Obvious naming** – given a route or concept name, you should know what file to search for.

Everything below exists to make those goals explicit.

### Instant understanding defaults

- **Domain‑first naming:** keep the language 1:1 with the product (types such as `Workspace`, `Run`, `Configuration`, `Document`; hooks like `useRunsQuery`, `useStartRunMutation`; sections `/documents`, `/runs`, `/config-builder`, `/settings` mirrored under `screens/workspace-shell/sections/...`).
- **One canonical home per concept:** routes live in `@shared/nav/routes`; query parameter names stay consistent with `docs/03`, `docs/06`, `docs/07` and their filter helpers (`parseDocumentFilters`, `parseRunFilters`, `build*SearchParams`); permission keys live in `@schema/permissions` with helpers in `@shared/permissions`.
- **Reuse patterns:** new list/detail flows should copy Documents/Runs; new URL‑backed filters should reuse the existing filter helpers rather than inventing new query names; NDJSON streaming should go through the shared helper and event model.
- **Respect the layers:** never import “upwards” (e.g. `shared/` → `screens/`); linting enforces the boundaries.

See `../CONTRIBUTING.md` for the quick version; the rest of this doc unpacks where things live.

---

## 2. Top‑level layout

All relevant code lives under `apps/ade-web/src`:

```text
apps/ade-web/
  src/
    app/              # App shell: providers, global layout, top-level routing
    screens/          # Screen/feature slices (aliased as "@screens")
    ui/               # Reusable presentational components
    shared/           # Cross-cutting hooks, utilities, and API modules (no UI)
    schema/           # Hand-written domain models / schemas
    generated-types/  # Types generated from backend schemas
    test/             # Vitest setup and shared testing helpers
````

> Screen folders live in `src/screens` and are imported via `@screens/*`. There is no `src/features` directory.

At a high level:

* `app/` is the **composition root**.
* `screens/` contains **route‑level screens/features**.
* `ui/` contains **UI primitives** with no domain knowledge.
* `shared/` contains **infrastructure** and **cross‑cutting logic**.
* `schema/` and `generated-types/` define **types**.
* `test/` holds **test infrastructure**.

---

## 3. Layers and dependency rules

We treat the codebase as layered, with imports flowing “down” only:

```text
        app
        ↑
     screens (@screens)
     ↑          ↑
    ui        shared
      ↑         ↑
   schema   generated-types
        ↑
       test (can see everything)
```

Allowed dependencies:

* `app/` → may import from `screens/`, `ui/`, `shared/`, `schema/`, `generated-types/`.
* `screens/` → may import from `ui/`, `shared/`, `schema/`, `generated-types/`.
* `ui/` → may import from `shared/`, `schema/`, `generated-types/`.
* `shared/` → may import from `schema/`, `generated-types/`.
* `schema/` → may import from `generated-types/` (if needed).
* `generated-types/` → must not import from anywhere else.
* `test/` → may import from anything in `src/`, but nothing in `src/` should import from `@test`.

Forbidden dependencies:

* `ui/` **must not** import from `screens/` or `app/`.
* `shared/` **must not** import from `screens/`, `ui/`, or `app/`.
* `screens/` **must not** import from `app/`.

If you ever want to import “upwards” (e.g. from `shared/` to `screens/`), that’s a sign the code should be moved into a smaller module at the right layer.

We lint these boundaries (module‑boundary rules in ESLint) so you get a fast failure if, for example, `shared/` tries to import a screen. Update the rule if you add new top‑level folders.

---

## 4. `app/` – application shell

**Responsibility:** Compose the entire app: providers, navigation, top‑level layout, and screen selection.

Typical structure:

```text
src/app/
  App.tsx
  ScreenSwitch.tsx
  NavProvider/
    NavProvider.tsx
    Link.tsx
    NavLink.tsx
  AppProviders/
    AppProviders.tsx
  layout/
    GlobalLayout.tsx
    WorkspaceShellLayout.tsx
```

What belongs here:

* `<App>` – root component used in `main.tsx`.
* `NavProvider` – custom navigation context built on `window.history`.
* `AppProviders` – React Query client and other global providers.
* `ScreenSwitch` – top‑level route switch that decides which feature screen to show.
* High‑level layout wrappers (e.g. global error boundary, shell frame).

What does **not** belong here:

* Feature‑specific logic (documents, runs, configurations, etc.).
* Direct API calls to `/api/v1/...`.
* Reusable UI primitives (those go in `ui/`).

`app/` is glue and composition only.

---

## 5. `screens/` – screen/feature slices

**Responsibility:** Implement user‑facing features and screens: auth, workspace directory, workspace shell, and each shell section (Documents, Runs, Configuration Builder, Settings, Overview). The physical folder is `src/screens/`, imported via the `@screens/*` alias.

Example structure:

```text
src/screens/
  auth/
    LoginScreen.tsx
    AuthCallbackScreen.tsx
    LogoutScreen.tsx
    useLoginMutation.ts
  workspace-directory/
    WorkspaceDirectoryScreen.tsx
    WorkspaceCard.tsx
    useWorkspaceDirectoryQuery.ts
  workspace-shell/
    WorkspaceShellScreen.tsx
    nav/
      WorkspaceNav.tsx
      useWorkspaceNavItems.ts
    sections/
      documents/
        DocumentsScreen.tsx
        DocumentsTable.tsx
        DocumentsFilters.tsx
        useDocumentsQuery.ts
        useUploadDocumentMutation.ts
      runs/
        RunsScreen.tsx
        RunsTable.tsx
        RunsFilters.tsx
        useRunsQuery.ts
        useStartRunMutation.ts
      config-builder/
        ConfigBuilderScreen.tsx
        ConfigList.tsx
        workbench/
          WorkbenchWindow.tsx
          WorkbenchExplorer.tsx
          WorkbenchTabs.tsx
          useWorkbenchFiles.ts
          useWorkbenchUrlState.ts
      settings/
        WorkspaceSettingsScreen.tsx
        MembersTab.tsx
        RolesTab.tsx
      overview/
        WorkspaceOverviewScreen.tsx
```

Keep section naming 1:1 across the UI: the nav item is **Configuration Builder**, the route segment is `config-builder`, and the feature folder is `screens/workspace-shell/sections/config-builder`. That folder owns both the configurations list and the workbench editing mode.

What belongs here:

* **Screen components** (`*Screen.tsx`) that:

  * Decide which data to fetch.
  * Map URL state to props.
  * Compose `ui/` components into a page.
  * Choose which mutations to call on user actions.

* **Feature‑specific hooks**:

  * `useDocumentsQuery`, `useRunsQuery`, `useStartRunMutation`, `useWorkspaceMembersQuery`, etc.

* **Feature‑specific components**:

  * `DocumentsTable`, `RunsFilters`, `ConfigurationList`, `RunExtractionDialog`.

What does **not** belong here:

* Generic UI primitives (buttons, inputs, layout) → `ui/`.
* Cross‑feature logic (API clients, storage helpers) → `shared/`.

When you add a new route or screen, it should live under `screens/`, in a folder that mirrors the URL path.

---

## 6. `ui/` – presentational component library

**Responsibility:** Provide reusable UI components with no knowledge of ADE’s domain concepts. They render markup, accept props, and raise events; they don’t know what a “run”, “workspace”, or “configuration” is.

Example structure:

```text
src/ui/
  button/
    Button.tsx
    SplitButton.tsx
  form/
    Input.tsx
    TextArea.tsx
    Select.tsx
    FormField.tsx
  feedback/
    Alert.tsx
    ToastContainer.tsx
  nav/
    Tabs/
      TabsRoot.tsx
      TabsList.tsx
      TabsTrigger.tsx
      TabsContent.tsx
    ContextMenu.tsx
  identity/
    Avatar.tsx
    ProfileDropdown.tsx
  layout/
    Page.tsx
    SidebarLayout.tsx
  global/
    GlobalTopBar.tsx
    GlobalSearchField.tsx
  code/
    CodeEditor.tsx
```

What belongs here:

* Buttons, split buttons, links styled as buttons.
* Inputs, textareas, selects, form field wrappers.
* Alerts, banners, toasts.
* Tabs, context menus, dropdowns.
* Avatars and profile menus.
* Global top bar and search field components.
* Monaco editor wrapper (`CodeEditor`).

What does **not** belong here:

* Business logic (no calls to `*Api` modules).
* Domain types in props (prefer generic names like `items`, `onSelect` rather than `runs`, `onRunClick`).
* Route knowledge (no `navigate` calls).

Screens in `screens/` own domain logic and pass data into these components.

---

## 7. `shared/` – cross‑cutting utilities and hooks

**Responsibility:** Provide non‑UI building blocks used by many features. This includes API clients, URL helpers, storage utilities, streaming helpers, permission checks, keyboard shortcut wiring, etc.

Example structure:

```text
src/shared/
  api/
    authApi.ts
    permissionsApi.ts
    rolesApi.ts
    workspacesApi.ts
    documentsApi.ts
    runsApi.ts
    configurationsApi.ts
    buildsApi.ts
    systemApi.ts
    apiKeysApi.ts
  nav/
    routes.ts             # route builders like workspaceRuns(workspaceId)
  url-state/
    urlState.ts           # toURLSearchParams, getParam, setParams
    useSearchParams.ts
    SearchParamsOverrideProvider.tsx
  navigation-blockers/
    useNavigationBlocker.ts
  storage/
    storage.ts            # namespaced localStorage helpers
  streams/
    ndjson.ts             # NDJSON streaming and event parsing
  keyboard/
    shortcuts.ts          # global/workbench shortcut registration
  permissions/
    permissions.ts        # hasPermission, hasAnyPermission
  time/
    formatters.ts         # time/date formatting helpers
```

What belongs here:

* **API modules** wrapping `/api/v1/...`:

  * `documentsApi.listWorkspaceDocuments`, `runsApi.listWorkspaceRuns`, `runsApi.startRun`, `configurationsApi.listConfigurations`, etc.

* **URL helpers**:

  * `toURLSearchParams`, `getParam`, `setParams`.
  * `useSearchParams` hook and `SearchParamsOverrideProvider`.

* **Route builders**:

  * Functions that produce pathnames from IDs:

    * `workspaceDocuments(workspaceId)`, `workspaceRuns(workspaceId)`, etc.

* **Infrastructure hooks and utilities**:

  * `useNavigationBlocker`.
  * Local storage read/write with ADE‑specific namespacing.
  * NDJSON stream parsing.
  * Permission check helpers.
  * Keyboard shortcut registration helpers.

What does **not** belong here:

* JSX components.
* Feature‑specific business logic (that belongs under `screens/`).
* Any knowledge of `Screen` components.

If a utility function does not render UI and is reused by multiple features, it probably belongs in `shared/`. Rule of thumb for service‑style orchestration: if the logic only makes sense inside a single workspace section (e.g. “Run & follow run” within Documents), keep it with that screen; move it into `shared/` only when it is truly reusable across sections (e.g. NDJSON parsing, per‑document run preferences, permission helpers).

---

## 8. `schema/` and `generated-types/` – types and models

### 8.1 `generated-types/`

**Responsibility:** Contain types generated directly from backend schemas (e.g. OpenAPI codegen).

* These types are the “raw wire” shapes.
* This folder is a leaf: it should not import from anywhere else in `src/`.

You can use these types directly where appropriate, but often it’s better to wrap them in `schema/` so the rest of the app works with stable, frontend‑friendly models.

### 8.2 `schema/`

**Responsibility:** Define the frontend domain types and any mapping from backend models.

Example structure:

```text
src/schema/
  index.ts
  adeArtifact.ts
  adeTelemetry.ts
```

Typical content:

* `WorkspaceOut`, `DocumentOut`.
* `RunResource`, `RunStatus`.
* Configuration and safe-mode types.
* Permission and role models.

The curated types already use wire shapes, so mapping helpers are only needed when you introduce UI‑specific view models.

Features import types from `@schema`, not from `@generated-types`, to keep the rest of the code insulated from backend schema churn.

---

## 9. `test/` – testing setup and helpers

**Responsibility:** Provide shared testing configuration and helpers.

Example structure:

```text
src/test/
  setup.ts             # Vitest config: JSDOM, polyfills, globals
  factories.ts         # test data builders (workspaces, documents, runs, configurations)
  test-utils.tsx       # renderWithProviders, etc.
```

* `setup.ts` is referenced from `vitest.config.ts` and runs before each test.
* Factories can live here or near their domains, but this is the central place for shared ones.
* Only test code should import from `@test/*`.

Tests for a specific component or hook live alongside that code (e.g. `RunsScreen.test.tsx` next to `RunsScreen.tsx`).

---

## 10. Path aliases and import style

We use a small set of TS/Vite aliases to keep imports readable:

* `@app` → `src/app`
* `@screens` → `src/screens`
* `@ui` → `src/ui`
* `@shared` → `src/shared`
* `@schema` → `src/schema`
* `@generated-types` → `src/generated-types`
* `@test` → `src/test` (tests only)

Guidelines:

* Use aliases when crossing top‑level directories:

  ```ts
  // Good
  import { WorkspaceShellScreen } from "@screens/workspace-shell/WorkspaceShellScreen";
  import { GlobalTopBar } from "@ui/global/GlobalTopBar";
  import { createRun } from "@shared/runs/api";
  import type { RunResource } from "@schema";

  // Avoid
  import { createRun } from "../../../shared/runs/api";
  ```

* Within a small screen folder, relative imports are fine and often clearer:

  ```ts
  // inside screens/workspace-shell/sections/runs
  import { RunsTable } from "./RunsTable";
  import { useRunsQuery } from "./useRunsQuery";
  ```

* Use barrel files (`index.ts`) sparingly and only for small, coherent clusters; they can hide dependency direction and complicate tree‑shaking.

---

## 11. Naming conventions

This section summarises naming conventions used in this document. See **01‑domain‑model‑and‑naming** for the domain vocabulary itself.

### 11.1 Screens and containers

* Screen components end with `Screen`:

  * `LoginScreen`, `WorkspaceDirectoryScreen`, `WorkspaceShellScreen`.
  * `DocumentsScreen`, `RunsScreen`, `ConfigBuilderScreen`, `WorkspaceSettingsScreen`, `WorkspaceOverviewScreen`.

* Each screen file is named identically to its component, and exports it as the default or main named export.

### 11.2 Feature components

* Feature‑local components describe their role:

  * `DocumentsTable`, `DocumentsFilters`, `RunsTable`, `RunsFilters`, `ConfigList`, `RunExtractionDialog`.

* Folder structure mirrors URL structure:

  * `/workspaces/:workspaceId/documents` → `screens/workspace-shell/sections/documents/`.
  * `/workspaces/:workspaceId/runs` → `screens/workspace-shell/sections/runs/`.

### 11.3 Hooks

* **Queries** use `use<Domain><What>Query`:

  * `useDocumentsQuery`, `useRunsQuery`, `useConfigurationsQuery`, `useWorkspaceMembersQuery`.

* **Mutations** use `use<Verb><Domain>Mutation`:

  * `useUploadDocumentMutation`, `useStartRunMutation`, `useMakeActiveConfigurationMutation`, `useArchiveConfigurationMutation`.

* **State / infra hooks** use descriptive names:

  * `useSafeModeStatus`, `useWorkbenchUrlState`, `useNavigationBlocker`, `useSearchParams`.

### 11.4 API modules

* API modules live under `shared/api` and are named `<domain>Api.ts`:

  * `authApi.ts`, `permissionsApi.ts`, `rolesApi.ts`, `workspacesApi.ts`, `documentsApi.ts`, `runsApi.ts`, `configurationsApi.ts`, `buildsApi.ts`, `systemApi.ts`, `apiKeysApi.ts`.

* Functions are “verb + noun” with noun matching the domain model:

  ```ts
  listWorkspaces();
  createWorkspace(input);
  listWorkspaceDocuments(workspaceId, params);
  uploadDocument(workspaceId, file);
  listWorkspaceRuns(workspaceId, params);
  startRun(workspaceId, payload);
  listConfigurations(workspaceId, params);
  makeActiveConfiguration(workspaceId, configurationId);
  ```

Feature hooks wrap these functions into React Query calls.

### 11.5 Types and models

* Domain types are singular, PascalCase:

  * `WorkspaceSummary`, `WorkspaceDetail`.
  * `DocumentSummary`, `DocumentDetail`, `DocumentStatus`.
  * `RunResource`, `RunStatus`.
  * `Configuration`.

* If you need to distinguish backend wire types, use a clear prefix/suffix (`ApiRun`, `ApiDocument`) and isolate them in `schema/` or `generated-types/`.

---

## 12. Worked example: the Documents feature

To make the structure concrete, here’s how the **Documents** section of the workspace shell fits into the architecture.

```text
src/
  app/
    ScreenSwitch.tsx              # Routes /workspaces/:id/documents → DocumentsScreen
  screens/
    workspace-shell/
      sections/
        documents/
          DocumentsScreen.tsx
          DocumentsTable.tsx
          DocumentsFilters.tsx
          RunExtractionDialog.tsx
          useDocumentsQuery.ts
          useUploadDocumentMutation.ts
  ui/
    button/Button.tsx
    form/Input.tsx
    feedback/Alert.tsx
    global/GlobalTopBar.tsx
  shared/
    api/documentsApi.ts           # listWorkspaceDocuments, uploadDocument, deleteDocument...
    url-state/useSearchParams.ts
    nav/routes.ts                 # workspaceDocuments(workspaceId)
    permissions/permissions.ts
  schema/
    document.ts                   # DocumentSummary, DocumentDetail, DocumentStatus
```

Flow:

1. **Routing**

   * `ScreenSwitch` examines the current location.
   * `/workspaces/:workspaceId/documents` is mapped to `DocumentsScreen`.

2. **Screen logic**

   * `DocumentsScreen`:

     * Reads search parameters (`q`, `status`, `sort`, `view`) via `useSearchParams` from `@shared/url-state`.
     * Calls `useDocumentsQuery(workspaceId, filters)` to fetch data.
     * Renders `GlobalTopBar` and the page layout.
     * Composes `DocumentsFilters`, `DocumentsTable`, and `RunExtractionDialog`.
     * Wires buttons to `useUploadDocumentMutation` and navigation helpers from `@shared/nav/routes`.

3. **Data fetching**

   * `useDocumentsQuery` uses React Query and `documentsApi.listWorkspaceDocuments` under the hood.
   * `documentsApi` builds the `/api/v1/workspaces/{workspace_id}/documents` URL and parses the JSON response.
   * The response is mapped into `DocumentSummary[]` using types from `@schema/document`.

4. **Presentation**

   * `DocumentsTable` and `DocumentsFilters` are presentational components:

     * They receive data and callbacks via props.
     * They use `ui` primitives (`Button`, `Input`, `Alert`) for consistent look and accessibility.

The **Runs** section follows the same pattern, with:

* `screens/workspace-shell/sections/runs/…`
* `RunsScreen`, `RunsTable`, `useRunsQuery`, `useStartRunMutation`.
* `shared/api/runsApi.ts`.
* Domain types in `schema/run.ts`.

If you follow the structure and rules in this doc, adding or changing a feature should always feel the same: pick the right folder in `screens/`, wire it through `app/ScreenSwitch.tsx`, use `shared/` for cross‑cutting logic, and build the UI out of `ui/` primitives.
