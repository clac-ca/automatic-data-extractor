# 04 – Data layer and backend contracts

This document describes how `ade-web` talks to the ADE backend:

- The **data layer architecture** (HTTP client, API modules, React Query hooks).
- How we **group `/api/v1/...` routes** into domain‑specific modules.
- How we **type** responses and model them in the frontend.
- How **streaming NDJSON endpoints** are consumed.
- Our **error handling and retry** conventions.

Treat this as the canonical spec for frontend ↔ backend contracts. When new endpoints are added to the backend, they should either fit into one of the modules described here or motivate a new module.

---

## 1. Goals and layering

The data layer is built around a few simple goals:

- **Single source of truth** for each backend route.
- **Type‑safe** access to backend data.
- **Predictable caching** with React Query.
- **Separation of concerns**:
  - HTTP details & error handling live in a shared **HTTP client**.
  - Each backend “area” has a small, focused **API module**.
  - Screens use **React Query hooks** built on those modules.

The layering looks like this:

```text
[ Screens / Features ]
        │
        ▼
[ React Query hooks ]  e.g. useWorkspacesQuery, useDocumentsQuery
        │
        ▼
[ API modules ]        e.g. workspacesApi, documentsApi
        │
        ▼
[ HTTP client ]        shared/api/httpClient.ts
        │
        ▼
[ ADE API ]            /api/v1/...
````

* API modules are **pure TypeScript** (no React).
* React Query hooks are defined in feature folders and **only** call API modules.

---

## 2. React Query configuration and conventions

React Query is configured in `AppProviders`:

```ts
new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});
```

**Conventions:**

* **Query keys** are simple arrays, grouped by domain:

  * Workspaces: `['workspaces']`, `['workspaces', workspaceId]`
  * Documents: `['workspaces', workspaceId, 'documents', params]`
  * Jobs: `['workspaces', workspaceId, 'jobs', params]`
  * Configurations: `['workspaces', workspaceId, 'configurations']`
  * Safe mode: `['system', 'safe-mode']`
  * Session: `['session']`

  Use objects or serialisable parameter bags as the **last element** when needed.

* **Hooks** follow a consistent naming scheme:

  * Queries: `use<Domain><What>Query`
    e.g. `useWorkspacesQuery`, `useWorkspaceDocumentsQuery`.
  * Mutations: `use<Verb><Domain>Mutation`
    e.g. `useUploadDocumentMutation`, `useSubmitJobMutation`.

* **Staleness**:

  * For most list/detail queries we accept a 30s `staleTime`.
  * For highly dynamic views (e.g. running jobs/builds) we rely on:

    * **Streaming updates** for state.
    * Manual `refetch()` on significant UI events.

---

## 3. HTTP client and base URL

All HTTP calls go through a single shared client in `src/shared/api/httpClient.ts` (or equivalent).

### 3.1 Base URL and proxy

* In development, Vite proxies `/api` → the backend port, so the client simply calls paths like `/api/v1/...`.
* In production, the frontend is served behind the backend, and `/api` is routed appropriately.

The HTTP client:

* Handles JSON encoding/decoding.
* Attaches credentials (e.g. cookies) as required.
* Normalises errors into a consistent shape.

### 3.2 Client interface

At a minimum:

```ts
interface ApiErrorPayload {
  status: number;
  message: string;
  code?: string;
  details?: unknown;
}

class ApiError extends Error {
  status: number;
  code?: string;
  details?: unknown;
}

