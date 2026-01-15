# ADE Web — Domain model & naming

This doc is the **source of truth for names** in ADE Web.

It defines:

* Core entities (workspace, configuration, environment, run, document, outputs/telemetry)
* What we call them in UI text, TypeScript types, routes, and local storage keys

If this doc, the routes, and the feature folders stay in sync, the codebase is much easier to navigate.

---

## 0. Quick naming checklist

When you add or touch code, copy, or routes, keep these aligned:

**Entities & IDs**

* **Workspace** – UI: *Workspace* – field: `workspaceId`
* **Configuration** – UI: *Configuration* – field: `configurationId`
* **Configuration package** – the **Python project backing a Configuration** (not a UI entity)
* **Environment** – UI: *Environment* – field: `environmentId`
* **Run** – UI: *Run* – field: `runId`
* **Document** – UI: *Document* – field: `documentId`
* **Config template** – built into `ade-engine config init`; not exposed as an API resource

**Routes**

* Workspace shell entry: `/workspaces`
* Workspace sections: `/workspaces/:workspaceId/{documents|runs|config-builder|settings}`

**Feature folders**

```text
pages/Workspace/sections/
  Documents
  Runs
  ConfigBuilder
  Settings
```

**API modules**

* `workspacesApi`
* `configurationsApi`
* `documentsApi`
* `runsApi`

**Local storage prefix**

* `ade.ui.workspace.<workspaceId>…`

### Configuration Builder naming rule (important)

Keep these three in lockstep:

* **Nav label**: `Configuration Builder`
* **Route segment**: `/config-builder`
* **Folder**: `pages/Workspace/sections/ConfigBuilder`

---

## 1. Big picture: ADE Web domain

At a high level:

1. A **Workspace** is the top-level container for a team/tenant.
2. Inside a workspace, users define **Configurations** that describe how ADE processes documents.
3. The worker provisions **Environments** (virtualenvs) keyed by configuration + dependency digest.
4. Users upload **Documents** (Excel/CSV) to the workspace.
5. Users start **Runs** that execute a configuration against one or more documents, producing outputs and telemetry.

Conceptually:

```text
Workspace
 ├─ Configurations (backed by configuration packages)
 │    ├─ Environments (cached venvs per deps_digest)
 │    │    └─ Runs
 │    │         ├─ Input documents
 │    │         └─ Outputs (output.xlsx) + telemetry (events.ndjson)
 └─ Shared documents
```

---

## 3. Core entities (reference table)

### 3.1 Summary table

| Concept               | UI label      | TS type name           | Typical ID field(s)              | Storage / backend hints                                  |
| --------------------- | ------------- | ---------------------- | -------------------------------- | -------------------------------------------------------- |
| Workspace             | Workspace     | `Workspace`            | `workspaceId`                    | `workspaces/<workspace_id>/…`                            |
| Configuration         | Configuration | `Configuration`        | `configurationId`, `workspaceId` | `config_packages/<configuration_id>/…`                   |
| Configuration package | *(no label)*  | n/a (Python project)   | same as `configurationId`        | `config_packages/<configuration_id>/…`                   |
| Environment           | Environment   | `Environment`          | `environmentId`, `configurationId` | `venvs/<workspace>/<config>/<deps>/<env>/.venv`       |
| Run                   | Run           | `Run`                  | `runId`                          | `runs/<run_id>/…`                                        |
| Document              | Document      | `Document`             | `documentId`, `workspaceId`      | `documents/<document_id>.<ext>`                          |

> OpenAPI-generated types live under `@schema`. In app code we alias them to clean domain names instead of using the raw generated names everywhere.

---

## 4. Entity details

### 4.1 Workspace

* Top-level container and isolation boundary.
* Owns configurations, runs, documents, and runtime state.

### 4.2 Configuration & configuration package

* User-facing concept that defines ADE behavior.
* Backed by an installable Python `ade_config` package stored on disk.
* Lifecycle: **Draft → Active → Archived**.

### 3.4 Environment

* Worker-owned execution cache for a configuration + dependency digest.
* Provisioned automatically when runs start; not a user action.
* Status: `queued` → `building` → `ready` (or `failed`).

### 4.4 Run

* User-visible execution of a configuration against a document.
* Status: `queued` → `running` → `succeeded` / `failed`.

### 4.5 Document

* Immutable input file uploaded into a workspace.
* No top-level status; run state is exposed via `lastRun.phase` (`queued`, `building`, `running`, `succeeded`, `failed`) with optional `lastRun.phaseReason` when `phase=building`.
* `lastSuccessfulRun` points at the latest successful output when available.
