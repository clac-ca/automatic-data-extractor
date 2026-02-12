# Access Management API Reference

## Purpose

Document access-management endpoints for users, groups, role assignments,
invitations, batch mutations, and SCIM provisioning surfaces.

## Authentication Requirements

Application endpoints (`/api/v1/*`) require one of:

1. session cookie auth (browser) with CSRF for mutating calls
2. `X-API-Key` auth for service clients

SCIM endpoints (`/scim/v2/*`) require SCIM bearer token auth issued via
`/api/v1/admin/scim/tokens*`.

## Endpoint Matrix

### Core access resources (`/api/v1`)

| Method | Path | Auth | Primary status | Request shape | Response shape | Common errors |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/users` | protected | `200` | query: list filters | user page | `401`, `403` |
| `POST` | `/api/v1/users` | protected + CSRF | `201` | JSON user create | user create response | `401`, `403`, `409`, `422` |
| `GET` | `/api/v1/users/{userId}` | protected | `200` | path | user | `401`, `403`, `404` |
| `PATCH` | `/api/v1/users/{userId}` | protected + CSRF | `200` | path + JSON patch | user | `401`, `403`, `404`, `422` |
| `POST` | `/api/v1/users/{userId}/deactivate` | protected + CSRF | `200` | path | user | `401`, `403`, `404` |
| `GET` | `/api/v1/users/{userId}/memberOf` | protected | `200` | path | user memberships | `401`, `403`, `404` |
| `POST` | `/api/v1/users/{userId}/memberOf/$ref` | protected + CSRF | `200` | path + group ref | user memberships | `401`, `403`, `404`, `409`, `422` |
| `DELETE` | `/api/v1/users/{userId}/memberOf/{groupId}/$ref` | protected + CSRF | `204` | path | empty | `401`, `403`, `404`, `409` |
| `GET` | `/api/v1/groups` | protected | `200` | query: optional search | groups list | `401`, `403` |
| `POST` | `/api/v1/groups` | protected + CSRF | `201` | JSON group create | group | `401`, `403`, `409`, `422` |
| `GET` | `/api/v1/groups/{groupId}` | protected | `200` | path | group | `401`, `403`, `404` |
| `PATCH` | `/api/v1/groups/{groupId}` | protected + CSRF | `200` | path + JSON patch | group | `401`, `403`, `404`, `409`, `422` |
| `DELETE` | `/api/v1/groups/{groupId}` | protected + CSRF | `204` | path | empty | `401`, `403`, `404` |
| `GET` | `/api/v1/groups/{groupId}/members` | protected | `200` | path | group members | `401`, `403`, `404` |
| `POST` | `/api/v1/groups/{groupId}/members/$ref` | protected + CSRF | `200` | path + member ref | group members | `401`, `403`, `404`, `409`, `422` |
| `DELETE` | `/api/v1/groups/{groupId}/members/{memberId}/$ref` | protected + CSRF | `204` | path | empty | `401`, `403`, `404`, `409` |
| `GET` | `/api/v1/groups/{groupId}/owners` | protected | `200` | path | group owners | `401`, `403`, `404` |
| `POST` | `/api/v1/groups/{groupId}/owners/$ref` | protected + CSRF | `200` | path + owner ref | group owners | `401`, `403`, `404`, `409`, `422` |
| `DELETE` | `/api/v1/groups/{groupId}/owners/{ownerId}/$ref` | protected + CSRF | `204` | path | empty | `401`, `403`, `404`, `409` |
| `GET` | `/api/v1/roles` | protected | `200` | query: scope/filter/sort | role page | `401`, `403` |
| `POST` | `/api/v1/roles` | protected + CSRF | `201` | JSON role create | role | `401`, `403`, `409`, `422` |
| `GET` | `/api/v1/roles/{roleId}` | protected | `200` | path | role | `401`, `403`, `404` |
| `PATCH` | `/api/v1/roles/{roleId}` | protected + CSRF | `200` | path + JSON role patch | role | `401`, `403`, `404`, `409`, `422` |
| `DELETE` | `/api/v1/roles/{roleId}` | protected + CSRF | `204` | path | empty | `401`, `403`, `404`, `409` |
| `GET` | `/api/v1/permissions` | protected | `200` | query: filters/sort/search | permission page | `401`, `403` |
| `GET` | `/api/v1/roleAssignments` | protected | `200` | query | role assignment page | `401`, `403` |
| `POST` | `/api/v1/roleAssignments` | protected + CSRF | `201` | JSON assignment create | role assignment | `401`, `403`, `404`, `409`, `422` |
| `GET` | `/api/v1/workspaces/{workspaceId}/roleAssignments` | protected | `200` | path | role assignment page | `401`, `403`, `404` |
| `POST` | `/api/v1/workspaces/{workspaceId}/roleAssignments` | protected + CSRF | `201` | path + JSON assignment create | role assignment | `401`, `403`, `404`, `409`, `422` |
| `DELETE` | `/api/v1/roleAssignments/{assignmentId}` | protected + CSRF | `204` | path | empty | `401`, `403`, `404` |
| `GET` | `/api/v1/invitations` | protected | `200` | query: `workspace_id` / `invitation_status` | invitation list | `401`, `403` |
| `POST` | `/api/v1/invitations` | protected + CSRF | `201` | JSON invitation create | invitation | `401`, `403`, `404`, `409`, `422` |
| `GET` | `/api/v1/invitations/{invitationId}` | protected | `200` | path | invitation | `401`, `403`, `404` |
| `POST` | `/api/v1/invitations/{invitationId}/resend` | protected + CSRF | `200` | path | invitation | `401`, `403`, `404`, `409` |
| `POST` | `/api/v1/invitations/{invitationId}/cancel` | protected + CSRF | `200` | path | invitation | `401`, `403`, `404`, `409` |

### Batch endpoint (`/api/v1/$batch`)

| Method | Path | Auth | Primary status | Request shape | Response shape | Common errors |
| --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/api/v1/$batch` | protected + CSRF | `200` | Graph-style batch envelope (`requests[]`) | batch envelope (`responses[]`) | `401`, `403`, `413`, `422`, mixed per-item errors |

