# API Routes (Hard Cutover, Graph-Aligned)

## Design Principles

1. No `/v2` parallel family.
2. Resource-first endpoints.
3. Consistent assignment resource for both org and workspace scopes.
4. Graph-like group membership reference operations.
5. Invitation as first-class resource.

## Canonical Route Set

Base: `/api/v1`

### Users

- `GET /users`
- `POST /users`
- `GET /users/{userId}`
- `PATCH /users/{userId}`
- `POST /users/{userId}/deactivate`

Notes:

- `POST /users` remains for organization admins and system provisioning use-cases.
- Workspace-owner provisioning uses invitations (not direct global user create).

### Groups

- `GET /groups`
- `POST /groups`
- `GET /groups/{groupId}`
- `PATCH /groups/{groupId}`
- `DELETE /groups/{groupId}`
- `GET /groups/{groupId}/members`
- `POST /groups/{groupId}/members/$ref`
- `DELETE /groups/{groupId}/members/{memberId}/$ref`

### Roles

- `GET /roles?scope=organization|workspace`
- `POST /roles`
- `GET /roles/{roleId}`
- `PATCH /roles/{roleId}`
- `DELETE /roles/{roleId}`

### Role Assignments

- `GET /roleAssignments` (organization assignments)
- `POST /roleAssignments` (organization assignments)
- `GET /workspaces/{workspaceId}/roleAssignments`
- `POST /workspaces/{workspaceId}/roleAssignments`
- `DELETE /roleAssignments/{assignmentId}`

### Invitations

- `GET /invitations`
- `POST /invitations`
- `GET /invitations/{invitationId}`
- `POST /invitations/{invitationId}/resend`
- `POST /invitations/{invitationId}/cancel`

## Workspace-Owner Invite Payload (Recommended)

`POST /api/v1/invitations`

```json
{
  "invitedUserEmail": "new.user@example.com",
  "displayName": "New User",
  "workspaceContext": {
    "workspaceId": "<uuid>",
    "roleAssignments": [
      {
        "roleId": "<workspace-role-uuid>"
      }
    ]
  }
}
```

Behavior:

1. If user exists: create assignment (and optional invitation record for traceability).
2. If user does not exist: create invited user stub + invitation + assignment in one transaction.

## Hard-Cutover Mapping from Current Routes

| Current | New | Action |
|---|---|---|
| `GET/POST /workspaces/{workspaceId}/members` | `GET/POST /workspaces/{workspaceId}/roleAssignments` | Replace members-as-assignment API |
| `PUT/DELETE /workspaces/{workspaceId}/members/{userId}` | `DELETE /roleAssignments/{assignmentId}` + update through assignment create/delete | Normalize to assignment resource semantics |
| `GET /users/{userId}/roles` and `PUT/DELETE /users/{userId}/roles/{roleId}` | `GET/POST/DELETE /roleAssignments...` | Remove user-specific special-case routes |
| `GET /roleassignments` | `GET /roleAssignments` | Rename and standardize casing |

## Query and Filtering Conventions

- Continue ADE cursor pagination baseline.
- Add consistent filter keys across resources (`scopeType`, `scopeId`, `principalType`, `principalId`, `status`).
- Support deterministic sorting on stable keys.
- Keep optional Graph-like aliases for query compatibility where useful.

## Error Contract Expectations

1. `403` for permission boundary violations.
2. `404` for unknown resource IDs.
3. `409` for uniqueness conflicts (duplicate assignment, duplicate group slug, etc.).
4. `422` for scope mismatches and invalid payload combinations.

## Compatibility Note

Because this is a hard cutover, frontend and backend route changes ship in the same release with no compatibility shim.

