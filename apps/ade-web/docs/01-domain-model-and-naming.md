# ADE Web — Domain model & naming

This doc is the **source of truth for names** in ADE Web.

It defines:

* What the core entities are (workspace, configuration, build, run, document, outputs/telemetry, …)
* What we call them in:

  * UI text
  * TypeScript & schemas
  * Routes, folders, and local storage keys

If this doc, the routes, and the feature folders stay in sync, the codebase is much easier to navigate for both humans and agents.

---

## 0. Quick naming checklist

When you add or touch code, copy, or routes, keep these aligned:

**Entities & IDs**

* **Workspace** – UI: *Workspace* – field: `workspaceId`
* **Configuration** – UI: *Configuration* – field: `configurationId`
* **Configuration package** – the **Python project backing a Configuration**

  * Never a separate UI concept. Mention only when talking about Python packaging.
* **Configuration version** – type `ConfigurationVersion` – field: `configurationVersionId`
* **Build** – UI: *Build* – field: `buildId`
* **Run** – UI: *Run* – field: `runId`
* **Document** – UI: *Document* – field: `documentId`
* **Config template** – baked into the ade-engine CLI (`ade-engine config init`); no longer listed as an API resource.

**Routes**

* Workspace shell entry:
  `/workspaces`
* Workspace sections:
  `/workspaces/:workspaceId/{documents|runs|config-builder|settings}`

**Feature folders**

```text
features/workspace-shell/sections/
  documents
  runs
  config-builder
  settings
```

**API modules**

* `workspacesApi`
* `configurationsApi`
* `documentsApi`
* `runsApi`
* `buildsApi`

**Local storage prefix**

* `ade.ui.workspace.<workspaceId>…`

### Configuration Builder naming rule (important)

Keep these three in lockstep:

* **Nav label**: `Configuration Builder`
* **Route segment**: `/config-builder`
* **Folder**: `features/workspace-shell/sections/config-builder`

If these disagree, the app becomes much harder to reason about.

---

## 1. Audience & goals

**Audience**

* Frontend engineers working in `apps/ade-web/`
* API / engine maintainers who care about user-facing terminology
* Anyone writing tests, docs, or debug logs that reference ADE entities

**Goals**

1. Share a **single mental model** of “things” in ADE Web.
2. Keep **user-facing names, API types, and filesystem terms** aligned.
3. Avoid subtle naming drift (e.g. “execution” vs “run”, “project” vs “workspace”).
4. Make it obvious how to name new **screens, hooks, and types**.

---

## 2. Big picture: ADE Web domain

At a high level:

1. A **Workspace** is the top-level container for a team/tenant.
2. Inside a workspace, users define **Configurations** that describe how ADE processes documents.
   Each Configuration is backed by an installable **configuration package** (`ade_config`).
3. Each Configuration can be **built** into a Python environment (virtualenv) — a **Build**.
4. Users upload **Documents** (Excel/CSV) to the workspace.
5. Users start **Runs** that execute a particular **Build** against one or more **Documents**, producing normalized outputs (`output.xlsx`) and telemetry (`events.ndjson`).

Conceptually:

```text
Workspace
 ├─ Configurations (backed by configuration packages)
 │    ├─ Builds (frozen Python environments for that configuration)
 │    │    └─ Runs
 │    │         ├─ Input documents
 │    │         └─ Outputs (output.xlsx) + telemetry (events.ndjson)
 └─ Shared documents
```

The rest of this doc just pins down the **canonical names** for each box in this picture.

---

## 3. Core entities (reference table)

### 3.1 Summary table

| Concept               | UI label        | TS type name               | Typical ID field(s)              | Storage / backend hints                                |
| --------------------- | --------------- | -------------------------- | -------------------------------- | ------------------------------------------------------ |
| Workspace             | Workspace       | `Workspace`                | `workspaceId`                    | `workspaces/<workspace_id>/…`                          |
| Configuration         | Configuration   | `Configuration`            | `configurationId`, `workspaceId` | `configurations/<configuration_id>/…`                  |
| Configuration package | *(no label)*    | n/a (Python project)       | same as `configurationId`        | `config_packages/<configuration_id>/…`                 |
| Configuration version | *(varies)*      | `ConfigurationVersion`     | `configurationVersionId`         | Backend versioning record for a configuration          |
| Build                 | Build           | `Build`                    | `buildId`, `configurationId`     | `.venv/<configuration_id>/ade-runtime/build.json`      |
| Run                   | Run             | `Run`                      | `runId`                          | `runs/<run_id>/…`                                      |
| Document              | Document        | `Document`                 | `documentId`, `workspaceId`      | `documents/<document_id>.<ext>`                        |
| Config template       | Config template | *(built-in engine template)* | n/a (engine-managed)             | Provided by `ade-engine config init`; no API storage    |

