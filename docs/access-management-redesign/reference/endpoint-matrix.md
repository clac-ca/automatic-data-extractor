# Endpoint Matrix (Recommended Hard-Cutover Contracts)

## ADE Application APIs

Base path: `/api/v1`

## Users

| Method | Path | Purpose | Required permission |
|---|---|---|---|
| GET | `/users` | List users | `users.read_all` |
| POST | `/users` | Create user (org/admin path) | `users.manage_all` |
| GET | `/users/{userId}` | Read user profile | `users.read_all` |
| PATCH | `/users/{userId}` | Update user profile/status | `users.manage_all` |
| POST | `/users/{userId}/deactivate` | Deactivate account | `users.manage_all` |
| GET | `/users/{userId}/memberOf` | List group affiliations for a user | `users.read_all` + `groups.members.read_all` |
| POST | `/users/{userId}/memberOf/$ref` | Add user to group by reference | `users.manage_all` + `groups.members.manage_all` |
| DELETE | `/users/{userId}/memberOf/{groupId}/$ref` | Remove user from group by reference | `users.manage_all` + `groups.members.manage_all` |

## Batch (User Lifecycle)

| Method | Path | Purpose | Required permission |
|---|---|---|---|
| POST | `/$batch` | Execute up to 20 user lifecycle subrequests using Graph-style envelope semantics | Evaluated per subrequest (`users.manage_all`, etc.) |

Allowed subrequests (phase 1):

1. `POST /users`
2. `PATCH /users/{userId}`
3. `POST /users/{userId}/deactivate`

Batch execution notes:

1. Supports optional per-item dependencies (`dependsOn`).
2. Dependency failures return item-level `424`.
3. Partial success is expected; correlate outcomes by subrequest `id`.

## Groups

| Method | Path | Purpose | Required permission |
|---|---|---|---|
| GET | `/groups` | List groups | `groups.read_all` |
| POST | `/groups` | Create group | `groups.manage_all` |
| GET | `/groups/{groupId}` | Read group | `groups.read_all` |
| PATCH | `/groups/{groupId}` | Update group metadata | `groups.manage_all` |
| DELETE | `/groups/{groupId}` | Delete group | `groups.manage_all` |
| GET | `/groups/{groupId}/members` | List members of group | `groups.members.read_all` |
| POST | `/groups/{groupId}/members/$ref` | Add member reference to group | `groups.members.manage_all` |
| DELETE | `/groups/{groupId}/members/{memberId}/$ref` | Remove member reference from group | `groups.members.manage_all` |
| GET | `/groups/{groupId}/owners` | List owners of group | `groups.members.read_all` |
| POST | `/groups/{groupId}/owners/$ref` | Add owner reference to group | `groups.manage_all` |
| DELETE | `/groups/{groupId}/owners/{ownerId}/$ref` | Remove owner reference from group | `groups.manage_all` |

## Roles

| Method | Path | Purpose | Required permission |
|---|---|---|---|
| GET | `/roles` | List role definitions (filter by scope) | `roles.read_all` or `workspace.roles.read` |
| POST | `/roles` | Create role definition | `roles.manage_all` or `workspace.roles.manage` |
| GET | `/roles/{roleId}` | Read role definition | `roles.read_all` or `workspace.roles.read` |
| PATCH | `/roles/{roleId}` | Update role definition | `roles.manage_all` or `workspace.roles.manage` |
| DELETE | `/roles/{roleId}` | Delete role definition | `roles.manage_all` or `workspace.roles.manage` |

## Role Assignments

| Method | Path | Purpose | Required permission |
|---|---|---|---|
| GET | `/roleAssignments` | List organization-scope assignments | `roles.read_all` |
| POST | `/roleAssignments` | Create organization-scope assignment | `roles.manage_all` |
| GET | `/workspaces/{workspaceId}/roleAssignments` | List workspace-scope assignments | `workspace.members.read` |
| POST | `/workspaces/{workspaceId}/roleAssignments` | Create workspace-scope assignment | `workspace.members.manage` |
| DELETE | `/roleAssignments/{assignmentId}` | Delete assignment | org: `roles.manage_all`; workspace: `workspace.members.manage` |

Payload shape (assignment create):

```json
{
  "principalType": "user",
  "principalId": "<uuid>",
  "roleId": "<uuid>"
}
```

Workspace scope is implied by path. Organization scope uses `/roleAssignments` with no `scopeId`.

## Invitations

| Method | Path | Purpose | Required permission |
|---|---|---|---|
| GET | `/invitations` | List invitations (filter by scope/status) | `users.read_all` or `workspace.members.read` (scoped) |
| POST | `/invitations` | Create invitation and optional assignment | `users.manage_all` or `workspace.members.manage` (scoped) |
| GET | `/invitations/{invitationId}` | Read invitation details | same scope rule as list |
| POST | `/invitations/{invitationId}/resend` | Resend invite | inviter authority in scope |
| POST | `/invitations/{invitationId}/cancel` | Cancel invite | inviter authority in scope |

## SCIM Provisioning APIs

Base path: `/scim/v2`

These routes are enabled only when provisioning mode is `scim`.

| Method | Path | Purpose | Auth model |
|---|---|---|---|
| GET | `/ServiceProviderConfig` | Advertise SCIM capabilities | SCIM bearer token |
| GET | `/Schemas` | Return supported schemas/extensions | SCIM bearer token |
| GET | `/ResourceTypes` | Return resource type metadata | SCIM bearer token |
| GET | `/Users` | List/query users | SCIM bearer token |
| POST | `/Users` | Provision user | SCIM bearer token |
| GET | `/Users/{id}` | Read user | SCIM bearer token |
| PATCH | `/Users/{id}` | Partial update user | SCIM bearer token |
| PUT | `/Users/{id}` | Replace user | SCIM bearer token |
| GET | `/Groups` | List/query groups | SCIM bearer token |
| POST | `/Groups` | Provision group | SCIM bearer token |
| GET | `/Groups/{id}` | Read group | SCIM bearer token |
| PATCH | `/Groups/{id}` | Partial update group/members | SCIM bearer token |
| PUT | `/Groups/{id}` | Replace group | SCIM bearer token |

SCIM explicit defer:

1. `POST /Bulk` is not part of initial SCIM scope.

## Query Contract (Cross-Resource)

### `/api/v1` resources

- cursor pagination (`limit`, `cursor`, `includeTotal`)
- search (`q`)
- filters (`scopeType`, `scopeId`, `principalType`, `principalId`, `status`, `source`)
- sorting (`sort`)

### `/scim/v2` resources

- SCIM-standard pagination (`startIndex`, `count`)
- SCIM-standard filtering (`filter`)

## Deprecated/Removed in Cutover

1. `/users/{userId}/roles*` endpoints
2. `/workspaces/{workspaceId}/members*` endpoints
3. `/roleassignments` (lowercase legacy alias)
