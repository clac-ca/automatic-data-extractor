# Frontend Access First-Class Execution Plan (Post-Research)

Date: February 12, 2026

## Summary

This execution plan translates the refreshed research into implementation phases that
close the remaining first-class UX gaps, with priority on group/user membership
management and action affordance clarity.

## Scope

In scope:

1. Group detail member/owner management UX.
2. User detail group-membership management UX.
3. Org/workspace command-surface consistency.
4. Disabled-state and permission-boundary clarity.
5. Mobile parity for critical access actions.

Out of scope:

1. Visual theme redesign.
2. Non-access settings pages.
3. New provisioning protocol behavior.

## Candidate Interface Delta (Execution Input)

1. Phase 1 can ship with current APIs for group-centric membership operations.
2. Phase 2 should evaluate adding user-centric `memberOf` endpoints to reduce client
   joins and improve user-detail UX performance.

Proposed endpoints (if approved):

1. `GET /api/v1/users/{userId}/memberOf`
2. `POST /api/v1/users/{userId}/memberOf/$ref`
3. `DELETE /api/v1/users/{userId}/memberOf/{groupId}/$ref`

## Milestones

## M1: Group detail first-class membership management

Objective:

1. Make groups page operationally complete.

Tasks:

1. Add `Members` section in group detail with add/remove controls.
2. Add `Owners` section in group detail (UI surface and staged backend integration).
3. Add provider-managed/dynamic read-only lock state with deterministic reason text.
4. Add member search and safe remove confirmation.

Acceptance:

1. Admin can complete member lifecycle from group detail alone.
2. Read-only groups show clear reason and next action guidance.

## M2: User detail group-membership management

Objective:

1. Let admins manage a user's group memberships from user detail.

Tasks:

1. Add `Groups` tab/section to org user detail.
2. Add add/remove membership actions.
3. Show membership source and inherited/direct markers.
4. If user-centric endpoints are not yet available, implement via group-centric API
   adapter with clear performance limits.

Acceptance:

1. Admin can add/remove user memberships without leaving user detail.

## M3: Affordance and boundary standardization

Objective:

1. Remove non-intuitive button behavior across access surfaces.

Tasks:

1. Apply shared disabled-state reason codes and copy.
2. Standardize hidden-vs-disabled decision logic.
3. Add local UI instrumentation for disabled-action impressions and denied attempts.

Acceptance:

1. No disabled action remains unexplained.

## M4: Command-surface consistency and cross-linking

Objective:

1. Align list and detail navigation patterns across org/workspace.

Tasks:

1. Ensure all access pages use shared command bar pattern.
2. Add deep links between user detail and relevant groups; group detail and member
   profiles where permissions allow.
3. Align action menu patterns and confirmation dialogs.

Acceptance:

1. Common actions are discoverable in predictable locations.

## M5: Mobile parity and accessibility hardening

Objective:

1. Ensure first-class behavior on mobile and assistive workflows.

Tasks:

1. Validate action hierarchy in narrow drawer layouts.
2. Verify keyboard and focus behavior for add/remove member flows.
3. Ensure status/source/reason labels are screen-reader discoverable.

Acceptance:

1. Critical actions are equivalent across desktop and mobile.

## Verification Matrix

Use and maintain:

1. `docs/access-management-redesign/reference/access-ui-state-matrix.md`
2. `docs/access-management-redesign/reference/access-ui-flow-maps.mmd`
3. `docs/access-management-redesign/reference/access-test-matrix.md`

## Test Additions

1. Org groups page tests: member add/remove, read-only lock state.
2. Org users page tests: membership add/remove flows.
3. Cross-link tests between users/groups screens.
4. Mobile action hierarchy tests for drawers.
5. Playwright acceptance for the seven research validation scenarios.

## Research Anchors

1. `docs/access-management-redesign/research/access-ui-task-flows-entra-plus-peers.md`
2. `docs/access-management-redesign/research/access-ui-competitive-patterns-matrix.md`
3. `docs/access-management-redesign/analysis/group-membership-ux-models.md`
4. `docs/access-management-redesign/analysis/action-affordance-and-disabled-state-model.md`

## External Source Highlights

1. [How to manage groups (Entra)](https://learn.microsoft.com/en-gb/azure/active-directory/fundamentals/how-to-manage-groups)
2. [Bulk import group members (Entra)](https://learn.microsoft.com/en-us/azure/active-directory/enterprise-users/groups-bulk-import-members)
3. [Manually assign people to a group (Okta)](https://help.okta.com/en-us/Content/Topics/users-groups-profiles/usgp-assign-group-people.htm)
4. [Directory API group members (Google)](https://developers.google.com/workspace/admin/directory/v1/guides/manage-group-members)
5. [Adding people to your organization (GitHub)](https://docs.github.com/en/organizations/managing-membership-in-your-organization/adding-people-to-your-organization)
6. [What are the different types of admin roles? (Atlassian)](https://support.atlassian.com/user-management/docs/what-are-the-different-types-of-admin-roles/)