> OpenAPI-generated types live under `@schema`. In app code we alias them to clean domain names instead of using the raw generated names everywhere.

---

## 4. Entity details

### 4.1 Workspace

**What it is**

* Top-level container and isolation boundary.
* Owns configurations, runs, documents, and runtime state, typically under
  `./data/workspaces/<workspace_id>/…`.

**User-facing naming**

* Singular: **Workspace**
* Plural: **Workspaces**
* Example copy:

  * “Create workspace”
  * “Switch workspace”
  * “No workspaces yet”

**Code & API naming**

* ID:

  * `workspaceId` in TypeScript
  * `workspace_id` in engine / API responses and URLs
* Storage / URL segments:

  * `workspaces/<workspace_id>/…`

**Frontend conventions**

```ts
import type { WorkspaceEnvelope } from "@schema";

// Alias generated types at the edge.
type Workspace = WorkspaceEnvelope;
```

Examples:

* Hooks:

  * `useWorkspaces()` – list
  * `useWorkspace(workspaceId)` – detail
* Components:

  * `<WorkspacesScreen />`
  * `<WorkspaceSelector />`

---

### 4.2 Configuration & configuration package

**What a Configuration is**

* A **workspace-scoped configuration** that describes how ADE processes documents.
* It is the user-facing concept: when we say “edit this configuration” we mean “change how ADE behaves”.

**Backing configuration package**

* Each Configuration is backed by a **Python `ade_config` package** that lives on disk and is installable.
* The backing package contains detectors, transforms, validators, hooks, and a manifest.
* Source of truth on disk is typically under:

  * `configurations/<configuration_id>/…` for workspace-level config state
  * `config_packages/<configuration_id>/…` for the Python project structure

**Important rule**

* In UI copy and React components, always say **Configuration**.
* When you need to talk about the Python-level package, call it the **backing configuration package**.
* Do **not** introduce a separate “Config Package” entity in the UI.

**User-facing naming**

* Singular: **Configuration**
* Plural: **Configurations**

**Code & API naming**

* IDs:

  * `configurationId: string`
  * `workspaceId: string`
* Common fields:

  * `name`, `description`
  * `createdAt`, `updatedAt`
  * Optional version / status fields (see Configuration Version below)
* Backend:

  * `configuration_id` in JSON and URLs
  * Canonical paths: `configurations/<configuration_id>/…`, `config_packages/<configuration_id>/…`

**Frontend conventions**

```ts
import type { ConfigurationEnvelope } from "@schema";

type Configuration = ConfigurationEnvelope;
```

Examples:

* Hooks:

  * `useConfigurations(workspaceId)`
  * `useConfiguration({ workspaceId, configurationId })`
* Components:

  * `<ConfigurationList />`
  * `<ConfigurationDetail />`
  * `<CreateConfigurationDialog />`

---

### 4.3 Configuration version

Some APIs expose an explicit record for a configuration’s version (for example, buildable revisions).

**User-facing naming**

* Usually implied (e.g. “Latest build uses configuration X”).
* If you surface it explicitly, use phrasing like **Configuration version** and keep it tied to a Configuration.

**Code & API naming**

* Type: `ConfigurationVersion`
* ID field: `configurationVersionId`
* Relates to:

  * `configurationId`
  * Possibly `buildId` if versions are build-specific

**Frontend conventions**

* Keep version-specific types and components obviously attached to the parent concept:

  * `ConfigurationVersion`, `ConfigurationVersionBadge`, etc.

---

### 4.4 Build

**What it is**

* A **Build** is a frozen Python environment (virtualenv) for a given Configuration.
* It contains:

  * `ade_engine`
  * the backing configuration package (`ade_config`)
  * their dependencies
* Build metadata lives under (example):

  * `.venv/<configuration_id>/ade-runtime/build.json`

**User-facing naming**

* Singular: **Build**
* Plural: **Builds**
* Example copy:

  * “Latest build”
  * “Build failed”
  * “Trigger build”

**Code & API naming**

* IDs:

  * `buildId`
  * plus `configurationId` and `workspaceId`
* Typical fields:

  * `status` (`"pending" | "running" | "succeeded" | "failed"` — actual values defined by the schema)
  * `createdAt`, `startedAt`, `finishedAt`
  * `engineVersion`, `configVersion` or similar fields

**Frontend conventions**

