# Access Endpoint Matrix

## Purpose

Define stable hard-cutover access-management endpoints for ADE.

Base application path: `/api/v1`  
SCIM path: `/scim/v2`

## Application Endpoints

| Method | Path | Purpose | Primary authz gate |
| --- | --- | --- | --- |
| `GET` | `/users` | list users | `users.read_all` |
| `POST` | `/users` | create user | `users.manage_all` |
| `GET` | `/users/{userId}` | read user | `users.read_all` |
| `PATCH` | `/users/{userId}` | update user | `users.manage_all` |
| `POST` | `/users/{userId}/deactivate` | deactivate user | `users.manage_all` |
| `POST` | `/$batch` | batch user lifecycle mutations (current scope) | per-subrequest |
| `GET` | `/groups` | list groups | `groups.read_all` |
| `POST` | `/groups` | create group | `groups.manage_all` |
| `GET` | `/groups/{groupId}` | read group | `groups.read_all` |
| `PATCH` | `/groups/{groupId}` | update group | `groups.manage_all` |
| `DELETE` | `/groups/{groupId}` | delete group | `groups.manage_all` |
| `GET` | `/groups/{groupId}/members` | list group members | `groups.members.read_all` |
| `POST` | `/groups/{groupId}/members/$ref` | add group member reference | `groups.members.manage_all` |
| `DELETE` | `/groups/{groupId}/members/{memberId}/$ref` | remove group member reference | `groups.members.manage_all` |
| `GET` | `/roles` | list role definitions | scope-dependent (`roles.read_all` / workspace read) |
| `POST` | `/roles` | create role definition | scope-dependent (`roles.manage_all` / workspace manage) |
| `GET` | `/roles/{roleId}` | read role definition | scope-dependent (`roles.read_all` / workspace read) |
| `PATCH` | `/roles/{roleId}` | update role definition | scope-dependent (`roles.manage_all` / workspace manage) |
| `DELETE` | `/roles/{roleId}` | delete role definition | scope-dependent (`roles.manage_all` / workspace manage) |
| `GET` | `/permissions` | list permission catalog | `roles.read_all` |
| `GET` | `/roleAssignments` | list org assignments | `roles.read_all` |
| `POST` | `/roleAssignments` | create org assignment | `roles.manage_all` |
| `GET` | `/workspaces/{workspaceId}/roleAssignments` | list workspace assignments | `workspace.members.read` |
| `POST` | `/workspaces/{workspaceId}/roleAssignments` | create workspace assignment | `workspace.members.manage` |
| `DELETE` | `/roleAssignments/{assignmentId}` | delete assignment | org: `roles.manage_all`, workspace: `workspace.members.manage` |
| `GET` | `/invitations` | list invitations | org or workspace invite read permissions |
| `POST` | `/invitations` | create invitation with optional role seeds | org or workspace invite manage permissions |
| `GET` | `/invitations/{invitationId}` | read invitation | scope-aware invitation read permissions |
| `POST` | `/invitations/{invitationId}/resend` | resend invitation | scope-aware invitation manage permissions |
| `POST` | `/invitations/{invitationId}/cancel` | cancel invitation | scope-aware invitation manage permissions |
| `GET` | `/admin/scim/tokens` | list SCIM tokens | `system.settings.read` |
| `POST` | `/admin/scim/tokens` | create SCIM token | `system.settings.manage` |
| `POST` | `/admin/scim/tokens/{tokenId}/revoke` | revoke SCIM token | `system.settings.manage` |

## Batch Subrequest Scope (Current)

Current supported `POST /api/v1/$batch` subrequests:

1. `POST /users`
2. `PATCH /users/{userId}`
3. `POST /users/{userId}/deactivate`

Behavior:

1. max 20 subrequests
2. optional `dependsOn`
3. dependency failures return per-item `424`
4. partial success is expected

## SCIM Endpoints

Enabled only when provisioning mode is `scim`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/ServiceProviderConfig` | SCIM service capability declaration |
| `GET` | `/Schemas` | supported schema definitions |
| `GET` | `/ResourceTypes` | supported resource types |
| `GET` | `/Users` | list/query users |
| `POST` | `/Users` | provision user |
| `GET` | `/Users/{id}` | read user |
| `PATCH` | `/Users/{id}` | patch user |
| `PUT` | `/Users/{id}` | replace user |
| `GET` | `/Groups` | list/query groups |
| `POST` | `/Groups` | provision group |
| `GET` | `/Groups/{id}` | read group |
| `PATCH` | `/Groups/{id}` | patch group |
| `PUT` | `/Groups/{id}` | replace group |

Deferred:

1. `POST /scim/v2/Bulk`

## Removed in Hard Cutover

1. `/users/{userId}/roles*`
2. `/workspaces/{workspaceId}/members*`
3. `/roleassignments` (legacy lowercase alias)
