# Unified Settings Console

This document defines the active `/settings` admin console contract and permission behavior.

## Routes

### Home
- `/settings`

### Organization
- `/settings/organization/users`
- `/settings/organization/users/create`
- `/settings/organization/users/:userId`
- `/settings/organization/groups`
- `/settings/organization/groups/create`
- `/settings/organization/groups/:groupId`
- `/settings/organization/roles`
- `/settings/organization/roles/create`
- `/settings/organization/roles/:roleId`
- `/settings/organization/api/keys`
- `/settings/organization/authentication`
- `/settings/organization/run/controls`

### Workspaces
- `/settings/workspaces`
- `/settings/workspaces/:workspaceId/general`
- `/settings/workspaces/:workspaceId/processing`
- `/settings/workspaces/:workspaceId/access/principals`
- `/settings/workspaces/:workspaceId/access/principals/create`
- `/settings/workspaces/:workspaceId/access/principals/:principalType/:principalId`
- `/settings/workspaces/:workspaceId/access/roles`
- `/settings/workspaces/:workspaceId/access/roles/create`
- `/settings/workspaces/:workspaceId/access/roles/:roleId`
- `/settings/workspaces/:workspaceId/access/invitations`
- `/settings/workspaces/:workspaceId/access/invitations/create`
- `/settings/workspaces/:workspaceId/access/invitations/:invitationId`
- `/settings/workspaces/:workspaceId/lifecycle/danger`

## Legacy Route Policy
- `/organization/*` is not registered.
- `/workspaces/:workspaceId/settings/*` is not registered.
- No compatibility redirects are provided.

## Permission Behavior

### Navigation visibility
- Unauthorized settings sections are hidden from the left rail.
- Workspace section visibility is evaluated against the currently selected workspace permission set.

### Deep links
- Unauthorized deep links render a settings access-denied state.
- Unknown workspace IDs in `/settings/workspaces/:workspaceId/*` render workspace-not-found state.

## QA Checklist
- Home page shows Organization and Workspaces entry surfaces only when authorized.
- Organization list pages route to full-page create and detail routes.
- Workspace list page routes to full-page section routes.
- Principal, role, and invitation routes use `create` and deep-link detail paths.
- Dirty detail pages show sticky save/discard actions.
- Authentication page keeps the existing SSO setup popup flow.
- Workspace general page does not include user-level appearance/theme controls.
