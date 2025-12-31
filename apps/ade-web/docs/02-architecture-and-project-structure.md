# 02 – Architecture and project structure

This document describes how `ade-web` is organised on disk, how the main layers depend on each other, and the naming conventions we use for files and modules.

If **01‑domain‑model‑and‑naming** tells you *what* the app talks about (workspaces, documents, runs, configurations), this doc tells you *where* that logic lives and *how* it is wired together.

---

## 1. Goals and principles

The architecture is intentionally boring and predictable:

- **Layer‑based** – code is grouped by technical layer (pages, components, api, hooks, utils, types), with features composed at the page level.
- **Layered** – app shell → pages → components/api/hooks/utils → types.
- **One‑way dependencies** – each layer imports “downwards” only, which keeps cycles and hidden couplings out.
- **Obvious naming** – given a route or concept name, you should know what file to search for.

Everything below exists to make those goals explicit.

### Instant understanding defaults

- **Domain‑first naming:** keep the language 1:1 with the product (types such as `Workspace`, `Run`, `Configuration`, `Document`; hooks like `useRunsQuery`, `useStartRunMutation`; sections `/documents`, `/runs`, `/config-builder`, `/settings` mirrored under `pages/Workspace/sections/...`).
- **One canonical home per concept:** navigation helpers live under `@app/nav`; query parameter names stay consistent with `docs/03`, `docs/06`, `docs/07` and their filter helpers (`parseDocumentFilters`, `parseRunFilters`, `build*SearchParams`).
- **Reuse patterns:** new list/detail flows should copy Documents/Runs; new URL‑backed filters should reuse the existing filter helpers rather than inventing new query names; NDJSON streaming should go through the helper in `api/ndjson`.
- **Respect the layers:** never import “upwards” (e.g. `api/` → `pages/`); linting enforces the boundaries.

See `../CONTRIBUTING.md` for the quick version; the rest of this doc unpacks where things live.

---

## 2. Top‑level layout

All relevant code lives under `apps/ade-web/src`:

```text
apps/ade-web/
  src/
    app/              # App shell: providers, global layout, top-level routing
    pages/            # Route-level pages (aliased as "@pages")
    components/       # Reusable presentational components + providers
    api/              # HTTP client + domain API calls
    hooks/            # Shared React hooks (React Query + app hooks)
    utils/            # Cross-cutting utilities (storage, url helpers, etc.)
    types/            # Hand-written domain models / schemas
    types/  # Types generated from backend schemas
    test/             # Vitest setup and shared testing helpers
````

> Page folders live in `src/pages` and are imported via `@pages/*`. There is no `src/features` directory.

At a high level:

* `app/` is the **composition root**.
* `pages/` contains **route‑level pages/features**.
* `components/` contains **UI primitives** with no domain knowledge (plus shared providers).
* `api/`, `hooks/`, `utils/` contain **infrastructure** and **cross‑cutting logic**.
* `types/` and `types/` define **types**.
* `test/` holds **test infrastructure**.

---

## 3. Layers and dependency rules

We treat the codebase as layered, with imports flowing “down” only:

```text
        app
        ↑
      pages (@pages)
   ↑    ↑    ↑    ↑
components api hooks utils
        ↑
      types
        ↑
  types
        ↑
       test (can see everything)
```

Allowed dependencies:

* `app/` → may import from `pages/`, `components/`, `api/`, `hooks/`, `utils/`, `types/`, `types/`.
* `pages/` → may import from `components/`, `api/`, `hooks/`, `utils/`, `types/`, `types/`.
* `components/`, `api/`, `hooks/`, `utils/` → may import from `types/`, `types/`.
* `types/` → may import from `types/` (if needed).
* `types/` → must not import from anywhere else.
* `test/` → may import from anything in `src/`, but nothing in `src/` should import from `@test`.

Forbidden dependencies:

* `components/`, `api/`, `hooks/`, `utils/` **must not** import from `pages/` or `app/`.
* `pages/` **must not** import from `app/`.

If you ever want to import “upwards” (e.g. from `api/` to `pages/`), that’s a sign the code should be moved into a smaller module at the right layer.

We lint these boundaries (module‑boundary rules in ESLint) so you get a fast failure if, for example, `api/` tries to import a page. Update the rule if you add new top‑level folders.

---

## 4. `app/` – application shell

**Responsibility:** Compose the entire app: providers, navigation, top‑level layout, and page selection.

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
* `ScreenSwitch` – top‑level route switch that decides which feature page to show.
* High‑level layout wrappers (e.g. global error boundary, shell frame).

What does **not** belong here:

* Feature‑specific logic (documents, runs, configurations, etc.).
* Direct API calls to `/api/v1/...`.
* Reusable UI primitives (those go in `components/`).

`app/` is glue and composition only.

---

## 5. `pages/` – page/feature slices

**Responsibility:** Implement user‑facing features and pages: auth, workspace directory, workspace shell, and each shell section (Documents, Runs, Configuration Builder, Settings, Overview). The physical folder is `src/pages/`, imported via the `@pages/*` alias.

Example structure:

```text
src/pages/
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

Keep section naming 1:1 across the UI: the nav item is **Configuration Builder**, the route segment is `config-builder`, and the feature folder is `pages/Workspace/sections/ConfigBuilder`. That folder owns both the configurations list and the workbench editing mode.

What belongs here:

* **Page components** (`*Page.tsx` or `index.tsx`) that:

  * Decide which data to fetch.
  * Map URL state to props.
  * Compose `components/` primitives into a page.
  * Choose which mutations to call on user actions.

* **Feature‑specific hooks**:

  * `useDocumentsQuery`, `useRunsQuery`, `useStartRunMutation`, `useWorkspaceMembersQuery`, etc.

* **Feature‑specific components**:

  * `DocumentsTable`, `RunsFilters`, `ConfigurationList`, `RunExtractionDialog`.

What does **not** belong here:

* Generic UI primitives (buttons, inputs, layout) → `components/`.
* Cross‑feature logic (API clients, storage helpers) → `api/`, `hooks/`, `utils/`.

When you add a new route or page, it should live under `pages/`, in a folder that mirrors the URL path.

---

## 6. `components/` – presentational component library

**Responsibility:** Provide reusable UI components with no knowledge of ADE’s domain concepts. They render markup, accept props, and raise events; they don’t know what a “run”, “workspace”, or “configuration” is.

Example structure:

```text
src/components/
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

Pages in `pages/` own domain logic and pass data into these components.

---

## 7. `api/`, `hooks/`, `utils/` – shared building blocks

**Responsibility:** Provide non‑UI building blocks used by many pages. This includes API clients, React Query hooks, URL helpers, storage utilities, streaming helpers, upload helpers, etc.

Example structure:

```text
src/api/
  client.ts
  errors.ts
  pagination.ts
  auth/
    api.ts
  documents/
    index.ts
    uploads.ts
  runs/
    api.ts
  workspaces/
    api.ts

src/hooks/
  auth/
    useSessionQuery.ts
  documents/
    uploadManager.ts
  workspaces/
    useWorkspacesQuery.ts

src/utils/
  storage.ts
  uploads/
    xhr.ts
  auth/
    authNavigation.ts
```

What belongs here:

* **API modules** wrapping `/api/v1/...` (no React).
* **React Query + shared hooks** used by multiple pages.
* **URL helpers, storage helpers, streaming helpers**, and other cross‑cutting utilities.

What does **not** belong here:

* JSX components (those live in `components/`).
* Page‑specific business logic (that stays under `pages/`).

Rule of thumb: if the logic only makes sense inside a single page/section, keep it with that page; move it into `api/`, `hooks/`, or `utils/` only when it is truly reusable across pages.

---

## 8. `types/` and `types/` – types and models

### 8.1 `types/`

**Responsibility:** Contain types generated directly from backend schemas (e.g. OpenAPI codegen).

* These types are the “raw wire” shapes.
* This folder is a leaf: it should not import from anywhere else in `src/`.

You can use these types directly where appropriate, but often it’s better to wrap them in `types/` so the rest of the app works with stable, frontend‑friendly models.

### 8.2 `types/`

**Responsibility:** Define the frontend domain types and any mapping from backend models.

Example structure:

```text
src/types/
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

Features import types from `@schema`, not from `@schema`, to keep the rest of the code insulated from backend schema churn.

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
* `@pages` → `src/pages`
* `@components` → `src/components`
* `@api` → `src/api`
* `@hooks` → `src/hooks`
* `@utils` → `src/utils`
* `@schema` → `src/types`
* `@schema` → `src/types`
* `@test` → `src/test` (tests only)

Guidelines:

* Use aliases when crossing top‑level directories:

  ```ts
  // Good
  import { WorkspaceShellScreen } from "@pages/workspace-shell/WorkspaceShellScreen";
  import { GlobalTopBar } from "@components/global/GlobalTopBar";
  import { createRun } from "@api/runs/api";
  import type { RunResource } from "@schema";

  // Avoid
  import { createRun } from "../../../api/runs/api";
  ```

* Within a small page folder, relative imports are fine and often clearer:

  ```ts
  // inside pages/Workspace/sections/Runs
  import { RunsTable } from "./RunsTable";
  import { useRunsQuery } from "./useRunsQuery";
  ```

* Use barrel files (`index.ts`) sparingly and only for small, coherent clusters; they can hide dependency direction and complicate tree‑shaking.

---

## 11. Naming conventions

This section summarises naming conventions used in this document. See **01‑domain‑model‑and‑naming** for the domain vocabulary itself.

### 11.1 Pages and containers

* Route components typically end with `Screen` or `Page`:

  * `LoginScreen`, `WorkspaceDirectoryScreen`, `WorkspaceScreen`.
  * `DocumentsScreen`, `RunsScreen`, `ConfigBuilderScreen`, `WorkspaceSettingsScreen`, `WorkspaceOverviewScreen`.

* Each page file is named identically to its component, and exports it as the default or main named export.

### 11.2 Feature components

* Feature‑local components describe their role:

  * `DocumentsTable`, `DocumentsFilters`, `RunsTable`, `RunsFilters`, `ConfigList`, `RunExtractionDialog`.

* Folder structure mirrors URL structure:

  * `/workspaces/:workspaceId/documents` → `pages/Workspace/sections/Documents/`.
  * `/workspaces/:workspaceId/runs` → `pages/Workspace/sections/Runs/`.

### 11.3 Hooks

* **Queries** use `use<Domain><What>Query`:

  * `useDocumentsQuery`, `useRunsQuery`, `useConfigurationsQuery`, `useWorkspaceMembersQuery`.

* **Mutations** use `use<Verb><Domain>Mutation`:

  * `useUploadDocumentMutation`, `useStartRunMutation`, `useMakeActiveConfigurationMutation`, `useArchiveConfigurationMutation`.

* **State / infra hooks** use descriptive names:

  * `useSafeModeStatus`, `useWorkbenchUrlState`, `useNavigationBlocker`, `useSearchParams`.

### 11.4 API modules

* API modules live under `api/<domain>/api.ts`:

  * `auth/api.ts`, `workspaces/api.ts`, `documents/uploads.ts`, `runs/api.ts`, `configurations/api.ts`, `system/api.ts`, `api-keys/api.ts`.

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

* If you need to distinguish backend wire types, use a clear prefix/suffix (`ApiRun`, `ApiDocument`) and isolate them in `types/` or `types/`.

---

## 12. Worked example: the Documents feature

To make the structure concrete, here’s how the **Documents** section of the workspace shell fits into the architecture.

```text
src/
  app/
    ScreenSwitch.tsx              # Routes /workspaces/:id/documents → DocumentsScreen
    nav/
      urlState.ts                 # useSearchParams helpers
  pages/
    Workspace/
      sections/
        Documents/
          index.tsx
          components/
          hooks/
  components/
    Button/
    Input/
    Alert/
  api/
    documents/
      index.ts                    # listWorkspaceDocuments, uploadDocument, deleteDocument...
      uploads.ts
  types/
    documents.ts                  # DocumentSummary, DocumentDetail, DocumentStatus
```

Flow:

1. **Routing**

   * `ScreenSwitch` examines the current location.
   * `/workspaces/:workspaceId/documents` is mapped to `DocumentsScreen`.

2. **Screen logic**

   * `DocumentsScreen`:

     * Reads search parameters (`q`, `status`, `sort`, `view`) via `useSearchParams` from `@app/nav/urlState`.
     * Calls `useDocumentsQuery(workspaceId, filters)` to fetch data.
     * Renders the page layout.
     * Composes `DocumentsFilters`, `DocumentsTable`, and `RunExtractionDialog`.

3. **Data fetching**

   * `useDocumentsQuery` uses React Query and `api/documents` under the hood.
   * `api/documents` builds the `/api/v1/workspaces/{workspace_id}/documents` URL and parses the JSON response.
   * The response is mapped into `DocumentSummary[]` using types from `@schema/documents`.

4. **Presentation**

   * `DocumentsTable` and `DocumentsFilters` are presentational components:

     * They receive data and callbacks via props.
     * They use `components` primitives (`Button`, `Input`, `Alert`) for consistent look and accessibility.

The **Runs** section follows the same pattern, with:

* `pages/Workspace/sections/Runs/…`
* `RunsScreen`, `RunsTable`, `useRunsQuery`, `useStartRunMutation`.
* `api/runs/api.ts`.
* Domain types in `types/runs.ts`.

If you follow the structure and rules in this doc, adding or changing a feature should always feel the same: pick the right folder in `pages/`, wire it through `app/ScreenSwitch.tsx`, use `api/`, `hooks/`, and `utils/` for cross‑cutting logic, and build the UI out of `components/` primitives.
