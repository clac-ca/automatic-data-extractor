# 08 – Configurations and Config Builder

This document describes how **configurations** are modelled in ADE Web and how the
**Config Builder** feature is structured around them.

It focuses on:

- The **domain model** (configuration, config version, build, manifest).
- The **configuration list** and high‑level Config Builder flows.
- How ADE Web **interacts with the backend** for configuration management.
- How configurations **connect to documents and jobs** in the rest of the UI.

Editor/workbench internals (file tree, tabs, console, Monaco) are covered in
[`09-workbench-editor-and-scripting.md`].

---

## 1. Concepts and terminology

### 1.1 Configuration

A **configuration** is a workspace‑scoped unit that represents a single Python
config package and its lifecycle in ADE.

Conceptually, a configuration answers:

> “For this workspace, what code describes how to interpret and transform a
> certain class of documents?”

Key properties:

- **Workspace‑scoped**

  - A configuration belongs to exactly one workspace.
  - Different workspaces may have configurations with the same name but are
    entirely isolated.

- **Owns versions**

  - Each configuration has many **config versions** (immutable snapshots).

- **Backed by code**

  - Each version corresponds to a concrete file tree on disk on the backend
    (`ade_config/…`, `manifest.json`, detectors, hooks, tests, etc.).

In UI code and copy:

- We use **“Config”** as the generic noun (“Config list”, “Open config”).
- We use **`Configuration`** in types that mirror backend models
  (e.g. `Configuration`, `ConfigurationVersion`).

### 1.2 Config version

A **config version** is an immutable snapshot of the configuration package:

- Represents a specific state of the config files and manifest.
- Has a **status**: `draft`, `active`, or `inactive` (see below).
- Is referenced by jobs and runs:

  - When a job runs, it records which config version it used.

Once created, a config version is treated as **read‑only** from the user’s
perspective; edits happen by creating or cloning another draft.

The backend may store versions as:

- A row in a versions table, or
- A tagged commit in a repo or object store,

…but ADE Web only depends on stable IDs and status.

### 1.3 Build

A **build** is the process of preparing an execution environment for a config
version:

- Installing dependencies.
- Validating files on disk.
- Preparing the engine environment.

In the UI, build state is surfaced mainly inside the **Config Builder workbench**
console (see doc 09). This doc treats builds as an implementation detail of
“getting a config version ready”.

### 1.4 Manifest

Each config version exposes a JSON **manifest** (typically `manifest.json`)
describing:

- Tables and columns.
- Transforms and validators.
- Metadata needed for ADE to interpret outputs.

The manifest is the structured surface that **non‑code UI** can work with:

- Reordering columns.
- Toggling `enabled` / `required`.
- Linking columns to script entrypoints.

Manifest details are in [README] and are referenced, not redefined, here.

---

## 2. Configuration lifecycle

Each workspace can have **many configurations** (e.g. per client, per pipeline).
Each configuration can have **many versions**. ADE Web presents a simple
three‑state lifecycle per version.

### 2.1 Version states

The product‑level lifecycle for a **config version** is:

- **Draft**

  - Editable, actively developed.
  - Used for build/validate/test‑run cycles.
  - Can be activated (see below).

- **Active**

  - Exactly **one version per configuration** is active at a time.
  - Used by default for “normal” runs in that workspace.
  - Read‑only in the UI.

- **Inactive**

  - Versions that were active in the past, or never activated.
  - Not used for new runs.
  - Kept for history, audit, and rollback (by cloning).

The backend may have internal states (e.g. “published”, “archived”), but ADE Web
maps everything into **Draft → Active → Inactive** for presentation.

### 2.2 Invariants

The Config Builder enforces several invariants:

- **Per configuration**:

  - At most **one `active` version**.
  - Any number of `draft` and `inactive` versions.

- **Version immutability**:

  - Once a version is marked `active` or `inactive`, its content is not edited
    directly from the UI.
  - Users clone an existing version to a **new draft** to make changes.

- **Job references**:

  - Jobs always record the specific **config version ID** they used.
  - Past jobs do not break when a new version becomes active.

### 2.3 Typical version flow

Common lifecycle flows:

1. **Initial setup**

   - Create a configuration from a template or starter skeleton.
   - This produces an initial **draft** version.