async function apiRequest<T>(
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  options?: { query?: Record<string, unknown>; body?: unknown; signal?: AbortSignal },
): Promise<T> {
  // ...
}
```

**Rules:**

* API modules do **not** use `fetch` directly; they only call `apiRequest`.
* `apiRequest` is responsible for:

  * Building the full URL with query params.
  * Throwing `ApiError` for non‑2xx responses.
  * Returning the parsed JSON for success.

---

## 4. Domain API modules

All backend routes are grouped into small, focussed API modules under `src/shared/api/`. Each module exports plain functions; React hooks live in feature folders.

Below we describe the intended module layout and how `/api/v1/...` routes map into them.

> **Note:** Function names are indicative. Exact naming can vary as long as the intent is clear and consistent.

### 4.1 Auth & session (`authApi.ts`)

Backend routes:

* `GET  /api/v1/auth/providers` – list configured auth providers.
* `GET  /api/v1/setup/status` – check if initial admin setup is required.
* `POST /api/v1/setup` – create the first administrator account.
* `POST /api/v1/auth/session` – create a browser session (email/password).
* `DELETE /api/v1/auth/session` – terminate the active session.
* `POST /api/v1/auth/session/refresh` – refresh session.
* `GET  /api/v1/auth/session` – read active session profile (canonical session endpoint).
* `GET  /api/v1/auth/me` / `GET /api/v1/users/me` – user profile convenience endpoints.
* `GET  /api/v1/auth/sso/login` – initiate SSO login.
* `GET  /api/v1/auth/sso/callback` – handle SSO callback.

> For `ade-web`, **`GET /api/v1/auth/session` is the canonical session endpoint**. Other “me” endpoints are treated as legacy or supplemental.

Typical functions:

* `getSetupStatus()`
* `completeSetup(payload)`
* `listAuthProviders()`
* `createSession(credentials)`
* `refreshSession()`
* `deleteSession()`
* `getSession()` – wraps `GET /auth/session`.

SSO endpoints are usually not called directly from the SPA (they cause full‑page redirects), but `authApi` can expose helpers to construct URLs.

### 4.2 Workspaces & members (`workspacesApi.ts`)

Backend routes:

* `GET  /api/v1/workspaces` – list workspaces for user.
* `POST /api/v1/workspaces` – create workspace.
* `GET  /api/v1/workspaces/{workspace_id}` – read workspace detail/context.
* `PATCH /api/v1/workspaces/{workspace_id}` – update workspace metadata.
* `DELETE /api/v1/workspaces/{workspace_id}` – delete workspace.
* `POST /api/v1/workspaces/{workspace_id}/default` – mark as user’s default.

Membership & roles at workspace scope:

* `GET  /api/v1/workspaces/{workspace_id}/members`
* `POST /api/v1/workspaces/{workspace_id}/members`
* `DELETE /api/v1/workspaces/{workspace_id}/members/{membership_id}`
* `PUT  /api/v1/workspaces/{workspace_id}/members/{membership_id}/roles`

Workspace‑role definitions and assignments:

* `GET  /api/v1/workspaces/{workspace_id}/roles`
* `GET  /api/v1/workspaces/{workspace_id}/role-assignments`
* `POST /api/v1/workspaces/{workspace_id}/role-assignments`
* `DELETE /api/v1/workspaces/{workspace_id}/role-assignments/{assignment_id}`

Typical functions:

* `listWorkspaces()`
* `createWorkspace(payload)`
* `getWorkspace(workspaceId)`
* `updateWorkspace(workspaceId, patch)`
* `deleteWorkspace(workspaceId)`
* `setDefaultWorkspace(workspaceId)`

Membership:

* `listWorkspaceMembers(workspaceId)`
* `addWorkspaceMember(workspaceId, payload)`
* `removeWorkspaceMember(workspaceId, membershipId)`
* `replaceWorkspaceMemberRoles(workspaceId, membershipId, roleIds)`

Workspace roles:

* `listWorkspaceRoles(workspaceId)`
* `listWorkspaceRoleAssignments(workspaceId)`
* `createWorkspaceRoleAssignment(workspaceId, payload)`
* `deleteWorkspaceRoleAssignment(workspaceId, assignmentId)`

### 4.3 Documents (`documentsApi.ts`)

Backend routes:

* `GET  /api/v1/workspaces/{workspace_id}/documents` – list documents.
* `POST /api/v1/workspaces/{workspace_id}/documents` – upload document.
* `GET  /api/v1/workspaces/{workspace_id}/documents/{document_id}` – read metadata.
* `DELETE /api/v1/workspaces/{workspace_id}/documents/{document_id}` – soft delete.
* `GET  /api/v1/workspaces/{workspace_id}/documents/{document_id}/download` – download original file.
* `GET  /api/v1/workspaces/{workspace_id}/documents/{document_id}/sheets` – list worksheets.

Typical functions:

* `listDocuments(workspaceId, params)`
* `uploadDocument(workspaceId, file, options)`
* `getDocument(workspaceId, documentId)`
* `deleteDocument(workspaceId, documentId)`
* `downloadDocument(workspaceId, documentId)` – returns a `Blob` or download URL.
* `listDocumentSheets(workspaceId, documentId)`

Uploads are typically implemented with `FormData`. The API function should hide those details behind a simple signature.

### 4.4 Jobs & runs (`jobsApi.ts`, `runsApi.ts`)

Jobs (workspace‑scoped):

* `GET  /api/v1/workspaces/{workspace_id}/jobs` – list jobs.
* `POST /api/v1/workspaces/{workspace_id}/jobs` – submit job.
* `GET  /api/v1/workspaces/{workspace_id}/jobs/{job_id}` – read job detail.
* `GET  /api/v1/workspaces/{workspace_id}/jobs/{job_id}/artifact` – download artifact.
* `GET  /api/v1/workspaces/{workspace_id}/jobs/{job_id}/logs` – download job logs.
* `GET  /api/v1/workspaces/{workspace_id}/jobs/{job_id}/outputs` – list outputs.
* `GET  /api/v1/workspaces/{workspace_id}/jobs/{job_id}/outputs/{output_path}` – download output file.

Runs (engine‑level, when used directly):

* `POST /api/v1/configs/{config_id}/runs` – create run.
* `GET  /api/v1/runs/{run_id}` – get run.
* `GET  /api/v1/runs/{run_id}/logs` – streaming run logs (NDJSON).
* `GET  /api/v1/runs/{run_id}/logfile` – download logs file.
* `GET  /api/v1/runs/{run_id}/artifact` – download run artifact.
* `GET  /api/v1/runs/{run_id}/outputs` – list outputs.
* `GET  /api/v1/runs/{run_id}/outputs/{output_path}` – download output.

In the UI we generally talk about **Jobs** and treat “runs” as implementation detail. For clarity:

* `jobsApi` covers workspace jobs, their artifacts, and downloadable outputs.
* `runsApi` is a lower‑level module used where we need fine‑grained streaming control (e.g. Config Builder validation).

Typical functions:

* Jobs:

  * `listJobs(workspaceId, params)`
  * `submitJob(workspaceId, payload)`  // includes document IDs, config version, options
  * `getJob(workspaceId, jobId)`
  * `downloadJobArtifact(workspaceId, jobId)`
  * `listJobOutputs(workspaceId, jobId)`
  * `downloadJobOutput(workspaceId, jobId, outputPath)`

* Runs (if/where used):

  * `createRun(configId, payload)`
  * `getRun(runId)`
  * `downloadRunArtifact(runId)`
  * `listRunOutputs(runId)`
  * `downloadRunOutput(runId, outputPath)`

Streaming log endpoints are covered separately in §6.

### 4.5 Configurations & builds (`configsApi.ts`, `buildsApi.ts`)

Configurations (workspace scope):

* `GET  /api/v1/workspaces/{workspace_id}/configurations` – list configs.
* `POST /api/v1/workspaces/{workspace_id}/configurations` – create config (from template/clone).
* `GET  /api/v1/workspaces/{workspace_id}/configurations/{config_id}` – config metadata.
* `GET  /api/v1/workspaces/{workspace_id}/configurations/{config_id}/versions` – list versions.
* `POST /api/v1/workspaces/{workspace_id}/configurations/{config_id}/activate` – activate config.
* `POST /api/v1/workspaces/{workspace_id}/configurations/{config_id}/deactivate` – deactivate config.
* `POST /api/v1/workspaces/{workspace_id}/configurations/{config_id}/publish` – publish draft.
* `GET  /api/v1/workspaces/{workspace_id}/configurations/{config_id}/export` – export config.

Config files & directories (workbench):

* `GET    /api/v1/workspaces/{workspace_id}/configurations/{config_id}/files` – list editable files/directories.
* `GET    /api/v1/workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}` – read file content.
* `PUT    /api/v1/workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}` – upsert file.
* `PATCH  /api/v1/workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}` – rename/move file.
* `DELETE /api/v1/workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}` – delete file.
* `POST   /api/v1/workspaces/{workspace_id}/configurations/{config_id}/directories/{directory_path}` – create directory.
* `DELETE /api/v1/workspaces/{workspace_id}/configurations/{config_id}/directories/{directory_path}` – delete directory.

Builds:

* `POST /api/v1/workspaces/{workspace_id}/configs/{config_id}/builds` – create build.
* `GET  /api/v1/builds/{build_id}` – get build.
* `GET  /api/v1/builds/{build_id}/logs` – streaming build logs (NDJSON).

Validation:

* `POST /api/v1/workspaces/{workspace_id}/configurations/{config_id}/validate` – validate config on disk.

Typical functions (configsApi):

* `listConfigurations(workspaceId)`
* `createConfiguration(workspaceId, payload)`
* `getConfiguration(workspaceId, configId)`
* `listConfigVersions(workspaceId, configId)`
* `activateConfiguration(workspaceId, configId)`
* `deactivateConfiguration(workspaceId, configId)`
* `publishConfiguration(workspaceId, configId)`
* `exportConfiguration(workspaceId, configId)`

Files:

* `listConfigFiles(workspaceId, configId)`
* `getConfigFile(workspaceId, configId, path)`
* `upsertConfigFile(workspaceId, configId, path, content, options)`  // includes ETag preconditions
* `renameConfigFile(workspaceId, configId, fromPath, toPath)`
* `deleteConfigFile(workspaceId, configId, path)`
* `createConfigDirectory(workspaceId, configId, path)`
* `deleteConfigDirectory(workspaceId, configId, path)`

Builds (buildsApi):

* `createBuild(workspaceId, configId, options)`  // returns buildId
* `getBuild(buildId)`
* (Streaming logs: see §6)

Validation:

* `validateConfiguration(workspaceId, configId, options)` – may integrate with streaming if implemented that way.

### 4.6 Roles & permissions (`rolesApi.ts`)

Backend routes:

* `GET  /api/v1/permissions` – list permission catalog.
* `GET  /api/v1/me/permissions` – effective permissions for caller.
* `POST /api/v1/me/permissions/check` – check specific permissions.

Global roles:

* `GET  /api/v1/roles` – list global roles.
* `POST /api/v1/roles` – create global role.
* `GET  /api/v1/roles/{role_id}` – read role.
* `PATCH /api/v1/roles/{role_id}` – update role.
* `DELETE /api/v1/roles/{role_id}` – delete role.

Global role assignments:

* `GET  /api/v1/role-assignments` – list assignments.
* `POST /api/v1/role-assignments` – create assignment.
* `DELETE /api/v1/role-assignments/{assignment_id}` – delete assignment.

Typical functions:

* `listPermissions()`
* `getEffectivePermissions()`
* `checkPermissions(payload)`
* `listGlobalRoles()`
* `createGlobalRole(payload)`
* `getGlobalRole(roleId)`
* `updateGlobalRole(roleId, patch)`
* `deleteGlobalRole(roleId)`
* `listGlobalRoleAssignments()`
* `createGlobalRoleAssignment(payload)`
* `deleteGlobalRoleAssignment(assignmentId)`

Workspace‑level roles and assignments live in `workspacesApi` (§4.2).

### 4.7 System & safe mode (`systemApi.ts`)

Backend routes:

* `GET  /api/v1/health` – service health status.
* `GET  /api/v1/system/safe-mode` – read safe mode.
* `PUT  /api/v1/system/safe-mode` – update safe mode.

Typical functions:

* `getHealth()`
* `getSafeMode()`
* `updateSafeMode(payload)`

These functions are consumed by:

* The global health indicator (if any).
* Safe mode banner and Settings controls.

### 4.8 Users & API keys (`usersApi.ts`, `apiKeysApi.ts`)

Users:

* `GET /api/v1/users` – list users (admin only).

API keys:

* `GET    /api/v1/auth/api-keys` – list API keys.
* `POST   /api/v1/auth/api-keys` – create API key.
* `DELETE /api/v1/auth/api-keys/{api_key_id}` – revoke API key.

Typical functions:

* `listUsers(params)`
* `listApiKeys()`
* `createApiKey(payload)`
* `revokeApiKey(apiKeyId)`

These modules power administrative surfaces when present (e.g. API key management UI).

---

## 5. Typed models and schemas

The data layer uses TypeScript types from two primary sources:

1. **Generated types** (if available) under `src/generated-types/`.
2. **Hand‑written domain models** under `src/schema/`.

### 5.1 Generated types

* Generated types mirror the backend OpenAPI or Pydantic models.
* They are authoritative for field names and raw response shapes.
* They should not be imported directly in screens if they reveal unstable internal structure.

We may still use them in API modules:

```ts
import type { ApiWorkspace, ApiJob } from '@generated-types';

