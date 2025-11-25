# 02 – Architecture and project structure

This document describes how `ade-web` is organised on disk, how the main layers of the frontend relate to each other, and what naming and dependency rules we follow.

If you’re wondering **“where should this code live?”** or **“what is allowed to import what?”**, this is the document to read.

---

## 1. Goals and design principles

The architecture is intentionally simple:

- **Feature‑first**: group code by feature/route, not by technical layer.
- **Clear layering**: app shell → feature screens → shared infra & UI.
- **Predictable imports**: avoid circular dependencies and “god modules”.
- **Obvious naming**: file and folder names should make intent obvious to humans and AI agents.
- **Local complexity**: keep tricky logic isolated in a small number of well‑named modules.

Domain terminology (Workspace, Document, Job, Configuration, etc.) is defined in detail in `01-domain-model-and-naming.md` and reused here.

---

## 2. High‑level runtime architecture

At runtime, the app is built from four main layers:

1. **App shell (`app/`)**
   - Mounts React, sets up providers, and routes between screens.
   - Owns the *global* layout (top bar, workspace shell frame).
   - Does not contain domain logic.

2. **Feature screens (`features/`, aliased as `@features` or `@screens`)**
   - Route‑level containers for functional areas:
     - Auth, workspace directory, workspace shell + its sections (Documents, Jobs, Config Builder, Settings, Overview).
   - Fetch data via hooks, compose UI components, handle workflows.

3. **Shared infrastructure (`shared/`, aliased as `@shared`)**
   - Cross‑cutting utilities and hooks:
     - Navigation helpers, URL state, local storage, NDJSON streaming, keyboard handling, permission checks, etc.
   - Contains no JSX that renders UI.

4. **UI library (`ui/`, aliased as `@ui`)**
   - Reusable, presentational components:
     - Buttons, forms, alerts, layout primitives, top bar, search field, code editor wrapper, etc.
   - No domain knowledge and no data fetching.

Supporting layers:

- **`schema/`** – hand‑written domain models and schema helpers.
- **`generated-types/`** – backend‑generated TypeScript types (if used).
- **`test/`** – Vitest setup, test utilities, and factories.

App entry looks like:

```tsx
// main.tsx
ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// App.tsx (simplified)
export function App() {
  return (
    <NavProvider>
      <AppProviders>
        <ScreenSwitch />
      </AppProviders>
    </NavProvider>
  );
}
````

`ScreenSwitch` maps the current location to a feature screen component (see doc `03-routing-navigation-and-url-state.md`).

---

## 3. Directory layout

The canonical layout for `apps/ade-web/src` is:

```text
src/
  app/                   # App shell, providers, global layout & routing
  features/              # Route/feature slices (was: screens)
    auth/
    workspace-directory/
    workspace-shell/
      WorkspaceShellScreen.tsx
      documents/
      jobs/
      config-builder/
      settings/
      overview/
  ui/                    # Reusable presentational components
  shared/                # Cross-cutting hooks and utilities
  schema/                # Hand-written domain schemas/models
  generated-types/       # Backend-generated API types
  test/                  # Vitest setup + shared testing helpers
```

Each top‑level folder has a well‑defined responsibility.

### 3.1 `app/` – App shell and providers

**Contains:**

* `App.tsx` – root component.
* `ScreenSwitch.tsx` – top‑level route switch.
* `NavProvider/` – custom navigation provider and hooks.
* `AppProviders/` – global providers (React Query, theming, etc.).
* Optional high‑level layout wrappers (e.g. a global error boundary).

**Does not contain:**

* Feature‑specific logic.
* Direct API calls.
* UI components that belong in `ui/`.

If you’re wiring top‑level providers, shells, or routing, it goes here.

---

### 3.2 `features/` – Feature screens and domain flows

`features/` contains **route‑level screens** and deeply related feature code.

Typical structure:

```text
src/features/
  auth/
    LoginScreen.tsx
    AuthCallbackScreen.tsx
    LogoutScreen.tsx
    authApi.ts               # optionally shared/api instead
    useLoginMutation.ts
  workspace-directory/
    WorkspaceDirectoryScreen.tsx
    WorkspaceCard.tsx
    WorkspaceDirectoryEmptyState.tsx
  workspace-shell/
    WorkspaceShellScreen.tsx
    documents/
      DocumentsScreen.tsx
      DocumentsTable.tsx
      DocumentsFilters.tsx
      useDocumentsQuery.ts
    jobs/
      JobsScreen.tsx
      JobsTable.tsx
      useJobsQuery.ts
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
      GeneralSettingsTab.tsx
      MembersTab.tsx
      RolesTab.tsx
    overview/
      WorkspaceOverviewScreen.tsx