```ts
import type { BuildEnvelope } from "@schema";

type Build = BuildEnvelope;
```

Examples:

* Hooks:

  * `useBuilds(configurationId)`
  * `useBuild(configurationId, buildId)`
  * `useTriggerBuild()` (mutation)
* Components:

  * `<BuildStatusBadge />`
  * `<BuildTimeline />`

---

### 4.5 Run

**What it is**

* A **Run** is a user-visible execution of a Build against one or more Documents.
* It is the main unit you see in “Run history”.

**Terminology**

* In UI copy and UX discussions: **always say “Run”**, not “execution”, “job”, or “batch”.

  * E.g. “Start run”, “Run details”, “Run history”.

**Code & API naming**

* Backend field: `run_id`
* Frontend field: **`runId`** — we translate snake_case → camelCase once in schema mapping helpers.
* If the engine exposes an additional low-level ID, name it `engineRunId` to avoid confusion with `runId`.

Typical fields:

* IDs:

  * `runId`
  * `workspaceId`, `configurationId`, `buildId`
* Status:

  * e.g. `"queued"`, `"running"`, `"succeeded"`, `"failed"` (the exact enum is defined by the API)
* Inputs / outputs:

  * `inputDocuments: Document[]` or similar
  * Output metadata (paths to `output.xlsx`, `events.ndjson`)

**Frontend conventions**

```ts
import type { RunEnvelope } from "@schema";

type Run = RunEnvelope;
// Optionally narrow it with a view model if needed.
```

* Hooks:

  * `useRuns(workspaceId)` or `useRunsForBuild(buildId)`
  * `useRun(runId)`
  * `useStartRun()` (mutation)
* Components:

  * `<RunList />`
  * `<RunDetailScreen />`
  * `<RunStatusPill />`

---

### 4.6 Document

**What it is**

* A **Document** is an uploaded input file (Excel/CSV) owned by a workspace.
* On disk it typically lives under:
  `workspaces/<workspace_id>/documents/<document_id>.<ext>`

**User-facing naming**

* Singular: **Document**
* Plural: **Documents**
* Example copy:

  * “Upload document”
  * “Recent documents”
  * “Document used in this run”

**Code & API naming**

* IDs:

  * `documentId`
  * `workspaceId`
* Typical fields:

  * `filename`, `contentType`, `sizeBytes`
  * `uploadedAt`, `uploadedBy`
  * Optional derived fields like `lastRunId`, `lastRunStatus` (view-model level)

**Frontend conventions**

```ts
import type { DocumentEnvelope } from "@schema";

type Document = DocumentEnvelope;
```

Examples:

* Hooks:

  * `useDocuments(workspaceId)`
  * `useDocument(documentId)`
* Components:

  * `<DocumentUpload />`
  * `<DocumentTable />`

---

### 4.7 Config template

**What it is**

* A **template** used to bootstrap new configuration packages.
* The starter template now ships with the ade-engine CLI (`ade-engine config init`) and is not listed by the API.

**Naming**

* UI label: **Config template** (if you surface a choice, it will likely be a single “Default” option).
* No dedicated API type/ID; treat it as an engine capability rather than an API resource.

---

## 5. Naming conventions in the frontend

### 5.1 General principles

1. **Prefer domain words over implementation words**

   * Use **Run**; avoid “execution”, “job”, “task”.
   * Use **Configuration**; avoid ad-hoc labels like “ruleset” or “profile”.
   * Only mention **configuration package** when specifically talking about Python packaging / repo layout.

2. **Mirror backend identifiers, but adapt to JS/TS style**

   * Backend (JSON / URLs): `workspace_id`, `configuration_id`, `run_id`, …
   * Frontend (TS / React):

     * `workspaceId`, `configurationId`, `runId`, …

3. **One concept → one name**

   * Don’t mix “workspace” vs “project”.
   * Don’t mix “run” vs “execution”.
   * Don’t introduce synonyms unless they’re clearly secondary / descriptive (“backing configuration package” is clearly secondary to “Configuration”).

---

### 5.2 Schema types & aliases

**Sources of truth**

* OpenAPI-generated types live in `apps/ade-web/src/generated-types/openapi.d.ts`.
* A curated module under `src/schema/` re-exports stable shapes (e.g. `WorkspaceEnvelope`, `RunEnvelope`).

**Conventions**

* **App code imports from `@schema`**, not from `@generated-types/*` directly.

* At the edge, alias verbose API types to clean domain types:

  ```ts
  import type { WorkspaceEnvelope, RunEnvelope } from "@schema";

  type Workspace = WorkspaceEnvelope;
  type Run = RunEnvelope;
  ```

