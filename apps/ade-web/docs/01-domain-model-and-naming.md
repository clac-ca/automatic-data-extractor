# 01-domain-model-and-naming

**Purpose:** Single source of truth for concepts, vocabulary, and naming rules. Every other doc links back here instead of redefining things.

### 1. Overview

* What this doc is and why it exists.
* “If you’re unsure what to call something, check this first.”
* Scope: domain language, UI labels, and core TypeScript type names.

### 2. Core entities

For each, define:

* Canonical **name** (UI term).
* One-line definition.
* Primary **identifiers** (id/slug).
* Main **screen(s)** and **primary API endpoints**.

Entities to cover:

* **Workspace directory** vs **Workspace shell**.
* **Workspace** (owner of documents, jobs, configs, members).
* **Document**.
* **Job** (the main term in the UI – “job” vs “run”).
* **Run** (if used in the UI at all) – or explicitly state it’s a backend/internal name only.
* **Build** (Config build, not engine build if there’s a distinction).
* **Configuration / Config** (and how those two words are used).
* **Config version** (draft / active / inactive).
* **User** vs **Member** vs **Principal**.
* **Role** / **Permission** / **Role assignment**.
* **Safe mode** (system vs workspace scoped if you ever add workspace scope).

### 3. Statuses and lifecycles

Subsections:

* **Documents**

  * Allowed statuses and meanings: `uploaded`, `processing`, `processed`, `failed`, `archived`.
  * Trigger events that move between statuses (upload, job start, job completion, delete/archive).

* **Jobs**

  * Allowed statuses: `queued`, `running`, `succeeded`, `failed`, `cancelled`.
  * Relationship to runs/builds if relevant.
  * How these map to badge colours in the UI (high-level).

* **Configurations / Config versions**

  * Lifecycle states: `Draft`, `Active`, `Inactive`.
  * Allowed transitions (Draft → Active, Active → Inactive, etc.).
  * How “publish” vs “activate” vs “deactivate” map onto these states.

* **Safe mode**

  * `enabled`/`disabled`.
  * What “turned on” means in UX terms (all engine-invoking actions blocked).

### 4. Naming rules and conventions

* **UI vs backend naming:**

  * Use **Job** consistently in the UI for `/jobs`.
  * Reserve **Run** for engine-level concepts or API object names if needed.
  * Use **Config** for UX & helper code (`ConfigList`, `useConfigsQuery`).
  * Use **Configuration** for TS types that mirror backend data (`Configuration`, `ConfigurationVersion`).

* **Type names:**

  * Singular, PascalCase domain types: `Workspace`, `WorkspaceSummary`, `Document`, `JobSummary`, `Configuration`, `ConfigVersion`.
  * `Summary` for list-row types, `Detail` for fully hydrated types.

* **Hook names:**

  * Queries: `use<Domain><What>Query` (`useDocumentsQuery`, `useJobsQuery`).
  * Mutations: `use<Verb><Domain>Mutation` (`useUploadDocumentMutation`).
  * UI state: `use<Something>State` or explicit (`useWorkbenchUrlState`, `useSafeModeStatus`).

* **File and component names:**

  * Screens: `<Domain>Screen.tsx` (`DocumentsScreen`, `JobsScreen`).
  * Shells: `WorkspaceShellScreen`.
  * Presentational components: `GlobalTopBar`, `ProfileDropdown`, `DocumentsTable`.

### 5. Term → Route → Type → Component mapping

* A table mapping:

  * Domain term → Primary URL → Main TS type(s) → Screen component(s).

* Example rows:

  * Workspace, Document, Job, Configuration, Config version, Safe mode.

### 6. Reserved and non-preferred terms

* List of words we **don’t** use, or aliases we explicitly discourage:

  * Don’t call a workspace a “project”.
  * Don’t call jobs “tasks”.
  * Don’t call configs “pipelines” in the UI.
  * etc.

* The goal: reduce synonym noise for humans and AI.