```

**Contains:**

* Screen components (`*Screen.tsx`).
* Feature‑specific hooks and helper components.
* Small amounts of feature‑local state and logic.

**Does not contain:**

* Cross‑cutting utilities (should go in `shared/`).
* Generic UI components likely to be reused (should go in `ui/`).

Think of `features/` as: “What appears at a URL and all the glue around it.”

---

### 3.3 `ui/` – UI component library

`ui/` holds reusable, domain‑agnostic UI components built on Tailwind.

Examples:

```text
src/ui/
  Button.tsx
  SplitButton.tsx
  Input.tsx
  TextArea.tsx
  Select.tsx
  FormField.tsx
  Alert.tsx
  Avatar.tsx
  ProfileDropdown.tsx
  Tabs/
    TabsRoot.tsx
    TabsList.tsx
    TabsTrigger.tsx
    TabsContent.tsx
  ContextMenu.tsx
  GlobalTopBar.tsx
  GlobalSearchField.tsx
  CodeEditor.tsx
```

**Rules:**

* No calls to APIs.
* No knowledge of ADE‑specific domain objects.
* Props should be generic (`label`, `value`, `onChange`, `tone`, etc.).

Screens compose these primitives and add domain behaviour on top.

---

### 3.4 `shared/` – Cross‑cutting utilities and hooks

`shared/` contains logic used by many features but not tied to rendering.

Examples:

```text
src/shared/
  nav/
    routes.ts              # URL builders like workspaceDocuments(workspaceId)
  url-state/
    useSearchParams.ts
    urlState.ts
  storage/
    localStorage.ts        # namespaced storage helpers
  permissions/
    permissions.ts         # hasPermission, hasAnyPermission helpers
  streams/
    ndjson.ts              # NDJSON streaming helpers
  keyboard/
    shortcuts.ts           # global/workbench shortcut registration
  api/
    httpClient.ts          # fetch wrapper
    authApi.ts             # optionally here instead of in features/*
    workspacesApi.ts
    documentsApi.ts
    jobsApi.ts
    configsApi.ts
    buildsApi.ts
    rolesApi.ts
```

**Contains:**

* Pure functions and hooks that don’t care about *where* they are used.
* Infrastructure code like HTTP clients and NDJSON stream parsers.
* Route builders that keep raw path strings out of features.

**Does not contain:**

* JSX for UI components (that belongs in `ui/`).
* Screen‑specific state (belongs in `features/`).

When in doubt: if it has no visual representation and could be used in multiple features, it probably belongs here.

---

### 3.5 `schema/` and `generated-types/`

These folders represent the type system.

* **`schema/`**

  * Hand‑written domain models and helpers:

    * E.g. `WorkspaceSummary`, `DocumentSummary`, `JobSummary`, `Configuration`, `ConfigVersion`.
  * Optional Zod schemas or runtime validation.
  * Mapping functions from raw API responses to domain types.

* **`generated-types/`**

  * Types generated from backend schemas or OpenAPI.
  * May be used directly in `schema/` or wrapped.

Guideline:

> Features should import domain types from `@schema`, not reach into `@generated-types` directly.

This avoids tight coupling to backend codegen decisions.

---

### 3.6 `test/` – Test setup and helpers

**Contains:**

* `setup.ts` for Vitest (JSDOM, polyfills, global config).
* Shared factories/mock builders (e.g. `makeWorkspace`, `makeDocument`, `makeJob`).
* Test helpers like `renderWithProviders`.

Actual test files live near the code they test (e.g. `features/documents/DocumentsScreen.test.tsx`), but `test/` hosts common scaffolding.

---

## 4. Dependency rules

We enforce simple “downward only” imports to keep the graph clean:

```text
app
└── features
    ├── ui
    ├── shared
    ├── schema
    └── generated-types
