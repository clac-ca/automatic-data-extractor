# Codebase Current State (Source of Truth)

This document captures current behavior from the ADE codebase and highlights constraints relevant to the access-management redesign and SCIM/provisioning-mode decisions.

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

### 6. User data model is now partially enterprise-ready

- Migration `0002_access_model_hard_cutover` already introduces AD-like user profile fields and `source/external_id/last_synced_at`.
  - `backend/src/ade_db/migrations/versions/0002_access_model_hard_cutover.py:58`
- `groups`, `group_memberships`, `role_assignments`, and `invitations` tables are defined in the same migration.
  - `backend/src/ade_db/migrations/versions/0002_access_model_hard_cutover.py:96`

### 7. Current auth policy exposes JIT toggle, not full provisioning mode

- Runtime settings support `auth.identityProvider.jitProvisioningEnabled` only.
  - `backend/src/ade_api/features/admin_settings/schemas.py:42`
  - `backend/src/ade_api/features/admin_settings/service.py:150`
- No `disabled|jit|scim` enum exists yet.

### 8. Current group sync implementation has two paths

- Scheduled full sync path exists in `GroupSyncService.run_once(...)` and pulls provider users/groups.
  - `backend/src/ade_api/features/sso/group_sync.py:251`
- Sign-in per-user hydration exists in SSO callback (`sync_user_memberships`).
  - `backend/src/ade_api/features/auth/sso_router.py:561`
  - `backend/src/ade_api/features/sso/group_sync.py:292`
- Current implementation already links known users and skips unknown provider members in background reconciliation.
  - `backend/src/ade_api/features/sso/group_sync.py:347`
  - `backend/src/ade_api/features/sso/group_sync.py:481`

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

### 3. Org auth settings page currently models only JIT toggle for provisioning strategy

- UI state and save payload include `idpJitProvisioningEnabled`, but no explicit provisioning mode selector.
  - `frontend/src/pages/OrganizationSettings/pages/SystemSsoSettingsPage.tsx:73`
  - `frontend/src/pages/OrganizationSettings/pages/SystemSsoSettingsPage.tsx:118`

## Current Constraints Summary

1. Access routes and UI IA are still split between org and workspace mental models.
2. Provisioning policy lacks an explicit `disabled|jit|scim` mode selector.
3. Scheduled group sync plus login-time hydration creates conceptual overlap.
4. API naming remains partly legacy and inconsistent.
5. Frontend permission keys are not fully aligned with backend registry.

These constraints justify a standards-aligned simplification: explicit provisioning modes plus clear separation of provisioning and access assignment semantics.
