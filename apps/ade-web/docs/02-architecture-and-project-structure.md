# 02 – Architecture and project structure

This document describes how `ade-web` is organised on disk, how the main layers depend on each other, and the naming conventions we use for files and modules.

If **01‑domain‑model‑and‑naming** tells you *what* the app talks about (workspaces, documents, runs, configurations), this doc tells you *where* that logic lives and *how* it is wired together.

---

## 1. Goals and principles

The architecture is intentionally boring and predictable:

- **Feature‑first** – code is grouped by user‑facing feature (auth, documents, runs, config builder), not by technical layer.
- **Layered** – app shell → features → shared utilities & UI primitives → types.
- **One‑way dependencies** – each layer imports “downwards” only, which keeps cycles and hidden couplings out.
- **Obvious naming** – given a route or concept name, you should know what file to search for.

Everything below exists to make those goals explicit.

---

## 2. Top‑level layout

All relevant code lives under `apps/ade-web/src`:

```text
apps/ade-web/
  src/
    app/              # App shell: providers, global layout, top-level routing
    features/         # Route/feature slices (aliased as "@screens")
    ui/               # Reusable presentational components
    shared/           # Cross-cutting hooks, utilities, and API modules (no UI)
    schema/           # Hand-written domain models / schemas
    generated-types/  # Types generated from backend schemas
    test/             # Vitest setup and shared testing helpers
````

> For historical reasons, the TS/Vite alias `@screens` points to `src/features`. In this doc we refer to the directory as `features/`, but you may see `@screens/...` imports in the code.

At a high level:

* `app/` is the **composition root**.
* `features/` contains **route‑level features**.
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
     features
     ↑     ↑
    ui   shared
      ↑    ↑
   schema  generated-types
        ↑
       test (can see everything)
```

Allowed dependencies:

* `app/` → may import from `features/`, `ui/`, `shared/`, `schema/`, `generated-types/`.
* `features/` → may import from `ui/`, `shared/`, `schema/`, `generated-types/`.
* `ui/` → may import from `shared/`, `schema/`, `generated-types/`.
* `shared/` → may import from `schema/`, `generated-types/`.
* `schema/` → may import from `generated-types/` (if needed).
* `generated-types/` → must not import from anywhere else.
* `test/` → may import from anything in `src/`, but nothing in `src/` should import from `@test`.

Forbidden dependencies:

* `ui/` **must not** import from `features/` or `app/`.
* `shared/` **must not** import from `features/`, `ui/`, or `app/`.
* `features/` **must not** import from `app/`.

If you ever want to import “upwards” (e.g. from `shared/` to `features/`), that’s a sign the code should be moved into a smaller module at the right layer.

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

* Feature‑specific logic (documents, runs, configs, etc.).
* Direct API calls to `/api/v1/...`.
* Reusable UI primitives (those go in `ui/`).

`app/` is glue and composition only.

---

## 5. `features/` – route‑level features

**Responsibility:** Implement user‑facing features and screens: auth, workspace directory, workspace shell, and each shell section (Documents, Runs, Config Builder, Settings, Overview).

Example structure:

```text
src/features/
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

What belongs here:

* **Screen components** (`*Screen.tsx`) that:

  * Decide which data to fetch.
  * Map URL state to props.
  * Compose `ui/` components into a page.
  * Choose which mutations to call on user actions.

* **Feature‑specific hooks**:

  * `useDocumentsQuery`, `useRunsQuery`, `useStartRunMutation`, `useWorkspaceMembersQuery`, etc.

* **Feature‑specific components**:

  * `DocumentsTable`, `RunsFilters`, `ConfigList`, `RunExtractionDialog`.

What does **not** belong here:

* Generic UI primitives (buttons, inputs, layout) → `ui/`.
* Cross‑feature logic (API clients, storage helpers) → `shared/`.

When you add a new route or screen, it should live under `features/`, in a folder that mirrors the URL path.

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

Screens in `features/` own domain logic and pass data into these components.

---

## 7. `shared/` – cross‑cutting utilities and hooks

**Responsibility:** Provide non‑UI building blocks used by many features. This includes API clients, URL helpers, storage utilities, streaming helpers, permission checks, keyboard shortcut wiring, etc.

Example structure:

```text
src/shared/
  api/
    authApi.ts
    workspacesApi.ts
    documentsApi.ts
    runsApi.ts
    configsApi.ts
    buildsApi.ts
    rolesApi.ts
    safeModeApi.ts
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

  * `documentsApi.listWorkspaceDocuments`, `runsApi.listWorkspaceRuns`, `runsApi.startRun`, `configsApi.listConfigurations`, etc.

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
* Feature‑specific business logic (that belongs under `features/`).
* Any knowledge of `Screen` components.

