# Access Implementation Notes

## Purpose

Capture concise implementation-oriented notes for maintainers without duplicating
full redesign analysis.

## Source of Truth Modules

### Backend

- `backend/src/ade_api/features/users/*`
- `backend/src/ade_api/features/groups/*`
- `backend/src/ade_api/features/invitations/*`
- `backend/src/ade_api/features/rbac/*`
- `backend/src/ade_api/features/batch/*`
- `backend/src/ade_api/features/scim/*`
- `backend/src/ade_api/features/admin_scim/*`
- `backend/src/ade_api/features/auth/sso_router.py`
- `backend/src/ade_api/features/authn/*`
- `backend/src/ade_db/migrations/versions/0002_access_model_hard_cutover.py`

### Frontend

- `frontend/src/pages/OrganizationSettings/pages/*`
- `frontend/src/pages/Workspace/sections/Settings/pages/*`
- `frontend/src/api/users/api.ts`
- `frontend/src/api/groups/api.ts`
- `frontend/src/api/invitations/api.ts`
- `frontend/src/api/workspaces/api.ts`
- `frontend/src/hooks/admin/*`

## Migration and Rollback Notes

1. Hard cutover release model; no `/v2` compatibility family.
2. Migration changes for access model live in `0002_access_model_hard_cutover.py`.
3. Rollback is snapshot/image rollback, not migration downgrade.

## Batch Notes

1. Current `POST /api/v1/$batch` scope is user lifecycle only.
2. Keep allowlist strict and per-subrequest authz evaluation mandatory.
3. Expand supported subrequests by registry-driven dispatcher, not ad-hoc parsing.

## Provisioning Notes

1. Provisioning mode is `disabled | jit | scim`.
2. JIT mode uses sign-in hydration for current user memberships.
3. SCIM mode blocks unknown-user JIT auto-create and relies on SCIM/invite provisioning.

## Testing and Documentation Sync

When behavior changes in access areas:

1. Update `docs/reference/access/endpoint-matrix.md`
2. Update `docs/reference/access/permission-matrix.md`
3. Update `docs/reference/access/test-matrix.md`
4. Update `docs/reference/api/access-management.md`
