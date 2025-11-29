# 04 – Data layer & backend contracts

This document explains how `ade-web` talks to the ADE backend. It covers:

* the **data layer architecture** (HTTP client → API modules → React Query hooks),
* how `/api/v1/...` routes are **grouped by domain**,
* how we represent **runs, workspaces, documents, and configurations** on the frontend,
* and how we handle **streaming**, **errors**, and **caching**.

It’s the implementation-level companion to:

* `01-domain-model-and-naming.md` (concepts and naming), and
* the top-level `README.md` (UX overview).

Throughout this doc, **Run** is the primary execution unit. Backend routes use the REST plural `/runs`; in the UI and types we treat each run as `Run` with a `runId` field.

---

## 1. Mental model: the data layer stack

The data layer has three tiers:

1. **HTTP client**
   Knows how to call `/api/v1/...`, handle auth, and normalise errors.
2. **Domain API modules**
   Grouped by backend domain: `workspacesApi`, `documentsApi`, `runsApi`, etc.
3. **React Query hooks**
   Live in feature folders and wire API functions into components.

Flow:

```text
[ Screens / Features ]
        │
        ▼
[ React Query hooks ]   e.g. useWorkspaceRunsQuery, useDocumentsQuery
        │
        ▼
[ API modules ]         e.g. workspacesApi, documentsApi, runsApi
        │
        ▼
[ HTTP client ]         shared/api/httpClient.ts
        │
        ▼
[ ADE API ]             /api/v1/...
```

Design goals:

* **Single source of truth per endpoint** – there is one function that owns each route.
* **Type-safe** – all responses are typed and mapped into domain models.
* **Predictable caching** – React Query keys follow consistent patterns.
* **Clear boundaries**:

  * Screens know about **hooks + domain types**.
  * Hooks know about **API modules**.
  * API modules know about **HTTP + paths**.

> **Rule:** UI code never calls `fetch` directly. All network calls go through the shared HTTP client.

---

## 2. HTTP client

All HTTP calls go through `src/shared/api/httpClient.ts` (or equivalent).

### 2.1 Responsibilities

The HTTP client handles:

* Building URLs under the `/api` proxy (e.g. `/api/v1/...`).
* Serialising request bodies (JSON by default).
* Attaching credentials (cookies, headers) as needed.
* Parsing JSON responses.
* Exposing streaming bodies (for NDJSON).
* Mapping non‑2xx responses into a unified `ApiError`.

It deliberately does **not** know about workspaces, runs, configs, etc. Domain logic lives in API modules.

### 2.2 Shape & behaviour

Minimal shape:

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

* API modules **only** use `apiRequest`. No module calls `fetch` directly.
* Any non‑2xx status results in an `ApiError` being thrown, with a best-effort `message`.

### 2.3 Auth, 401, and 403

* **401 (Unauthenticated)**
  Handled globally (session invalidation, redirect to `/login`, etc.).
* **403 (Forbidden)**
  Exposed to the UI as a permissions error; screens decide how to present it.

The HTTP client itself does not refresh tokens; that logic lives in the auth/session layer and React Query hooks.

---

## 3. React Query

React Query is our fetch/cache/refresh engine.

### 3.1 Query client defaults

`AppProviders` creates a single `QueryClient` with defaults such as:

* `retry: 1` – ADE errors are usually not transient.
* `staleTime: 30_000` – many reads can be reused for ~30 seconds.
* `refetchOnWindowFocus: false` – avoids surprise reloads when switching tabs.

Individual queries can override these (for health checks, etc.).

### 3.2 Query keys

Good keys are:

* **Stable** – same inputs → same key.
* **Descriptive** – easy to read in devtools.
* **Scoped** – global → workspace → resource.
* **Canonical** – objects are serialised in a consistent way.

Avoid inline objects created in render as part of keys. Instead, use small helpers that canonicalise parameters.

Example patterns:

* Session & permissions

  * `['session']`
  * `['permissions', 'effective']`

* Workspaces

  * `['workspaces']`
  * `['workspace', workspaceId]`
  * `['workspace', workspaceId, 'members']`
  * `['workspace', workspaceId, 'roles']`

* Documents

  * `['workspace', workspaceId, 'documents', canonicaliseDocumentParams(params)]`
  * `['workspace', workspaceId, 'document', documentId]`
  * `['workspace', workspaceId, 'document', documentId, 'sheets']`

* Runs

  * `['workspace', workspaceId, 'runs', canonicaliseRunsFilters(filters)]`
    (workspace ledger from `/workspaces/{id}/runs`)
  * `['run', runId]`
    (canonical detail via `/runs/{run_id}`)
  * `['workspace', workspaceId, 'run', runId]`
    (optional workspace-scoped variant)
  * `['run', runId, 'outputs']`

* Configurations

  * `['workspace', workspaceId, 'configurations']`
  * `['workspace', workspaceId, 'configuration', configurationId]`
  * `['workspace', workspaceId, 'configuration', configurationId, 'versions']`
  * `['workspace', workspaceId, 'configuration', configurationId, 'files']`

* System

  * `['system', 'safe-mode']`
  * `['system', 'health']`

Example helper:

```ts
export const queryKeys = {
  workspaceRuns: (workspaceId: string, filters: RunsFilters) => [
    'workspace',
    workspaceId,
    'runs',
    canonicaliseRunsFilters(filters),
  ],
  run: (runId: string) => ['run', runId],
  documents: (workspaceId: string, params: DocumentFilters) => [
    'workspace',
    workspaceId,
    'documents',
    canonicaliseDocumentParams(params),
  ],
};
```

### 3.3 Query & mutation hooks

Per domain:

* API modules export **plain functions**, e.g.
  `listWorkspaceRuns`, `uploadDocument`, `activateConfiguration`.
* Feature folders wrap those functions in **React Query hooks**, e.g.

  * Queries: `useWorkspaceRunsQuery(workspaceId, filters)`, `useDocumentsQuery(workspaceId, filters)`
  * Mutations: `useCreateWorkspaceRunMutation(workspaceId)`, `useUploadDocumentMutation(workspaceId)`

Hooks live next to the screens that use them (e.g. `features/workspace-shell/runs/useWorkspaceRunsQuery.ts`) and depend only on the shared API modules.

---

## 4. Domain API modules

Domain modules live under `src/shared/api/`. Each one:

* owns a set of related endpoints, and
* exposes typed functions named `<verb><Noun>`.

Examples:

* `authApi`, `permissionsApi`, `rolesApi`
* `workspacesApi`, `documentsApi`, `runsApi`
* `configurationsApi`, `buildsApi`
* `systemApi`, `usersApi`, `apiKeysApi`

You should be able to navigate from a backend route to its module and function without guessing.

### 4.1 Auth & session (`authApi`)

**Responsibilities**

* Initial instance setup.
* Login/logout (password + SSO).
* Session + “who am I?”.

**Key routes**

Setup:

* `GET  /api/v1/setup/status` – initial setup status.
* `POST /api/v1/setup`        – complete first admin setup.

Session:

* `POST   /api/v1/auth/session`         – create session.
* `GET    /api/v1/auth/session`         – read session (canonical “who am I?”).
* `POST   /api/v1/auth/session/refresh` – refresh session.
* `DELETE /api/v1/auth/session`         – logout.

Auth providers:

* `GET /api/v1/auth/providers`       – configured auth providers.
* `GET /api/v1/auth/sso/login`       – start SSO login (302 redirect).
* `GET /api/v1/auth/sso/callback`    – finish SSO login.

Current user:

* `GET /api/v1/users/me` or `GET /api/v1/auth/me` – authenticated user (id, email, name).

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
* `useLoginMutation()`
* `useLogoutMutation()`

---

