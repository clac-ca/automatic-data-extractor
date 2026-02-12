# Access Test Matrix

This matrix defines required test coverage for access-management behavior.  
Status values:

1. `covered`: implemented and passing
2. `partial`: some coverage exists but key cases missing
3. `missing`: no meaningful coverage yet

## RBAC and Permission Boundaries

| Area | Scenario | Layer | Current file target | Status |
|---|---|---|---|---|
| Permission boundary | Global admin can perform org user/group/role mutations | Backend integration | `backend/tests/api/integration/users/test_users_router.py`, `backend/tests/api/integration/roles/test_roles_router.py` | covered |
| Permission boundary | Workspace owner can manage workspace role assignments but not org-wide users | Backend integration | `backend/tests/api/integration/roles/test_roles_router.py`, `backend/tests/api/integration/users/test_users_batch_router.py` | covered |
| Permission boundary | Workspace member cannot manage members/roles/invitations | Backend integration | `backend/tests/api/integration/roles/test_roles_router.py`, `backend/tests/api/integration/users/test_invitations_router.py` | partial |
| Effective access | Direct + group grants union deterministically | Backend integration + unit | `backend/tests/api/integration/roles/test_roles_router.py` | partial |
| Effective access | Deactivated user denied despite inherited grants | Backend integration | `backend/tests/api/integration/users/test_users_router.py` | covered |

## Invitations and Delegated Provisioning

| Area | Scenario | Layer | Current file target | Status |
|---|---|---|---|---|
| Invitations | Workspace owner invites unknown email with workspace role seed | Backend integration | `backend/tests/api/integration/users/test_invitations_router.py` | covered |
| Invitations | Invite existing user does not create duplicate identity | Backend integration | `backend/tests/api/integration/users/test_invitations_router.py` | covered |
| Invitations | Workspace-scoped invite read/manage boundaries | Backend integration | `backend/tests/api/integration/users/test_invitations_router.py` | covered |
| Invitations UI | List, resend, cancel states and permission gating | Frontend component/api | `frontend/src/pages/Workspace/sections/Settings/__tests__/invitationsSettingsPage.test.tsx` | covered |

## Groups and Membership Ownership

| Area | Scenario | Layer | Current file target | Status |
|---|---|---|---|---|
| Group lifecycle | Create/update/delete group with org permissions | Backend integration | `backend/tests/api/integration/roles/test_roles_router.py` | partial |
| Membership refs | Add/remove membership via `$ref` | Backend integration | `backend/tests/api/integration/roles/test_roles_router.py` | covered |
| Provider-managed guard | `source=idp` group membership mutation returns `409` | Backend integration | `backend/tests/api/integration/roles/test_roles_router.py` | covered |
| Group UI | Group management drawer and members rendering | Frontend component | `frontend/src/pages/OrganizationSettings/pages/GroupsSettingsPage.tsx` tests (new) | missing |

## Provisioning Modes and SSO/JIT

| Area | Scenario | Layer | Current file target | Status |
|---|---|---|---|---|
| Settings | Read/write provisioningMode (`disabled|jit|scim`) and legacy normalization | Backend integration + unit | `backend/tests/api/integration/features/admin_settings/test_admin_settings_router.py`, `backend/tests/api/unit/features/admin_settings/test_service.py` | covered |
| SSO callback | `disabled` and `scim` block unknown sign-in auto-provision | Backend integration | `backend/tests/api/integration/features/sso/test_auth_sso_callback.py` | covered |
| SSO callback | `jit` allows unknown sign-in and hydrates memberships | Backend integration | `backend/tests/api/integration/features/sso/test_auth_sso_callback.py` | covered |
| SSO callback | Hydration failure does not block login + async retry scheduling | Backend integration | `backend/tests/api/integration/features/sso/test_auth_sso_callback.py` | partial |
| JIT membership sync | Reconcile known user memberships only | Backend integration | `backend/tests/api/integration/features/sso/test_group_sync.py` | covered |
| SSO settings UI | Provisioning mode selection, lock-state, validation messages | Frontend component | `frontend/src/pages/OrganizationSettings/__tests__/systemSsoSettingsPage.test.tsx` | covered |

## SCIM