function toWorkspaceSummary(api: ApiWorkspace): WorkspaceSummary { /* ... */ }
```

### 5.2 Domain models

Domain models live under `src/schema/` and give us stable, UI‑centric types:

* `WorkspaceSummary`, `WorkspaceDetail`
* `DocumentSummary`, `DocumentDetail`
* `JobSummary`, `JobDetail`
* `Configuration`, `ConfigVersion`
* `SafeModeStatus`, etc.

API modules are responsible for mapping wire types into these domain models. This gives us:

* A place to **rename** awkward backend fields without touching every screen.
* A stable layer when backend schemas evolve.

---

## 6. Streaming NDJSON endpoints

ADE exposes streaming NDJSON logs for long‑running operations. The data layer wraps these as **streams of events**, not as React Query queries.

### 6.1 Endpoints

Current streaming endpoints:

* Build logs:

  * `GET /api/v1/builds/{build_id}/logs`

* Run logs:

  * `GET /api/v1/runs/{run_id}/logs`

These endpoints return `Content-Type: application/x-ndjson` (or similar) and stream events like:

```jsonl
{"type":"build.started","timestamp":"...","data":{...}}
{"type":"build.log","timestamp":"...","data":{"level":"info","message":"..."}}
{"type":"build.completed","timestamp":"...","data":{"status":"succeeded"}}
```

Exactly which event types exist is defined by the engine/backend; the frontend treats them as opaque `event.type` + `event.data`.

### 6.2 Streaming client abstraction

Streaming support lives in `src/shared/ndjson/` and exposes a small API, for example:

```ts
interface StreamOptions {
  signal?: AbortSignal;
}

