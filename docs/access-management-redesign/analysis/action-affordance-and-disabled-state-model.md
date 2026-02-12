# Action Affordance and Disabled-State Model

Date: February 12, 2026

## Purpose

Define a deterministic model for clickable/disabled/hidden controls so ADE access UI
is intuitive and admins always understand why actions are unavailable.

## Problem Statement

"Buttons that are not clickable" without explanation creates operator confusion and
support burden. Access-management UI must expose intent and boundaries explicitly.

## Affordance Decision Model

For each action, choose one state:

1. `Enabled`: user can execute now.
2. `Disabled-with-reason`: user has context to see action but currently cannot execute.
3. `Hidden`: action is irrelevant to role/context and would add noise.

## Rules

1. Use `disabled-with-reason` when action is core to the screen's mental model.
2. Use `hidden` only when showing the action would be misleading or cluttered.
3. Every disabled action must have deterministic reason text, not generic "forbidden".
4. Reasons must distinguish:
   - missing permission
   - provider-managed read-only state
   - inactive/immutable object state
   - missing required input selection

## Canonical Reason Text

1. Missing permission:
   - "You need `groups.members.manage_all` to manage group members."
2. Provider-managed group:
   - "Membership is managed by your identity provider for this group."
3. Dynamic membership group:
   - "Membership is dynamic. Update the membership rule instead."
4. Missing form selection:
   - "Select at least one role to continue."
5. Self-protection constraints:
   - "You cannot remove your own last administrative assignment from this screen."

## UI Treatment Standards

1. Buttons:
   - Disabled buttons keep visible text and include tooltip/help text.
2. Row actions:
   - If an action menu item is disabled, include inline explanatory helper text in detail
     pane or status banner.
3. Drawer footers:
   - Primary action right-aligned.
   - Destructive action separated from primary cluster.
4. Badges:
   - Show object state chips (`Provider-managed`, `Dynamic`, `Inactive`) next to title.

## Permission Boundary Display Contract

1. At screen level:
   - If no read permission: show full-page blocked state.
2. At action level:
   - If read allowed but manage denied: keep read-only content and disabled actions with reasons.
3. At mutation failure:
   - Preserve optimistic affordance model and show API reason details in alert/toast.

## Telemetry Contract

Track:

1. Disabled action impressions by reason code.
2. Attempted clicks on disabled actions.
3. Permission-denied API responses by route.
4. Provider-managed mutation conflicts (`409`) by surface.

Use telemetry to identify unclear affordances and copy gaps.

## Acceptance Criteria

1. No disabled action appears without explicit reason text nearby.
2. Non-clickable controls are explainable by reading the screen only.
3. Permission boundaries are consistent between org and workspace surfaces.
4. Provider-managed read-only behavior is visually obvious before click.

## Sources

1. [How to manage groups (Entra)](https://learn.microsoft.com/en-gb/azure/active-directory/fundamentals/how-to-manage-groups)
2. [What are the different types of admin roles? (Atlassian)](https://support.atlassian.com/user-management/docs/what-are-the-different-types-of-admin-roles/)
3. [Group membership administrators (Okta)](https://help.okta.com/en-us/content/topics/security/administrators-group-membership-admin.htm)
4. [Groups administrator FAQ (Google Workspace)](https://support.google.com/a/answer/167085?hl=en)
5. [Synchronizing a team with an IdP group (GitHub)](https://docs.github.com/enterprise-cloud%40latest/organizations/organizing-members-into-teams/synchronizing-a-team-with-an-identity-provider-group)
