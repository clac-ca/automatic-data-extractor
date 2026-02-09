# Workspaces API Reference

## Purpose

Document workspace and workspace membership endpoints.

## Authentication Requirements

All workspace endpoints are protected. Send `X-API-Key` or a valid session cookie.

## Endpoint Matrix

| Method | Path | Auth | Primary status | Request shape | Response shape | Common errors |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/workspaces` | protected | `200` | query: cursor/search/sort filters | cursor page of workspaces | `401`, `403` |
| `POST` | `/api/v1/workspaces` | protected | `201` | JSON: workspace create payload | workspace object | `401`, `403`, `409`, `422` |
| `GET` | `/api/v1/workspaces/{workspaceId}` | protected | `200` | path: `workspaceId` | workspace object | `401`, `403`, `404` |
| `PATCH` | `/api/v1/workspaces/{workspaceId}` | protected | `200` | path + JSON patch | workspace object | `401`, `403`, `404`, `409`, `422` |
| `DELETE` | `/api/v1/workspaces/{workspaceId}` | protected | `204` | path | empty | `401`, `403`, `404` |
| `PUT` | `/api/v1/workspaces/{workspaceId}/default` | protected | `204` | path | empty | `401`, `403` |
| `GET` | `/api/v1/workspaces/{workspaceId}/members` | protected | `200` | path + cursor/search/sort filters | cursor page of workspace members | `401`, `403` |
| `POST` | `/api/v1/workspaces/{workspaceId}/members` | protected | `201` | path + JSON member create payload | workspace member object | `401`, `403`, `404`, `409`, `422` |
| `PUT` | `/api/v1/workspaces/{workspaceId}/members/{userId}` | protected | `200` | path + JSON member role set | workspace member object | `401`, `403`, `404`, `422` |
| `DELETE` | `/api/v1/workspaces/{workspaceId}/members/{userId}` | protected | `204` | path | empty | `401`, `403`, `404` |

## Core Endpoint Details

### `GET /api/v1/workspaces`

- Supports cursor pagination and structured filters.
- Returns only workspaces visible to the authenticated principal.

### `POST /api/v1/workspaces`

- Requires tenant-level permission to create workspaces.
- `slug` conflicts return `409 Conflict`.

### `GET /api/v1/workspaces/{workspaceId}/members`

- Use for membership and role audits.
- Combine with query filters for targeted checks.

## Error Handling

- `401 Unauthorized`: no valid auth context.
- `403 Forbidden`: principal lacks required global or workspace permissions.
- `404 Not Found`: workspace or user does not exist in scope.
- `409 Conflict`: uniqueness/state conflicts (for example duplicate slug).
- `422 Unprocessable Content`: payload shape/validation failure.

See [Errors and Problem Details](errors-and-problem-details.md) for shared response format.

## Related Guides

- [Authenticate with API Key](../../how-to/api-authenticate-with-api-key.md)
