# 04 – Data layer and backend contracts

This document explains how `ade-web` talks to the ADE backend:

- the **data layer architecture** (HTTP client, API modules, React Query hooks),
- how `/api/v1/...` routes are **grouped by domain**,
- how we model **runs**, workspaces, documents, and configs in the data layer,
- and how we handle **streaming**, **errors**, and **caching**.

It is the implementation‑level companion to:

- the domain language in `01-domain-model-and-naming.md`, and
- the UX overview in the top‑level `README.md`.

All terminology here uses **run** as the primary execution unit. Backend routes that currently use `/runs` are treated as “workspace run ledger” endpoints.

---

## 1. Architecture and goals

The data layer has three tiers:

1. A **thin HTTP client** that knows how to call `/api/v1/...` and normalise errors.
2. **Domain API modules** (e.g. `workspacesApi`, `documentsApi`, `runsApi`) that wrap specific endpoints.
3. **React Query hooks** in feature folders that connect those modules to UI components.

Flow:

```text
[ Screens / Features ]
        │
        ▼
[ React Query hooks ]  e.g. useWorkspaceRunsQuery, useDocumentsQuery
        │
        ▼
[ API modules ]        e.g. workspacesApi, documentsApi, runsApi
        │
        ▼
[ HTTP client ]        shared/api/httpClient.ts
        │
        ▼
[ ADE API ]            /api/v1/...
````

Design goals:

* **Single source of truth** for each endpoint.
* **Type‑safe** responses with explicit models.
* **Predictable caching** via React Query.
* **Clear separation**:

  * Screens know about hooks and domain types.
  * Hooks know about API modules.
  * API modules know about HTTP and paths.

No UI code calls `fetch` directly; everything goes through the shared HTTP client.

---

## 2. HTTP client

All HTTP calls go through a shared client in `src/shared/api/httpClient.ts` (or equivalent).

### 2.1 Responsibilities

The HTTP client is responsible for:

* Building the full URL (e.g. `/api/v1/...` under the `/api` proxy).
* Serialising request bodies (JSON by default).
* Attaching credentials (cookies, headers) as required.
* Parsing JSON responses.
* Exposing streaming bodies when needed (for NDJSON).
* Mapping non‑2xx responses to a unified `ApiError`.

It deliberately does **not** know about workspaces, runs, configs, etc.

### 2.2 Basic interface

A minimal shape:

```ts
export interface ApiErrorPayload {
  status: number;
  message: string;
  code?: string;
  details?: unknown;
}

export class ApiError extends Error {
  status: number;
  code?: string;
  details?: unknown;
}

