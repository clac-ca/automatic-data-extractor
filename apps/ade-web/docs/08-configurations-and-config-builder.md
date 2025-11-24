# 08-configurations-and-config-builder

**Purpose:** Conceptual model for configurations and the non-editor parts of the Config Builder.

### 1. Overview

* What a configuration is (workspace-scoped config package).
* Relationship to underlying Python package and engine.

### 2. Configurations domain model

* Fields (id, name, display name, status, active version).
* Relationship with config versions (each config has multiple versions).

### 3. Config version lifecycle

* States: Draft, Active, Inactive (per doc 01).

* Actions and mappings:

  * Create/clone → new draft.
  * Validate/build draft.
  * Publish/activate → becomes active, previous active becomes inactive.
  * Deactivate/archive (if supported).

* How backend routes map:

  * `/configurations/{config_id}/publish`, `/activate`, `/deactivate`.
  * `/configurations/{config_id}/versions`.

### 4. Configurations list UI

* Columns:

  * Name, id, active version, draft state, last updated.

* Actions:

  * Open editor (workbench).
  * Clone from existing version.
  * Export configuration.
  * Activate/deactivate/publish.

* Filters/search on configs.

### 5. Manifest overview

* What the manifest describes:

  * Tables, columns, transforms, validators, options.

* How ADE Web uses it:

  * For display, column ordering, toggles for `enabled`, `required`.
  * To wire scripts (transforms, validators) via manifest references.

* Patch model:

  * ADE Web sends partial updates.
  * Rule: preserve unknown fields for forward compatibility.

### 6. Entering and exiting the workbench

* Routes & navigation:

  * How we navigate from `/config-builder` list to the workbench (e.g. query param with `configId` or deeper route).

* Return path:

  * Storage key: `ade.ui.workspace.<workspaceId>.workbench.returnPath`.
  * How we store the path before entering and restore on exit.

### 7. Safe mode interaction

* Which actions are disabled in safe mode:

  * Build, validate, publish/activate, run extraction from builder.

* Visual feedback:

  * Disabled build/run buttons and tooltip copy.
  * Cross-link to doc 05.

### 8. Backend contracts for configurations

* Key endpoints:

  * Listing configs: `/workspaces/{workspace_id}/configurations`.
  * Detail: `/configurations/{config_id}`.
  * Versions: `/configurations/{config_id}/versions`.
  * Export: `/configurations/{config_id}/export`.
  * Validate: `/configurations/{config_id}/validate`.

* How these map to hooks: `useConfigurationsQuery`, `useConfigVersionsQuery`, etc.