| Area | Scenario | Layer | Current file target | Status |
|---|---|---|---|---|
| Mode gating | SCIM routes blocked when mode != `scim` | Backend integration | `backend/tests/api/integration/features/scim/test_scim_router.py` | covered |
| Auth | SCIM token lifecycle and revoked token enforcement | Backend integration | `backend/tests/api/integration/features/admin_settings/test_admin_scim_tokens_router.py`, `backend/tests/api/integration/features/scim/test_scim_router.py` | covered |
| User provisioning | SCIM create/list/patch user semantics | Backend integration | `backend/tests/api/integration/features/scim/test_scim_router.py` | covered |
| Group provisioning | SCIM group create/patch membership semantics and invalid member handling | Backend integration | `backend/tests/api/integration/features/scim/test_scim_router.py` | covered |
| SCIM contracts | Error envelope and content-type compliance across key failures | Backend integration | `backend/tests/api/integration/features/scim/test_scim_router.py` | partial |

## Batch User Lifecycle (`POST /api/v1/$batch`)

| Area | Scenario | Layer | Current file target | Status |
|---|---|---|---|---|
| Envelope validation | max size, duplicate ids, unsupported method/url | Backend unit + integration | `backend/tests/api/unit/features/batch/test_batch_service.py`, `backend/tests/api/integration/users/test_users_batch_router.py` | covered |
| Mixed outcomes | partial success with per-item status correlation | Backend integration | `backend/tests/api/integration/users/test_users_batch_router.py` | covered |
| Dependencies | `dependsOn` success chain and `424` on dependency failure | Backend unit + integration | `backend/tests/api/unit/features/batch/test_batch_service.py`, `backend/tests/api/integration/users/test_users_batch_router.py` | covered |
| Authz | per-item permission enforcement with mixed permitted/denied items | Backend integration | `backend/tests/api/integration/users/test_users_batch_router.py` | covered |
| Client behavior | chunking and failed-item retry behavior | Frontend API tests | `frontend/src/api/users/__tests__/api.test.ts` | covered |

## Frontend Route and UX Consistency

| Area | Scenario | Layer | Current file target | Status |
|---|---|---|---|---|
| Org route IA | `/organization/access/*` route resolution + nav visibility | Frontend component | `frontend/src/pages/OrganizationSettings/__tests__/settingsNav.test.tsx` | covered |
| Workspace route IA | `/workspaces/:id/settings/access/*` route resolution + nav visibility | Frontend component | `frontend/src/pages/Workspace/sections/Settings/__tests__/settingsNav.test.ts` | covered |
| Principals screen | Users/Groups tabs and drawer actions with permission gating | Frontend component | `frontend/src/pages/Workspace/sections/Settings/pages/MembersSettingsPage.tsx` tests (new) | missing |
| Org users first-class flow | Create user stepper includes assignment step and review | Frontend component + E2E | `frontend/src/pages/OrganizationSettings/__tests__/usersSettingsPage.test.tsx`, Playwright access suite | missing |
| Workspace principal parity | Add principal supports existing user, invite, and group paths | Frontend component + E2E | `frontend/src/pages/Workspace/sections/Settings/__tests__/principalsSettingsPage.test.tsx`, Playwright access suite | missing |
| Invitations clarity | List renders role seeds/inviter metadata and safe actions | Frontend component | `frontend/src/pages/Workspace/sections/Settings/__tests__/invitationsSettingsPage.test.tsx` | partial |
| Batch UX | Bulk action toolbar + partial-success retry-failed behavior | Frontend component + API tests | `frontend/src/pages/SharedAccess/__tests__/batchResultPanel.test.tsx`, `frontend/src/api/users/__tests__/api.test.ts` | missing |
| Accessibility | Drawer keyboard/focus/action accessibility on access surfaces | Frontend component + E2E | Access page tests + Playwright keyboard flows | missing |
| Mobile parity | primary actions/destructive actions are reachable and safe | E2E | Playwright access suite (new) | missing |

## CI Gate Mapping

| Gate | Command | Required for access-management PRs |
|---|---|---|
| Backend tests | `cd backend && uv run ade api test` | yes |
| Frontend tests | `cd backend && uv run ade web test` | yes |
| OpenAPI types | `cd backend && uv run ade api types` | yes |
| Frontend typecheck | `cd frontend && npm run typecheck` (or project equivalent) | yes |

## Ownership and Maintenance

1. Update this matrix whenever routes/permissions/provisioning behavior changes.
2. PRs touching access-management code should include matrix delta (`status` updates).
3. Do not mark `covered` unless at least one deterministic test exists for both success and failure path.
