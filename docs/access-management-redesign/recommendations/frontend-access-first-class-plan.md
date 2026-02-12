# Frontend Access Management First-Class Plan (Research-Backed Refresh)

Date: February 12, 2026

## Goal

Define a first-class, intuitive access-management UI model aligned to Entra task
patterns and validated against Okta, Google Workspace Admin, GitHub Enterprise,
and Atlassian Admin.

## Decision Locks

1. Benchmark baseline: Entra primary, peers for pressure-testing.
2. Membership editing must exist in both contexts:
   - group-centric (group detail)
   - user-centric (user detail)
3. One command grammar across org/workspace list surfaces.
4. Disabled states are allowed only with explicit reason text.
5. Provider-managed/dynamic memberships are visibly read-only.

## Selected Target UX Model

## Surface model

1. Organization
   - `/organization/access/users`
   - `/organization/access/groups`
   - `/organization/access/roles`
2. Workspace
   - `/workspaces/:workspaceId/settings/access/principals`
   - `/workspaces/:workspaceId/settings/access/roles`
   - `/workspaces/:workspaceId/settings/access/invitations`

## Shared grammar

1. List command bar: search, filters, bulk entry, primary action.
2. Primary table/card: stable columns, source/status chips, deterministic action column.
3. Detail drawer (or tabbed pane inside drawer):
   - entity profile/properties
   - assignments
   - memberships
   - audit-relevant metadata
4. Footer action hierarchy:
   - primary action isolated
   - destructive actions separated + confirmed

## Membership management requirements

1. Group detail must support add/remove members for mutable groups.
2. Group detail should include owner management surface in the same context.
3. User detail must support add/remove group memberships.
4. Both surfaces must show membership source and read-only rationale.

## Affordance contract

1. Screen denied: full-page blocked state.
2. Read-only screen: actions visible but disabled with explicit reason.
3. Provider-managed object: mutation controls disabled with provider guidance.

## Candidate Interface Delta

Immediate phase:

1. No mandatory API changes for group-detail membership editing.

Recommended small extension:

1. Add user-centric membership endpoints for efficient user-detail management:
   - `GET /api/v1/users/{userId}/memberOf`
   - `POST /api/v1/users/{userId}/memberOf/$ref`
   - `DELETE /api/v1/users/{userId}/memberOf/{groupId}/$ref`

Rationale:

1. Reduces client-side joins and improves user-detail performance and simplicity.
2. Aligns with Graph-style membership surface.

## Rejected Alternatives

1. Group-only membership editing:
   - rejected due high context switching from user-centric tasks.
2. User-only membership editing:
   - rejected due weak group administration ergonomics.
3. Hidden-only unauthorized actions:
   - rejected because it obscures capability boundaries and feels inconsistent.

## Definition of Done

1. Group and user membership management are both first-class.
2. No "mystery disabled" controls remain.
3. Org/workspace access surfaces feel structurally symmetric.
4. Provider-managed read-only behavior is clear before mutation attempts.

## Research Anchors

1. `docs/access-management-redesign/research/access-ui-task-flows-entra-plus-peers.md`
2. `docs/access-management-redesign/research/access-ui-competitive-patterns-matrix.md`
3. `docs/access-management-redesign/research/entra-admin-ui-patterns.md`
4. `docs/access-management-redesign/analysis/group-membership-ux-models.md`
5. `docs/access-management-redesign/analysis/action-affordance-and-disabled-state-model.md`

## External Source Highlights

1. [How to manage groups (Entra)](https://learn.microsoft.com/en-gb/azure/active-directory/fundamentals/how-to-manage-groups)
2. [Manage users and groups assignment to an application (Entra)](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/assign-user-or-group-access-portal)
3. [Group administrators (Okta)](https://help.okta.com/oie/en-us/content/topics/security/administrators-group-admin.htm)
4. [Add or invite users to a group (Google Workspace)](https://support.google.com/cloudidentity/answer/9400087?hl=en)
5. [Synchronizing a team with an IdP group (GitHub)](https://docs.github.com/enterprise-cloud%40latest/organizations/organizing-members-into-teams/synchronizing-a-team-with-an-identity-provider-group)
6. [Edit a group (Atlassian)](https://support.atlassian.com/user-management/docs/edit-a-group/)