type NdjsonEvent = { type: string; [key: string]: any };

function streamNdjson(
  path: string,
  options?: StreamOptions,
): AsyncIterable<NdjsonEvent> { /* ... */ }
```

On top of this, we can build domain‑specific helpers:

* `streamBuildEvents(buildId, options)`
* `streamRunEvents(runId, options)`

These:

* Handle reconnection/backoff if desired.
* Decode and normalise event payloads when appropriate.

### 6.3 Consumption in features

In the Config Builder workbench and job detail views, we use streaming helpers in React components, typically via `useEffect` and `AbortController`:

* Start streaming when the component mounts or when the run/build starts.
* Append log events to a console buffer in React state.
* Stop streaming when the component unmounts or the job/build reaches a terminal state.

**Important:**

* Streaming is **not** wrapped in React Query. Query state represents **snapshots**, whereas streams represent **ongoing event flows**.
* We must always supply an `AbortSignal` to avoid leaking connections.

---

## 7. Error handling and retry policy

Errors are handled consistently across API modules and hooks.

### 7.1 Normalised errors

`apiRequest` throws an `ApiError` with:

* `status` – HTTP status code.
* `message` – user‑facing message, if available.
* `code` – optional backend error code string.
* `details` – optional machine‑readable details.

API modules do **not** catch errors; they let them propagate to React Query or explicit callers.

### 7.2 React Query errors

React Query queries:

* Use the default `retry: 1` unless there is a reason to override.
* Surface errors to screens via `error` state. Screens decide whether to:

  * Show an inline `Alert`.
  * Render a full “Something went wrong” state.
  * Trigger a toast notification.

For certain status codes we follow specific patterns:

* `401 Unauthorized`:

  * A global handler may invalidate the session and redirect to `/login`.

* `403 Forbidden`:

  * Usually shown inline (e.g. “You don’t have permission to view jobs in this workspace.”).

* `404 Not Found`:

  * For detail pages, show a not‑found state rather than a generic error.

### 7.3 Mutations

Mutations (create/update/delete):

* Use React Query’s `useMutation`.

* On success:

  * Update or invalidate relevant query keys (`invalidateQueries`).
  * Show a success toast where appropriate.

* On error:

  * Show an inline error on the form if possible (e.g. validation errors).
  * Otherwise show a toast with `error.message`.

### 7.4 Network issues and timeouts

The HTTP client may implement:

* A global network error handler (e.g. show a “connection lost” banner).
* Optional timeouts for long‑running non‑streaming requests.

Streaming endpoints rely on:

* Aborting via `AbortController` when the user navigates away.
* A simple reconnection strategy if the connection drops unexpectedly (optional; can be done at the `streamNdjson` layer).

---

## 8. Adding new endpoints

When a new backend route is added, follow this process:

1. **Choose a module**

   * Pick an existing `*Api` module based on the resource (workspaces, documents, jobs, configs, roles, system, auth, users).
   * If truly new domain, create a new `xyzApi.ts`.

2. **Add a typed function**

   * Implement a thin, typed function in that module using `apiRequest`.
   * Map the wire response into an appropriate domain model if needed.

3. **Add or reuse a hook**

   * In the relevant feature folder, create `useXxxQuery` or `useXxxMutation` using the new API function.
   * Use consistent query keys and invalidation patterns.

4. **Update documentation**

   * Update this doc’s relevant section to include the new path and function.
   * If the new feature introduces a new domain concept, also update `01-domain-model-and-naming.md`.

By keeping this structure, the data layer stays predictable and easy to navigate—for humans and for tooling.