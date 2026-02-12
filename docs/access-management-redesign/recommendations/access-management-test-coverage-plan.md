# Access Management Test Coverage Plan

## Summary

Define and enforce a complete test strategy for ADE access management so behavior remains correct across org/workspace RBAC, invitations, groups, provisioning modes (`disabled|jit|scim`), and batch mutations.

This plan is implementation-focused and designed to close coverage gaps without adding brittle tests.

## Objectives

1. Ensure permission boundaries are provably correct for all core actors.
2. Ensure identity/provisioning paths are deterministic and policy-safe.
3. Ensure API contracts are stable and well tested end to end.
4. Ensure UI behavior is consistent with backend authorization and error semantics.
5. Keep tests maintainable, fast, and easy to reason about.

## Best-Practice Principles

1. Test behavior, not implementation details.
2. Use a testing pyramid:
   - unit tests for evaluator and validation logic
   - integration tests for API + DB boundaries
   - targeted e2e tests for critical user flows
3. Keep fixtures deterministic and explicit.
4. Prefer matrix-driven authorization tests (actor x endpoint x expected outcome).
5. Validate failure paths as rigorously as happy paths.
6. Use contract tests for external protocol surfaces (SCIM and batch envelope).
7. Gate merges on risk-relevant suites, not only broad smoke tests.

## Coverage Scope

## Backend domains in scope

1. Users lifecycle (`/api/v1/users*`)
2. Groups and memberships (`/api/v1/groups*`)
3. Invitations (`/api/v1/invitations*`)
4. Role definitions and assignments (`/api/v1/roles*`, `/api/v1/roleAssignments*`)
5. Provisioning mode policy (`disabled|jit|scim`)
6. SSO callback/JIT hydration and identity linking
7. SCIM provisioning (`/scim/v2/*`)
8. Batch envelope for user lifecycle (`/api/v1/$batch`)

## Frontend surfaces in scope

1. Organization access screens (`users`, `groups`, `roles`)
2. Workspace access screens (`principals/members`, `roles`, `invitations`)
3. Organization SSO/provisioning mode + SCIM token management
4. API clients and hooks for users/groups/invitations/roleAssignments/batch

## Test Architecture Plan

## Layer 1: Backend unit tests (fast, deterministic)

Focus:

1. RBAC evaluator union logic (direct + group grants)
2. scope/principal validation for assignments
3. provisioning mode decision logic (`disabled`, `jit`, `scim`)
4. group membership ownership guards (provider-managed read-only)
5. batch envelope validation:
   - allowlist
   - dependency graph
   - duplicate request ids
   - limit checks

Primary target folders:

1. `backend/tests/api/unit/features/rbac/`
2. `backend/tests/api/unit/features/admin_settings/`
3. `backend/tests/api/unit/features/batch/` (new)
4. `backend/tests/api/unit/features/scim/` (if needed for pure transform/validation helpers)

## Layer 2: Backend integration tests (API + DB + authz)

Focus:

1. Actor permission matrix across access routes
2. invitations and workspace-owner delegation behavior
3. role assignment lifecycle and boundary checks
4. JIT sign-in membership hydration behavior and failure tolerance
5. SCIM mode gating and SCIM user/group mutation flows
6. batch mixed-outcome semantics and dependency behavior

Primary target folders:

1. `backend/tests/api/integration/users/`
2. `backend/tests/api/integration/roles/`
3. `backend/tests/api/integration/features/sso/`
4. `backend/tests/api/integration/features/scim/`
5. `backend/tests/api/integration/features/admin_settings/`

## Layer 3: Frontend unit/component tests

Focus:

1. navigation/route resolution for org/workspace access IA
2. permission-gated rendering and action availability
3. form payload correctness for add/invite/assign flows
4. error and partial-success UX states (including batch)
5. SSO settings provisioning mode and SCIM token actions

Primary target folders:

1. `frontend/src/pages/OrganizationSettings/__tests__/`
2. `frontend/src/pages/Workspace/sections/Settings/__tests__/`
3. `frontend/src/api/admin/__tests__/`
4. `frontend/src/api/users/__tests__/`
5. `frontend/src/api/workspaces/__tests__/`

## Layer 4: E2E acceptance tests (critical path only)

Focus:

1. workspace owner invite flow with scoped assignment
2. org admin user/group/role management happy paths
3. mobile parity for critical access actions
4. provisioning mode switch + SCIM token UX smoke
5. bulk user operation UX with partial success handling

Tooling:

1. Playwright-based specs for end-to-end interaction and cross-breakpoint verification.

