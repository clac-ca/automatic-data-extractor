# 110-BACKEND-API.md  
**ADE Web – Backend API Surface & Frontend Integration**

---

## 0. Status & Purpose

This document describes the **backend API surface** relevant to `apps/ade-web` and how the frontend should integrate with it.

It covers:

- The main API domains (auth, workspaces, configs, documents, runs, roles).
- How routes map to frontend features (Documents, Config Builder, Run Detail, Workspace).
- How we use the **generated OpenAPI types** (no hand-rolled API types in the frontend).
- Conventions for organizing API calls in the new app.

This spec complements:

- Architecture: `020-ARCHITECTURE.md`
- UX flows: `030-UX-FLOWS.md`
- Run streaming: `050-RUN-STREAMING-SPEC.md`
- Navigation: `060-NAVIGATION.md`

---

## 1. OpenAPI & Type Usage

### 1.1 Source of truth

The backend’s OpenAPI schema is compiled into a TypeScript declaration file:

- Current path:  
  `apps/ade-web/src/generated-types/openapi.d.ts`

This file defines:

- Request/response shapes (`paths[...]`).
- Shared schemas (`components["schemas"][...]`).

> **Rule:**  
> **Do not** redefine API response/request types manually in the frontend.  
> Use the generated OpenAPI types as the canonical source of truth and only add **view-model wrappers** where necessary.

### 1.2 Using the types

Pattern (pseudo-code):

