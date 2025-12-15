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
[ HTTP client ]         shared/api/client.ts
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

All HTTP calls go through `src/shared/api/client.ts`, a typed `openapi-fetch` client backed by the generated OpenAPI schema (`@schema`). Middleware attaches auth/CSRF headers, and non‑2xx responses are normalised into `ApiError`.

### 2.1 Responsibilities

The HTTP client handles:

* Building URLs under the `/api` proxy (e.g. `/api/v1/...`).
* Serialising request bodies (JSON by default).
* Attaching credentials (bearer tokens, CSRF headers) as needed.
* Parsing JSON responses with generated types.
* Exposing streaming bodies (for NDJSON).
* Mapping non‑2xx responses into a unified `ApiError`.

It deliberately does **not** know about workspaces, runs, configs, etc. Domain logic lives in API modules.

### 2.2 Shape & behaviour

Rules:

* API modules use the shared `client` instance; no module calls `fetch` directly.
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
  * `['run', runId, 'output']`

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
* `POST   /api/v1/auth/session/refresh` – refresh session.
* `DELETE /api/v1/auth/session`         – logout.
* `GET    /api/v1/me/bootstrap`         – session bootstrap (profile, global roles/permissions, workspaces).

Auth providers:

* `GET /api/v1/auth/providers`             – configured auth providers.
* `GET /api/v1/auth/sso/{provider}/authorize` – start SSO login (302 redirect).
* `GET /api/v1/auth/sso/{provider}/callback`  – finish SSO login.

**Example functions**

* `readSetupStatus()`
* `completeSetup(payload)`
* `listAuthProviders()`
* `createSession(credentials)`
* `refreshSession()`
* `deleteSession()`
* `fetchSession()` (wraps `/me/bootstrap`)

Hooks:

* `useSetupStatusQuery()`
* `useSessionQuery()`
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

* `GET    /api/v1/rbac/roles`
* `POST   /api/v1/rbac/roles`
* `GET    /api/v1/rbac/roles/{role_id}`
* `PATCH  /api/v1/rbac/roles/{role_id}`
* `DELETE /api/v1/rbac/roles/{role_id}`

Assignments:

* `GET    /api/v1/rbac/role-assignments`
* `POST   /api/v1/rbac/role-assignments`
* `DELETE /api/v1/rbac/role-assignments/{assignment_id}`
* `GET    /api/v1/users/{user_id}/roles`
* `PUT    /api/v1/users/{user_id}/roles/{role_id}`
* `DELETE /api/v1/users/{user_id}/roles/{role_id}`

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
* `PUT    /api/v1/workspaces/{workspace_id}/default`

Members:

* `GET    /api/v1/workspaces/{workspace_id}/members`
* `POST   /api/v1/workspaces/{workspace_id}/members`
* `PUT    /api/v1/workspaces/{workspace_id}/members/{user_id}`
* `DELETE /api/v1/workspaces/{workspace_id}/members/{user_id}`

Workspace roles & assignments:

* Workspace role definitions reuse `/api/v1/rbac/roles` with `scope=workspace`.
* Role bindings are managed via workspace members (`/api/v1/workspaces/{workspace_id}/members`).

**Example functions**

Workspaces:

* `listWorkspaces()`
* `createWorkspace(payload)`
* `readWorkspace(workspaceId)`
* `updateWorkspace(workspaceId, patch)`
* `deleteWorkspace(workspaceId)`
* `setDefaultWorkspace(workspaceId)`
* `useSetDefaultWorkspaceMutation()`

Members:

* `listWorkspaceMembers(workspaceId)`
* `addWorkspaceMember(workspaceId, payload)`
* `removeWorkspaceMember(workspaceId, userId)`
* `updateWorkspaceMemberRoles(workspaceId, userId, roles)`

Workspace roles:

* `listWorkspaceRoles(workspaceId)`

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
* Per-run input/output downloads and event logs.
* Config-triggered runs (e.g. from the Configuration Builder).
* Run NDJSON event streams.
* A **run-centric** API once you have a `runId`.

The backend uses `/runs` for all execution units. On the frontend, a Run is globally identified by `runId`.

**Two key ideas:**

1. Run creation is **configuration-scoped**: `POST /configurations/{id}/runs`.
2. Use workspace-scoped `/workspaces/{id}/runs` for **listing** runs.
3. Use global `/runs/{run_id}` for **detail, events, output, and logs** once you know `runId`.

#### Workspace run ledger (list only)

* `GET  /api/v1/workspaces/{workspace_id}/runs` – list runs in a workspace.

#### Canonical run detail & assets (global)

- `GET  /api/v1/runs/{run_id}` – canonical run detail.
- `GET  /api/v1/runs/{run_id}/events` – poll/stream events; `GET /runs/{run_id}/events/download` downloads NDJSON (legacy `/logs` alias).
- `GET  /api/v1/runs/{run_id}/input` – input metadata; `GET /runs/{run_id}/input/download` downloads the source file.
- `GET  /api/v1/runs/{run_id}/output` – output metadata; `GET /runs/{run_id}/output/download` downloads once ready (returns 409 if not).
- Legacy outputs endpoints (`/runs/{run_id}/outputs*`) remain for compatibility and map to the singular output.