### 4.2 Permissions (`permissionsApi`)

**Responsibilities**

* Permission catalog.
* Effective permissions for current user.
* Point-in-time permission checks.

**Key routes**

* `GET  /api/v1/permissions`          – catalog.
* `GET  /api/v1/me/permissions`       – effective permissions.
* `POST /api/v1/me/permissions/check` – check specific permissions.

**Example functions**

* `listPermissions()`
* `readEffectivePermissions()`
* `checkPermissions(request)`

Hooks:

* `usePermissionCatalogQuery()`
* `useEffectivePermissionsQuery()`

---

### 4.3 Global roles & assignments (`rolesApi`)

Global roles are separate from permissions, and parallel the workspace-scoped roles API.

**Responsibilities**

* Global roles (definitions).
* Global role assignments.

**Key routes**

Roles:

* `GET    /api/v1/roles`
* `POST   /api/v1/roles`
* `GET    /api/v1/roles/{role_id}`
* `PATCH  /api/v1/roles/{role_id}`
* `DELETE /api/v1/roles/{role_id}`

Assignments:

* `GET    /api/v1/role-assignments`
* `POST   /api/v1/role-assignments`
* `DELETE /api/v1/role-assignments/{assignment_id}`

**Example functions**

* `listGlobalRoles()`
* `createGlobalRole(payload)`
* `readGlobalRole(roleId)`
* `updateGlobalRole(roleId, patch)`
* `deleteGlobalRole(roleId)`
* `listGlobalRoleAssignments()`
* `createGlobalRoleAssignment(payload)`
* `deleteGlobalRoleAssignment(assignmentId)`

Hooks:

* `useGlobalRolesQuery()`
* `useGlobalRoleAssignmentsQuery()`

---

### 4.4 Workspaces & membership (`workspacesApi`)

**Responsibilities**

* Workspace lifecycle and metadata.
* Membership.
* Workspace roles and assignments.
* Default workspace.

**Key routes**

Workspaces:

* `GET    /api/v1/workspaces`
* `POST   /api/v1/workspaces`
* `GET    /api/v1/workspaces/{workspace_id}`
* `PATCH  /api/v1/workspaces/{workspace_id}`
* `DELETE /api/v1/workspaces/{workspace_id}`
* `POST   /api/v1/workspaces/{workspace_id}/default`

Members:

* `GET    /api/v1/workspaces/{workspace_id}/members`
* `POST   /api/v1/workspaces/{workspace_id}/members`
* `DELETE /api/v1/workspaces/{workspace_id}/members/{membership_id}`
* `PUT    /api/v1/workspaces/{workspace_id}/members/{membership_id}/roles`

Workspace roles & assignments:

* `GET    /api/v1/workspaces/{workspace_id}/roles`
* `GET    /api/v1/workspaces/{workspace_id}/role-assignments`
* `POST   /api/v1/workspaces/{workspace_id}/role-assignments`
* `DELETE /api/v1/workspaces/{workspace_id}/role-assignments/{assignment_id}`

**Example functions**

Workspaces:

* `listWorkspaces()`
* `createWorkspace(payload)`
* `readWorkspace(workspaceId)`
* `updateWorkspace(workspaceId, patch)`
* `deleteWorkspace(workspaceId)`
* `setDefaultWorkspace(workspaceId)`

Members:

* `listWorkspaceMembers(workspaceId)`
* `addWorkspaceMember(workspaceId, payload)`
* `removeWorkspaceMember(workspaceId, membershipId)`
* `updateWorkspaceMemberRoles(workspaceId, membershipId, roles)`

Workspace roles:

* `listWorkspaceRoles(workspaceId)`
* `listWorkspaceRoleAssignments(workspaceId)`
* `createWorkspaceRoleAssignment(workspaceId, payload)`
* `deleteWorkspaceRoleAssignment(workspaceId, assignmentId)`

Hooks:

* `useWorkspacesQuery()`
* `useWorkspaceQuery(workspaceId)`
* `useWorkspaceMembersQuery(workspaceId)`
* `useWorkspaceRolesQuery(workspaceId)`

---

### 4.5 Documents (`documentsApi`)

**Responsibilities**

* Document upload & listing (per workspace).
* Document metadata & download.
* Sheet metadata for spreadsheet-like inputs.

**Key routes**

* `GET    /api/v1/workspaces/{workspace_id}/documents`
* `POST   /api/v1/workspaces/{workspace_id}/documents`
* `GET    /api/v1/workspaces/{workspace_id}/documents/{document_id}`
* `DELETE /api/v1/workspaces/{workspace_id}/documents/{document_id}`
* `GET    /api/v1/workspaces/{workspace_id}/documents/{document_id}/download`
* `GET    /api/v1/workspaces/{workspace_id}/documents/{document_id}/sheets`

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

---

### 4.6 Runs (`runsApi`)

**Responsibilities**

* Workspace run ledger (all runs in a workspace).
* Per-run outputs and log files.
* Config-triggered runs (e.g. from the Configuration Builder).
* Run NDJSON event streams.
* A **run-centric** API once you have a `runId`.

The backend uses `/runs` for all execution units. On the frontend, a Run is globally identified by `runId`.

**Two key ideas:**

1. Use workspace-scoped `/workspaces/{id}/runs` for **listing/creating** runs.
2. Use global `/runs/{run_id}` for **detail, outputs, and logs** once you know `runId`.

#### Workspace run ledger

* `GET  /api/v1/workspaces/{workspace_id}/runs` – list runs in a workspace.
* `POST /api/v1/workspaces/{workspace_id}/runs` – create a new run.
* `GET  /api/v1/workspaces/{workspace_id}/runs/{run_id}` – optional workspace-scoped detail (for tenancy enforcement).

#### Canonical run detail & assets (global)

* `GET  /api/v1/runs/{run_id}` – canonical run detail.
* `GET  /api/v1/runs/{run_id}/logfile` – download telemetry log.
* `GET  /api/v1/runs/{run_id}/logfile` – download log file.
* `GET  /api/v1/runs/{run_id}/logs` – NDJSON event stream.
* `GET  /api/v1/runs/{run_id}/outputs` – list outputs.
* `GET  /api/v1/runs/{run_id}/outputs/{output_path}` – download specific output.

#### Configuration-scoped triggers

* `POST /api/v1/configurations/{configuration_id}/runs` – start a run for a configuration.

**Example functions**

Workspace ledger:

* `listWorkspaceRuns(workspaceId, params)`
* `createWorkspaceRun(workspaceId, payload)`
* `readWorkspaceRun(workspaceId, runId)`  // use only if backend enforces workspace scopes

Run-centric:

* `readRun(runId)`
* `listRunOutputs(runId)`
* `downloadRunOutput(runId, outputPath)`
* `downloadRunArtifact(runId)`
* `downloadRunLogFile(runId)`
* `streamRunLogs(runId)`   // NDJSON event stream

Configuration triggers:

* `createConfigurationRun(configurationId, payload)`  // wraps `/configurations/{id}/runs`

Hooks:

* `useWorkspaceRunsQuery(workspaceId, filters)`
* `useRunQuery(runId)`                 // canonical detail
* Optional: `useWorkspaceRunQuery(workspaceId, runId)`
* `useCreateWorkspaceRunMutation(workspaceId)`
* `useCreateConfigurationRunMutation(configurationId)`

Streaming:

* `useRunLogsStream(runId)` – live run console and events.

---

### 4.7 Configurations & builds (`configurationsApi`, `buildsApi`)

**Responsibilities**

* Configuration entities & versions.
* Configuration file tree (for the workbench).
* Builds & build logs (mostly implicit via runs).

> For day‑to‑day flows, builds are **implicit**: starting a run will rebuild the environment if needed. The explicit `/builds` API is mainly for admin/backfill/debug flows.

