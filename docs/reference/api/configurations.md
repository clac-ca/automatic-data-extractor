# Configurations API Reference

## Purpose

Document configuration lifecycle and configuration file-management endpoints.

## Authentication Requirements

All configuration endpoints are protected and scoped to workspace permissions.

## Endpoint Matrix

| Method | Path | Auth | Primary status | Request shape | Response shape | Common errors |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/workspaces/{workspaceId}/configurations` | protected | `200` | path + cursor/search/sort | cursor page of configurations | `401`, `403` |
| `POST` | `/api/v1/workspaces/{workspaceId}/configurations` | protected | `201` | path + JSON create payload | configuration record | `401`, `403`, `404`, `409`, `422` |
| `GET` | `/api/v1/workspaces/{workspaceId}/configurations/history` | protected | `200` | path + history filters | configuration timeline payload | `401`, `403`, `404`, `422` |
| `POST` | `/api/v1/workspaces/{workspaceId}/configurations/import` | protected | `201` | path + multipart archive upload | configuration record | `400`, `401`, `403`, `409`, `413`, `422` |
| `POST` | `/api/v1/workspaces/{workspaceId}/configurations/import/github` | protected | `201` | path + JSON GitHub import payload | configuration record | `400`, `401`, `403`, `404`, `409`, `422` |
| `GET` | `/api/v1/workspaces/{workspaceId}/configurations/{configurationId}` | protected | `200` | path | configuration record + `ETag` | `401`, `403`, `404` |
| `PATCH` | `/api/v1/workspaces/{workspaceId}/configurations/{configurationId}` | protected | `200` | path + JSON metadata patch | configuration record | `401`, `403`, `404`, `409` |
| `POST` | `/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/archive` | protected | `200` | path | configuration record | `401`, `403`, `404`, `409` |
| `PUT` | `/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/directories/{directoryPath}` | protected | `200` | path | directory write response | `400`, `401`, `403`, `404`, `409` |
| `DELETE` | `/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/directories/{directoryPath}` | protected | `204` | path + optional `recursive` query | empty | `400`, `401`, `403`, `404`, `409` |
| `GET` | `/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/export` | protected | `200` | path + optional `format=zip` | ZIP stream | `400`, `401`, `403`, `404` |
| `GET` | `/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/files` | protected | `200` | path + listing filters | file listing payload | `400`, `401`, `403`, `404` |
| `GET` | `/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/files/{filePath}` | protected | `200` | path + optional `format` | file bytes or JSON payload | `400`, `401`, `403`, `404`, `416` |
| `PUT` | `/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/files/{filePath}` | protected | `200` | path + raw body + conditional headers | file write response | `400`, `401`, `403`, `404`, `409`, `412`, `413`, `428` |
| `PATCH` | `/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/files/{filePath}` | protected | `200` | path + JSON move payload | file rename response | `400`, `401`, `403`, `404`, `409`, `412`, `428` |
| `DELETE` | `/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/files/{filePath}` | protected | `204` | path + optional `If-Match` | empty | `400`, `401`, `403`, `404`, `409`, `412`, `428` |
| `PUT` | `/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/import` | protected | `200` | path + multipart archive + `If-Match` | configuration record | `400`, `401`, `403`, `404`, `409`, `412`, `413`, `422`, `428` |
| `PUT` | `/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/import/github` | protected | `200` | path + JSON GitHub import payload + `If-Match` | configuration record | `400`, `401`, `403`, `404`, `409`, `412`, `422`, `428` |
| `POST` | `/api/v1/workspaces/{workspaceId}/configurations/{configurationId}/restore` | protected | `201` | path + JSON restore payload | configuration record | `401`, `403`, `404`, `409`, `422` |

## Core Endpoint Details

### `POST /api/v1/workspaces/{workspaceId}/configurations`

- Creates a new draft configuration from template or clone source.
- Response includes configuration lifecycle metadata.

### `POST /api/v1/workspaces/{workspaceId}/configurations/import`

- Imports a configuration archive into a new draft.
- Large archives can return `413 Content Too Large`.

### `POST /api/v1/workspaces/{workspaceId}/configurations/import/github`

- Creates a new draft from a GitHub source using repository import settings.
- Use this path when source control is the draft origin instead of archive upload.

### `GET /api/v1/workspaces/{workspaceId}/configurations/{configurationId}/files`

- Returns editable file/directory structure for the selected draft.
- Supports prefix/depth/filter cursor controls for large config trees.

### `PUT /api/v1/workspaces/{workspaceId}/configurations/{configurationId}/import/github`

- Re-imports an existing configuration draft from GitHub.
- Requires concurrency protection headers when the endpoint contract specifies
  `If-Match`.

## Error Handling

- `401 Unauthorized`: auth missing or invalid.
- `403 Forbidden`: missing workspace configuration permissions.
- `404 Not Found`: workspace/config/resource not found.
- `409 Conflict`: state conflicts (for example non-editable draft state).
- `412 Precondition Failed` / `428 Precondition Required`: optimistic concurrency failures.
- `413 Content Too Large`: archive/file size exceeds configured limit.
- `422 Unprocessable Content`: invalid source/archive shape.

See [Errors and Problem Details](errors-and-problem-details.md) for shared response format.

## Related Guides

- [Manage Configurations](../../how-to/api-manage-configurations.md)