If a utility function does not render UI and is reused by multiple features, it probably belongs in `shared/`.

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
  workspace.ts
  document.ts
  run.ts
  configuration.ts
  permissions.ts
```

Typical content:

* `WorkspaceSummary`, `WorkspaceDetail`.
* `DocumentSummary`, `DocumentDetail`, `DocumentStatus`.
* `RunSummary`, `RunDetail`, `RunStatus`.
* `Configuration`, `ConfigVersion`.
* Permission and role models.

You can also provide mapping helpers:

```ts
// run.ts
import type { ApiRun } from "@generated-types";

export interface RunSummary {
  id: string;
  status: RunStatus;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  // ...
}

export function fromApiRun(apiRun: ApiRun): RunSummary {
  // convert and normalise fields here
}
```

Features import types from `@schema`, not from `@generated-types`, to keep the rest of the code insulated from backend schema churn.

---

## 9. `test/` – testing setup and helpers

**Responsibility:** Provide shared testing configuration and helpers.

Example structure:

```text
src/test/
  setup.ts             # Vitest config: JSDOM, polyfills, globals
  factories.ts         # test data builders (workspaces, documents, runs, configs)
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
* `@features` / `@screens` → `src/features`
* `@ui` → `src/ui`
* `@shared` → `src/shared`
* `@schema` → `src/schema`
* `@generated-types` → `src/generated-types`
* `@test` → `src/test` (tests only)

Guidelines:

* Use aliases when crossing top‑level directories:

  ```ts
  // Good
  import { WorkspaceShellScreen } from "@features/workspace-shell/WorkspaceShellScreen";
  import { GlobalTopBar } from "@ui/global/GlobalTopBar";
  import { listWorkspaceRuns } from "@shared/api/runsApi";
  import { RunSummary } from "@schema/run";

  // Avoid
  import { listWorkspaceRuns } from "../../../shared/api/runsApi";
  ```

* Within a small feature folder, relative imports are fine and often clearer:

  ```ts
  // inside features/workspace-shell/sections/runs
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

  * `/workspaces/:workspaceId/documents` → `features/workspace-shell/sections/documents/`.
  * `/workspaces/:workspaceId/runs` → `features/workspace-shell/sections/runs/`.

### 11.3 Hooks

* **Queries** use `use<Domain><What>Query`:

  * `useDocumentsQuery`, `useRunsQuery`, `useConfigurationsQuery`, `useWorkspaceMembersQuery`.

* **Mutations** use `use<Verb><Domain>Mutation`:

  * `useUploadDocumentMutation`, `useStartRunMutation`, `useActivateConfigurationMutation`, `useDeactivateConfigurationMutation`.

* **State / infra hooks** use descriptive names:

  * `useSafeModeStatus`, `useWorkbenchUrlState`, `useNavigationBlocker`, `useSearchParams`.

### 11.4 API modules

* API modules live under `shared/api` and are named `<domain>Api.ts`:

  * `authApi.ts`, `workspacesApi.ts`, `documentsApi.ts`, `runsApi.ts`, `configsApi.ts`, `buildsApi.ts`, `rolesApi.ts`, `safeModeApi.ts`.

* Functions are “verb + noun” with noun matching the domain model:

  ```ts
  listWorkspaces();
  createWorkspace(input);
  listWorkspaceDocuments(workspaceId, params);
  uploadDocument(workspaceId, file);
  listWorkspaceRuns(workspaceId, params);
  startRun(workspaceId, payload);
  listConfigurations(workspaceId, params);
  activateConfiguration(workspaceId, configId);
  ```

Feature hooks wrap these functions into React Query calls.

### 11.5 Types and models

* Domain types are singular, PascalCase:

  * `WorkspaceSummary`, `WorkspaceDetail`.
  * `DocumentSummary`, `DocumentDetail`, `DocumentStatus`.
  * `RunSummary`, `RunDetail`, `RunStatus`.
  * `Configuration`, `ConfigVersion`.

* If you need to distinguish backend wire types, use a clear prefix/suffix (`ApiRun`, `ApiDocument`) and isolate them in `schema/` or `generated-types/`.

---

## 12. Worked example: the Documents feature

To make the structure concrete, here’s how the **Documents** section of the workspace shell fits into the architecture.

```text
src/
  app/
    ScreenSwitch.tsx              # Routes /workspaces/:id/documents → DocumentsScreen
  features/
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

* `features/workspace-shell/sections/runs/…`
* `RunsScreen`, `RunsTable`, `useRunsQuery`, `useStartRunMutation`.
* `shared/api/runsApi.ts`.
* Domain types in `schema/run.ts`.

If you follow the structure and rules in this doc, adding or changing a feature should always feel the same: pick the right folder in `features/`, wire it through `app/ScreenSwitch.tsx`, use `shared/` for cross‑cutting logic, and build the UI out of `ui/` primitives.