export async function apiRequest<T>(
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  options?: {
    query?: Record<string, unknown>;
    body?: unknown;
    signal?: AbortSignal;
    headers?: Record<string, string>;
  },
): Promise<T> {
  // ...
}
```

Rules:

* API modules **only** use `apiRequest`; they never use `fetch` directly.
* `apiRequest` throws an `ApiError` for any non‑2xx status, with a meaningful `message` where possible.

### 2.3 Authentication and 401/403

* 401 (unauthenticated) is handled at a **global** layer (e.g. invalidate session, redirect to `/login`).
* 403 (forbidden) is surfaced to the UI as a permissions error.

The HTTP client itself does not automatically refresh tokens; that logic lives in the auth/session layer and React Query hooks.

---

## 3. React Query

React Query orchestrates fetching, caching, and background updates.

### 3.1 Query client configuration

`AppProviders` creates a single `QueryClient` with sane defaults:

* `retry: 1` – most ADE errors are not transient.
* `staleTime: 30_000` – many reads can be reused for ~30 seconds.
* `refetchOnWindowFocus: false` – avoids surprise reloads when switching tabs.

These can be overridden per query (e.g. for health checks).

### 3.2 Query keys

Query keys must be:

* **Stable** – same inputs → same key.
* **Descriptive** – easy to inspect in devtools.
* **Scoped** – from global → workspace → resource.

Patterns:

* Session & permissions:

  * `['session']`
  * `['permissions', 'effective']`

* Workspaces:

  * `['workspaces']`
  * `['workspace', workspaceId]`
  * `['workspace', workspaceId, 'members']`
  * `['workspace', workspaceId, 'roles']`

* Documents:

  * `['workspace', workspaceId, 'documents', params]`
  * `['workspace', workspaceId, 'document', documentId]`
  * `['workspace', workspaceId, 'document', documentId, 'sheets']`

* Runs:

  * `['workspace', workspaceId, 'runs', params]`     // lists from `/runs` endpoints
  * `['workspace', workspaceId, 'run', runId]`       // detail via `/runs/{run_id}`
  * `['run', runId]`                                 // detail via `/runs/{run_id}` if used directly
  * `['run', runId, 'outputs']`

* Configurations:

  * `['workspace', workspaceId, 'configurations']`
  * `['workspace', workspaceId, 'configuration', configId]`
  * `['workspace', workspaceId, 'configuration', configId, 'versions']`
  * `['workspace', workspaceId, 'configuration', configId, 'files']`

* System:

  * `['system', 'safe-mode']`
  * `['system', 'health']`

Filters and sort options go into a `params` object that is part of the key.

### 3.3 Query and mutation hooks

For each domain:

* API modules export **plain functions** (`listWorkspaceRuns`, `uploadDocument`, `activateConfiguration`).
* Features define **hooks** that wrap those functions in React Query:

  * Queries: `useWorkspaceRunsQuery(workspaceId, filters)`, `useDocumentsQuery(workspaceId, filters)`.
  * Mutations: `useCreateRunMutation(workspaceId)`, `useUploadDocumentMutation(workspaceId)`.

Hooks live near the screen components that use them (e.g. `features/workspace-shell/runs/useWorkspaceRunsQuery.ts`) and depend on the shared API modules.

---

## 4. Domain API modules

Domain API modules live under `src/shared/api/`. Each module owns a set of related endpoints and exposes typed functions.

Naming:

* Modules: `authApi`, `workspacesApi`, `documentsApi`, `runsApi`, `configsApi`, `buildsApi`, `rolesApi`, `systemApi`, `apiKeysApi`.
* Functions: `<verb><Noun>` (e.g. `listWorkspaceRuns`, `createRun`, `activateConfiguration`).

Below we describe what each module covers and how it maps to backend routes.

### 4.1 Auth & session (`authApi`)

**Responsibilities**

* Initial setup.
* Login/logout (email/password and SSO).
* Session and current user.

**Key routes**

* Setup:

  * `GET  /api/v1/setup/status` – read initial setup status.
  * `POST /api/v1/setup`        – complete first admin setup.

* Session:

  * `POST   /api/v1/auth/session`         – create session.
  * `GET    /api/v1/auth/session`         – read session (canonical “who am I?”).
  * `POST   /api/v1/auth/session/refresh` – refresh session.
  * `DELETE /api/v1/auth/session`         – logout.

* Auth providers:

  * `GET /api/v1/auth/providers` – configured auth providers.
  * `GET /api/v1/auth/sso/login` – initiate SSO login (302 redirect).
  * `GET /api/v1/auth/sso/callback` – finish SSO login.

* User profile:

  * `GET /api/v1/users/me` or `GET /api/v1/auth/me` – authenticated user (name, email, id).

**Example functions**

* `readSetupStatus()`
* `completeSetup(payload)`
* `listAuthProviders()`
* `createSession(credentials)`
* `refreshSession()`
* `deleteSession()`
* `readSession()`
* `readCurrentUser()`

Hooks:

* `useSetupStatusQuery()`
* `useSessionQuery()`
* `useCurrentUserQuery()`
* `useLoginMutation()`, `useLogoutMutation()`

### 4.2 Permissions & global roles (`rolesApi`)

**Responsibilities**

* Global roles.
* Global role assignments.
* Permission catalog and effective permissions.

**Key routes**

* Permissions:

  * `GET  /api/v1/permissions`             – permission catalog.
  * `GET  /api/v1/me/permissions`          – effective permissions.
  * `POST /api/v1/me/permissions/check`    – check specific permissions.

* Global roles:

  * `GET    /api/v1/roles`
  * `POST   /api/v1/roles`
  * `GET    /api/v1/roles/{role_id}`
  * `PATCH  /api/v1/roles/{role_id}`
  * `DELETE /api/v1/roles/{role_id}`

* Global role assignments:

  * `GET    /api/v1/role-assignments`
  * `POST   /api/v1/role-assignments`
  * `DELETE /api/v1/role-assignments/{assignment_id}`

**Example functions**

* `listPermissions()`
* `readEffectivePermissions()`
* `checkPermissions(request)`
* `listGlobalRoles()`
* `createGlobalRole(payload)`
* `readGlobalRole(roleId)`
* `updateGlobalRole(roleId, patch)`
* `deleteGlobalRole(roleId)`
* `listGlobalRoleAssignments()`
* `createGlobalRoleAssignment(payload)`
* `deleteGlobalRoleAssignment(assignmentId)`

Hooks:

* `useEffectivePermissionsQuery()`
* `usePermissionCatalogQuery()`
* Admin screens: `useGlobalRolesQuery()`, `useGlobalRoleAssignmentsQuery()`

### 4.3 Workspaces & membership (`workspacesApi`)

**Responsibilities**

* Workspace lifecycle and metadata.
* Membership within a workspace.
* Workspace‑scoped roles and role assignments.
* Default workspace.

**Key routes**

* Workspaces:

  * `GET    /api/v1/workspaces`
  * `POST   /api/v1/workspaces`
  * `GET    /api/v1/workspaces/{workspace_id}`
  * `PATCH  /api/v1/workspaces/{workspace_id}`
  * `DELETE /api/v1/workspaces/{workspace_id}`
  * `POST   /api/v1/workspaces/{workspace_id}/default`

* Members:

  * `GET    /api/v1/workspaces/{workspace_id}/members`
  * `POST   /api/v1/workspaces/{workspace_id}/members`
  * `DELETE /api/v1/workspaces/{workspace_id}/members/{membership_id}`
  * `PUT    /api/v1/workspaces/{workspace_id}/members/{membership_id}/roles`

* Workspace roles & assignments:

  * `GET    /api/v1/workspaces/{workspace_id}/roles`
  * `GET    /api/v1/workspaces/{workspace_id}/role-assignments`
  * `POST   /api/v1/workspaces/{workspace_id}/role-assignments`
  * `DELETE /api/v1/workspaces/{workspace_id}/role-assignments/{assignment_id}`

**Example functions**

* Workspaces:

  * `listWorkspaces()`
  * `createWorkspace(payload)`
  * `readWorkspace(workspaceId)`
  * `updateWorkspace(workspaceId, patch)`
  * `deleteWorkspace(workspaceId)`
  * `setDefaultWorkspace(workspaceId)`

* Members:

  * `listWorkspaceMembers(workspaceId)`
  * `addWorkspaceMember(workspaceId, payload)`
  * `removeWorkspaceMember(workspaceId, membershipId)`
  * `updateWorkspaceMemberRoles(workspaceId, membershipId, roles)`

* Workspace‑scoped roles:

  * `listWorkspaceRoles(workspaceId)`
  * `listWorkspaceRoleAssignments(workspaceId)`
  * `createWorkspaceRoleAssignment(workspaceId, payload)`
  * `deleteWorkspaceRoleAssignment(workspaceId, assignmentId)`

Hooks:

* `useWorkspacesQuery()`
* `useWorkspaceQuery(workspaceId)`
* `useWorkspaceMembersQuery(workspaceId)`
* `useWorkspaceRolesQuery(workspaceId)`

### 4.4 Documents (`documentsApi`)

**Responsibilities**

* Document upload and listing per workspace.
* Document metadata and download.
* Sheet metadata for spreadsheet‑like inputs.

**Key routes**

* `GET  /api/v1/workspaces/{workspace_id}/documents`
* `POST /api/v1/workspaces/{workspace_id}/documents`
* `GET  /api/v1/workspaces/{workspace_id}/documents/{document_id}`
* `DELETE /api/v1/workspaces/{workspace_id}/documents/{document_id}`
* `GET  /api/v1/workspaces/{workspace_id}/documents/{document_id}/download`
* `GET  /api/v1/workspaces/{workspace_id}/documents/{document_id}/sheets`

**Example functions**

* `listDocuments(workspaceId, params)`
* `uploadDocument(workspaceId, file, options?)`
* `readDocument(workspaceId, documentId)`
* `deleteDocument(workspaceId, documentId)`
* `downloadDocument(workspaceId, documentId)`
* `listDocumentSheets(workspaceId, documentId)`

Hooks:

* `useDocumentsQuery(workspaceId, filters)`
* `useDocumentQuery(workspaceId, documentId)`
* `useDocumentSheetsQuery(workspaceId, documentId)`

Mutations:

* `useUploadDocumentMutation(workspaceId)`
* `useDeleteDocumentMutation(workspaceId)`

### 4.5 Runs (`runsApi`)

**Responsibilities**

* Workspace run ledger (list of all runs in a workspace).
* Per‑run artifacts, outputs, and log files.
* Config‑initiated runs (e.g. from Config Builder).
* Run‑level streaming logs.

There are two groups of endpoints:

* Workspace‑scoped ledger endpoints, currently under `/runs` in the API.
* Global run endpoints, under `/runs`.

In the frontend we treat both as variants of the same **Run** domain concept.

**Key routes: workspace run ledger (under `/runs`)**

* `GET  /api/v1/workspaces/{workspace_id}/runs` – list runs for workspace.
* `POST /api/v1/workspaces/{workspace_id}/runs` – submit new run.
* `GET  /api/v1/workspaces/{workspace_id}/runs/{run_id}` – read run summary.
* `GET  /api/v1/workspaces/{workspace_id}/runs/{run_id}/artifact` – download artifact.
* `GET  /api/v1/workspaces/{workspace_id}/runs/{run_id}/logs` – download logs file.
* `GET  /api/v1/workspaces/{workspace_id}/runs/{run_id}/outputs` – list outputs.
* `GET  /api/v1/workspaces/{workspace_id}/runs/{run_id}/outputs/{output_path}` – download output.

**Key routes: config‑scoped & global run endpoints**

* `POST /api/v1/configs/{config_id}/runs` – start a run for a given config.
* `GET  /api/v1/runs/{run_id}` – read run detail.
* `GET  /api/v1/runs/{run_id}/artifact` – download artifact.
* `GET  /api/v1/runs/{run_id}/logfile` – download logs file.
* `GET  /api/v1/runs/{run_id}/logs` – stream logs (NDJSON).
* `GET  /api/v1/runs/{run_id}/outputs` – list outputs.
* `GET  /api/v1/runs/{run_id}/outputs/{output_path}` – download output.

**Example functions**

Workspace‑level:

* `listWorkspaceRuns(workspaceId, params)`
* `createWorkspaceRun(workspaceId, payload)`
* `readWorkspaceRun(workspaceId, runId)`           // wraps `/runs/{run_id}`
* `listWorkspaceRunOutputs(workspaceId, runId)`
* `downloadWorkspaceRunOutput(workspaceId, runId, outputPath)`
* `downloadWorkspaceRunArtifact(workspaceId, runId)`
* `downloadWorkspaceRunLogFile(workspaceId, runId)`

Config/global‑level:

* `createConfigRun(configId, payload)`             // wraps `/configs/{config_id}/runs`
* `readRun(runId)`                                 // wraps `/runs/{run_id}`
* `listRunOutputs(runId)`
* `downloadRunOutput(runId, outputPath)`
* `downloadRunArtifact(runId)`
* `downloadRunLogFile(runId)`
* `streamRunLogs(runId)`                           // wraps `/runs/{run_id}/logs`

Hooks:

* `useWorkspaceRunsQuery(workspaceId, filters)`
* `useRunQuery(runId)` (or `useWorkspaceRunQuery(workspaceId, runId)` depending on which endpoint you use)
* `useCreateWorkspaceRunMutation(workspaceId)`
* `useCreateConfigRunMutation(configId)`

Streaming hook:

* `useRunLogsStream(runId)` for the live run console.

### 4.6 Configurations & builds (`configsApi`, `buildsApi`)

**Responsibilities**

* Configuration entities and versions.
* Config file tree and file contents for the workbench.
* Build and validate operations.

**Key routes: configurations**

* `GET  /api/v1/workspaces/{workspace_id}/configurations`
* `POST /api/v1/workspaces/{workspace_id}/configurations`
* `GET  /api/v1/workspaces/{workspace_id}/configurations/{config_id}`
* `GET  /api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions`
* `POST /api/v1/workspaces/{workspace_id}/configurations/{config_id}/activate`
* `POST /api/v1/workspaces/{workspace_id}/configurations/{config_id}/deactivate`
* `POST /api/v1/workspaces/{workspace_id}/configurations/{config_id}/publish`
* `POST /api/v1/workspaces/{workspace_id}/configurations/{config_id}/validate`
* `GET  /api/v1/workspaces/{workspace_id}/configurations/{config_id}/export`

**Key routes: config files**

* `GET    /api/v1/workspaces/{workspace_id}/configurations/{config_id}/files`
* `GET    /api/v1/workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}`
* `PUT    /api/v1/workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}`
* `PATCH  /api/v1/workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}`
* `DELETE /api/v1/workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}`
* `POST   /api/v1/workspaces/{workspace_id}/configurations/{config_id}/directories/{directory_path}`
* `DELETE /api/v1/workspaces/{workspace_id}/configurations/{config_id}/directories/{directory_path}`

**Key routes: builds**

* `POST /api/v1/workspaces/{workspace_id}/configs/{config_id}/builds`
* `GET  /api/v1/builds/{build_id}`
* `GET  /api/v1/builds/{build_id}/logs` – stream build logs (NDJSON).

**Example functions**

Configurations:

* `listConfigurations(workspaceId)`
* `createConfiguration(workspaceId, payload)`
* `readConfiguration(workspaceId, configId)`
* `listConfigVersions(workspaceId, configId)`
* `activateConfiguration(workspaceId, configId)`
* `deactivateConfiguration(workspaceId, configId)`
* `publishConfiguration(workspaceId, configId)`
* `validateConfiguration(workspaceId, configId, payload)`
* `exportConfiguration(workspaceId, configId)`

Config files:

* `listConfigFiles(workspaceId, configId)`
* `readConfigFile(workspaceId, configId, filePath)`
* `upsertConfigFile(workspaceId, configId, filePath, content, options?)`  // includes ETag preconditions.
* `renameConfigFile(workspaceId, configId, filePath, newPath)`
* `deleteConfigFile(workspaceId, configId, filePath)`
* `createConfigDirectory(workspaceId, configId, dirPath)`
* `deleteConfigDirectory(workspaceId, configId, dirPath)`

Builds:

* `createBuild(workspaceId, configId, options)`  // returns `buildId`.
* `readBuild(buildId)`
* `streamBuildLogs(buildId)`

Hooks:

* `useConfigurationsQuery(workspaceId)`
* `useConfigurationQuery(workspaceId, configId)`
* `useConfigVersionsQuery(workspaceId, configId)`
* `useConfigFilesQuery(workspaceId, configId)`
* `useCreateBuildMutation(workspaceId, configId)`
* `useBuildLogsStream(buildId)`

### 4.7 System & safe mode (`systemApi`)

**Responsibilities**

* System health.
* Safe mode status and updates.

**Key routes**

* `GET /api/v1/health`
* `GET /api/v1/system/safe-mode`
* `PUT /api/v1/system/safe-mode`

**Example functions**

* `readHealth()`
* `readSafeMode()`
* `updateSafeMode(payload)`

Hooks:

* `useSafeModeQuery()`
* `useUpdateSafeModeMutation()`

### 4.8 Users & API keys (`usersApi`, `apiKeysApi`)

**Responsibilities**

* User directory (admin use).
* API key management for users.

**Key routes**

* Users:

  * `GET /api/v1/users` – list all users (admin only).

* API keys:

  * `GET    /api/v1/auth/api-keys`
  * `POST   /api/v1/auth/api-keys`
  * `DELETE /api/v1/auth/api-keys/{api_key_id}`

**Example functions**

* `listUsers(params?)`
* `listApiKeys()`
* `createApiKey(payload)`
* `revokeApiKey(apiKeyId)`

Hooks:

* `useUsersQuery()`
* `useApiKeysQuery()`
* `useCreateApiKeyMutation()`
* `useRevokeApiKeyMutation()`

---

## 5. Typed models and schemas

The data layer uses TypeScript types from two places:

1. **Generated types** (if present) in `src/generated-types/`.
2. **Domain models** in `src/schema/`.

### 5.1 Generated types

Generated types:

* Mirror backend schemas 1:1 (field names, nested structures).
* Are authoritative for the wire format.
* May expose internal details that we don’t want to leak into screens.

We typically consume them only in API modules and mapping functions.

### 5.2 Domain models

Domain models in `src/schema/` provide UI‑oriented shapes:

* `WorkspaceSummary`, `WorkspaceDetail`
* `DocumentSummary`, `DocumentDetail`
* `RunSummary`, `RunDetail`
* `Configuration`, `ConfigVersion`
* `SafeModeStatus`, etc.

API modules are responsible for mapping:

```ts
function toRunSummary(apiRun: ApiRun): RunSummary { /* ... */ }
```

This gives us:

* A stable surface for screens, even if backend fields change.
* A clear place to rename things (e.g. `run_id` → `runId` in the UI).

---

## 6. Streaming NDJSON logs

Some endpoints stream logs/events as NDJSON. We treat these as **event streams**, not as “queries”.

### 6.1 Streaming abstraction

A small module in `src/shared/ndjson/` provides a generic NDJSON reader, for example:

```ts
export interface NdjsonEvent {
  type?: string;
  [key: string]: unknown;
}

