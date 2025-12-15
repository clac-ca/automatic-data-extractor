# API Guide

This guide is for developers who want to integrate with the Automatic Data Extractor (ADE) directly through the HTTP API. It summarises authentication, core resources, and usage patterns so you can build reliable automations without reading the entire codebase.

## Base URL and versioning

ADE exposes a JSON REST API under a versioned base path:

- **Base URL**: `https://{your-domain}/api`
- **Current version**: `v1`
- **Example**: `https://ade.example.com/api/v1`

Future versions will follow the same resource model. When breaking changes are required, a new version path (for example `/api/v2`) will be introduced.

## Version discovery

- `GET /api/v1/meta/versions` returns the installed backend package versions (`ade-api` and `ade-engine`).
- In the web UI, open the profile menu and pick **About / Versions** to see the built `ade-web` version alongside the backend versions.

## Authentication and RBAC

- **Session + bearer tokens**: `POST /api/v1/auth/session` (and `/session/refresh`) return a `SessionEnvelope` with tokens and
  session context. Browser callers also receive `httponly` cookies; API/CLI callers use the `Authorization: Bearer <token>`
  header.
- **API keys**: Issue long-lived credentials via `/api/v1/me/api-keys` for self-service or `/api/v1/users/{user_id}/api-keys`
  for admins. Submit them via `X-API-Key` (or the bearer header for compatibility).
- **Permissions**: Every route enforces RBAC. Global permissions (for example `users.read_all`) apply across the tenant; workspace
  permissions (for example `workspace.documents.manage`) apply to the workspace ID in the URL path.
- **CSRF**: Not enforced yet. The dependency is wired for future use but currently no-ops.

Requests without valid credentials receive HTTP `401 Unauthorized`. If the token is valid but lacks permissions for a resource you
will receive `403 Forbidden`.

## Core resources

### Users and identity

- `GET /users` – list users (requires `users.read_all`).
- `GET /users/{user_id}` – retrieve a single user's profile, including roles and permissions.
- `PATCH /users/{user_id}` – update display name or activation (`users.manage_all`).
- `GET /users/{user_id}/roles` – list global role assignments; `PUT`/`DELETE` manage assignments.
- `GET /users/{user_id}/api-keys` – list user-owned API keys; `POST` issues, `DELETE /users/{user_id}/api-keys/{api_key_id}` revokes.
- `/me` endpoints return the caller’s profile, effective permissions, and workspace list for bootstrap flows.

### RBAC catalog and assignments

- `GET /rbac/permissions` – list permission definitions by scope.
- `GET/POST /rbac/roles` – list or create roles (scope via query parameter).
- `GET/PATCH/DELETE /rbac/roles/{role_id}` – manage a specific role.
- `GET /rbac/role-assignments` – admin view of assignments across users.
- Workspace membership and role bindings live under `/workspaces/{workspace_id}/members` (list/create/update/delete) and are scoped by workspace permissions.

### Documents

Upload source files for extraction. All document routes are nested under the workspace path segment.

- `GET /workspaces/{workspace_id}/documents` – list documents with pagination, sorting, and filters.
- `POST /workspaces/{workspace_id}/documents` – multipart upload endpoint (accepts optional metadata JSON and expiration).
- `GET /workspaces/{workspace_id}/documents/{document_id}` – fetch metadata, including upload timestamps and submitter.
- `GET /workspaces/{workspace_id}/documents/{document_id}/download` – download the stored file with a safe `Content-Disposition` header.
- `GET /workspaces/{workspace_id}/documents/{document_id}/sheets` – enumerate worksheets for spreadsheet uploads (falls back to a single-sheet descriptor for other file types).
- `DELETE /workspaces/{workspace_id}/documents/{document_id}` – remove a document, if permitted.

### Runs

Trigger and monitor extraction runs. Creation is configuration-scoped; reads are global by run ID.

- `POST /configurations/{configuration_id}/runs` – submit a run for the given configuration; supports inline streaming or background execution depending on `stream`.
- `GET /workspaces/{workspace_id}/runs` – list recent runs for a workspace, filterable by status or source document.
- `GET /runs/{run_id}` – retrieve run metadata (status, timing, config/build references, input/output hints).
- `GET /runs/{run_id}/events` – fetch or stream structured events (use `?stream=true` for SSE/NDJSON).
- `GET /runs/{run_id}/summary` – retrieve the run summary payload when available.
- `GET /runs/{run_id}/input` – fetch input metadata; `GET /runs/{run_id}/input/download` downloads the original file.
- `GET /runs/{run_id}/output` – fetch output metadata (`ready`, size, content type, download URL).
- `GET /runs/{run_id}/output/download` – download the normalized output; returns `409` when not ready.
- `GET /runs/{run_id}/events/download` – download the NDJSON event log (legacy `/runs/{run_id}/logs` remains as an alias).
- Legacy: `/runs/{run_id}/outputs*` endpoints are deprecated and alias the singular output file.

