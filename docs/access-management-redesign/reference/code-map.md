# Code Map (Current -> Target Implementation Areas)

This map identifies where implementation work should occur during cutover.

## Backend API Layer

### Current

- `backend/src/ade_api/features/users/router.py`
- `backend/src/ade_api/features/workspaces/members.py`
- `backend/src/ade_api/features/rbac/router.py`

### Target changes

1. Add new feature modules:
   - `features/groups/` (router/service/schemas/repository)
   - `features/invitations/` (router/service/schemas/repository)
   - `features/role_assignments/` (or refactor existing `rbac` assignment routes)
2. Remove member-specific assignment routes after cutover.
3. Normalize route registration in `backend/src/ade_api/api/v1/router.py`.

## Backend Domain / Service Layer

### Current

- `backend/src/ade_api/features/rbac/service.py`
- `backend/src/ade_api/features/workspaces/service.py`
- `backend/src/ade_api/features/users/service.py`

### Target changes

1. Refactor permission evaluator for principal-aware assignments.
2. Add group membership union logic in effective-permission resolution.
3. Add invitation orchestration service (existing user vs new user transaction path).
4. Keep workspace service focused on workspace lifecycle/settings, not identity lifecycle.

## Backend Data Model

### Current

- `backend/src/ade_db/models/rbac.py`
- `backend/src/ade_db/models/user.py`
- `backend/src/ade_db/models/sso.py`

### Target changes

1. Add `Group`, `GroupMembership`, `Invitation`, `RoleAssignment` models.
2. Extend `User` with AD/Entra profile fields and external sync metadata.
3. Introduce migrations and backfill scripts for assignment model conversion.

## Auth/SSO Integration

### Current

- `backend/src/ade_api/features/auth/sso_router.py`
- `backend/src/ade_api/features/auth/sso_claims.py`
- `backend/src/ade_api/features/sso/router.py`

### Target changes

1. Add sync integration service for provider groups/memberships.
2. Persist external IDs and source metadata for users/groups.
3. Add observability and audit around sync actions.

## Frontend Routes and IA

### Current

- `frontend/src/pages/OrganizationSettings/index.tsx`
- `frontend/src/pages/OrganizationSettings/settingsNav.tsx`
- `frontend/src/pages/Workspace/sections/Settings/index.tsx`
- `frontend/src/pages/Workspace/sections/Settings/settingsNav.tsx`

### Target changes

1. Normalize org routes to `/organization/access/*`.
2. Normalize workspace access routes to `/settings/access/*` with `principals|roles|invitations`.
3. Update route resolvers and search indexing for new paths.

## Frontend Access Screens

### Current

- `frontend/src/pages/OrganizationSettings/pages/UsersSettingsPage.tsx`
- `frontend/src/pages/Workspace/sections/Settings/pages/MembersSettingsPage.tsx`
- `frontend/src/pages/Workspace/sections/Settings/pages/RolesSettingsPage.tsx`

### Target changes

1. Replace `MembersSettingsPage` with `PrincipalsSettingsPage` (Users + Groups tabs).
2. Add `InvitationsSettingsPage` in workspace access.
3. Add org groups page.
4. Keep shared table/drawer component pattern for continuity.

## Frontend API Clients and Hooks

### Current

- `frontend/src/api/users/api.ts`
- `frontend/src/api/workspaces/api.ts`
- `frontend/src/api/admin/users.ts`
- `frontend/src/api/admin/roles.ts`
- `frontend/src/hooks/users/useUsersQuery.ts`
- `frontend/src/pages/Workspace/sections/Settings/hooks/useWorkspaceMembers.ts`

### Target changes

1. Add clients for groups, invitations, and normalized role assignments.
2. Replace member-specific hooks with principal-aware hooks.
3. Regenerate OpenAPI types after backend contract cutover.

## Testing and Validation Areas

1. Backend unit tests for assignment evaluator (direct + group union).
2. API tests for invitation transaction behavior and permission boundaries.
3. E2E UI tests for org/workspace access flows on desktop and mobile.
4. Migration verification tests (assignment parity and effective permission parity).

