# Target Model (Recommended)

This is the single recommended design for hard cutover.

## Model Overview

Adopt a principal-centric access model:

- Principals: `user`, `group`
- Scopes: `organization`, `workspace`
- Grants: role assignments from principal to scope
- Membership: user-to-group links (assigned or dynamic)

This yields one mental model across organization and workspace screens:

`Principal -> Assignment(s) -> Effective Access`

## Resource Set

1. `users`
2. `groups`
3. `groupMemberships`
4. `roles`
5. `roleAssignments`
6. `invitations`

## RBAC and Scope Rules

1. Role definitions are scope-typed (`organization` or `workspace`).
2. Assignments enforce scope compatibility.
3. Effective permissions are union of direct + group-derived grants.
4. Inactive users have no effective access, regardless of assignments.
5. Workspace-owner delegated admin is enabled through workspace permissions, not global user-admin grants.

## Invitation-Driven Provisioning

Default user-add flow for workspace access:

1. Actor opens workspace principals screen.
2. Actor enters email and initial workspace role(s).
3. System calls `POST /api/v1/invitations` with workspace context.
4. System either:
   - links existing user and creates assignment, or
   - creates invited user + invitation + assignment atomically.

This directly solves the “workspace owner can create users without org user permissions” requirement.

## Groups (Future-Ready, First-Cut Safe)

- Support both:
  - `assigned` memberships (ADE-managed)
  - `dynamic` memberships (IdP-managed, read-only in ADE)
- Keep nested groups out of first cut.
- Add `external_id` + sync metadata to support Entra/SCIM reconciliation.

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

1. Keep user creation globally privileged only.
   - Rejected: blocks delegated admin and harms onboarding velocity.
2. Grant workspace owners global user-management permissions.
   - Rejected: violates least-privilege boundaries.
3. Build internal dynamic-group rules in first cut.
   - Rejected: high complexity and delivery risk for hard cutover.
4. Keep mixed legacy route families.
   - Rejected: locks in conceptual drift and technical debt.

## Why this is the right cutover

- It is standard, not bespoke.
- It aligns to Graph/Entra patterns while respecting ADE constraints.
- It resolves current UX and policy pain without overbuilding.
- It is implementation-ready with clear API/data/UI boundaries.

