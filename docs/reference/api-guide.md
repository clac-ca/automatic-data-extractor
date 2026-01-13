# API Guide

This guide is for developers who want to integrate with the Automatic Data Extractor (ADE) directly through the HTTP API. It summarises authentication, core resources, and usage patterns so you can build reliable automations without reading the entire codebase.

## Base URL and versioning

ADE exposes a JSON REST API under a versioned base path:

- **Base URL**: `https://{your-domain}/api/v1`
- **Current version**: `v1`
- **Example**: `https://ade.example.com/api/v1`

Future versions will follow the same resource model. When breaking changes are required, a new version path (for example `/api/v2`) will be introduced.

## Version discovery

- `GET /api/v1/meta/versions` returns the installed backend package versions (`ade-api` and `ade-engine`).
- In the web UI, open the profile menu and pick **About / Versions** to see the built `ade-web` version alongside the backend versions.

## Operational endpoints

- `GET /health` returns `200` when the process is running (no database check).
- `GET /ready` verifies database connectivity and returns `200` when ready (else `503`).
- `GET /api/v1/info` returns build/runtime metadata (`version`, `commitSha`, `environment`, `startedAt`).

## Authentication and RBAC

- **Session cookies**: `POST /api/v1/auth/cookie/login` sets the `ade_session` cookie for browser clients. Use
  `POST /api/v1/auth/cookie/logout` to terminate the session.
- **Bearer tokens**: `POST /api/v1/auth/jwt/login` returns a JWT for non-browser clients; send it via
  `Authorization: Bearer <token>`.
- **API keys**: Issue long-lived credentials via `/api/v1/users/me/apikeys` for self-service or
  `/api/v1/users/{userId}/apikeys` for admins. Submit them via `X-API-Key` or `Authorization: Api-Key <token>`.
- **Permissions**: Every route enforces RBAC. Global permissions (for example `users.read_all`) apply across the tenant; workspace
  permissions (for example `workspace.documents.manage`) apply to the workspace ID in the URL path.
- **CSRF**: Enforced for cookie-authenticated unsafe methods via `X-CSRF-Token` + `ade_csrf` cookie.

Requests without valid credentials receive HTTP `401 Unauthorized`. If the token is valid but lacks permissions for a resource you
will receive `403 Forbidden`.

## Platform conventions

### Request IDs

- The API accepts `X-Request-Id` on inbound requests and always echoes it back.
- Every response includes `X-Request-Id`; error responses also include `requestId` in the body.
- Provide request IDs when contacting support to speed up debugging.

### Error format (Problem Details)

All non-2xx responses use `application/problem+json` with a consistent schema:

```json
{
  "type": "validation_error",
  "title": "Validation error",
  "status": 422,
  "detail": "Invalid request",
  "instance": "/api/v1/workspaces/ws_123/documents",
  "requestId": "req_abc123",
  "errors": [
    { "path": "filters[0].operator", "message": "Unsupported operator", "code": "invalid_operator" }
  ]
}
```

### Optimistic concurrency

- `GET` item endpoints return an `ETag` header.
- `PATCH` and `DELETE` require `If-Match` with that ETag.
  - Missing `If-Match` returns `428 precondition_required`.
  - Mismatched `If-Match` returns `412 precondition_failed`.

Example:

```http
GET /api/v1/workspaces/ws_123/documents/doc_123
ETag: W/"doc_123:1700000000"

PATCH /api/v1/workspaces/ws_123/documents/doc_123
If-Match: W/"doc_123:1700000000"
```

### Idempotent POSTs

- Creating documents, runs, and API keys requires `Idempotency-Key`.
- Replaying the same key + payload returns the original response.
- Reusing a key with a different payload returns `409 idempotency_key_conflict`.

## Core resources

### List endpoints (canonical contract)

Every list endpoint uses the same query contract and envelope. Unknown query
params return `422`.

Query params:

- `limit` (default `50`, max `200`)
- `cursor` (opaque cursor token)
- `sort` (JSON array of `{ id, desc }`)
- `filters` (URL-encoded JSON array of `{ id, operator, value }`)
- `joinOperator` (`and` or `or`, default `and`)
- `q` (free-text search)
- `includeTotal` (default `false`)
- `includeFacets` (default `false`)

See `docs/reference/list-search.md` for `q` tokenization rules and per-resource
searchable fields.

Response envelope:

```json
{
  "items": [],
  "meta": {
    "limit": 50,
    "hasMore": false,
    "nextCursor": null,
    "totalIncluded": false,
    "totalCount": null,
    "changesCursor": "0"
  },
  "facets": null
}
```

`changesCursor` is a snapshot watermark. For resources without change feeds it
is omitted or `null`.

Filter operators follow the Tablecn DSL (for example `eq`, `in`, `between`,
`iLike`, `isEmpty`). Values must match the operator shape (arrays for `in`,
two-element arrays for `between`, etc.).

### Users and identity

- `GET /users` – list users (requires `users.read_all`).
- `GET /users/{userId}` – retrieve a single user's profile, including roles and permissions.
- `PATCH /users/{userId}` – update display name or activation (`users.manage_all`).
- `GET /users/{userId}/roles` – list global role assignments; `PUT`/`DELETE` manage assignments.
- `GET /users/{userId}/apikeys` – list user-owned API keys; `POST` issues, `DELETE /users/{userId}/apikeys/{apiKeyId}` revokes.
- `/me` endpoints return the caller’s profile, effective permissions, and workspace list for bootstrap flows.

### RBAC catalog and assignments

- `GET /permissions` – list permission definitions by scope.
- `GET/POST /roles` – list or create roles (scope via query parameter).
- `GET/PATCH/DELETE /roles/{roleId}` – manage a specific role.
- `GET /roleassignments` – admin view of assignments across users.
- Workspace membership and role bindings live under `/workspaces/{workspaceId}/members` (list/create/update/delete) and are scoped by workspace permissions.

### Documents

Upload source files for extraction. All document routes are nested under the workspace path segment.

- `GET /workspaces/{workspaceId}/documents` – list documents with pagination, sorting, and filters; includes a `changesCursor`
  watermark in the response body and `X-Ade-Changes-Cursor` header.
- `POST /workspaces/{workspaceId}/documents` – multipart upload endpoint (accepts optional metadata JSON and expiration); uploads store bytes + metadata only (worksheet inspection is on-demand).
- `GET /workspaces/{workspaceId}/documents/{documentId}` – fetch metadata, including upload timestamps and submitter.
- `GET /workspaces/{workspaceId}/documents/{documentId}/download` – download the stored file with a safe `Content-Disposition` header.
- `GET /workspaces/{workspaceId}/documents/{documentId}/sheets` – enumerate worksheets for spreadsheet uploads by inspecting the stored file (falls back to a single-sheet descriptor for other file types; returns `422` when parsing fails).
- `DELETE /workspaces/{workspaceId}/documents/{documentId}` – remove a document, if permitted.

**Change feed + streaming**

- `GET /workspaces/{workspaceId}/documents/changes?cursor=<int>` – cursor-based change feed (use `nextCursor` as the new cursor).
- `GET /workspaces/{workspaceId}/documents/changes/stream?cursor=<int>` – SSE stream of the same feed; honors `Last-Event-ID` or `cursor`.
- When a cursor is too old the API returns `410` with `{"error": "resync_required", "oldestCursor": "...", "latestCursor": "..."}`.
- Change entries are minimal (`documentId`, `documentVersion`, `occurredAt`); clients fetch the latest row on `document.changed`.

**Resumable upload sessions (large files)**

- `POST /workspaces/{workspaceId}/documents/uploadsessions` – create a resumable upload session.
- `PUT /workspaces/{workspaceId}/documents/uploadsessions/{uploadSessionId}` – upload a `Content-Range` chunk.
- `GET /workspaces/{workspaceId}/documents/uploadsessions/{uploadSessionId}` – poll session status and `next_expected_ranges`.
- `POST /workspaces/{workspaceId}/documents/uploadsessions/{uploadSessionId}/commit` – finalize the document record.
- `DELETE /workspaces/{workspaceId}/documents/uploadsessions/{uploadSessionId}` – cancel and clean up the session.

### Runs

Trigger and monitor extraction runs. Creation is configuration-scoped; reads are global by run ID.

