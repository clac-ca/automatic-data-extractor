# Manage Users and Access

## Goal

Create and manage users, groups, invitations, and role assignments using the
hard-cutover principal-based access model.

## Before You Start

1. Confirm your permission scope:
   - organization admin tasks need org-level permissions (`users.*`, `groups.*`, `roles.*`)
   - workspace delegation tasks need workspace permissions (`workspace.members.*`, `workspace.roles.*`, `workspace.invitations.*`)
2. Confirm provisioning mode for your organization:
   - `disabled`, `jit`, or `scim`
3. Use current routes only:
   - `roleAssignments` (camelCase)
   - no legacy `/members` or `/users/{userId}/roles*` endpoints

## Steps

### 1. List users and groups

```bash
curl -sS "$ADE_URL/api/v1/users?limit=50" \
  -H "X-API-Key: $ADE_API_KEY"

curl -sS "$ADE_URL/api/v1/groups" \
  -H "X-API-Key: $ADE_API_KEY"
```

### 2. Create user (org scope)

```bash
curl -sS -X POST "$ADE_URL/api/v1/users" \
  -H "X-API-Key: $ADE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "displayName": "User Example",
    "passwordProfile": {
      "mode": "auto_generate",
      "forceChangeOnNextSignIn": true
    }
  }'
```

### 3. Create or update group

```bash
curl -sS -X POST "$ADE_URL/api/v1/groups" \
  -H "X-API-Key: $ADE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "display_name": "Finance Reviewers",
    "membership_mode": "assigned",
    "source": "internal"
  }'
```

Add a member to an internal assigned group:

```bash
curl -sS -X POST "$ADE_URL/api/v1/groups/$GROUP_ID/members/\$ref" \
  -H "X-API-Key: $ADE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"memberId": "'$USER_ID'"}'
```

Add an owner to an internal assigned group:

```bash
curl -sS -X POST "$ADE_URL/api/v1/groups/$GROUP_ID/owners/\$ref" \
  -H "X-API-Key: $ADE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"ownerId": "'$USER_ID'"}'
```

### 4. Manage group membership from user context (`memberOf`)

List a user's memberships:

```bash
curl -sS "$ADE_URL/api/v1/users/$USER_ID/memberOf" \
  -H "X-API-Key: $ADE_API_KEY"
```

Add a user to a group:

```bash
curl -sS -X POST "$ADE_URL/api/v1/users/$USER_ID/memberOf/\$ref" \
  -H "X-API-Key: $ADE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"groupId": "'$GROUP_ID'"}'
```

### 5. Assign roles to users or groups

Organization assignment:

```bash
curl -sS -X POST "$ADE_URL/api/v1/roleAssignments" \
  -H "X-API-Key: $ADE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "principal_type": "user",
    "principal_id": "'$USER_ID'",
    "role_id": "'$ORG_ROLE_ID'"
  }'
```

Workspace assignment:

```bash
curl -sS -X POST "$ADE_URL/api/v1/workspaces/$WORKSPACE_ID/roleAssignments" \
  -H "X-API-Key: $ADE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "principal_type": "group",
    "principal_id": "'$GROUP_ID'",
    "role_id": "'$WORKSPACE_ROLE_ID'"
  }'
```

### 6. Invite user into workspace (workspace-owner path)

```bash
curl -sS -X POST "$ADE_URL/api/v1/invitations" \
  -H "X-API-Key: $ADE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "invitedUserEmail": "new.user@example.com",
    "workspaceContext": {
      "workspaceId": "'$WORKSPACE_ID'",
      "roleAssignments": [{"roleId": "'$WORKSPACE_ROLE_ID'"}]
    }
  }'
```

### 7. Batch high-volume user lifecycle operations

```bash
curl -sS -X POST "$ADE_URL/api/v1/\$batch" \
  -H "X-API-Key: $ADE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "requests": [
      {"id": "1", "method": "PATCH", "url": "/users/'$USER_ID'", "body": {"department": "Finance"}},
      {"id": "2", "method": "POST", "url": "/users/'$USER_ID'/deactivate"}
    ]
  }'
```

## Verify

1. List assignments in organization and workspace scopes.
2. Confirm expected principal appears in workspace principals UI.
3. Confirm invitation status and seeded role assignments.
4. For deactivation, confirm access is denied for the user.

```bash
curl -sS "$ADE_URL/api/v1/roleAssignments" -H "X-API-Key: $ADE_API_KEY"
curl -sS "$ADE_URL/api/v1/workspaces/$WORKSPACE_ID/roleAssignments" -H "X-API-Key: $ADE_API_KEY"
curl -sS "$ADE_URL/api/v1/invitations?workspaceId=$WORKSPACE_ID" -H "X-API-Key: $ADE_API_KEY"
```

## If Something Fails

1. `403 Forbidden`:
   - check org vs workspace permission boundary for the caller.
2. `409 Conflict`:
   - check duplicate state (existing assignment or immutable/provider-managed group membership).
3. `422 Unprocessable Content`:
   - validate request field casing and scope-compatible role usage.
4. `404 Not Found`:
   - verify principal, role, assignment, invitation, or workspace identifiers.

Related:

- [Access Management API Reference](../reference/api/access-management.md)
- [Access Reference](../reference/access/README.md)
- [Access Management Incident Runbook](../troubleshooting/access-management-incident-runbook.md)