#### Configuration entities

* `GET  /api/v1/workspaces/{workspace_id}/configurations`
* `POST /api/v1/workspaces/{workspace_id}/configurations`
* `GET  /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}`
* `GET  /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/versions`
* `POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/activate`
* `POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/deactivate`
* `POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/publish`
* `POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/validate`
* `GET  /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/export`

#### Configuration file tree

* `GET    /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files`
* `GET    /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}`
* `PUT    /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}`
* `PATCH  /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}`
* `DELETE /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}`
* `POST   /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/directories/{directory_path}`
* `DELETE /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/directories/{directory_path}`

#### Builds

* `POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds`
* `GET  /api/v1/builds/{build_id}`
* Build logs are observed via the run event stream (`/runs/{run_id}/events?stream=true`, `console.line` with `scope:"build"`).

The backend may rebuild environments automatically when:

* a run starts,
* the environment is missing or stale,
* content has changed, or
* a run includes `force_rebuild` (`RunOptions.forceRebuild`).

**Example functions**

Configurations:

* `listConfigurations(workspaceId)`
* `createConfiguration(workspaceId, payload)`
* `readConfiguration(workspaceId, configurationId)`
* `listConfigurationVersions(workspaceId, configurationId)`
* `activateConfiguration(workspaceId, configurationId)`
* `deactivateConfiguration(workspaceId, configurationId)`
* `publishConfiguration(workspaceId, configurationId)`
* `validateConfiguration(workspaceId, configurationId, payload)`
* `exportConfiguration(workspaceId, configurationId)`

Config files:

* `listConfigurationFiles(workspaceId, configurationId)`
* `readConfigurationFile(workspaceId, configurationId, filePath)`
* `upsertConfigurationFile(workspaceId, configurationId, filePath, content, options?)`
  (including ETag preconditions)
* `renameConfigurationFile(workspaceId, configurationId, filePath, newPath)`
* `deleteConfigurationFile(workspaceId, configurationId, filePath)`
* `createConfigDirectory(workspaceId, configurationId, dirPath)`
* `deleteConfigDirectory(workspaceId, configurationId, dirPath)`

Builds:

* `createBuild(workspaceId, configurationId, options)`  // returns `buildId`
* `readBuild(buildId)` (for metadata/status; events are streamed via runs)

Hooks:

* `useConfigurationsQuery(workspaceId)`
* `useConfigurationQuery(workspaceId, configurationId)`
* `useConfigurationVersionsQuery(workspaceId, configurationId)`
* `useConfigurationFilesQuery(workspaceId, configurationId)`
* `useCreateBuildMutation(workspaceId, configurationId)` (triggers build; observe via run event stream)

---

### 4.8 System & safe mode (`systemApi`)

**Responsibilities**

* System health.
* Safe mode state.

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

---

### 4.9 Users & API keys (`usersApi`, `apiKeysApi`)

**Responsibilities**

* User directory (admin).
* API key management for users.

**Key routes**

Users:

* `GET /api/v1/users` – list all users (admin).

API keys:

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

## 5. Types, schemas, and mapping

The data layer uses TypeScript types from two places:

1. **Generated types** (if available) in `src/generated-types/`
2. **Domain models** in `src/schema/`

### 5.1 Generated types (wire format)

Generated types:

* Mirror backend schemas exactly (field names and nesting).
* Are authoritative for the **wire format**.
* May include details we don’t want to expose directly to screens.

They are typically used in:

* API modules, and
* mapping functions that convert to UI-facing types.

### 5.2 Domain models (UI-facing)

Domain models in `src/schema/` define shapes the UI actually consumes, e.g.:

* `WorkspaceSummary`, `WorkspaceDetail`
* `DocumentSummary`, `DocumentDetail`
* `RunSummary`, `RunDetail`
* `Configuration`, `ConfigVersion`
* `SafeModeStatus`, ...