- `POST /configurations/{configurationId}/runs` – submit a run for the given configuration; requires `input_document_id` and returns a queued `Run` snapshot.
- `POST /configurations/{configurationId}/runs/batch` – enqueue runs for multiple documents in one request (all-or-nothing; no sheet selection).
- `GET /workspaces/{workspaceId}/runs` – list recent runs for a workspace; use the filter DSL for status or source document filters.
- `GET /runs/{runId}` – retrieve run metadata (status, timing, configuration, input/output hints).
- `GET /runs/{runId}/events` – fetch structured events (JSON or NDJSON).
- `GET /runs/{runId}/events/stream` – SSE stream of the run event log.
- `GET /runs/{runId}/input` – fetch input metadata; `GET /runs/{runId}/input/download` downloads the original file.
- `GET /runs/{runId}/output` – fetch output metadata (`ready`, size, content type, download URL).
- `GET /runs/{runId}/output/download` – download the normalized output; returns `409` when not ready.
- `GET /runs/{runId}/events/download` – download the NDJSON event log.

### Configurations

Author and manage ADE configuration packages. All routes are workspace-scoped.

- `GET /workspaces/{workspaceId}/configurations` – list configurations in the workspace (canonical list envelope).
- `POST /workspaces/{workspaceId}/configurations` – create from a bundled template or clone an existing config.
- `GET /workspaces/{workspaceId}/configurations/{configurationId}` – fetch configuration metadata.
- `POST /workspaces/{workspaceId}/configurations/{configurationId}/validate` – validate the working tree and return issues/content digest.
- `POST /workspaces/{workspaceId}/configurations/{configurationId}/publish` – make the draft active (archives any previous active configuration).
- `POST /workspaces/{workspaceId}/configurations/{configurationId}/archive` – archive the active configuration.
- `GET /workspaces/{workspaceId}/configurations/{configurationId}/export` – download a ZIP of the editable tree.

**File editor surface**

- `GET /workspaces/{workspaceId}/configurations/{configurationId}/files` – list files/directories with cursor pagination, include/exclude globs, and weak list ETag (`If-None-Match` → `304`).
- `GET|HEAD /workspaces/{workspaceId}/configurations/{configurationId}/files/{filePath}` – read bytes or JSON helper (`Accept: application/json`); supports strong `ETag`, range reads, and `Last-Modified`.
- `PUT /workspaces/{workspaceId}/configurations/{configurationId}/files/{filePath}` – create or update bytes; honors `If-None-Match: *` for create and `If-Match` for updates; returns `ETag` and `Location` on create.
- `PATCH /workspaces/{workspaceId}/configurations/{configurationId}/files/{filePath}` – rename/move atomically with source/dest preconditions.
- `DELETE /workspaces/{workspaceId}/configurations/{configurationId}/files/{filePath}` – delete a file or empty directory (use `If-Match` for safety).
- `PUT /workspaces/{workspaceId}/configurations/{configurationId}/directories/{directoryPath}` – ensure an empty directory exists (idempotent; returns `created` flag).
- `DELETE /workspaces/{workspaceId}/configurations/{configurationId}/directories/{directoryPath}` – remove a directory; `?recursive=true` allowed.

### Environments

Environments are worker-owned cached venvs keyed by configuration + dependency digest. They are
provisioned automatically as runs start. There is no public environment API in v1; operational
visibility comes from run event streams and worker logs.

## Error handling

ADE follows standard HTTP semantics and returns Problem Details (`application/problem+json`) for every non-2xx response. The payload includes a stable `type`, `title`, `status`, `detail`, and `requestId`, plus optional `errors` for validation-style issues.

Use the HTTP status code to drive retry behaviour—`5xx` and `429` responses merit exponential backoff, whereas `4xx` errors require user action before retrying. Validation errors (`422`), conflicts (`409`), and precondition failures (`412`/`428`) include structured detail to help clients resolve the issue. Always log `requestId` when reporting problems.

## Webhooks and callbacks

If you need near real-time updates, register a webhook endpoint with the ADE team. Webhooks fire on run completion and failure. Delivery includes an HMAC signature header so you can verify authenticity.

## SDKs and client libraries

Official client libraries are on the roadmap. Until they ship, use your preferred HTTP client. The API uses predictable JSON schemas, making it easy to generate typed clients with tools such as OpenAPI Generator once the schema is formally versioned.

## Sandbox environment

For integration testing, ADE provides a sandbox deployment with seeded workspaces and sample documents. Contact support to receive credentials. Sandbox data resets daily, so do not store production information there.

## Support

If you encounter issues or need new API capabilities, reach out through the developer support channel listed in your onboarding pack. Provide request IDs and timestamps when reporting problems to help the team diagnose them quickly.