## Coverage Matrix and Ownership

Authoritative scenario matrix:

1. `docs/access-management-redesign/reference/access-test-matrix.md`

Each scenario in that matrix should map to:

1. one primary test file
2. one owner area (`users`, `roles`, `sso`, `scim`, `frontend settings`, `batch`)
3. one CI gate (unit, integration, frontend test, e2e)

## CI and Quality Gates

## Required CI stages for access-management changes

1. Backend unit + integration:
   - `cd backend && uv run ade api test`
2. Frontend unit/component:
   - `cd backend && uv run ade web test`
3. API schema/type integrity:
   - `cd backend && uv run ade api types`
   - frontend typecheck against regenerated types

## Risk-based gating rule

For changes touching access-critical paths (`features/users`, `features/groups`, `features/rbac`, `features/invitations`, `features/scim`, `features/sso`, `features/batch`, access settings pages), require:

1. all corresponding integration tests green
2. no skipped scenarios in `reference/access-test-matrix.md`

## Coverage target policy (scoped)

Enforce scoped coverage thresholds for access-management modules:

1. Backend access modules: line >= 90%, branch >= 80%
2. Frontend access modules: line >= 85%, branch >= 75%

Note:

1. Keep thresholds scoped to access paths to avoid unrelated historical coverage debt blocking progress.

## Implementation Phases

### Phase 1: Baseline and gap report

1. Inventory current tests by scenario using `reference/access-test-matrix.md`.
2. Mark each scenario as `covered`, `partial`, or `missing`.
3. Publish short gap report in PR description template for access changes.

### Phase 2: Backend core hardening

1. Add missing RBAC/provisioning/batch unit tests.
2. Add missing integration tests for permission boundaries and failure semantics.
3. Add regression tests for previously found authz/provisioning defects.

### Phase 3: Frontend reliability

1. Add component tests for access settings pages and drawers.
2. Add API client tests for new/changed endpoints and payload mappings.
3. Add partial-failure UI tests for batch operations.

### Phase 4: E2E and mobile parity

1. Add targeted e2e flows for org/workspace access.
2. Add mobile viewport assertions for primary and destructive actions.

### Phase 5: CI enforcement

1. Add scoped coverage gates and fail-on-threshold-breach.
2. Add risk-based required-check mapping for access-critical file paths.

## File-Level Work Plan

## Backend tests

1. `backend/tests/api/integration/users/test_users_router.py`
2. `backend/tests/api/integration/users/test_invitations_router.py`
3. `backend/tests/api/integration/roles/test_roles_router.py`
4. `backend/tests/api/integration/features/sso/test_auth_sso_callback.py`
5. `backend/tests/api/integration/features/sso/test_group_sync.py`
6. `backend/tests/api/integration/features/scim/test_scim_router.py`
7. `backend/tests/api/integration/features/admin_settings/test_admin_settings_router.py`
8. `backend/tests/api/integration/users/test_users_batch_router.py` (new)
9. `backend/tests/api/unit/features/batch/test_batch_service.py` (new)

## Frontend tests

1. `frontend/src/pages/OrganizationSettings/__tests__/systemSsoSettingsPage.test.tsx`
2. `frontend/src/pages/OrganizationSettings/__tests__/settingsNav.test.tsx`
3. `frontend/src/pages/Workspace/sections/Settings/__tests__/settingsNav.test.ts`
4. `frontend/src/api/admin/__tests__/roles.test.ts`
5. `frontend/src/api/admin/__tests__/scim.test.ts`
6. `frontend/src/api/admin/__tests__/settings.test.ts`
7. `frontend/src/api/workspaces/__tests__/api.test.ts`
8. `frontend/src/api/users/__tests__/api.test.ts` (expand/create for batch + access payloads)

## Definition of Done

1. All scenarios in `reference/access-test-matrix.md` are `covered` with owned test files.
2. Permission matrix behavior is verified for global admin, global user, workspace owner, workspace member.
3. Provisioning modes (`disabled|jit|scim`) are validated end to end.
4. SCIM and batch contracts have deterministic success/failure coverage.
5. Frontend access screens have route, permission, and core-action tests for desktop and mobile.
6. CI gates enforce scoped coverage and required suites for access-critical changes.

## Execution Status (Current)

1. Batch endpoint coverage plan execution: in progress with new backend unit/integration and frontend API tests.
2. Invitation scope boundary and workspace invitation UI coverage: implemented.
3. Remaining high-priority gaps: group-management UI component tests, principals screen component tests, and mobile e2e parity suite.
