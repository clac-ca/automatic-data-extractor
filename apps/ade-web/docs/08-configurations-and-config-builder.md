# 08 – Configurations and Configuration Builder

This document explains how **configurations** work in ADE Web and how the
**Configuration Builder** section is structured.

It focuses on:

- The **Configuration** domain model and version lifecycle.
- The **Configurations** workspace section (Configuration Builder)  
  (`/workspaces/:workspaceId/config-builder`).
- How configuration metadata (including the manifest) flows between frontend and
  backend.
- How environment readiness (auto builds), validation runs, and test runs are
  represented in the UI.
- How we enter and exit the **Configuration Builder workbench** (the editing surface
  described in `09-workbench-editor-and-scripting.md`).

Definitions for terms like *Configuration*, *Config version*, *Draft*, *Active*,
*Inactive*, and *Run* are established in
`01-domain-model-and-naming.md`. This doc assumes that vocabulary.

Naming: the **Configuration Builder** is the workspace section that lists configurations and launches editing. The **Configuration Builder workbench** is the dedicated window for editing a single configuration version. Use “Configuration Builder workbench” on first mention and “workbench” afterwards; use “editor” only for the Monaco instance inside that window.

---

## 1. Scope and mental model

From ADE Web’s perspective:

- A **Configuration** is a *workspace‑scoped* unit backed by a **configuration
  package** (Python package + manifest + supporting files).
- Each Configuration has **multiple versions** over time (drafts and immutable
  snapshots).
- The **Configurations** section (home of the Configuration Builder) is where users:
  - View and manage configurations for a workspace.
  - Inspect version history and status.
  - Open a specific configuration version in the **workbench** to edit code,
    ensure the environment is ready (auto rebuild when needed), run validation runs, and perform test runs.

Backend implementations may have more nuanced state machines, but ADE Web
presents a **simple, stable model**:

- Configuration (high‑level object)
- Configuration version (Draft / Active / Inactive)

Runs themselves are described in `07-documents-and-runs.md`. This doc focuses
on how configurations feed into those runs.

---

## 2. Configuration domain model

### 2.1 Configuration

A **Configuration** is the primary row in the Configuration Builder list.

Conceptually:

- **Scope**
  - Belongs to exactly one workspace.
- **Identity**
  - `id: string` – stable identifier.
  - `name: string` – human‑friendly display name.
- **Metadata**
  - `description?: string` – optional description for humans.
- **Version summary**
  - A pointer to an **active** version (if any).
  - Counts of versions and drafts.
  - Timestamps for last relevant change.

Example conceptual shape:

```ts
interface ConfigurationSummary {
  id: string;
  name: string;
  description?: string | null;

  // Active configuration version, if any
  activeVersion?: ConfigurationVersionSummary | null;

  // Aggregated metadata
  totalVersions: number;
  draftVersions: number;
  lastUpdatedAt?: string | null;
}
````

Wire types may include additional backend‑specific fields; this is the
frontend’s mental model.

### 2.2 Configuration versions

Each Configuration has many **configuration versions**. A configuration version is treated as
an immutable snapshot.

Key properties:

* **Identity**

  * `id: string` – version id.
  * `label: string` – human‑friendly label (e.g. `v4 – Q1 tweaks`).
* **Lifecycle**

  * `status: "draft" | "active" | "inactive"`.
* **Environment & validation health**

  * `lastBuildStatus?: "ok" | "error" | "pending" | "unknown"`.
  * `lastBuildAt?: string | null`.
  * `lastValidationStatus?: "ok" | "error" | "pending" | "unknown"`.
  * `lastValidationAt?: string | null`.
* **Provenance**

  * `createdAt: string`.
  * `createdBy: string`.
  * `derivedFromVersionId?: string` (if cloned).

Example conceptual interface:

```ts
type ConfigurationVersionStatus = "draft" | "active" | "inactive";

interface ConfigurationVersionSummary {
  id: string;
  label: string;
  status: ConfigurationVersionStatus;

  createdAt: string;
  createdBy: string;

  lastBuildStatus?: "ok" | "error" | "pending" | "unknown";
  lastBuildAt?: string | null;

