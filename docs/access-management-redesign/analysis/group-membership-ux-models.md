# Group Membership UX Models (Decision Analysis)

Date: February 12, 2026

## Problem

ADE currently allows group membership API operations, but the UI is not first-class:

1. Group detail does not provide full member management ergonomics.
2. User detail does not provide direct group membership editing.
3. Provider-managed group read-only constraints are not consistently surfaced as
   explanatory UX states.

## Models Considered

## Model A: Group-centric only

Description:

1. Membership editing is only available in group detail.
2. User detail shows memberships read-only.

Pros:

1. Fewer screens with edit controls.
2. Minimal UI complexity.

Cons:

1. High context switching from user troubleshooting tasks.
2. Slower operator workflows when starting from a user incident.

Decision: rejected.

## Model B: User-centric only

Description:

1. Membership editing only available in user detail.
2. Group detail becomes a passive list.

Pros:

1. Works for user-level troubleshooting.

Cons:

1. Weak for group administration at scale.
2. Group owners/admins lose natural group control center.

Decision: rejected.

## Model C: Dual-surface editing (recommended)

Description:

1. Group detail: add/remove members and owners (if internally managed).
2. User detail: add/remove group memberships.
3. Shared mutation semantics and permission/readonly rules.

Pros:

1. Matches first-class admin products.
2. Reduces task switching for both user-centric and group-centric workflows.
3. Aligns with Entra/Google/Okta/GitHub/Atlassian mixed patterns.

Cons:

1. Requires stronger consistency controls to avoid duplicate logic.

Decision: selected.

## Model D: Conditional dual-surface by role

Description:

1. One surface for some admins, dual-surface for others.

Pros:

1. Could simplify novice UI.

Cons:

1. Increases confusion and test complexity.
2. Creates inconsistent support and documentation burden.

Decision: rejected.

## Candidate Interface Delta

Current ADE API capability:

1. Group-centric membership endpoints already exist:
   - `GET /api/v1/groups/{groupId}/members`
   - `POST /api/v1/groups/{groupId}/members/$ref`
   - `DELETE /api/v1/groups/{groupId}/members/{memberId}/$ref`

Gap for first-class user-detail membership UX:

1. No user-centric membership endpoint currently exists.

Recommendation:

1. Add Graph-aligned user membership interfaces for efficiency and clarity:
   - `GET /api/v1/users/{userId}/memberOf`
   - `POST /api/v1/users/{userId}/memberOf/$ref`
   - `DELETE /api/v1/users/{userId}/memberOf/{groupId}/$ref`

Fallback if deferred:

1. UI can still mutate via group-centric endpoints, but user-detail membership UX will
   require additional client-side joins and higher API round-trips.

## Permission and Read-Only Rules

1. `groups.members.manage_all` allows membership add/remove on internal assigned groups.
2. `groups.members.read_all` allows read-only visibility.
3. If `group.source == idp` or `group.membership_mode == dynamic`, member mutations are
   read-only and must show reason + next action (manage in IdP/rule definition).

## Selected Target Behavior

1. From group detail:
   - Members tab supports search, add, remove.
   - Owners tab supports add, remove (new concept in UI spec, owner backing model may
     be staged if backend does not yet expose owners).
2. From user detail:
   - Groups tab supports add/remove memberships and displays membership source.
3. Both surfaces:
   - Use same error texts and read-only rationale.
   - Use same confirmation model for destructive actions.

## Sources

1. [How to manage groups (Entra)](https://learn.microsoft.com/en-gb/azure/active-directory/fundamentals/how-to-manage-groups)
2. [Group administrators (Okta)](https://help.okta.com/oie/en-us/content/topics/security/administrators-group-admin.htm)
3. [Manually assign people to a group (Okta)](https://help.okta.com/en-us/Content/Topics/users-groups-profiles/usgp-assign-group-people.htm)
4. [Add or invite users to a group (Google Workspace)](https://support.google.com/cloudidentity/answer/9400087?hl=en)
5. [Can't add a user to a group (Google Workspace)](https://support.google.com/a/answer/9242708?hl=en)
6. [Synchronizing a team with an IdP group (GitHub)](https://docs.github.com/enterprise-cloud%40latest/organizations/organizing-members-into-teams/synchronizing-a-team-with-an-identity-provider-group)
7. [Edit a group (Atlassian)](https://support.atlassian.com/user-management/docs/edit-a-group/)
8. [List user memberOf (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/api/user-list-memberof?view=graph-rest-1.0)