```ts
import type { paths, components } from '@/generated-types/openapi';

type Workspace = components['schemas']['Workspace'];
type ListWorkspacesResponse =
  paths['/api/v1/workspaces']['get']['responses'][200]['content']['application/json'];

type ListDocumentsResponse =
  paths['/api/v1/workspaces/{workspace_id}/documents']['get']['responses'][200]['content']['application/json'];
````

We’ll likely re-export curated types via `src/schema/index.ts`:

```ts
// schema/index.ts
export type { paths, components } from '@/generated-types/openapi';
// plus any narrow view models
```

> **Guideline:**
> Frontend “feature API” modules (e.g. `features/documents/api/documentsApi.ts`) should:
>
> * Use the generated OpenAPI types for request/response shapes.
> * Convert to lightweight view models only at the boundary (if needed for UI ergonomics).

---

## 2. API Domains Overview

The backend routes fall into a few major domains:

1. **Auth & bootstrap**
2. **System & health**
3. **Workspaces & membership**
4. **Configurations & config files**
5. **Documents & sheets**
6. **Runs, logs, events & outputs**
7. **Roles & permissions**

Below we group the routes and describe how `ade-web` should use them.

> **Note:**
> In the route paths below, path parameters like `{workspace_id}` and `{configuration_id}` are placeholders and will be supplied by the frontend.

---

## 3. Auth & Bootstrap

These endpoints handle login, sessions, and initial setup.

### 3.1 Auth & Sessions

* `GET /api/v1/auth/api-keys`
  List issued API keys (admin/user management UI – not required for v1 of ade-web UI, unless we build an API-key management screen).

* `POST /api/v1/auth/api-keys`
  Issue new API key.

* `DELETE /api/v1/auth/api-keys/{api_key_id}`
  Revoke an API key.

* `GET /api/v1/auth/me`
  Return authenticated user profile.

* `GET /api/v1/auth/providers`
  List configured auth providers (useful for login screen if we differentiate SSO vs password login).

* `GET /api/v1/auth/session`
  Read active session profile.

* `POST /api/v1/auth/session`
  Create a browser session with email/password.

* `DELETE /api/v1/auth/session`
  Terminate active session (logout).

* `POST /api/v1/auth/session/refresh`
  Refresh session token (used by auth client / interceptor).

* `GET /api/v1/auth/sso/login`
  Initiate SSO login flow (redirect).

* `GET /api/v1/auth/sso/callback`
  Handle SSO callback.

### 3.2 Bootstrap & Setup

* `GET /api/v1/bootstrap`
  Bootstrap session, permissions, workspaces, safe-mode status.
  **Frontend usage:**

  * Called during app boot to get:

    * current user
    * workspace list (or default workspace)
    * safe-mode flag

* `GET /api/v1/setup/status`
  Whether initial admin setup is required.

* `POST /api/v1/setup`
  Create first admin account.

**Frontend plan:**

* Implement `authApi` and/or `sessionApi` wrappers that:

  * Expose `readBootstrap()`, `readSession()`, `createSession()`, `deleteSession()`.
  * Use them from `AuthProvider` and `AppShell` on startup.
* For v1 of ade-web, deep auth/admin UIs (API-key management, global roles) can be considered **out-of-scope** unless we explicitly create admin screens.

---

## 4. System & Health

* `GET /api/v1/health`
  Liveness/health check; primarily used by infrastructure.

* `GET /api/v1/system/safe-mode`
  Read ADE safe mode status.

* `PUT /api/v1/system/safe-mode`
  Toggle safe mode (admin).

**Frontend plan:**

* `healthApi` used only for diagnostics or dev tools, if desired.
* `systemSettingsApi` used by:

  * Bootstrap flow (safe-mode indicates feature restrictions).
  * Potential admin screen (future).

---

## 5. Workspaces & Membership

Workspace endpoints (multi-tenant & permissions context):

### 5.1 Workspace CRUD

* `GET /api/v1/workspaces`
  List workspaces for the authenticated user.

* `POST /api/v1/workspaces`
  Create a new workspace.

* `GET /api/v1/workspaces/{workspace_id}`
  Retrieve workspace context.

* `PATCH /api/v1/workspaces/{workspace_id}`
  Update workspace metadata.

* `DELETE /api/v1/workspaces/{workspace_id}`
  Delete workspace.

* `POST /api/v1/workspaces/{workspace_id}/default`
  Mark a workspace as the caller’s default.

### 5.2 Workspace Members & Roles

* `GET /api/v1/workspaces/{workspace_id}/members`
  List members within the workspace.

* `POST /api/v1/workspaces/{workspace_id}/members`
  Add a member.

* `DELETE /api/v1/workspaces/{workspace_id}/members/{membership_id}`
  Remove a member.

* `PUT /api/v1/workspaces/{workspace_id}/members/{membership_id}/roles`
  Replace the set of roles for a workspace member.

* `GET /api/v1/workspaces/{workspace_id}/roles`
  List roles available in workspace.

* `POST /api/v1/workspaces/{workspace_id}/roles`
  Create workspace role.

* `PUT /api/v1/workspaces/{workspace_id}/roles/{role_id}`
  Update workspace role.

* `DELETE /api/v1/workspaces/{workspace_id}/roles/{role_id}`
  Delete workspace role.

* `GET /api/v1/workspaces/{workspace_id}/role-assignments`
  List workspace role assignments.

* `POST /api/v1/workspaces/{workspace_id}/role-assignments`
  Assign a workspace role.

* `DELETE /api/v1/workspaces/{workspace_id}/role-assignments/{assignment_id}`
  Delete a workspace role assignment.

### 5.3 Workspace Runs

* `GET /api/v1/workspaces/{workspace_id}/runs`
  List workspace runs (for workspace-level run history).

**Frontend plan:**

* For **this workpackage**:

  * Assume a single, active `workspaceId` (provided by route/bootstrap; workspace selector UX is deferred to `090-FUTURE-WORKSPACES.md`).
  * Implement minimal workspace fetching in a `workspaceApi` module (e.g., `listWorkspaces()`, `getWorkspace()`, `setDefaultWorkspace()`).
  * Only basic membership/role information as needed for:

    * Displaying membership info (optional).
    * Authorizing actions (e.g., only admins can toggle safe-mode).
* Workspace management screens (creation, membership, roles) are **future work**.

---

## 6. Configurations & Config Files

These endpoints drive the **Config Builder**.

### 6.1 Configuration Listing & Metadata

* `GET /api/v1/workspaces/{workspace_id}/configurations`
  List configurations for a workspace.

* `POST /api/v1/workspaces/{workspace_id}/configurations`
  Create a configuration from a template or clone.

* `GET /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}`
  Retrieve configuration metadata.

* `GET /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/versions`
  List configuration versions (drafts & published).

### 6.2 Publish, Activate, Deactivate

* `POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/publish`
  Publish a configuration draft.

* `POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/activate`
  Activate a configuration.

* `POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/deactivate`
  Deactivate (previously “archive”) a configuration.

### 6.3 Files & Directories

The Config Builder “Explorer” + editor uses:

* `GET /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files`
  List editable files and directories (tree view).

* `GET /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}`
  Read config file contents.

* `PUT /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}`
  Upsert config file.

* `PATCH /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}`
  Rename or move file.

* `DELETE /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}`
  Delete config file.

* `POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/directories/{directory_path}`
  Create config directory.

* `DELETE /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/directories/{directory_path}`
  Delete config directory.

* `GET /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/export`
  Export configuration (e.g., for download).

### 6.4 Build & Validate

* `POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds`
  Create Build (build config before running).

* `GET /api/v1/builds/{build_id}`
  Get Build detail.

* `POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/validate`
  Validate configuration on disk (static validation).

### 6.5 Runs from Config

* `POST /api/v1/configurations/{configuration_id}/runs`
  Create Run (for a given configuration).

**Frontend plan:**

* Implement `configsApi` feature module:

  * `listConfigurations(workspaceId)`
  * `getConfiguration(workspaceId, configurationId)`
  * `listConfigFiles(workspaceId, configurationId)`
  * `readConfigFile(workspaceId, configurationId, path)`
  * `upsertConfigFile(...)`, `renameConfigFile(...)`, `deleteConfigFile(...)`
  * `validateConfiguration(...)`
  * `exportConfiguration(...)`
  * `createConfigurationRun(configurationId, payload)` (bridging to runs)
* Modeling in UI:

  * Use `files` endpoints to populate the **Explorer** tree in Config Builder.
  * Raw editor for file contents via `files/{file_path}` GET/PUT.
  * Validation results surfaced in the bottom run/validation panel.

All of this is detailed in `100-CONFIG-BUILDER-EDITOR.md`.

---

## 7. Documents & Sheets

These are used for the **Documents** UX (upload → run → review → download).

* `GET /api/v1/workspaces/{workspace_id}/documents`
  List documents.

* `POST /api/v1/workspaces/{workspace_id}/documents`
  Upload a document.

* `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}`
  Retrieve document metadata.

* `DELETE /api/v1/workspaces/{workspace_id}/documents/{document_id}`
  Soft delete document.

* `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/download`
  Download stored document (original file).

* `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/sheets`
  List worksheets (sheets) for a document (e.g., Excel).

**Frontend plan:**

* Implement `documentsApi`:

  * `listDocuments(workspaceId)`
  * `uploadDocument(workspaceId, file)`
  * `getDocument(workspaceId, documentId)`
  * `deleteDocument(workspaceId, documentId)`
  * `downloadDocument(workspaceId, documentId)` (trigger browser download)
  * `listDocumentSheets(workspaceId, documentId)`
* Map to UX (`030-UX-FLOWS.md`):

  * Upload panel uses `uploadDocument`.
  * Documents list uses `listDocuments`.
  * Document detail uses `getDocument` & `listDocumentSheets`.
  * Download actions in Outputs & Downloads use `downloadDocument` (original file).

---

## 8. Runs, Events, Logs & Outputs

The run endpoints power the **Run Detail**, Documents run cards, and Config Builder run panel.

### 8.1 Run Metadata & Summary

* `GET /api/v1/runs/{run_id}`
  Get run metadata.

* `GET /api/v1/runs/{run_id}/summary`
  Get run summary (aggregated stats, validation summary, etc).

* `GET /api/v1/workspaces/{workspace_id}/runs`
  List runs for a workspace (for workspace-level run history or recent runs).

### 8.2 Events & Streaming

* `GET /api/v1/runs/{run_id}/events`
  Get run events.
  This endpoint supports:

  * SSE streaming when `?stream=true` is set.
  * `after_sequence` query param for replay / resuming.

This is the endpoint used by the **RunStream** foundation:

* Live SSE: `/api/v1/runs/{run_id}/events?stream=true&after_sequence=0`
* Replay (SSE or paged): `after_sequence={lastSequence}`

### 8.3 Logs & NDJSON

* `GET /api/v1/runs/{run_id}/logs`
  Get run logs (likely JSON/structured view).

* `GET /api/v1/runs/{run_id}/logfile`
  Download run logs file (plain text / NDJSON archive).

Some installations may also expose `events.ndjson` via:

* Either `logs` or a separate endpoint (consult OpenAPI spec).

### 8.4 Outputs

* `GET /api/v1/runs/{run_id}/outputs`
  List run outputs (normalized files, artifacts).

* `GET /api/v1/runs/{run_id}/outputs/{output_path}`
  Download a specific output object.

**Frontend plan:**

* Implement `runsApi`:

  * `getRun(runId)`
  * `getRunSummary(runId)`
  * `listWorkspaceRuns(workspaceId)`
  * `listRunOutputs(runId)`
  * `downloadRunOutput(runId, outputPath)` (browser download)
  * `getRunLogs(runId)` (for structured log viewer)
  * `downloadRunLogsFile(runId)` (for full log download)
* Run streaming logic (`features/runs/stream`):

  * `streamRunEvents(runId, afterSequence)` → wraps `runs/{run_id}/events`.
  * `fetchRunTelemetry(runId)` → wraps NDJSON/logs endpoint for replay.

These are wired into:

* Run Detail (`RunTimeline`, `RunConsole`, `RunSummaryPanel`, `ValidationSummary`).
* Config Builder run panel.
* Documents’ Live Run cards (simplified view).

---

## 9. Roles & Permissions (Global)

Global roles & permissions support admin UIs and authorization:

* `GET /api/v1/permissions`
  List permission catalog.

* `GET /api/v1/me/permissions`
  Caller’s effective permission set.

* `POST /api/v1/me/permissions/check`
  Check specific permissions.

* `GET /api/v1/roles`
  List global roles.

* `POST /api/v1/roles`
  Create global role.

* `GET /api/v1/roles/{role_id}`
  Read role detail.

* `PATCH /api/v1/roles/{role_id}`
  Update role definition.

* `DELETE /api/v1/roles/{role_id}`
  Delete role.

* `GET /api/v1/role-assignments`
  List global role assignments.

* `POST /api/v1/role-assignments`
  Create global role assignment.

* `DELETE /api/v1/role-assignments/{assignment_id}`
  Delete global role assignment.

**Frontend plan:**

* For this workpackage:

  * Use `me/permissions` to conditionally show/hide admin or dangerous actions.
  * Full global roles/permission management UI is **future work**.

---

## 10. Frontend Integration Conventions

### 10.1 API Module Organization

Per `020-ARCHITECTURE.md`, we keep API wrappers under feature-specific modules:

* `features/auth/api/authApi.ts`
* `features/workspaces/api/workspacesApi.ts`
* `features/configs/api/configsApi.ts`
* `features/documents/api/documentsApi.ts`
* `features/runs/api/runsApi.ts`
* `features/roles/api/rolesApi.ts` (optional/admin)

Each module:

* Wraps fetch calls against these backend routes.
* Uses **generated OpenAPI types** for type safety.
* Returns strongly typed data usable by React Query hooks.

### 10.2 React Query Usage

Patterns:

* `useQuery(['documents', workspaceId], () => documentsApi.listDocuments(workspaceId))`
* `useQuery(['run-summary', runId], () => runsApi.getRunSummary(runId))`
* `useMutation(() => documentsApi.uploadDocument(workspaceId, file))`

Streaming endpoints (`events`) are **not** handled via React Query, but via dedicated hooks in `features/runs/stream`.

### 10.3 Error Handling

* API wrappers should throw typed errors or return a consistent error shape.
* Screens should:

  * Show friendly error states (never raw exception text).
  * Use the design system’s `Toast` and `ErrorState` components.

---

## 11. Open Questions / TODOs

* Confirm NDJSON endpoint naming (whether `logs` or separate `events.ndjson` is the canonical historic telemetry).
* Decide where to relocate `openapi.d.ts` long term:

  * e.g. `apps/ade-web/src/generated/openapi/` and alias as `@generated/openapi`.
* Decide which admin endpoints (roles, workspace membership) we want to expose in the first UI iteration.

Update this document when:

* Backend routes change.
* OpenAPI file path changes.
* We extend the frontend to cover new areas (admin UIs, workspace management, etc.).