  lastValidationStatus?: "ok" | "error" | "pending" | "unknown";
  lastValidationAt?: string | null;
}
```

Runs record the **configuration version id** they used, so historical runs are always
traceable to the code that produced them.

---

## 3. Version lifecycle

### 3.1 Lifecycle states

At the ADE Web level, every configuration version is presented as one of:

* **Draft**

  * Editable.
  * Used for development, validation runs, and test runs; environment rebuild happens automatically when those runs start.
* **Active**

  * Exactly **one** active version per Configuration.
  * Read‑only in the UI (no direct edits to files).
  * Used as the default version for “normal” runs that reference this
    Configuration.
* **Inactive**

  * Older or superseded versions.
  * Not used by default for new runs.
  * Kept for audit, comparison, and cloning.

Backend‑specific states (e.g. `published`, `archived`) are normalised into one
of these three for display.

### 3.2 Allowed transitions

From the **UI’s perspective**, we support:

* **Draft → Active**

  * User activates a draft version.
  * That version becomes **Active**.
  * The previous active version (if any) becomes **Inactive**.

* **Active → Inactive**

  * User deactivates the active version, leaving the Configuration with no
    active version (if the backend supports this).

* **Any → Draft (via clone)**

  * User clones any existing version (Active or Inactive).
  * The clone is a new **Draft** version.

We avoid arbitrary state jumps; to “revive” an inactive version, users clone it
into a new draft and then activate that draft.

### 3.3 Configuration vs workspace defaults

A few important invariants:

* **Per Configuration**, at most one active version.
* A workspace may have many Configurations, each with its own active version.
* When creating a **run**:

  * From the **Documents** screen, the UI selects a Configuration + version
    (typically the active version of the chosen Configuration).
  * From the **Configuration Builder workbench**, the run is tied to the version that
    workbench is editing (often a draft), unless explicitly overridden.

Any workspace‑level “default configuration for new runs” is an additional layer
on top of this model and should be described separately if introduced.

---

## 4. Configurations section architecture (Configuration Builder)

The Configurations section (home of the Configuration Builder) is the workspace‑local section at:

```text
/workspaces/:workspaceId/config-builder
```

It has two main responsibilities:

1. **Configuration list / overview**
   Show all configurations in the workspace, with high‑level status.
2. **Workbench launcher**
   Provide clear entry points into the workbench for a particular Configuration +
   version.

High‑level behaviour:

* On load, we fetch the configurations list for the current workspace.
* Users can:

  * Create new configurations.
  * Clone existing configurations.
  * Inspect version summaries.
  * Export configurations.
  * Open a configuration version in the workbench.

Safe mode and permissions determine which actions are enabled (see §9).

---

## 5. Configuration list UI

### 5.1 Columns and content

Each row represents a Configuration. Typical columns:

* **Name** – display name.
* **Active version** – label for the active version or “None”.
* **Drafts** – count of draft versions.
* **Last updated** – when any version was last changed (creation, build, or
  validation).
* **Health** (optional) – a compact “Build / Validation” indicator.
* **Actions** – inline buttons or a context menu.

Empty states:

* No configurations + user can create → short explanation of what a
  configuration is + a “Create configuration” button.
* No configurations + user cannot create → read‑only explanation and guidance to
  contact an admin.

### 5.2 Actions from the list

Per Configuration, we surface:

* **Open in workbench**

  * Opens the workbench on a reasonable starting version (see §5.3).
* **View versions**

  * Opens a panel or detail view listing all configuration versions.
* **Create draft**

  * Create a new draft version from:

    * The active version (default), or
    * A chosen version (if user selects one).
* **Clone configuration**

  * Create a new Configuration, seeded from this one.
* **Export**

  * Download an export of the backing configuration package.
* **Activate / Deactivate**

  * Promote a draft to Active or deactivate the currently active version.

All of these actions are permission‑gated and safe‑mode‑aware.

### 5.3 Which version opens in the workbench?

When a user clicks **Open in workbench**:

* If there is at least one **draft**:

  * Open the **latest draft** (most recently created).
* Else if there is an **active** version:

  * Open the active version in read‑only mode.
* Else:

  * Create a **new draft** (from template or empty skeleton) and open that.

Users can switch versions inside the workbench (if a version selector is
available), but the initial choice must be consistent and unsurprising.

---

## 6. Version management UI

When a user drills into a Configuration, we show its **versions** explicitly.

### 6.1 Versions view

The versions list can be presented as:

* A **side drawer** attached to the Configuration row, or
* A dedicated **detail view** (`ConfigDetailPanel`) for that Configuration.

Each version row shows:

* Label.
* Status (`Draft`, `Active`, `Inactive`).
* `createdAt` / `createdBy`.
* Last build status and timestamp.
* Last validation status and timestamp.
* Optional “derived from” information.

### 6.2 Version‑level actions

Allowed actions depend on status:

* **Draft**

  * Open in workbench (for code editing).
  * Start validation/test runs (environment rebuild is handled automatically when those runs start; the workbench “Force build and test” option sets `force_rebuild`).
  * Activate (if permitted and Safe mode is off).
  * Delete (if supported by backend and no runs depend on it).

* **Active**

  * Open in workbench (read‑only).
  * Clone into draft.
  * Deactivate (optional, if backend supports “no active version”).

* **Inactive**

  * Open in workbench (read‑only).
  * Clone into draft.

The versions view should make it obvious which version is currently active and
encourage “clone → edit → activate” as the main flow rather than direct edits.

### 6.3 Normalisation of backend states

Backends might expose states like `published`, `deprecated`, `archived`, etc.

We centralise a normalisation function, e.g.:

```ts
function normalizeConfigurationVersionStatus(
  raw: BackendVersionStatus,
): ConfigurationVersionStatus;
```

All views (Config list, versions drawer, workbench chrome) use this normalised
status, so the UI can evolve independently of backend nomenclature.

---

## 7. Manifest and schema integration

Each configuration version exposes a **manifest** (`manifest.json`) describing:

* Output tables and their schemas.
* Column metadata (keys, labels, ordinals, required/enabled).
* Links to transforms, validators, and detectors.

### 7.1 Discovering the manifest

The manifest is treated as just another file in the configuration file tree:

* Backend file listing includes `manifest.json`.
* The workbench’s file loading APIs fetch it like any other file.

The details of file listing and workbench integration are described in
`09-workbench-editor-and-scripting.md`. This section describes **how we use**
manifest data at the Configuration Builder level.

### 7.2 Manifest‑driven UI

ADE Web uses the manifest to:

* Render a **schema view** (if implemented):

  * Per‑table summary.
  * Per‑column fields: `key`, `label`, `required`, `enabled`, `depends_on`.

* Drive **column ordering**:

  * Sort columns by `ordinal` when rendering sample data or schema previews.

* Attach **script affordances**:

  * For example, show “Edit transform” or “Edit validator” buttons for entries
    that reference specific script paths.

* Improve **validation UI**:

  * Map validation messages to table/column paths from the manifest.

The schema view is intentionally **read‑focused** by default; any editing
capabilities (e.g. reordering columns or toggling `enabled`) must preserve
unknown manifest fields.

### 7.3 Patch model and stability

Manifest updates must be conservative:

* ADE Web should **not** rewrite `manifest.json` wholesale.

* Instead, it should:

  1. Read the manifest as JSON.
  2. Apply a narrow patch (e.g. update a column’s `enabled` flag).
  3. Send the updated document back (or call a dedicated “update manifest”
     API).

* Unknown keys and sections must be preserved.

This makes the Configuration Builder resilient to backend schema evolution.

---

## 8. Validation and test runs (environment auto-build)

Configuration Builder assumes **one environment per configuration**, rebuilt **automatically** when needed. There is no standalone “Build environment” control or shortcut; environment readiness is handled during run startup.

Two run modes are exposed:

1. **Validation run** – execute validators only to check configuration correctness (no full extraction). Implemented as a `Run` with `RunOptions.validateOnly: true` and usually `mode: "validation"`.
2. **Test run** – execute ADE on a sample document with the chosen configuration version, streaming logs into the workbench. Often sets `mode: "test"` and may use `dryRun: true`.

Run creation uses the canonical `RunOptions` shape (see `07-documents-and-runs.md`) in camelCase and converts those to backend snake_case fields (`dry_run`, `validate_only`, `force_rebuild`, `input_sheet_names`). When the user picks **Force build and test** in the Test split button, the frontend also sends `force_rebuild: true` (`RunOptions.forceRebuild`); otherwise the backend auto‑rebuilds when the environment is missing, stale, or built from outdated content and reuses it when clean.

### 8.1 Validation runs

Goal:

> Check that the configuration on disk is consistent without running a full
> extraction.

Behaviour:

* Triggered via a “Validation run” action in workbench controls.

* Frontend calls something like:

  ```http
  POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/validate
  ```

* Backend may stream logs; ADE Web treats this as a `Run`:

  * Writes textual logs to the console.
  * Populates the **Validation** panel with structured issues (severity,
    location, message).
  * Sends run options with `validate_only: true` (and optionally `mode:
    "validation"` in UI state).

* `lastValidationStatus` / `lastValidationAt` are updated for the version.

In Configuration Builder overview, these statuses can be summarised as simple badges
(“Validation OK”, “Validation failed”, etc.).

### 8.2 Test runs (run extraction from builder)

Goal:

> Execute ADE on a sample document using a particular configuration version,
> while seeing logs and summary in the workbench.

Behaviour:

1. User clicks the **Test** split button in the workbench (primary) or selects **Force build and test** from its dropdown.

2. A **Test run dialog** appears where they:

   * Choose a document (e.g. from recent workspace documents).
   * Optionally limit worksheets (for spreadsheets).

3. Frontend creates a run via the backend’s run creation endpoint:

   * This may be a configuration‑scoped route (e.g.
     `/configurations/{configuration_id}/runs`) or a workspace‑scoped route that accepts
     `config_version_id`. Payload uses `RunOptions` (camelCase → snake_case), can set
     `mode: "test"` for clarity, and includes `force_rebuild: true` only when the dropdown
     option was chosen; otherwise the backend can reuse or auto‑rebuild if dirty.

4. Workbench subscribes to the run’s event/log stream:

   * Console updates live as the run progresses.
   * A **Run summary** card appears at the end, with:

     * Run ID and status.
     * Document name.
     * Output file links and telemetry.

5. The run also appears in the global **Runs** history view (see
   `07-documents-and-runs.md`), which may still be backed by `/runs` endpoints
   server‑side.

Event schema reference for the streamed console: `apps/ade-web/docs/04-data-layer-and-backend-contracts.md` §6 and `apps/ade-engine/docs/11-ade-event-model.md`.

---

## 9. Safe mode and permissions

Configuration Builder is tightly integrated with **Safe mode** and **RBAC** (see
`05-auth-session-rbac-and-safe-mode.md`).

### 9.1 Safe mode

When Safe mode is **enabled**:

* The following actions are **blocked**:

  * Environment rebuilds (including auto-builds triggered at run start).
  * Validation runs (configuration validation).
  * Test runs (“Run extraction”).
  * Activate/publish configuration versions.

* The following remain available:

  * Viewing configurations, versions, manifest, and schema views.
  * Exporting configurations.
  * Viewing historical logs and validation results.

UI behaviour:

* The workspace shell shows a **Safe mode banner** with the backend‑provided
  `detail` message.
* Buttons for blocked actions are disabled and show a tooltip, e.g.:

  > “Safe mode is enabled: <detail>”

Configuration Builder does **not** attempt to perform these actions and then interpret
 errors; it reads Safe mode state and proactively disables them.

### 9.2 Permissions

Configuration operations are governed by workspace permissions, for example:

* `Workspace.Configurations.Read`
* `Workspace.Configurations.ReadWrite`
* `Workspace.Configurations.Activate`

Patterns:

* **View list / versions** → `Read`.
* **Create / clone configuration** → `ReadWrite`.
* **Edit files / rebuild (via run start) / validate / test run** → `ReadWrite` and Safe mode off.
* **Activate / deactivate version** → `Activate`.

Helpers in `shared/permissions` are used to:

* Decide which actions to show.
* Decide which actions are disabled with a tooltip vs hidden entirely.

---

## 10. Backend contracts (summary)

This section maps the conceptual model to backend routes. Names may evolve; keep
this in sync with the actual OpenAPI spec.

### 10.1 Configuration metadata

Under a workspace:

```http
GET  /api/v1/workspaces/{workspace_id}/configurations
POST /api/v1/workspaces/{workspace_id}/configurations

