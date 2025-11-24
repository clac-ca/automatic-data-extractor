# 02-architecture-and-project-structure

**Purpose:** Show where everything lives, what imports what, and how to name files and modules.

### 1. Overview

* Goal: “You can glance at the repo tree and know where to put/lookup code.”
* Relationship to 01 (concepts) and 03 (routing).

### 2. Directory layout

Describe the intended layout, e.g.:

```text
apps/ade-web/
  src/
    app/
    features/
    ui/
    shared/
    schema/
    generated-types/
    test/
```

For each top level:

* **`app/`**

  * `App.tsx`, `ScreenSwitch.tsx`, `NavProvider`, `AppProviders`.
  * Global shells, providers, and composition only. No domain details.

* **`features/`**

  * Route/feature slices (was `screens`).
  * Subfolders: `auth`, `workspace-directory`, `workspace-shell/documents`, `jobs`, `config-builder`, `settings`, `overview`.
  * Each subfolder contains the screen component(s), feature-specific hooks, and sub-components.

* **`ui/`**

  * Reusable, presentational components: buttons, form controls, layout primitives, top bar, search, code editor, etc.
  * No domain logic, no API calls.

* **`shared/`**

  * Cross-cutting hooks and utilities:

    * `urlState`, `storage`, `ndjson`, `keyboard`, `permissions`, etc.
  * No React components that render UI.

* **`schema/`**

  * Hand-written domain models / Zod schemas / mappers.

* **`generated-types/`**

  * Code-generated TypeScript types from backend schemas (if used).

* **`test/`**

  * Vitest `setup.ts`.
  * Shared factories and helpers.

### 3. Module responsibility and dependencies

Spell out allowed imports:

* `ui/` does **not** import from `features/` or `app/`.
* `shared/` does **not** import from `features/` or `ui/`.
* `features/*` may import from `ui/`, `shared/`, `schema/`, `generated-types/`.
* `app/` may import from all of the above, but tries to stay thin.

Explain the rationale: this keeps circular deps and “god modules” at bay.

### 4. Aliases

Document the Vite/TS paths:

* `@app` → `src/app`
* `@features` or `@screens` → `src/features`
* `@ui` → `src/ui`
* `@shared` → `src/shared`
* `@schema` → `src/schema`
* `@generated-types` → `src/generated-types`
* `@test` → `src/test`

Mention: we prefer `@features` going forward, but keep `@screens` as a compatibility alias if needed.

### 5. File & naming conventions

* **Screens & shells:**

  * `DocumentsScreen.tsx`, `JobsScreen.tsx`, `ConfigBuilderScreen.tsx`, `WorkspaceShellScreen.tsx`.

* **Feature components:**

  * Feature-scoped chunks: `DocumentsTable.tsx`, `JobsFilters.tsx`, `ConfigList.tsx`.

* **Hooks:**

  * In feature folders: `useDocumentsQuery.ts`, `useSubmitJobMutation.ts`.
  * In `shared/`: `useSafeModeStatus.ts`, `useSearchParams.ts`.

* **API modules:**

  * `authApi.ts`, `workspacesApi.ts`, `documentsApi.ts`, `jobsApi.ts`, `configsApi.ts`, `buildsApi.ts`, `rolesApi.ts`.
  * Thin, typed wrappers around fetch/axios.

* **Barrels (optional):**

  * Where, if anywhere, you allow `index.ts` barrels, and what they can re-export.

### 6. Example: walkthrough of one feature folder

* Pick `features/workspace-shell/documents/` and show:

  * `DocumentsScreen.tsx`
  * `DocumentsTable.tsx`
  * `useDocumentsQuery.ts`
  * `documentsApi.ts` (or imported from shared API folder)
  * How they compose.
