# Access UI State Matrix

Date: February 12, 2026

## Purpose

Define expected screen/action behavior by permission, source-of-truth, and object state.

## Matrix

| Surface | Action | Preconditions | Enabled | Disabled-with-reason | Hidden |
| --- | --- | --- | --- | --- | --- |
| Org Users list | Create user | `users.manage_all` | Yes | If manage missing but read present: show disabled create with reason | If no read permissions for users |
| Org User detail | Save profile | `users.manage_all` | Yes | Missing manage permission | If user detail inaccessible |
| Org User detail | Add to group | `users.manage_all` + `groups.members.manage_all` and group mutable | Yes | Missing user/group-manage permission or target group is provider-managed/dynamic | If groups feature unavailable |
| Org User detail | Remove from group | `users.manage_all` + `groups.members.manage_all` and group mutable | Yes | Same as above | Same as above |
| Org Groups list | Create group | `groups.manage_all` | Yes | Missing manage permission | If no `groups.read_all`/`groups.manage_all` |
| Org Group detail | Add member | `groups.members.manage_all` and group source internal + assigned mode | Yes | Missing manage permission; or `source=idp`; or `membership_mode=dynamic` | Never hidden when group detail is visible |
| Org Group detail | Remove member | Same as add member | Yes | Same as add member | Never hidden when group detail is visible |
| Org Group detail | Add/remove owner | `groups.manage_all` and mutable group | Yes | Missing permission; or `source=idp`; or `membership_mode=dynamic` | Never hidden when group detail is visible |
| Workspace Principals | Add principal | `workspace.members.manage` | Yes | Missing manage permission | If no workspace access read route |
| Workspace Principals | Update principal roles | `workspace.members.manage` | Yes | Missing manage permission | Never hidden on manage-capable principal rows |
| Workspace Invitations | Resend/cancel invite | `workspace.invitations.manage` and invite pending | Yes | Missing manage permission or invite non-pending | Hidden only if invitations not readable |

## Disabled-State Reason Codes

| Code | Meaning | UI copy guideline |
| --- | --- | --- |
| `perm_missing` | Actor lacks required permission | Include explicit permission key in admin-facing copy |
| `provider_managed` | IdP-owned object disallows local mutation | Tell admin to change in identity provider |
| `dynamic_membership` | Dynamic membership groups are rule-managed | Tell admin to update membership rule |
| `invalid_selection` | Required form input missing | State exact missing field/selection |
| `conflict_state` | Object changed or invalid state transition | Provide refresh/retry guidance |

## Cross-Surface Consistency Rules

1. Same action name means same behavior and same reason code mapping across org/workspace.
2. IdP-managed groups must always show a visible "Provider-managed" badge before any action attempt.
3. Destructive actions must require confirmation in both desktop and mobile.

## Validation Checklist

1. Every disabled button has adjacent explanatory text or tooltip.
2. No menu item is disabled without a reason in the panel/drawer context.
3. No mutation-only affordance is shown on read-only screens without explanation.