GET  /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}
GET  /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/export
```

* `GET /configurations` → list configurations for the workspace.
* `POST /configurations` → create new configuration (optionally from a template
  or existing configuration).
* `GET /configurations/{configuration_id}` → configuration detail.
* `GET /configurations/{configuration_id}/export` → export the backing configuration package.

### 10.2 Version lifecycle

```http
GET  /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/versions
POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/publish
POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/activate
POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/deactivate
```

* `GET /versions` → list all versions for a Configuration.
* `POST /publish` → (if present) mark a draft as “published” internally.
* `POST /activate` → mark version as active.
* `POST /deactivate` → clear active status (if supported).

Frontend responsibilities:

* Treat these endpoints as **actions** (no hand‑built state machine).
* Refresh Configuration + versions after each call.
* Apply `normalizeConfigurationVersionStatus` to map backend state into
  `draft/active/inactive`.

### 10.3 Files, manifest, and directories

File and directory operations:

```http
GET    /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files
GET    /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}
PUT    /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}
PATCH  /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}
DELETE /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}

POST   /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/directories/{directory_path}
DELETE /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/directories/{directory_path}
```

These underpin:

* The workbench file tree.
* Code editing (open/save).
* Manifest reads and writes.

Manifest is treated as `manifest.json` in the file tree unless a dedicated API
is introduced.

### 10.4 Build and validate

Build endpoints (kept for admin/backfill and specialised flows; normal workbench/test flows rely on run creation with auto rebuilds and `force_rebuild`):

```http
POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds
GET  /api/v1/builds/{build_id}
GET  /api/v1/runs/{run_id}/events?stream=true&after_sequence=<cursor>   # SSE (build + run + console.line)
```

Validation endpoint:

```http
POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/validate
```

Frontend wraps these in domain‑specific hooks, e.g.:

* `useTriggerConfigBuild`
* `useValidateConfiguration`

Day‑to‑day workbench usage typically skips the build hooks and instead starts a run with `force_rebuild` when a rebuild is required; the backend also rebuilds automatically when environments are missing or stale. Use the run event stream to observe build + run logs (`console.line`) and lifecycle.

Streaming details and React Query integration are described in
`04-data-layer-and-backend-contracts.md` and `09-workbench-editor-and-scripting.md`.

---

## 11. End‑to‑end flows

This section ties everything together in concrete scenarios.

### 11.1 Create and roll out a new configuration

1. User opens the **Configurations** section / Configuration Builder (`/workspaces/:workspaceId/config-builder`).
2. Clicks **Create configuration**.
3. Fills in name and optional template.
4. Frontend calls `POST /configurations`.
5. Backend returns a Configuration with an initial **draft** version.
6. UI opens the workbench on that draft.
7. User edits files, runs **validation** and **test** flows against sample documents; environment rebuild happens automatically at run start (use **Force build and test** if a rebuild is needed explicitly).
8. When ready, user clicks **Activate** on the draft version.
9. The new version becomes **Active**; it becomes the default for new runs
   using this Configuration.

### 11.2 Evolve an existing configuration safely

1. From the Configuration Builder list, user selects an existing Configuration.
2. In the versions view, user **clones** the current active version → new
   **draft**.
3. Workbench opens on the draft.
4. User makes changes, runs **validation runs**, and test‑runs against sample documents. Environment rebuild is handled automatically on run start; the **Force build and test** option can request a rebuild explicitly.
5. When satisfied, user **activates** this draft.
6. The previously active version becomes **Inactive**.
7. The next runs referencing this Configuration use the new active version,
   while historical runs remain tied to the old version.

### 11.3 Debug a run and patch configuration

1. A run fails or produces unexpected results (seen in the **Runs** history
   view).

2. From the run detail, the user follows a link to **view the configuration and
   version** used for that run.

3. ADE Web opens the workbench on that version:

   * If it is a draft or inactive → read‑only.
   * User can **clone** it into a new draft to make changes.

4. User edits, validates, and test‑runs against similar documents.

5. Once fixed, user activates the new version.

6. Future runs use the corrected configuration; the problematic run remains
   traceable to the original version.

---

This document provides the architectural and UX model for **Configurations** and
the **Configuration Builder** in ADE Web: how configurations and their versions are
structured, how users interact with them, how they map to backend APIs, and how
they feed into runs across the rest of the app.