#### Configuration-scoped triggers

* `POST /api/v1/configurations/{configuration_id}/runs` – start a run for a configuration.

**Example functions**

Workspace ledger:

* `listWorkspaceRuns(workspaceId, params)`

Run-centric:

- `readRun(runId)`
- `listRunOutputs(runId)`
- `downloadRunOutput(runId, outputPath)`
- `downloadRunArtifact(runId)`
- `downloadRunLogFile(runId)`

Configuration triggers:

* `createConfigurationRun(configurationId, payload)`  // wraps `/configurations/{id}/runs`

Hooks:

* `useWorkspaceRunsQuery(workspaceId, filters)`
* `useRunQuery(runId)`                 // canonical detail
* `useCreateConfigurationRunMutation(configurationId)`

Streaming:

- `useRunLogsStream(runId)` – live run console and events.

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
* `PUT    /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/directories/{directory_path}`
* `DELETE /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/directories/{directory_path}`

Directory creation is idempotent: `PUT` returns `201` when the folder is first created and `200` if it already exists.

#### Builds

* `POST /api/v1/workspaces/{workspace_id}/configurations/{configuration_id}/builds`
* `GET  /api/v1/builds/{build_id}`
* Build logs are observed via the run event stream (`/runs/{run_id}/events/stream`, `console.line` with `data.scope:"build"`).

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
* API key management for self-service and admins.

**Key routes**

Users:

* `GET /api/v1/users` – list all users (admin).

API keys:

* Self-service: `GET /api/v1/me/api-keys`, `POST /api/v1/me/api-keys`, `DELETE /api/v1/me/api-keys/{api_key_id}`
* Admin (global): `GET /api/v1/api-keys`, `POST /api/v1/api-keys`, `GET /api/v1/api-keys/{api_key_id}`, `DELETE /api/v1/api-keys/{api_key_id}`
* Admin (per user): `GET /api/v1/users/{user_id}/api-keys`, `POST /api/v1/users/{user_id}/api-keys`, `DELETE /api/v1/users/{user_id}/api-keys/{api_key_id}`

**Example functions**

* Users: `listUsers(params?)`
* API keys (self): `listMyApiKeys(params?)`, `createMyApiKey(payload)`, `revokeMyApiKey(apiKeyId)`
* API keys (admin): `listApiKeys(params?)`, `getApiKey(apiKeyId)`, `createApiKey(payload)`, `revokeApiKey(apiKeyId)`
* API keys (per user): `listUserApiKeys(userId, params?)`, `createUserApiKey(userId, payload)`, `revokeUserApiKey(userId, apiKeyId)`

Hooks:

* `useUsersQuery()`
* (API keys hooks not yet defined; call `@shared/api-keys/api` directly from screens as needed.)

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
* `Configuration`
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

The app supports **one-shot job streaming** for the workbench console, plus an NDJSON archive for post-run analysis.

### 6.1 Workbench job stream (preferred)

The Configuration Builder uses a single SSE stream that covers the full job lifecycle (environment build + run):

* `GET /api/v1/configurations/{configuration_id}/jobs/stream`

This stream is intentionally **live-only**:

* No replay.
* No resume (`Last-Event-ID` is ignored / unsupported).
* The UI keeps a bounded in-memory tail (e.g. last 2k lines) and relies on archived logs for full history.

### 6.2 SSE event types

The server uses **standard SSE `event:` dispatch** and keeps high-volume output as plain text.

* `event: meta` (JSON) – emitted once at connect time

  ```jsonc
  {
    "id": 0,
    "ts": "2025-12-15T19:45:05.637Z",
    "scope": "meta",
    "level": "info",
    "text": "connected",
    "details": {
      "jobId": "019b238b-8836-767d-a452-094a81a917eb",
      "workspaceId": "019b2334-e5e8-75c5-b342-734630c9531a",
      "configurationId": "019b2380-78bf-76ee-8b22-60ba3d86062c",
      "buildId": "019b238b-884a-712e-982a-2765b9c147b2"
    }
  }
  ```

* `event: log` (plain text) – high-volume console output

  Data is tab-separated to avoid JSON parsing overhead:

  ```
  <scope>\t<level>\t<ts>\t<message>
  ```

  Example:

  ```
  build\tinfo\t2025-12-15T19:45:08.287Z\tCollecting pip
  ```

* `event: done` (JSON) – emitted once when the job completes

  `details` contains the final run completion payload (status, execution timing, artifacts).

### 6.3 NDJSON archive

For full-fidelity logs and offline inspection, the backend still persists NDJSON event logs and exposes them via the run download endpoints (e.g. `GET /api/v1/runs/{run_id}/events/download`).

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
  * Once you have a `runId`, favour global `/runs/{run_id}` endpoints for detail/events/output downloads.
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
