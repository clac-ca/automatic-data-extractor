# Endpoint Matrix (Recommended Hard-Cutover Contracts)

Base path: `/api/v1`

## Users

| Method | Path | Purpose | Required permission |
|---|---|---|---|
| GET | `/users` | List users | `users.read_all` |
| POST | `/users` | Create user (org/admin path) | `users.manage_all` |
| GET | `/users/{userId}` | Read user profile | `users.read_all` |
| PATCH | `/users/{userId}` | Update user profile/status | `users.manage_all` |
| POST | `/users/{userId}/deactivate` | Deactivate account | `users.manage_all` |

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

## Query Contract (Cross-Resource)

Supported query semantics:

- cursor pagination (`limit`, `cursor`, `includeTotal`)
- search (`q`)
- filters (`scopeType`, `scopeId`, `principalType`, `principalId`, `status`, `source`)
- sorting (`sort`)

## Deprecated/Removed in Cutover

1. `/users/{userId}/roles*` endpoints
2. `/workspaces/{workspaceId}/members*` endpoints
3. `/roleassignments` (lowercase legacy alias)

