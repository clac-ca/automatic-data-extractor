# ADE Web — Domain model & naming

This document defines the domain concepts that the ADE web app works with and how we name them in the UI, API shapes, and frontend code. It’s meant to keep the frontend in lockstep with the ADE engine and API (workspaces, config packages, builds, runs, documents, artifacts).

---

## 1. Goals

**Audience**

* Frontend engineers working in `apps/ade-web/`
* API/engine maintainers who care about UX terminology
* Anyone writing docs, tests, or debug logs that reference ADE entities

**Goals**

1. Share a single mental model of “things” in ADE Web.
2. Align user‑facing names, API types, and filesystem terms.
3. Avoid subtle “job vs run”-style inconsistencies.
4. Make it obvious how to name new screens, hooks, and types.

---

## 2. Big picture: the ADE Web domain

At a high level:

1. A **Workspace** owns everything for a given team/tenant.
2. Within a workspace, users author **Config packages** — installable `ade_config` projects. 
3. Each config package can be **built** into a virtualenv that includes `ade_engine` + that `ade_config`. 
4. Users upload **Documents** (Excel/CSV) to the workspace. 
5. Users launch **Runs** that execute a **Build** against one or more **Documents**, producing **Artifacts** (`output.xlsx` and `artifact.json`).

Conceptually:

```text
Workspace
 ├─ Config packages
 │    ├─ Builds
 │    │    └─ Runs
 │    │         ├─ Input documents
 │    │         └─ Artifacts (output.xlsx, artifact.json)
 └─ Shared documents
```

---

## 3. Core entities

### 3.1 Summary table

| Concept        | UI label        | Recommended TS type name   | Typical ID field(s)            | Backend / storage hints                     |
| -------------- | --------------- | -------------------------- | ------------------------------ | ------------------------------------------- |
| Workspace      | Workspace       | `Workspace`                | `workspaceId`                  | `workspaces/<workspace_id>/…`               |
| Config package | Config package  | `ConfigPackage`            | `configId`, `workspaceId`      | `config_packages/<config_id>/…`             |
| Build          | Build           | `Build`                    | `buildId`, `configId`          | `.venv/<config_id>/ade-runtime/build.json`  |
| Run (job)      | Run             | `Run`                      | `runId` (UI), `jobId` (engine) | `jobs/<job_id>/…`                           |
| Document       | Document        | `Document`                 | `documentId`, `workspaceId`    | `documents/<document_id>.<ext>`             |
| Artifact       | Artifact        | `Artifact` / `JobArtifact` | `jobId` / `runId`              | `jobs/<job_id>/logs/artifact.json`          |
| Template       | Config template | `ConfigTemplate`           | `templateId`                   | `templates/config_packages/…`               |

> The exact TS types come from `@schema` (OpenAPI‑generated); in the web app we usually alias those to ergonomic names rather than importing from `@generated-types` directly. 

---

### 3.2 Workspace

**What it represents**

* Top‑level container and isolation boundary.
* Owns config packages, jobs/runs, documents, artifacts, and runtime state under `./data/workspaces/<workspace_id>/…`. 

**User‑facing naming**

* Singular: **Workspace**
* Plural: **Workspaces**
* Examples in copy:

  * “Create workspace”
  * “Switch workspace”
  * “No workspaces yet”

**Code & API naming**

* Route param: `workspaceId`
* TS field: `workspaceId: string`
* Backend / storage convention: `workspace_id` and `<workspace_id>` segments

**Frontend conventions**

* Type alias from schema:

  ```ts
  import type { WorkspaceEnvelope } from "@schema"; // example

  type Workspace = WorkspaceEnvelope; // frontend alias
  ```

* Hooks:

  * `useWorkspaces()` — list
  * `useWorkspace(workspaceId)` — detail

* Components:

  * `<WorkspacesScreen />`
  * `<WorkspaceSelector />`

---

### 3.3 Config package

**What it represents**

* A versioned, installable **`ade_config` package** containing detectors, transforms, validators, and hooks.
* Source of truth lives under a workspace: `config_packages/<config_id>/…`. 

**User‑facing naming**

* Singular: **Config package**
* Plural: **Config packages**
* Use this term consistently in UI copy (avoid “config project” / “ruleset” unless explicitly defined as synonyms).

**Code & API naming**

* IDs:

  * `configId: string`
  * `workspaceId: string`
* Common fields:

  * `name`, `description`
  * `version` / `displayVersion` (if applicable)
  * `createdAt`, `updatedAt`
* Backend convention: `config_id`, `config_packages/…`

**Frontend conventions**

* Type alias: `type ConfigPackage = Schema.ConfigPackage…;`
* Hooks:

  * `useConfigPackages(workspaceId)`
  * `useConfigPackage({ workspaceId, configId })`
