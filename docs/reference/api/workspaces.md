# Workspaces API Reference

## Purpose

Document workspace lifecycle endpoints.

Access administration endpoints for principals, invitations, and role assignments
are documented in [Access Management API Reference](access-management.md).

## Authentication Requirements

All workspace endpoints are protected. Use a valid session or `X-API-Key`.

## Endpoint Matrix

| Method | Path | Auth | Primary status | Request shape | Response shape | Common errors |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/workspaces` | protected | `200` | query: cursor/search/sort filters | cursor page of workspaces | `401`, `403` |
| `POST` | `/api/v1/workspaces` | protected | `201` | JSON workspace create payload | workspace object | `401`, `403`, `404`, `409`, `422` |
| `GET` | `/api/v1/workspaces/{workspaceId}` | protected | `200` | path: `workspaceId` | workspace object | `401`, `403`, `404` |
| `PATCH` | `/api/v1/workspaces/{workspaceId}` | protected | `200` | path + JSON workspace update | workspace object | `401`, `403`, `404`, `409`, `422` |
| `DELETE` | `/api/v1/workspaces/{workspaceId}` | protected | `204` | path | empty | `401`, `403`, `404` |
| `PUT` | `/api/v1/workspaces/{workspaceId}/default` | protected | `204` | path | empty | `401`, `403` |

## Core Endpoint Details

### `GET /api/v1/workspaces`

1. supports cursor pagination and structured filters
2. returns only workspaces visible to the authenticated principal

### `POST /api/v1/workspaces`

1. requires workspace-create authority
2. slug conflicts return `409 Conflict`

### `PATCH /api/v1/workspaces/{workspaceId}`

1. updates metadata and workspace settings
2. requires workspace settings management authority

## Error Handling

- `401 Unauthorized`: missing or invalid authentication.
- `403 Forbidden`: principal lacks required permissions for workspace operation.
- `404 Not Found`: workspace not found in visible scope.
- `409 Conflict`: uniqueness/state conflict (for example duplicate slug).
- `422 Unprocessable Content`: request validation failure.

See [Errors and Problem Details](errors-and-problem-details.md).

## Related Guides

- [Manage Users and Access](../../how-to/manage-users-and-access.md)
- [Access Management API Reference](access-management.md)