* Use **PascalCase** for type names:

  * `Workspace`, `Configuration`, `Build`, `Run`, `Document`, `Artifact`.

* Avoid `IWorkspace` / `TWorkspace` prefixes.

---

### 5.3 IDs & relationships

**Field naming**

Always use `<entity>Id`:

* `workspaceId`
* `configurationId`
* `configurationVersionId`
* `buildId`
* `runId`
* `documentId`

If you need the raw engine ID in addition to `run_id`:

* Map `run_id` to `runId` once.
* Add a separate field like `engineRunId` if that’s useful; don’t overload `runId`.

**Where to do the mapping**

* Do snake_case → camelCase **once** in schema mapping helpers (e.g. `fromApiRun`, `fromApiConfiguration`) so screens never see `run_id` / `configuration_id` directly.

**Relationship examples**

```ts
interface WorkspaceRef {
  workspaceId: string;
}

interface ConfigurationRef extends WorkspaceRef {
  configurationId: string;
}

interface BuildRef extends ConfigurationRef {
  buildId: string;
}

interface RunRef {
  runId: string;
}
```

---

### 5.4 Screens, components, hooks, and routes

**Screens**

* Place under `src/screens/<FeatureName>/`.
* Name the top-level component `<FeatureName>Screen`:

  * `<WorkspacesScreen />`
  * `<RunDetailScreen />`
  * `<ConfigurationBuilderScreen />` (for `/config-builder`)

**Feature components**

* Use domain nouns:

  * `<WorkspaceList />`
  * `<ConfigurationList />`
  * `<RunTable />`
* For dialogs / modals:

  * `<CreateWorkspaceDialog />`
  * `<StartRunDialog />`

**Hooks**

* Data-fetch hooks:

  * `useWorkspaces()`
  * `useConfigurations(workspaceId)`
  * `useRuns(workspaceId)`
* Mutations:

  * `useCreateWorkspace()`
  * `useCreateConfiguration()`
  * `useTriggerBuild()`
  * `useStartRun()`

**Routes**

* Use nav helpers from `@app/nav` (`useNavigate`, `useLocation`, `Link`, `NavLink`).
* Match route param names to the `<entity>Id` convention:

  ```text
  /workspaces
  /workspaces/:workspaceId/documents
  /workspaces/:workspaceId/runs
  /workspaces/:workspaceId/config-builder
  /workspaces/:workspaceId/settings
  ```

  Add nested params in the same style if needed, e.g.:

  ```text
  /workspaces/:workspaceId/config-builder/configurations/:configurationId
  /workspaces/:workspaceId/runs/:runId
  ```

---

### 5.5 Status strings & enums

**Backend**

* Status values are plain strings (e.g. `"pending"`, `"running"`, `"succeeded"`, `"failed"`).
* The exact set comes from the OpenAPI schema.

**Frontend**

Represent them as string unions, even if you also keep the raw OpenAPI type:

```ts
type BuildStatus = "pending" | "running" | "succeeded" | "failed";
type RunStatus = "queued" | "running" | "succeeded" | "failed";
```

UI components should map status strings to consistent visuals, e.g.:

* `"succeeded"` → success style
* `"failed"` → danger style

---

## 6. Example: end-to-end naming for a common flow

Putting it all together for a typical user interaction:

1. The user selects a **Workspace**.

   * Route: `/workspaces/:workspaceId/documents`
   * Code: `workspaceId` (TS), `workspace_id` (API)

2. They open a **Configuration** (`configurationId`) and click **Build**.

   * UI: “Trigger build”
   * API: `POST /configurations/{configuration_id}/builds`

3. The system creates a **Build** for that Configuration (`buildId`) and shows its **Build status**.

   * UI: `<BuildStatusBadge status={build.status} />`

4. They **Upload document(s)** to the workspace.

   * UI: “Upload document”
   * Code: `documentId` fields, `useDocuments(workspaceId)` to list

5. From the Configuration / Build context they click **Start run**.

   * Mutation hook: `useStartRun()`
   * API returns a `run_id`, mapped to `runId`.

6. A **Run** appears in the run list (`/workspaces/:workspaceId/runs`).

   * UI: “Run history”
   * Type: `Run` with `runId`, `status`, `inputDocuments`, …

7. When the run completes, the UI surfaces **Outputs and telemetry**.

   * UI: “Download output”, “View telemetry”
   * Code: output paths + telemetry log (`events.ndjson`) keyed by `runId`.

If you can tell, for every step, **what the entity is, what we call it in the UI, and which ID field it uses**, you’re using this doc correctly.