Current supported subrequests:

1. `POST /users`
2. `PATCH /users/{userId}`
3. `POST /users/{userId}/deactivate`

### SCIM and SCIM token admin

| Method | Path | Auth | Primary status | Request shape | Response shape | Common errors |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/admin/scim/tokens` | protected | `200` | none | token list | `401`, `403` |
| `POST` | `/api/v1/admin/scim/tokens` | protected + CSRF | `201` | JSON token create | token + one-time secret | `401`, `403`, `422` |
| `POST` | `/api/v1/admin/scim/tokens/{tokenId}/revoke` | protected + CSRF | `200` | path | token | `401`, `403`, `404` |
| `GET` | `/scim/v2/ServiceProviderConfig` | SCIM token | `200` | none | SCIM service config | `401`, `403` |
| `GET` | `/scim/v2/Schemas` | SCIM token | `200` | none | SCIM schema list | `401`, `403` |
| `GET` | `/scim/v2/ResourceTypes` | SCIM token | `200` | none | SCIM resource types | `401`, `403` |
| `GET` | `/scim/v2/Users` | SCIM token | `200` | query: filter/pagination | SCIM user list | `400`, `401`, `403` |
| `POST` | `/scim/v2/Users` | SCIM token | `201` | SCIM user create | SCIM user | `400`, `401`, `403`, `409` |
| `GET` | `/scim/v2/Users/{id}` | SCIM token | `200` | path | SCIM user | `401`, `403`, `404` |
| `PATCH` | `/scim/v2/Users/{id}` | SCIM token | `200` | SCIM patch | SCIM user | `400`, `401`, `403`, `404` |
| `PUT` | `/scim/v2/Users/{id}` | SCIM token | `200` | SCIM replace | SCIM user | `400`, `401`, `403`, `404` |
| `GET` | `/scim/v2/Groups` | SCIM token | `200` | query: filter/pagination | SCIM group list | `400`, `401`, `403` |
| `POST` | `/scim/v2/Groups` | SCIM token | `201` | SCIM group create | SCIM group | `400`, `401`, `403`, `409` |
| `GET` | `/scim/v2/Groups/{id}` | SCIM token | `200` | path | SCIM group | `401`, `403`, `404` |
| `PATCH` | `/scim/v2/Groups/{id}` | SCIM token | `200` | SCIM patch | SCIM group | `400`, `401`, `403`, `404` |
| `PUT` | `/scim/v2/Groups/{id}` | SCIM token | `200` | SCIM replace | SCIM group | `400`, `401`, `403`, `404` |

## Core Endpoint Details

### `POST /api/v1/invitations`

Use this as the workspace-owner provisioning path:

1. if user exists, role assignment is created in scope
2. if user does not exist, invited user is created and assignment is seeded

### `POST /api/v1/workspaces/{workspaceId}/roleAssignments`

Workspace-scoped assignment endpoint for both `user` and `group` principals.

### Membership and ownership mutation guardrails

Group membership and ownership mutations are blocked for groups with:

1. `source=idp`
2. `membership_mode=dynamic`

These endpoints return `409 Conflict` with a provider-managed read-only detail.

### `POST /api/v1/$batch`

Use for high-volume user lifecycle operations with per-item status handling and
optional dependency ordering via `dependsOn`.

## Error Handling

Use Problem Details for `/api/v1` errors and SCIM-compliant error envelopes for
`/scim/v2` errors.

Common operational guidance:

1. retry only failed batch subrequests
2. treat `403` as permission boundary, not transient failure
3. treat `409` as state conflict and require operator correction

## Related Guides

- [Manage Users and Access](../../how-to/manage-users-and-access.md)
- [Auth Operations](../../how-to/auth-operations.md)
- [Access Reference](../access/README.md)
- [Errors and Problem Details](errors-and-problem-details.md)