API modules handle mapping:

```ts
function toRunSummary(apiRun: ApiRun): RunSummary {
  // ...
}
```

Standard helpers in `schema/` keep snake_case out of the rest of the app:

* `fromApiRun(apiRun: ApiRun): Run` – translates `run_id` → `runId`, normalises status/timestamps.
* `fromApiConfiguration(apiConfig: ApiConfiguration): Configuration` – translates `configuration_id` → `configurationId`, etc.

Benefits:

* Screens & hooks only see **camelCase**, front-end-friendly types.
* Backend field changes are localised to mapping functions, not scattered across features.

---

## 6. Streaming events (SSE + NDJSON archive)

Run streams emit `AdeEvent` envelopes (live over SSE; persisted as NDJSON).

Treat these as **ordered event streams**, not snapshot queries.

### 6.1 Event envelope

All events share a common envelope; only the tail `payload` varies per `type`:

```jsonc
{
  "type": "console.line",                // e.g. run.started, build.completed, console.line
  "event_id": "evt_01JK3J0YRKJ...",
  "created_at": "2025-11-26T12:00:00Z",
  "sequence": 42,                        // monotonic within one run/build stream

  "workspace_id": "ws_1",
  "configuration_id": "cfg_1",
  "build_id": "b_1",
  "run_id": "run_1",

  "source": "api",

  "payload": {                           // type-specific payload
    "scope": "run",
    "stream": "stdout",
    "message": "Installing engine…"
  }
}
```

Additive changes (new event types, optional fields) are allowed. Breaking changes require a new schema or major version.

### 6.2 Event taxonomy & frontend usage

Key families:

* **Run lifecycle (`run.*`)**

  * `run.queued`, `run.started`
  * `run.phase.started` / `run.phase.completed`
  * `run.completed` (carries `run_summary` used for summary stats)

* **Table & validation**

  * `run.table.summary` – per-table metrics
  * `run.validation.issue` – fine-grained issues (optional)
  * `run.validation.summary` – aggregated counts

* **Console**

  * `console.line` – ordered stdout/stderr lines; `payload.scope` distinguishes build vs run

* **Build lifecycle (`build.*`)**

  * `build.created`, `build.started`
  * `build.phase.started` / `build.phase.completed`
  * `build.completed` (environment status/version)

* **Errors**

  * Stream-level `error` events for transport-level failures.

UI rules:

* Use `sequence` for ordering when transport may deliver events slightly out of order.
* Prefer the run event stream (`/runs/{id}/events?stream=true`) for live consoles; use archived NDJSON (`/runs/{id}/logfile`) for offline replay.
* Derive progress and summaries incrementally from lifecycle + validation events instead of waiting solely on `run.completed`.

### 6.3 Streaming helper

The browser-native `EventSource` API is used for live run streams:

```ts
const es = new EventSource(`/api/v1/runs/${runId}/events?stream=true`);
es.onmessage = (msg) => {
  const event = JSON.parse(msg.data); // AdeEvent envelope with payload
  // ...apply to reducer / UI
};
es.onerror = () => es.close();
```

Characteristics:

* Close the stream on unmount or when the user hides the console.
* Treat `run.completed` as terminal; callers can close the stream after it arrives.
* For post-run analysis, `events.ndjson` is still available via `/runs/{run_id}/logfile`.

### 6.4 Run & build streams in practice

Used by:

* **Configuration Builder**

  * `POST /api/v1/configurations/{configuration_id}/runs` then `GET /api/v1/runs/{run_id}/events?stream=true`
    (emits `build.*`, `console.line` with `scope`, `run.*`, `run.table.*`, `run.validation.*`)

* **Run consoles / details**

  * `GET /api/v1/runs/{run_id}/events?stream=true`
    (replay then live-stream `AdeEvent` envelopes; use `after_sequence` to resume)