* Components:

  * `<ConfigPackageList />`
  * `<ConfigPackageDetail />`
  * `<CreateConfigPackageDialog />`

---

### 3.4 Build

**What it represents**

* A build is a **frozen Python environment** (virtualenv) for a specific config package:

  * Contains `ade_engine`, the `ade_config` package, and its dependencies.
* Build metadata lives alongside the venv under `.venv/<config_id>/ade-runtime/build.json`. 

**User‑facing naming**

* Singular: **Build**
* Plural: **Builds**
* Copy examples:

  * “Latest build”
  * “Build failed”
  * “Trigger build”

**Code & API naming**

* IDs:

  * `buildId` (if surfaced as a first‑class entity)
  * `configId`, `workspaceId`
* Typical fields:

  * `status` (`"pending" | "running" | "succeeded" | "failed"` – actual values defined by the API)
  * `createdAt`, `startedAt`, `finishedAt`
  * `engineVersion`, `configVersion`

**Frontend conventions**

* Type: `Build`
* Hooks:

  * `useBuilds(configId)`
  * `useBuild(configId, buildId)`
  * `useTriggerBuild()` mutation
* Components:

  * `<BuildTimeline />`
  * `<BuildStatusBadge />`

---

### 3.5 Run (job)

**What it represents**

* A **Run** is a user‑visible execution of a build against one or more documents.
* The engine/backend call this concept a **job**; the filesystem layout exposes `jobs/<job_id>/input`, `output`, `logs/…`. 

**Terminology rule**

* In **UI copy** and UX discussions: say **Run**.

  * “Run history”, “Run details”, “Start run”
* In **code & API**:

  * It’s acceptable to use `jobId` to match the engine/job schema.
  * But the overall type should still be `Run` in the frontend.

**Code & API naming**

* IDs:

  * `runId` (frontend field name) — often the same value as `jobId`
  * `jobId` (backend/engine naming)
  * `workspaceId`, `configId`, `buildId`
* Typical fields:

  * `status` (`"queued"`, `"running"`, `"succeeded"`, `"failed"`, etc. — defined by API)
  * `inputDocuments: Document[]`
  * `artifact` metadata (path to `output.xlsx`, `artifact.json`)

**Frontend conventions**

* Type:

  ```ts
  interface Run {
    runId: string;   // alias for underlying job_id
    jobId: string;   // raw engine identifier, if needed
    status: RunStatus;
    // …
  }
  ```

* Hooks:

  * `useRuns(configId)` / `useRunsForBuild(buildId)`
  * `useRun(runId)`
  * `useStartRun()` mutation

* Components:

  * `<RunList />`
  * `<RunDetailScreen />`
  * `<RunStatusPill />`

---

### 3.6 Document

**What it represents**

* An uploaded **input file** (Excel/CSV) owned by a workspace.
* Stored under `workspaces/<workspace_id>/documents/<document_id>.<ext>`. 

**User‑facing naming**

* Singular: **Document**
* Plural: **Documents**
* Copy examples:

  * “Upload document”
  * “Recent documents”
  * “Document used in this run”

**Code & API naming**

* IDs:

  * `documentId`, `workspaceId`
* Typical fields:

  * `filename`, `contentType`, `sizeBytes`
  * `uploadedAt`, `uploadedBy`
  * Optional `lastRunId` / `lastRunStatus` (view model convenience)

**Frontend conventions**

* Types:

  * `Document`
  * `DocumentSummary` (if you introduce lightweight list DTOs)
* Hooks:

  * `useDocuments(workspaceId)`
  * `useDocument(documentId)`
* Components:

  * `<DocumentUpload />`
  * `<DocumentTable />`

---

### 3.7 Artifact

**What it represents**

* The structured result of a run:

  * Normalized workbook (`output.xlsx`)
  * Narrative + metrics in `artifact.json` under `jobs/<job_id>/logs/`. 

**User‑facing naming**

* Singular: **Artifact**
* Plural: **Artifacts**
* Copy examples:

  * “Download artifact”
  * “Artifact summary”

**Code & API naming**

* IDs:

  * `jobId` / `runId`
* Fields typically follow the artifact schema (see `docs/14-job_artifact_json.md` in the backend docs). 

**Frontend conventions**

* Types:

  * `Artifact` or `JobArtifact`
  * Specific views: `ArtifactSheetSummary`, `ArtifactIssue`
* Components:

  * `<ArtifactSummary />`
  * `<ArtifactIssuesPanel />`
  * `<DownloadArtifactButton />`

---

### 3.8 Config template

**What it represents**

* A **template** for bootstrapping new config packages.
* Backend templates live under `apps/ade-api/src/ade_api/templates/config_packages/`. 