```

More precisely:

* `ui/` **must not** import from:

  * `features/`
  * `app/`

* `shared/` **must not** import from:

  * `features/`
  * `ui/`
  * `app/`

* `schema/` **must not** import from:

  * `features/`
  * `ui/`
  * `app/`

* `generated-types/` **must not** import from anything outside itself.

* `features/` **may** import from:

  * `ui/`
  * `shared/`
  * `schema/`
  * `generated-types/` (but we prefer going through `schema/`).

* `app/` **may** import from:

  * `features/`
  * `ui/`
  * `shared/`
  * `schema/`

If you find yourself wanting to import “upwards” (e.g. from `shared/` into `features/` and back), that’s usually a sign that some logic should be pulled into a new, smaller module in `shared/`.

---

## 5. File and naming conventions

Consistent names make the repo searchable and predictable.

### 5.1 Components

* **Screen components**: `*Screen.tsx`

  * `LoginScreen.tsx`
  * `WorkspaceDirectoryScreen.tsx`
  * `WorkspaceShellScreen.tsx`
  * `DocumentsScreen.tsx`, `JobsScreen.tsx`, `ConfigBuilderScreen.tsx`, `WorkspaceSettingsScreen.tsx`

* **Feature components**:

  * Use descriptive names: `DocumentsTable.tsx`, `JobsFilters.tsx`, `ConfigList.tsx`, `RunExtractionDialog.tsx`.

* **UI primitives**:

  * Simple, generic names: `Button`, `SplitButton`, `Input`, `Alert`, `TabsRoot`, `GlobalTopBar`.

### 5.2 Hooks

Name hooks by intent:

* **Data fetching (React Query):**

  * `useDocumentsQuery`
  * `useJobsQuery`
  * `useConfigurationsQuery`
  * `useWorkspaceMembersQuery`

* **Mutations:**

  * `useUploadDocumentMutation`
  * `useSubmitJobMutation`
  * `useActivateConfigurationMutation`

* **State/infra:**

  * `useSafeModeStatus`
  * `useWorkbenchUrlState`
  * `useSearchParams`
  * `useNavigationBlocker`

Hooks live in the feature folder if they are specific to one screen,
or in `shared/` if they are generic.

### 5.3 API modules

API functions live in `shared/api` (or, if you prefer, in each feature folder, but the pattern stays the same).

* File names: `<domain>Api.ts`

  * `authApi.ts`
  * `workspacesApi.ts`
  * `documentsApi.ts`
  * `jobsApi.ts`
  * `configsApi.ts`
  * `buildsApi.ts`
  * `rolesApi.ts`
  * `safeModeApi.ts`

* Function naming: `verb + Noun` with nouns matching domain terms in doc 01:

  * `listWorkspaces`, `createWorkspace`, `updateWorkspace`.
  * `listWorkspaceDocuments`, `uploadDocument`, `deleteDocument`.
  * `listWorkspaceJobs`, `submitJob`.
  * `listConfigurations`, `activateConfiguration`, `deactivateConfiguration`.

Feature hooks wrap these functions and bind them to React Query.

---

## 6. Path aliases

The Vite/TSconfig aliases are:

* `@app` → `src/app`
* `@features` (or `@screens`) → `src/features`
* `@ui` → `src/ui`
* `@shared` → `src/shared`
* `@schema` → `src/schema`
* `@generated-types` → `src/generated-types`
* `@test` → `src/test`

Usage guidelines:

* Prefer aliases over relative paths for cross‑folder imports:

  ```ts
  // good
  import { GlobalTopBar } from "@ui/GlobalTopBar";
  import { useSearchParams } from "@shared/url-state/useSearchParams";
  import { WorkspaceSummary } from "@schema/workspaces";

  // avoid
  import { GlobalTopBar } from "../../ui/GlobalTopBar";
  ```

* Within a folder (e.g. inside `features/workspace-shell/documents`), relative imports are fine and often clearer.

---

## 7. Worked example: Documents feature

Putting it all together, here is how the **Documents** feature fits into the structure:

```text
src/
  app/
    ScreenSwitch.tsx          # routes /workspaces/:id/documents to DocumentsScreen
  features/
    workspace-shell/
      documents/
        DocumentsScreen.tsx   # entrypoint for the Documents section
        DocumentsTable.tsx
        DocumentsFilters.tsx
        RunExtractionDialog.tsx
        useDocumentsQuery.ts
        useUploadDocumentMutation.ts
  ui/
    Button.tsx
    Input.tsx
    Alert.tsx
    GlobalTopBar.tsx
  shared/
    api/
      documentsApi.ts         # listWorkspaceDocuments, uploadDocument, etc.
    url-state/
      useSearchParams.ts
    permissions/
      permissions.ts          # hasPermission for upload/execute actions
  schema/
    documents.ts              # DocumentSummary, DocumentDetail, enums
```

* `ScreenSwitch` sees `/workspaces/:workspaceId/documents` and renders `DocumentsScreen`.
* `DocumentsScreen`:

  * Uses `useDocumentsQuery` to fetch data.
  * Composes `GlobalTopBar` and `DocumentsTable`.
  * Uses `Button` from `@ui` for “Upload document”.
* `DocumentsTable` is purely presentational; it receives `DocumentSummary[]` and callbacks.
* `useDocumentsQuery` wraps `documentsApi.listWorkspaceDocuments` with React Query.
* `documentsApi.ts` is the only place that knows about `/api/v1/workspaces/{workspace_id}/documents`, and returns typed data using `DocumentSummary` from `@schema`.

This pattern scales cleanly to Jobs, Config Builder, Settings, and any new sections you add.

---

By adhering to this structure and these naming and dependency rules, `ade-web` stays:

* **Predictable** – new contributors and AI agents can quickly find the right place for any change.
* **Composable** – UI primitives are reusable and domain‑agnostic.
* **Maintainable** – cross‑cutting logic is centralised, and features don’t leak into each other.

Any time you add a new feature or route, start by deciding:

1. Which **feature folder** it belongs in.
2. Which parts are **presentational** (`ui/`) vs **domain logic** (`features/`) vs **shared infra** (`shared/`).

If that’s clear, the rest of the implementation tends to fall into place.