Because environments are usually rebuilt automatically when runs start (or when `force_rebuild` is set), the build stream is primarily for explicit `/builds` workflows and debugging. Normal workbench/test flows rely on the run stream.

UI components (e.g. workbench console, run detail):

* Append console lines from `console.line` events.
* Update status/progress from lifecycle + validation events.

### 6.5 Cancellation & error UX

When using streaming helpers:

* Always create an `AbortController` in the component.
* Cancel the stream on unmount or when the user closes the console.

On errors:

* Show a console-local banner (“Stream disconnected”) rather than crashing the whole screen.
* Optionally provide a “Retry stream” button.

React Query is **not** used for NDJSON streams; they’re long-lived event flows, not snapshot fetches.

---

## 7. Error handling & retry

### 7.1 `ApiError`

Every failed HTTP call throws an `ApiError`:

* `status` – HTTP status code.
* `message` – user-friendly message, if available.
* `code` – optional backend machine code.
* `details` – optional structured payload.

API modules generally **do not** catch these; they let React Query and UI code decide how to present them.

### 7.2 Where & how to show errors

Guidelines:

* **Mutations (buttons/forms)**

  * Show a toast for one-off actions (start run, save file).
  * Show inline error text for validation problems.

* **List/detail screens**

  * Show an inline `Alert` if initial load fails.
  * For critical surfaces, use a full “Something went wrong” state with a retry button.

* **Streaming consoles**

  * Show a local banner when the stream fails.
  * Do not crash the surrounding screen.

### 7.3 Retry policy

Global default: `retry: 1`.

Set `retry: false` for:

* Permission endpoints (403 → user action required, not network flakiness).
* Validation endpoints where retrying won’t change the result.

Mutations should rely on **explicit user retries** (“Run again”, “Save again”) rather than automatic retry.

---

## 8. Contracts, invariants & adding endpoints

### 8.1 Invariants

To keep the data layer predictable:

* **Single owner per endpoint**

  * Each backend route maps to exactly one function in one module.
  * Screens/hooks never embed raw URLs.

* **Explicit types**

  * No `any` for responses.
  * Map wire types → domain models in one place.

* **Stable query keys**

  * Canonicalise params (e.g. sort object keys before serialising).
  * Use `queryKeys.*` helpers instead of ad-hoc key construction.

* **No raw `fetch`**

  * Only the HTTP client talks to `fetch` / XHR.
  * Auth, error handling, and logging stay consistent.

* **Run-centric language**

  * Everything that executes is a **run** in UI types and hooks.
  * Once you have a `runId`, favour global `/runs/{run_id}` endpoints for detail/logs/outputs.
  * Workspace IDs are primarily for listing/creating runs, not reading them.

* **Backend-agnostic**

  * ADE Web depends on **behaviour + shapes** of `/api/v1/...`, not a specific implementation.
  * Any backend that honours these contracts can power the UI.

### 8.2 Adding a new endpoint (checklist)

When backend adds a route:

1. **Pick a module**

   * Does it belong to workspaces, documents, runs, configurations, roles, auth, system, …?
   * If no good fit, create a new module in `shared/api`.

2. **Add a typed function**

   * Implement `<verb><Noun>` using `apiRequest`.
   * Map the wire type into a domain model if needed.

3. **Add a hook**

   * Create `useXxxQuery` or `useXxxMutation` in the relevant feature folder.
   * Use existing query key patterns and invalidate affected keys on write.

4. **Update types**

   * Add/adjust domain types in `schema/`.
   * Wire in generated types if available.

5. **Update docs**

   * List the route and function in the relevant section of this file.
   * If it introduces a new concept, also update `01-domain-model-and-naming.md`.

6. **Add tests**

   * Unit tests for the API module function (mock `apiRequest`).
   * Integration/feature tests where appropriate.

Sticking to these rules keeps the data layer small, understandable, and easy to extend—for both humans and agents—while the ADE backend evolves underneath.
