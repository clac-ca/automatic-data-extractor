# API Routes (Hard Cutover, Graph + SCIM Aligned)

## Design Principles

1. No `/v2` parallel family.
2. Resource-first endpoints for application APIs (`/api/v1`).
3. Standards-shaped SCIM endpoints for enterprise provisioning (`/scim/v2`).
4. Consistent assignment resource for both org and workspace scopes.
5. Graph-like group membership reference operations.
6. Invitation as first-class resource.

## Canonical ADE API Route Set

Base: `/api/v1`

### Users

- `GET /users`
- `POST /users`
- `GET /users/{userId}`
- `PATCH /users/{userId}`
- `POST /users/{userId}/deactivate`

Notes:

- `POST /users` is for organization admins and system paths.
- Workspace-owner provisioning uses invitations.

### Batch (Graph-style envelope)

- `POST /$batch`

Notes:

1. Phase 1 supports user lifecycle operations only:
   - `POST /users`
   - `PATCH /users/{userId}`
   - `POST /users/{userId}/deactivate` (delete-equivalent in ADE policy)
2. Max 20 subrequests per batch.
3. Partial success is expected; each subrequest returns its own status/body.
4. Per-subrequest authorization uses existing permission rules.
5. Optional `dependsOn` enables dependency sequencing; failed dependency returns item-level `424`.

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

## SCIM Provisioning Route Set

Base: `/scim/v2`

### Discovery

- `GET /ServiceProviderConfig`
- `GET /Schemas`
- `GET /ResourceTypes`

### Users

- `GET /Users`
- `POST /Users`
- `GET /Users/{id}`
- `PATCH /Users/{id}`
- `PUT /Users/{id}`

### Groups

- `GET /Groups`
- `POST /Groups`
- `GET /Groups/{id}`
- `PATCH /Groups/{id}`
- `PUT /Groups/{id}`

### Explicitly deferred

- `POST /Bulk`

## Provisioning Mode Interaction

1. `disabled`: SCIM routes disabled; SSO login cannot auto-provision.
2. `jit`: SCIM routes disabled; SSO login can JIT-provision and hydrates current user memberships.
3. `scim`: SCIM routes enabled; SSO login does not JIT-create unknown users.

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
| `PUT/DELETE /workspaces/{workspaceId}/members/{userId}` | `DELETE /roleAssignments/{assignmentId}` + create/delete assignments | Normalize to assignment resource semantics |
| `GET /users/{userId}/roles` and `PUT/DELETE /users/{userId}/roles/{roleId}` | `GET/POST/DELETE /roleAssignments...` | Remove user-specific special-case routes |
| `GET /roleassignments` | `GET /roleAssignments` | Rename and standardize casing |

## Error Contract Expectations

1. `403` for permission boundary violations.
2. `404` for unknown resource IDs.
3. `409` for uniqueness/read-only conflicts.
4. `422` for scope mismatches and invalid payload combinations.

## Compatibility Note

Because this is hard cutover, frontend and backend route changes ship in the same release with no compatibility shim.
