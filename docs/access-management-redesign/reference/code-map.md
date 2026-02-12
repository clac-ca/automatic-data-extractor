# Code Map (Current -> Target Implementation Areas)

This map identifies where implementation work should occur during cutover.

## Backend API Layer

### Current

- `backend/src/ade_api/features/users/router.py`
- `backend/src/ade_api/features/workspaces/members.py`
- `backend/src/ade_api/features/rbac/router.py`
- `backend/src/ade_api/features/auth/sso_router.py`
- `backend/src/ade_api/features/sso/group_sync.py`

### Target changes

1. Add/normalize feature modules:
   - `features/groups/` (router/service/schemas/repository)
   - `features/invitations/` (router/service/schemas/repository)
   - `features/role_assignments/` (or refactor existing `rbac` assignment routes)
2. Add SCIM module:
   - `features/scim/router.py`
   - `features/scim/service.py`
   - `features/scim/schemas.py`
3. Add API batch module for Graph-style envelope execution:
   - `features/batch/router.py`
   - `features/batch/service.py`
   - `features/batch/schemas.py`
   - wire into `backend/src/ade_api/api/v1/router.py` as `POST /$batch`
4. Remove member-specific assignment routes after cutover.
5. Normalize route registration in `backend/src/ade_api/api/v1/router.py` and add SCIM router mount.

## Backend Domain / Service Layer

### Current

- `backend/src/ade_api/features/rbac/service.py`
- `backend/src/ade_api/features/workspaces/service.py`
- `backend/src/ade_api/features/users/service.py`
- `backend/src/ade_api/features/admin_settings/service.py`

### Target changes

1. Refactor permission evaluator for principal-aware assignments.
2. Add group membership union logic in effective-permission resolution.
3. Add invitation orchestration service (existing user vs new user transaction path).
4. Add provisioning-mode policy service (`disabled|jit|scim`).
5. Keep workspace service focused on workspace lifecycle/settings, not identity lifecycle.
6. Add batch dispatcher with allowlisted user lifecycle operations.
7. Add dependency-graph execution path (`dependsOn`) with `424` error handling.

## Backend Data Model

### Current

- `backend/src/ade_db/models/rbac.py`
- `backend/src/ade_db/models/user.py`
- `backend/src/ade_db/models/sso.py`
- `backend/src/ade_db/migrations/versions/0002_access_model_hard_cutover.py`

### Target changes

1. Finalize `Group`, `GroupMembership`, `Invitation`, `RoleAssignment` model usage.
2. Ensure user fields map cleanly to SCIM enterprise extension.
3. Add any remaining schema adjustments directly to `0002_access_model_hard_cutover.py` (in-place constraint).
4. Store provisioning mode in runtime settings payload (no new table required).

## Auth/SSO Integration

### Current

- `backend/src/ade_api/features/auth/sso_router.py`
- `backend/src/ade_api/features/auth/sso_claims.py`
- `backend/src/ade_api/features/sso/group_sync.py`
- `backend/src/ade_api/features/admin_settings/*`

### Target changes

1. Replace JIT toggle with provisioning-mode enum in admin settings.
2. Keep JIT membership hydration on sign-in only.
3. Remove dependence on tenant-wide background user provisioning via sync jobs.
4. Add SCIM token auth and request/audit instrumentation.

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
4. Add provisioning-mode selector UI in org authentication settings.

## Frontend Access Screens

### Current

- `frontend/src/pages/OrganizationSettings/pages/UsersSettingsPage.tsx`
- `frontend/src/pages/Workspace/sections/Settings/pages/MembersSettingsPage.tsx`
- `frontend/src/pages/Workspace/sections/Settings/pages/RolesSettingsPage.tsx`
- `frontend/src/pages/OrganizationSettings/pages/SystemSsoSettingsPage.tsx`

### Target changes

1. Replace `MembersSettingsPage` with `PrincipalsSettingsPage` (Users + Groups tabs).
2. Add `InvitationsSettingsPage` in workspace access.
3. Add org groups page.
4. Keep shared table/drawer component pattern for continuity.
5. Add provisioning mode control (`disabled|jit|scim`) with helper text.

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
3. Add SCIM admin-status surface (read-only health/diagnostics) if needed.
4. Add users bulk mutation client helper and chunking utility for >20 operations.
5. Regenerate OpenAPI types after backend contract cutover.

## Testing and Validation Areas

1. Backend unit tests for assignment evaluator (direct + group union).
2. API tests for invitation transaction behavior and permission boundaries.
3. SSO callback tests for JIT membership hydration behavior.
4. SCIM contract tests for Users/Groups/filter/PATCH semantics.
5. E2E UI tests for org/workspace access flows on desktop and mobile.
6. Migration verification tests (assignment parity and effective permission parity).
7. Batch API tests for partial success, permission boundaries, and throttling/retry behavior.
8. Batch client tests for chunking, dependency correlation, and per-item error surfacing.
9. Maintain scenario/status mapping in `docs/access-management-redesign/reference/access-test-matrix.md`.
10. Enforce implementation approach in `docs/access-management-redesign/recommendations/access-management-test-coverage-plan.md`.
