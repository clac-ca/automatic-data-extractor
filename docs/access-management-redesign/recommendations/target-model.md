# Target Model (Recommended)

This is the single recommended design for hard cutover.

## Model Overview

Adopt a principal-centric access model with explicit provisioning modes.

- Principals: `user`, `group`
- Scopes: `organization`, `workspace`
- Grants: role assignments from principal to scope
- Membership: user-to-group links (internal or provider-managed)
- Provisioning modes: `disabled | jit | scim`

Core mental model:

`Provisioning Mode -> Principal Records -> Role Assignment(s) -> Effective Access`

## Resource Set

1. `users`
2. `groups`
3. `groupMemberships`
4. `roles`
5. `roleAssignments`
6. `invitations`
7. `scim` discovery and provisioning resources (`/scim/v2/...`)

## RBAC and Scope Rules

1. Role definitions are scope-typed (`organization` or `workspace`).
2. Assignments enforce scope compatibility.
3. Effective permissions are union of direct + group-derived grants.
4. Inactive users have no effective access regardless of assignments.
5. Workspace-owner delegated admin is enabled through workspace permissions, not global user-admin grants.

## Provisioning Modes

### 1. `disabled`

- No automatic user creation on SSO login.
- Users enter by invite/admin create only.

### 2. `jit`

- Users may be created on first SSO login if policy permits.
- Group memberships hydrate at sign-in for that user only.
- No tenant-wide background sync that provisions unknown users.

### 3. `scim`

- SCIM endpoints provide automated user/group lifecycle.
- SSO login links existing identity; unknown users are not auto-created by JIT in this mode.

## Invitation-Driven Provisioning for Workspace Owners

Default workspace add flow remains invitation-based:

1. Actor opens workspace principals screen.
2. Actor enters email and initial workspace role(s).
3. System calls `POST /api/v1/invitations` with workspace context.
4. System either:
   - links existing user and creates assignment, or
   - creates invited user + invitation + assignment atomically.

This solves the delegated-admin requirement without global user-management grants.

## Groups (Future-Ready, First-Cut Safe)

- Support both internal assigned groups and provider-managed groups.
- Provider-managed groups are read-only in ADE membership mutation APIs.
- Nested groups remain out of first cut.

## UI Information Architecture

### Organization

- `/organization/access/users`
- `/organization/access/groups`
- `/organization/access/roles`

### Workspace

- `/workspaces/:workspaceId/settings/access/principals`
- `/workspaces/:workspaceId/settings/access/roles`
- `/workspaces/:workspaceId/settings/access/invitations`

Principals page includes segmented tabs (Users | Groups) with one shared table + one shared drawer pattern.

## Rejected Alternatives

1. Keep create-user globally privileged only.
2. Grant workspace owners global user-management permissions.
3. Keep mixed legacy routes and assignment semantics.
4. Keep background group sync as implicit user-provisioning path.
5. Remove JIT entirely and require SCIM for all organizations.

## Why This Model

1. It is standard and follows common Graph/SCIM conventions.
2. It keeps policy boundaries explicit and auditable.
3. It supports both enterprise and non-enterprise operators.
4. It simplifies runtime behavior with clear mode ownership.
