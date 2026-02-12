# Industry Patterns (GitHub, Atlassian, Slack)

This research captures practical admin-model conventions for user/group access management and invitation control.

## Pattern Snapshot

| Product | Pattern | What is transferable to ADE |
|---|---|---|
| GitHub Organizations | Invitation-first org membership model (invite by username/email, time-limited, policy checks) | Workspace-owner invite flow should be first-class, policy-aware, and auditable |
| Atlassian Cloud | Delegated admin role taxonomy (organization admin, site admin, user access admin, etc.) | Separate “identity lifecycle” authority from “resource access” authority |
| Slack | Optional invite approval controls and role-based invite permissions | Add policy gate for workspace-owner invitations if needed (approval mode)

## Findings

### 1. GitHub: invite-based onboarding is the default for organization membership

- GitHub org owners/admins can invite by username or email.
- Invitations expire after a fixed window (7 days).
- GitHub documents anti-abuse invitation limits (50/day for new/free orgs, 500/day for paid/older orgs).

Source: [GitHub org invitation model](https://docs.github.com/en/organizations/managing-membership-in-your-organization/inviting-users-to-join-your-organization)

Implication for ADE:

- Make invitation records first-class resources with status, expiry, inviter, and scope context.
- Keep “existing user vs new email” in one flow, not two unrelated screens.

### 2. Atlassian: distinct admin roles reduce over-privileging

- Atlassian distinguishes org-wide and scoped admin capabilities (for example, organization admin vs user access admin).

Source: [Atlassian admin role model](https://support.atlassian.com/user-management/docs/what-are-the-different-types-of-admin-roles/)

Implication for ADE:

- Treat workspace membership administration as a delegated permission (`workspace.members.manage`) that does not require global user-admin rights.
- Preserve strict boundaries for global user edits/role governance.

### 3. Slack: invite governance can require approval

- Slack supports controls where invitations can require owner/admin approval.

Source: [Slack invitation controls](https://slack.com/help/articles/115004854783-Require-admin-approval-for-workspace-invitations)

Implication for ADE:

- Add optional org policy for workspace-owner invites:
  - `auto-approve` (default)
  - `owner-approval-required` (future toggle)

## Common Cross-Product Conventions

1. Invitations are explicit resources, not side effects.
2. Membership assignment is separate from user profile authority.
3. Admin controls are delegated by scope (org vs workspace/site/project).
4. “Who can invite” and “who can assign high-privilege roles” are often distinct policy controls.
5. Auditability (who granted what, where, and when) is non-negotiable.

## ADE-Specific Design Takeaways

- Use invitation-driven provisioning for workspace owners.
- Keep organization-level user profile and global role administration separate.
- Support clean escalation policies for high-risk role grants (for example, workspace owner role).
- Preserve a single mental model for users/admins: principals + assignments + effective access.