2. **Development loop**

   - Open the draft in the Config Builder workbench.
   - Edit files & manifest, run builds and validations.
   - Test against real documents with **test runs**.

3. **Activation**

   - When satisfied, activate the draft:
     - Draft → Active.
     - Previously active version → Inactive.

4. **Maintenance**

   - To evolve behaviour:
     - Clone the current active or a known‑good inactive version → new draft.
     - Repeat the development loop.
   - To roll back:
     - Activate an older inactive version.

---

## 3. Config Builder surface

The **Config Builder** is the umbrella term for:

- The **Config list/overview** screen inside a workspace.
- The **Workbench** (editor) for a specific configuration and version.

This doc focuses on the **list/overview** and high‑level flows; the workbench
itself is in doc 09.

### 3.1 Routes and layout

Config Builder lives under the workspace shell at:

- `/workspaces/:workspaceId/config-builder`

Within that section:

- The **left nav** highlights “Config Builder”.
- The main content shows:

  - A list of configurations for this workspace.
  - Controls to create, clone, export, and open configs in the workbench.
  - Optional summary cards (e.g. counts of active/inactive, recently changed).

Clicking “Open editor” or a configuration row transitions into the **workbench
view** for that configuration (same route, plus additional state via URL
search params or nested routing).

### 3.2 Responsibilities of the Config Builder section

The Config Builder section:

- **Lists configurations** with enough context to make decisions:

  - Name, description, status.
  - Current active version (id and label).
  - Whether a draft exists.
  - When it was last updated.

- **Initiates configuration flows**:

  - Create configuration from template.
  - Clone configuration or version.
  - Export configuration.
  - Activate/deactivate configuration versions.
  - Open Configuration in the workbench.

- **Coordinates with other sections**:

  - Jobs and Documents can deep‑link back into a particular configuration or file
    (e.g. “Open detector for this table”).
  - The Config Builder records a “return path” so closing the workbench
    navigates back to where the user came from.

---

## 4. Configuration list & actions

### 4.1 Configuration row model

Each row in the Config list represents a `Configuration` and typically shows:

- **Name** – human‑friendly label.
- **Identifier** – short, stable `config_id` or slug.
- **Active version** – version id and possibly semantic label (e.g. `v12`).
- **Draft presence** – whether an editable draft exists.
- **Status summary** – concise summary of overall state:

  - “Active version: v12 • Draft in progress”  
  - “No active version” (for brand‑new or retired configs)

- **Last updated** – when any version of this configuration was last changed.

Optional columns:

- Owner / maintainer.
- Associated client/pipeline tags.

### 4.2 Actions from the list

Common actions surfaced per row:

- **Open in editor**

  - Opens the workbench for this configuration.
  - Default behaviour chooses a sensible starting version (see 4.3).

- **Create draft**

  - If no draft exists:
    - Options: “From active version” or “From template” (if appropriate).
  - Creates a new `draft` version and opens it in the workbench.

- **Clone configuration**

  - Creates a new `Configuration` using an existing one as a source.
  - Useful when splitting clients/pipelines.

- **Activate configuration version**

  - Prompts to select which version to activate if multiple candidates exist.
  - Calls the backend activation endpoint and updates list state.

- **Deactivate / retire active version**

  - Optional; if supported by backend, removes `active` flag so configuration
    has no active version.

- **Export configuration**

  - Downloads a bundle (e.g. zip) of the underlying Python package and manifest.

Actions are permission‑gated based on the user’s workspace roles and safe mode
status (see doc 05).

### 4.3 Which version opens in the editor?

When the user clicks “Open editor” on a configuration, the UI chooses a starting
version:

- **If a draft exists**:

  - Open the **latest draft**; this is where active development happens.

- **Else if an active version exists**:

  - Open the **active version**, read‑only.

- **Else**:

  - Create a **new draft** from a template or empty skeleton and open that.

Users can switch versions from within the workbench if you expose a version
selector, but the initial choice should be predictable and consistent.

---

## 5. Manifest usage

The manifest is the Config Builder’s window into the **logical structure** of a
config version.

### 5.1 Manifest responsibilities

ADE Web uses the manifest to:

- Render **table and column metadata**:

  - Table names, labels, ordinals.
  - Column keys, labels, enabled/required flags.

