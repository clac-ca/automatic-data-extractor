# API Capability Map

## Purpose

This page gives a high-level API map and points to detailed workflow references.

Use this page to choose where to read next. Use API reference pages for endpoint details.

## Scope Boundary

This map is intentionally high-level.

For request/response schemas, examples, and endpoint-specific behavior, use:

- [API Reference Hub](api/index.md)
- [Authentication API](api/authentication.md)
- [Workspaces API](api/workspaces.md)
- [Configurations API](api/configurations.md)
- [Documents API](api/documents.md)
- [Runs API](api/runs.md)
- [Errors and Problem Details](api/errors-and-problem-details.md)

## How to Discover Current Routes

```bash
cd backend
uv run ade-api routes
uv run ade api types
```

## Capability Areas

| Area | Typical URL prefixes | Main use | Detailed reference |
| --- | --- | --- | --- |
| Auth | `/api/v1/auth/*`, `/api/v1/me*` | sign-in, session bootstrap, API-key identity checks | [Authentication API](api/authentication.md) |
| Workspaces | `/api/v1/workspaces*` | create/update workspaces, manage members | [Workspaces API](api/workspaces.md) |
| Configurations | `/api/v1/workspaces/{workspaceId}/configurations*` | draft/import/archive configurations and manage config files | [Configurations API](api/configurations.md) |
| Documents | `/api/v1/workspaces/{workspaceId}/documents*` | upload, version, tag, preview, and stream document changes | [Documents API](api/documents.md) |
| Runs | `/api/v1/runs*`, `/api/v1/workspaces/{workspaceId}/runs*` | create runs, monitor status, stream events, and download output | [Runs API](api/runs.md) |
| Roles/Permissions | `/api/v1/roles*`, `/api/v1/permissions*`, `/api/v1/roleassignments*` | access-control administration | [Manage Users and Access](../how-to/manage-users-and-access.md) |
| System | `/api/v1/admin/settings` | view/change runtime settings (`safeMode`, auth policy) with env-lock metadata and revision-based updates | [Manage Runtime Settings](../how-to/manage-runtime-settings.md) |
| Health/Meta | `/api/v1/health`, `/api/v1/info`, `/api/v1/meta/versions` | health checks and runtime metadata | [CLI Reference](cli-reference.md) |

## Common Flows

### API-Key Integration Setup

1. Validate key transport with `GET /api/v1/me`.
2. Confirm workspace scope with `GET /api/v1/workspaces`.
3. Continue with workflow-specific guides.

Use: [Authenticate with API Key](../how-to/api-authenticate-with-api-key.md)

### Document to Output

1. Upload document: `POST /api/v1/workspaces/{workspaceId}/documents`.
2. Queue run automatically via upload options or explicitly via run create endpoint.
3. Monitor run: `GET /api/v1/workspaces/{workspaceId}/runs/{runId}`.
4. Download output: `GET /api/v1/workspaces/{workspaceId}/runs/{runId}/output/download`.

Use: [Upload a Document and Queue Runs](../how-to/api-upload-and-queue-runs.md) and [Create and Monitor Runs](../how-to/api-create-and-monitor-runs.md)

### Configuration Lifecycle

1. List workspace configurations.
2. Create draft (template/clone/import).
3. Update files as needed.
4. Archive superseded configurations.

Use: [Manage Configurations via API](../how-to/api-manage-configurations.md)
