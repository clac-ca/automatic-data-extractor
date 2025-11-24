# 04-data-layer-and-backend-contracts

**Purpose:** Show how the frontend talks to `/api/v1/...`, how it uses React Query, and how streaming works.

### 1. Overview

* Relationship to backend: ADE Web is backend-agnostic but expects certain API contracts.
* High-level goal: each domain has a clear API module + hooks.

### 2. React Query configuration

* `AppProviders`:

  * Single `QueryClient` instance via `useState`.
  * Default options (`retry`, `staleTime`, `refetchOnWindowFocus`).

* Pattern:

  * Query hooks wrap QueryClient with strongly typed API functions.
  * Mutations for writes.

### 3. HTTP client pattern

* Describe the standard fetch wrapper:

  * JSON parse, error handling, auth headers.
  * Optional base URL (`/api` via Vite proxy).

* Structure:

  * Domain modules: `authApi.ts`, `workspacesApi.ts`, `documentsApi.ts`, `jobsApi.ts`, `configsApi.ts`, `buildsApi.ts`, `runsApi.ts`, `rolesApi.ts`, etc.

* Function naming:

  * `listWorkspaces`, `createWorkspace`, `listDocuments`, `uploadDocument`, `listJobs`, `submitJob`, `listConfigurations`, `activateConfiguration`, etc.

### 4. Mapping ADE API routes to modules

Group the routes (from your CSV) by domain:

* **Auth & session (`authApi`)**

  * `/api/v1/auth/session`, `/auth/session/refresh`, `/auth/sso/login`, `/auth/sso/callback`, `/auth/me`, `/users/me`, `/setup`, `/setup/status`, auth providers, API keys.

* **Permissions & roles (`rolesApi`)**

  * `/api/v1/permissions`, `/me/permissions`, `/me/permissions/check`.
  * Global roles and role assignments: `/roles`, `/role-assignments`.

* **Workspaces (`workspacesApi`)**

  * `/api/v1/workspaces` CRUD.
  * `/workspaces/{workspace_id}/default`.
  * `/workspaces/{workspace_id}/members` (+ roles).
  * `/workspaces/{workspace_id}/roles`.
  * `/workspaces/{workspace_id}/role-assignments`.

* **Documents (`documentsApi`)**

  * `/workspaces/{workspace_id}/documents`.
  * `/documents/{document_id}` CRUD, `/download`, `/sheets`.

* **Jobs & runs (`jobsApi`, `runsApi`)**

  * `/workspaces/{workspace_id}/jobs` (ledger, artifact, logs, outputs).
  * `/api/v1/runs/{run_id}...` if used directly.

* **Configurations & builds (`configsApi`, `buildsApi`)**

  * Workspace configs: `/workspaces/{workspace_id}/configurations` and `/versions`.
  * Activation/publish: `/activate`, `/deactivate`, `/publish`.
  * Files/directories: `/files`, `/files/{file_path}`, `/directories/{directory_path}`, `/export`.
  * Builds: `/workspaces/{workspace_id}/configs/{config_id}/builds` & `/builds/{build_id}`.

* **System & safe mode (`systemApi`)**

  * `/api/v1/health`, `/api/v1/system/safe-mode`.

Explain:

* Not every endpoint is necessarily surfaced in the UI today, but grouping should still be stable.

### 5. Typed models

* How `schema/` and `generated-types/` are used:

  * Domain models: `WorkspaceSummary`, `DocumentSummary`, `JobSummary`.
  * Generated models from backend schemas.

* Mapping patterns:

  * “Wire → domain” transform functions if you don’t use generated types directly.

### 6. Streaming NDJSON endpoints

* Endpoints:

  * Build logs: `/builds/{build_id}/logs`.
  * Job logs: `/runs/{run_id}/logs`, `/jobs/{job_id}/logs` (depending on which you use).

* Abstractions in `shared/ndjson`:

  * Generic NDJSON stream parser.
  * Hook patterns, e.g. `useNdjsonStream(endpoint, options)`.

* Consumption in features:

  * Build console in Config Builder.
  * Job detail view console.

### 7. Error handling & retries

* Normalised error shape in the client:

  * HTTP status, message, optional code.

* Where 401/403 are handled:

  * Global handler (logout/redirect).
  * Local for permission errors (inline `Alert`).

* Patterns:

  * Toast vs inline error vs full error state.
  * When to `retry: false` in React Query (for permission errors).