- Link to **script entrypoints**:

  - For transforms and validators.
  - For row/column detectors.

- Provide a **stable structure** for:

  - Column reordering.
  - Enabling/disabling columns.
  - Marking fields as required/optional.

### 5.2 Safety and forward compatibility

When ADE Web edits the manifest:

- It sends **patches** rather than full documents wherever possible.
- It only modifies fields it **understands**:

  - e.g. `ordinal`, `enabled`, `required`, and script references.

- It preserves unknown fields untouched, so backend schema evolution does not
  break older UIs.

Design constraints:

- Manifest keys (`key`, `label`, `path`, etc.) should be treated as **stable
  identifiers** for UI state.
- The UI should not depend on internal, undocumented fields.

---

## 6. Version management flows

### 6.1 Creating a new configuration

From the Config list, “Create configuration” typically offers:

- **From template**:

  - Predefined starters (generic tabular, invoices, etc.) if supported.
  - Backend returns an initial draft tree.

- **Blank configuration**:

  - Minimal `ade_config` structure and manifest.
  - Good for advanced users starting from scratch.

The create call:

- Hits `/api/v1/workspaces/{workspace_id}/configurations` with template/clone
  parameters.
- Returns a new `Configuration` with an initial `draft` version.

The UI then:

- Navigates directly into the workbench for that draft.
- Optionally stores a “return path” to the Config list.

### 6.2 Editing and validating a draft

Editing happens inside the workbench (doc 09), but this doc summarises the flow:

1. User makes changes in code and manifest.
2. User runs **build** and/or **validate**:

   - Build prepares/refreshes the environment.
   - Validate runs static checks, schema validation, etc.

3. Console shows logs and results.
4. Validation issues populate the Validation panel.

From the Config list’s perspective:

- Drafts can be marked with badges like “Has validation errors” or “Last
  validated N minutes ago” for quick triage.

### 6.3 Testing against documents

From the workbench, “Run extraction”:

- Opens a dialog to select a document.
- Optionally select sheets for spreadsheet inputs.
- Starts a job using the **current draft version** as the config.

The job appears in the Jobs ledger like any other; its config version is
clearly recorded.

### 6.4 Publishing and activating

Publishing/activating a draft version is a two‑step concept, often mapped to a
single user action:

- **Publish/prepare**:

  - Ensures the draft is built and validated and considered ready.
  - May be implemented as `/configurations/{config_id}/publish`.

- **Activate**:

  - Mark this version as the active version for the configuration.
  - Backend endpoint:
    - `/workspaces/{workspace_id}/configurations/{config_id}/activate`.

In ADE Web, we typically present a single action, **“Activate version”**, which:

1. Optionally ensures a successful build/validation first.
2. Calls the activation endpoint.
3. Updates the list:

   - Old active → Inactive.
   - Draft → Active.

### 6.5 Deactivating or retiring versions

If supported:

- A configuration may be left with **no active version** by deactivating:

  - `/workspaces/{workspace_id}/configurations/{config_id}/deactivate`.

The UI should:

- Clearly show “No active version” in list and detail.
- Ensure that documents/jobs that require a config version prompt the user to
  choose an explicit version if none is active.

---

## 7. Navigation into and out of the workbench

### 7.1 Entry points

Common entry paths into the workbench:

- From Config list:

  - “Open editor” on a configuration row.

- From Documents:

  - “Edit configuration” from a document’s last‑run summary.

- From Jobs:

  - “Edit configuration” from a job detail, linking to the version used (read‑only) or to a new draft cloned from that version.

- From Settings/Overview:

  - Links to “View configuration for this workspace”.

### 7.2 Return path

To keep navigation intuitive, ADE Web tracks where the user came from:

- When navigating *into* the workbench:

  - Store the current URL in a scoped storage key, e.g.  
    `ade.ui.workspace.<workspaceId>.workbench.returnPath`.

- When closing the workbench:

  - Navigate back to `returnPath` if present.
  - Clear the stored value.

If no return path is stored:

- Default fallback is the Config list:
  - `/workspaces/:workspaceId/config-builder`.

---

## 8. Safe mode interaction

Safe mode is a system‑level or workspace‑level kill switch for engine execution.

Within Config Builder:

- When **safe mode is enabled**:

  - The Config Builder list is still visible.
  - Configuration metadata, versions, and manifest views are **read‑only**.
  - Actions that invoke the engine are **disabled**:

    - Build environment.
    - Validate configuration.
    - Test runs from the workbench.
    - Activate/publish configuration versions.

- UI behaviour:

  - A banner in the workspace shell explains that safe mode is on and includes
    the backend‑provided `detail` message.
  - Disabled buttons include tooltips like:
    > “Safe mode is enabled: <detail>”

- Permissions:

  - Only users with the appropriate permission (e.g.
    `System.Settings.ReadWrite`) see controls to toggle safe mode in Settings.

The goal is to make safe mode highly visible and to fail **proactively** at the
UI layer rather than letting engine calls error out.

---

## 9. Backend contracts for configurations

ADE Web is backend‑agnostic but assumes certain configuration‑related endpoints.

### 9.1 Configuration metadata

- `GET /api/v1/workspaces/{workspace_id}/configurations`

  - List configurations for a workspace.
  - Returns summaries used for the Config list.

- `POST /api/v1/workspaces/{workspace_id}/configurations`

  - Create a new configuration (from template or clone).

- `GET /api/v1/workspaces/{workspace_id}/configurations/{config_id}`

  - Retrieve configuration metadata and current active/draft/inactive summary.

### 9.2 Version management

- `GET /api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions`

  - List versions with status (`draft`, `active`, `inactive`).

- `POST /api/v1/workspaces/{workspace_id}/configurations/{config_id}/publish`

  - Publish a draft version (implementation‑specific).

- `POST /api/v1/workspaces/{workspace_id}/configurations/{config_id}/activate`

  - Activate a configuration version.

- `POST /api/v1/workspaces/{workspace_id}/configurations/{config_id}/deactivate`

  - Deactivate the active configuration (if supported).

### 9.3 Files, directories, and manifest

- `GET /api/v1/workspaces/{workspace_id}/configurations/{config_id}/files`

  - Flat listing of editable files and directories.
  - Used to build the workbench file tree.

- `GET /api/v1/workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}`

  - Read a file, with metadata (`size`, `mtime`, `content_type`, `etag`).

- `PUT /api/v1/workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}`

  - Upsert a file; uses ETag to protect against concurrent edits.

- `PATCH /api/v1/workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}`

  - Rename or move a file.

- `DELETE /api/v1/workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}`

  - Delete a file.

- `POST /api/v1/workspaces/{workspace_id}/configurations/{config_id}/directories/{directory_path}`

  - Create a directory.

- `DELETE /api/v1/workspaces/{workspace_id}/configurations/{config_id}/directories/{directory_path}`

  - Delete a directory.

- `GET /api/v1/workspaces/{workspace_id}/configurations/{config_id}/export`

  - Export configuration package (e.g. zip).

### 9.4 Validation and builds

- `POST /api/v1/workspaces/{workspace_id}/configurations/{config_id}/validate`

  - Validate the configuration on disk.
  - Returns structured validation issues for the workbench.

- `POST /api/v1/workspaces/{workspace_id}/configs/{config_id}/builds`

  - Trigger an environment build for the configuration.
  - Used by the workbench build controls.

- `GET /api/v1/builds/{build_id}` and `/builds/{build_id}/logs`

  - Read build outcome and stream build logs.

Details of how these endpoints are wrapped into hooks and how logs are streamed
are in doc 04 (data layer) and doc 09 (workbench console).

---

## 10. Design constraints and principles

To keep Config Builder predictable and maintainable:

- **Backend is the source of truth**

  - ADE Web does not infer lifecycles; it reads version status and only exposes
    actions that make sense.

- **No editing of active/inactive versions**

  - Users always work in a draft; the UI enforces this workflow.

- **Config versions are explicit**

  - Jobs record version IDs; Config Builder never mutates the version a job
    already used.

- **Manifest edits are conservative**

  - UI modifies only well‑understood fields, preserving unknown data.

- **Navigation should feel reversible**

  - Workbench entry/exit always leads back to where the user came from, or to
    the Config list as a safe default.

With these constraints, the Config Builder remains easy to understand, easy to
extend, and safe to use across different backend implementations.