export function streamNdjson(
  path: string,
  options?: { signal?: AbortSignal },
  onEvent?: (event: NdjsonEvent) => void,
): Promise<void> {
  // open fetch, read chunks, split by newline, JSON.parse, call onEvent
}
```

Key characteristics:

* Accepts an `AbortSignal` so callers can terminate the stream.
* Parses each line as JSON; lines that fail to parse are either ignored or reported via an error callback.

### 6.2 Run and build logs

Used by:

* Config Builder:

  * `streamBuildLogs(buildId)` → `/api/v1/builds/{build_id}/logs`.

* Run consoles:

  * `streamRunLogs(runId)` → `/api/v1/runs/{run_id}/logs`.

Event format is determined by the backend. We expect at minimum:

* A `type` field (e.g. `"log"`, `"status"`, `"summary"`).
* A `timestamp`.
* Either a `message` or structured `data`.

UI code in the workbench or run detail screen:

* Appends log lines to a console buffer.
* Updates derived status (e.g. completed, failed) when a terminal event arrives.

### 6.3 Cancellation and errors

Streaming helpers:

* Always create an `AbortController` in the calling component.
* Cancel the stream on unmount or when the user closes the console.

Error handling:

* Network or server errors should be surfaced as a **console banner** (“Stream disconnected”) rather than thrown.
* The component may optionally allow manual retry.

We deliberately do **not** wrap NDJSON streams in React Query; they are long‑lived event flows, not snapshot fetches.

---

## 7. Error handling and retry

### 7.1 `ApiError` handling

Every endpoint that fails returns an `ApiError` from the HTTP client:

* `status` – HTTP status code.
* `message` – user‑friendly message when available.
* `code` – optional machine code from backend.
* `details` – optional structured payload.

API modules do not catch these errors; they are allowed to propagate to React Query.

### 7.2 Where to surface errors

Guidelines:

* **Mutations (buttons/forms)**:

  * Show a toast for “one‑off” actions (start run, save file).
  * Show inline error text for validation problems.

* **List/detail screens**:

  * Use an inline `Alert` in the main content area if loading fails.
  * For critical surfaces, show a full “something went wrong” state with a retry button.

* **Streaming consoles**:

  * Show a console‑local banner on stream errors.
  * Don’t crash the surrounding screen.

### 7.3 Retry policy

Default `retry: 1` is fine for most queries.

Override with `retry: false` when:

* Hitting permission endpoints that will not succeed without user state change (403).
* Calling validation endpoints where repeated attempts won’t help.

Mutations:

* Rely on explicit user retries (e.g. clicking “Run again”) rather than automatic retry.

---

## 8. Contracts, invariants, and adding endpoints

### 8.1 Invariants

To keep the data layer predictable:

* **Single owner per endpoint**

  * Each backend route is wrapped by exactly one function in one module.
  * Screens and hooks never embed raw URLs.

* **Explicit types**

  * No `any` for responses; map to domain models.
  * Backend changes should be reflected in `schema/` and, where needed, in mapping functions.

* **No direct `fetch`**

  * Only the HTTP client talks to `fetch` / XHR.
  * This keeps auth, error handling, and logging consistent.

* **Run‑centric terminology**

  * All execution units are “runs” in frontend types, hooks, and screens.
  * API module mapping handles backend field names like `run_id` → `runId`.

* **Backend‑agnostic**

  * ADE Web depends on the *behaviour* and *shapes* described here, not on any specific backend implementation.
  * As long as `/api/v1/...` contracts are preserved, different backends can power the UI.

### 8.2 Adding a new endpoint

When a new backend route appears:

1. **Choose a module**

   * Workspaces, documents, runs, configurations, roles, auth, system, etc.
   * If it doesn’t fit, introduce a new module in `shared/api`.

2. **Add a typed function**

   * Implement `<verb><Noun>` in that module using `apiRequest`.
   * Map the wire shape into a domain model if needed.

3. **Add a hook**

   * Create `useXxxQuery` or `useXxxMutation` in the relevant feature folder.
   * Use a consistent query key pattern and invalidate affected keys on write.

4. **Update types**

   * Add or adjust domain types in `schema/`.
   * Wire in generated types if you have them.

5. **Update docs**

   * Add the route and function to the relevant section of this file.
   * If it introduces a new domain concept, update `01-domain-model-and-naming.md`.

6. **Add tests**

   * Unit tests for the API function (mocking `apiRequest`).
   * Integration tests for the feature, when appropriate.

Following these rules keeps the data layer small, obvious, and easy to navigate—for both humans and AI agents—while making it straightforward to evolve the ADE backend over time.