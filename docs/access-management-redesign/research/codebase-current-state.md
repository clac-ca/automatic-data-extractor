# Codebase Current State (Source of Truth)

This document captures current behavior from the ADE codebase and highlights constraints relevant to the access-management redesign.

## Backend: Current Access and Role Shape

### 1. User management is globally gated

- `/api/v1/users` list/read uses `users.read_all`.
  - `backend/src/ade_api/features/users/router.py:52`
  - `backend/src/ade_api/features/users/router.py:125`
- `/api/v1/users` create/update/deactivate uses `users.manage_all`.
  - `backend/src/ade_api/features/users/router.py:95`
  - `backend/src/ade_api/features/users/router.py:155`
  - `backend/src/ade_api/features/users/router.py:183`
- Consequence: workspace owners cannot create/invite users unless they also hold global user-admin permission.

### 2. Workspace member management is a separate model and only adds existing users

- Workspace members routes exist under `/api/v1/workspaces/{workspaceId}/members`.
  - `backend/src/ade_api/features/workspaces/members.py:29`
- Listing requires `workspace.members.read`; modify requires `workspace.members.manage`.
  - `backend/src/ade_api/features/workspaces/members.py:64`
  - `backend/src/ade_api/features/workspaces/members.py:99`
- Add member payload requires `user_id` + `role_ids` only.
  - `backend/src/ade_api/features/workspaces/schemas.py:75`
- Service path never provisions/invites; it only assigns roles to an existing `user_id` and creates `workspace_memberships` rows.
  - `backend/src/ade_api/features/workspaces/service.py:621`
  - `backend/src/ade_api/features/workspaces/service.py:650`

### 3. RBAC assignment model is user-only

- `user_role_assignments` has `user_id`, `role_id`, optional `workspace_id`.
  - `backend/src/ade_db/models/rbac.py:113`
  - `backend/src/ade_db/models/rbac.py:118`
  - `backend/src/ade_db/models/rbac.py:124`
- No `principal_type` or `group_id` dimension.
- Permission evaluation joins role assignments by user directly.
  - `backend/src/ade_api/features/rbac/service.py:754`
  - `backend/src/ade_api/features/rbac/service.py:787`
- Consequence: no native group-derived grants.

### 4. Role/assignment routes are mixed and partly legacy

- Role definitions live at `/api/v1/roles` and assignment listing at `/api/v1/roleassignments`.
  - `backend/src/ade_api/features/rbac/router.py:239`
  - `backend/src/ade_api/features/rbac/router.py:453`
- Global user-role assignment is under `/api/v1/users/{userId}/roles/{roleId}`.
  - `backend/src/ade_api/features/rbac/router.py:582`
- Workspace membership role assignment uses a different route family (`/workspaces/{workspaceId}/members`).
  - `backend/src/ade_api/features/workspaces/members.py:29`
- Consequence: principal/assignment semantics are split across APIs.

### 5. Permission vocabulary mismatch exists in frontend nav

- Registry defines `workspace.members.read` and `workspace.roles.read`.
  - `backend/src/ade_api/core/rbac/registry.py:125`
  - `backend/src/ade_api/core/rbac/registry.py:179`
- Workspace settings nav checks `workspace.members.view` and `workspace.roles.view`.
  - `frontend/src/pages/Workspace/sections/Settings/settingsNav.tsx:74`
  - `frontend/src/pages/Workspace/sections/Settings/settingsNav.tsx:83`
- Consequence: avoidable UI gating drift risk.

### 6. User data model is minimal for profile attributes

- User entity includes core auth fields and `display_name`, but no common AD profile fields (job title, department, office, phones, employee id).
  - `backend/src/ade_db/models/user.py:46`
  - `backend/src/ade_db/models/user.py:49`
- SSO identity linkage exists (`sso_identities`) but no group sync model.
  - `backend/src/ade_db/models/sso.py:144`

## Frontend: Current Route and UX Shape

### 1. Organization and workspace access surfaces diverge

- Org users route path remains `/organization/users`.
  - `frontend/src/pages/OrganizationSettings/pages/UsersSettingsPage.tsx:84`
- Workspace members route path is `/workspaces/:workspaceId/settings/access/members`.
  - `frontend/src/pages/Workspace/sections/Settings/pages/MembersSettingsPage.tsx:87`
- Org settings have `identity/users/roles`, workspace has `access/members/roles`; naming and route structure are not unified.
  - `frontend/src/pages/OrganizationSettings/settingsNav.tsx:58`
  - `frontend/src/pages/Workspace/sections/Settings/settingsNav.tsx:69`

### 2. Workspace add-member depends on global users API

- Workspace Add Member directory uses `useUsersQuery` -> `GET /api/v1/users`.
  - `frontend/src/pages/Workspace/sections/Settings/pages/MembersSettingsPage.tsx:289`
  - `frontend/src/api/users/api.ts:25`
- Since `/api/v1/users` is globally permissioned, workspace owner flows are coupled to org-level user read permission.

### 3. Workspace member rows can degrade to UUID-only identity rendering

- Workspace member schema only includes user and role ids/slugs, no guaranteed embedded user profile.
  - `backend/src/ade_api/features/workspaces/schemas.py:66`
- UI falls back to `user_id` when profile is absent.
  - `frontend/src/pages/Workspace/sections/Settings/pages/MembersSettingsPage.tsx:65`
  - `frontend/src/pages/Workspace/sections/Settings/pages/MembersSettingsPage.tsx:180`

## Current Constraints Summary

1. No first-class principal abstraction (user/group).
2. No group entities or membership sync semantics.
3. Workspace-owner invite/provision path is blocked by global user permission boundaries.
4. API and route information architecture is inconsistent between org and workspace access.
5. Frontend permission keys are not fully aligned with backend registry.
6. User profile schema is insufficient for AD/Entra-aligned identity attributes.

These constraints require a normalized hard cutover rather than incremental UI tweaks.