### Configurations

Author and manage ADE configuration packages. All routes are workspace-scoped.

- `GET /workspaces/{workspace_id}/configurations` – list configurations in the workspace (paged envelope).
- `POST /workspaces/{workspace_id}/configurations` – create from a bundled template or clone an existing config.
- `GET /workspaces/{workspace_id}/configurations/{configuration_id}` – fetch configuration metadata.
- `POST /workspaces/{workspace_id}/configurations/{configuration_id}/validate` – validate the working tree and return issues/content digest.
- `POST /workspaces/{workspace_id}/configurations/{configuration_id}/activate` – mark as the active configuration for the workspace.
- `POST /workspaces/{workspace_id}/configurations/{configuration_id}/publish` – freeze the draft into a published version.
- `POST /workspaces/{workspace_id}/configurations/{configuration_id}/deactivate` – mark the configuration inactive.
- `GET /workspaces/{workspace_id}/configurations/{configuration_id}/export` – download a ZIP of the editable tree.

**File editor surface**

- `GET /workspaces/{workspace_id}/configurations/{configuration_id}/files` – list files/directories with pagination, include/exclude globs, and weak list ETag (`If-None-Match` → `304`).
- `GET|HEAD /workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}` – read bytes or JSON helper (`Accept: application/json`); supports strong `ETag`, range reads, and `Last-Modified`.
- `PUT /workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}` – create or update bytes; honors `If-None-Match: *` for create and `If-Match` for updates; returns `ETag` and `Location` on create.
- `PATCH /workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}` – rename/move atomically with source/dest preconditions.
- `DELETE /workspaces/{workspace_id}/configurations/{configuration_id}/files/{file_path}` – delete a file or empty directory (use `If-Match` for safety).
- `PUT /workspaces/{workspace_id}/configurations/{configuration_id}/directories/{directory_path}` – ensure an empty directory exists (idempotent; returns `created` flag).
- `DELETE /workspaces/{workspace_id}/configurations/{configuration_id}/directories/{directory_path}` – remove a directory; `?recursive=true` allowed.

### Builds

Provision isolated virtual environments for configurations. Builds are configuration-scoped, with global lookup by `build_id`.

- `POST /workspaces/{workspace_id}/configurations/{configuration_id}/builds` – enqueue or stream a build (`stream: true|false`, `options.force`, `options.wait`).
- `GET /workspaces/{workspace_id}/configurations/{configuration_id}/builds` – list build history for a configuration (filters: `status`, pagination, optional totals).
- `GET /builds/{build_id}` – fetch a build snapshot (status, timestamps, exit code, engine/python metadata).

> Build console output is emitted as `EventRecord` entries (`console.line` with `data.scope="build"`) in the same stream used for run events. Attach to `/runs/{run_id}/events/stream` after submitting a run or use streaming build creation (`stream: true`) to receive the same EventRecords inline.

## Error handling

ADE follows standard HTTP semantics and FastAPI's default error envelope. Every non-2xx response returns a JSON document with a `detail` field:

- For most validation, authentication, and permission failures the `detail` value is a string describing the problem (for example `"Authentication required"` or `"Workspace slug already in use"`).
- Some operations include structured details for easier automation. Run submission failures return `{"detail": {"error": "run_failed", "run_id": "...", "message": "..."}}`.

Use the HTTP status code to drive retry behaviour—`5xx` and `429` responses merit exponential backoff, whereas `4xx` errors require user action before retrying. Validation errors (`422`) and conflict responses (`409`) intentionally provide enough context in the `detail` payload to help clients resolve the issue.

## Webhooks and callbacks

If you need near real-time updates, register a webhook endpoint with the ADE team. Webhooks fire on run completion and failure. Delivery includes an HMAC signature header so you can verify authenticity.

## SDKs and client libraries

Official client libraries are on the roadmap. Until they ship, use your preferred HTTP client. The API uses predictable JSON schemas, making it easy to generate typed clients with tools such as OpenAPI Generator once the schema is published.

## Sandbox environment

For integration testing, ADE provides a sandbox deployment with seeded workspaces and sample documents. Contact support to receive credentials. Sandbox data resets daily, so do not store production information there.

## Support

If you encounter issues or need new API capabilities, reach out through the developer support channel listed in your onboarding pack. Provide request IDs and timestamps when reporting problems to help the team diagnose them quickly.