**Naming**

* UI label: **Config template**
* Type: `ConfigTemplate`
* IDs: `templateId`

---

## 4. Naming conventions in the frontend

### 4.1 General principles

1. **Prefer domain words over implementation words**

   * Use **Run** instead of **Job** in UI.
   * Use **Config package** instead of “ruleset” or “profile”.
2. **Mirror backend identifiers but adapt to JS/TS style**

   * Backend JSON / URLs: `workspace_id`, `config_id`, `job_id`. 
   * TypeScript / React:

     * `workspaceId`, `configId`, `jobId` / `runId`.
3. **Single canonical name per concept**

   * Don’t mix “workspace” vs “project”, “run” vs “execution” in the same surface.

---

### 4.2 TypeScript & schema types

**Sources of truth**

* OpenAPI‑generated TS lives in `apps/ade-web/src/generated-types/openapi.d.ts`. 
* A curated module in `src/schema/` re‑exports stable shapes (e.g. `SessionEnvelope`). 

**Conventions**

* Import API types from `@schema` (never from `@generated-types/*` in app code).

* Alias noisy API names to clean domain aliases at the edge:

  ```ts
  import type { WorkspaceEnvelope, RunEnvelope } from "@schema";

  type Workspace = WorkspaceEnvelope;
  type Run = RunEnvelope;
  ```

* Use **PascalCase** for type names (`Workspace`, `ConfigPackage`, `Build`, `Run`).

* Avoid `IWorkspace` / `TWorkspace` prefixes.

---

### 4.3 IDs and relationships

**Field naming**

* Always use `<entity>Id`:

  * `workspaceId`
  * `configId`
  * `buildId`
  * `runId`
  * `documentId`
  * If you need the raw engine ID: add `jobId` instead of overloading `runId`.

**Relationship shape examples**

```ts
interface WorkspaceRef {
  workspaceId: string;
}

interface ConfigPackageRef extends WorkspaceRef {
  configId: string;
}

interface BuildRef extends ConfigPackageRef {
  buildId: string;
}

interface RunRef extends BuildRef {
  runId: string;   // UI name
  jobId: string;   // engine name (optional)
}
```

---

### 4.4 React screens, components, and hooks

**Screens**

* Place screens under `src/screens/<FeatureName>/`.
* Name the top‑level component `<FeatureName>Screen`:

  * `<WorkspacesScreen />`
  * `<ConfigPackageScreen />`
  * `<RunDetailScreen />`

**Feature components**

* Use domain nouns:

  * `<WorkspaceList />`, `<ConfigPackageList />`, `<RunTable />`
* For dialogs/modals:

  * `<CreateWorkspaceDialog />`
  * `<StartRunDialog />`

**Hooks**

* Data‑fetch hooks:

  * `useWorkspaces()`
  * `useConfigPackages(workspaceId)`
  * `useRuns(configId)`
* Mutation hooks:

  * `useCreateWorkspace()`
  * `useCreateConfigPackage()`
  * `useTriggerBuild()`
  * `useStartRun()`

**Navigation**

* Use the nav helpers from `@app/nav` (`useNavigate`, `useLocation`, `Link`, `NavLink`). 
* Route param names must match the `<entity>Id` convention:

  * `/workspaces/:workspaceId`
  * `/workspaces/:workspaceId/config-packages/:configId`
  * `/workspaces/:workspaceId/config-packages/:configId/builds/:buildId`
  * `/runs/:runId` (or nested, depending on actual router structure)

---

### 4.5 Status strings and enums

**Backend**

* Status values are plain strings (e.g. `"pending"`, `"running"`, `"succeeded"`, `"failed"`).
* Exact values are defined by the OpenAPI schema.

**Frontend**

* Represent them as string unions:

  ```ts
  type BuildStatus = "pending" | "running" | "succeeded" | "failed";
  type RunStatus = "queued" | "running" | "succeeded" | "failed";
  ```

* UI components should map status → consistent visual treatments:

  * `status="succeeded"` → success color
  * `status="failed"` → danger color

---

## 5. Putting it together (example flow)

End‑to‑end naming for a typical user flow:

1. User selects a **Workspace** (`workspaceId`).
2. They open a **Config package** (`configId`) and click **Build**.
3. The system creates/updates a **Build** for that config (`buildId`) and shows its **Build status**.
4. They **Upload document(s)** to the workspace (`documentId`).
5. From the config/build screen they click **Start run**:

   * Web sends a `jobId`‑centric request to the API.
   * UI shows a **Run** in the run list with `runId` (alias for `jobId`).
6. When the run completes, UI links to the **Artifact**:

   * “Download output workbook”
   * “View artifact details”

At each step, the same concepts and names are used in copy, code, and API contracts.