# Workspace Owner User-Creation Options

Question: Workspace owners do not have organization-level user-management permissions, but they need to add people to their workspace. How should this work?

## Requirements

1. Workspace owners can add people to their workspace.
2. Workspace owners cannot globally edit all users or global roles.
3. Unknown email addresses should be supported (invite/provision path).
4. No duplicate user identities should be created.
5. Action must be auditable and policy-safe.

## Options

### Option 1: Workspace owners can only add existing users

- Mechanism: keep current `POST /workspaces/{workspaceId}/members` with `user_id`.
- Pros: minimal changes.
- Cons: blocks first-contact onboarding; requires org admin bottleneck.

### Option 2: Grant workspace owners global `users.manage_all`

- Mechanism: broaden permission scope.
- Pros: easy implementation.
- Cons: unacceptable policy expansion; violates least privilege.

### Option 3: Introduce invitation-first workflow with workspace context (recommended)

- Mechanism:
  - `POST /api/v1/invitations`
  - payload includes `invited_user_email`, optional profile seed, `workspace_id`, and initial workspace role assignment.
- Permission gate:
  - allowed if actor has `workspace.members.manage` on the target workspace.
  - no requirement for global `users.manage_all`.
- Transaction behavior:
  1. Normalize email.
  2. If user exists: create invitation (optional) and workspace assignment only.
  3. If user does not exist: create invited user stub + invitation + assignment in one transaction.

## Recommended Policy Model

### Permission boundaries

- Workspace owner may:
  - invite users into owned workspace(s)
  - assign workspace roles they are allowed to grant
- Workspace owner may not:
  - edit global user profile fields unrelated to workspace onboarding
  - assign/remove global roles
  - manage users outside authorized workspace scope

### Guardrails

1. Role grant restrictions for high-risk roles (for example, workspace-owner assignment may require additional permission/policy).
2. Invitation TTL and revoke support.
3. Duplicate prevention by canonical email + unique identity key.
4. Full audit log with actor, workspace scope, target email/user, and resulting assignments.

## Recommendation

Adopt Option 3 as the default and primary path. It satisfies delegated administration requirements without breaking org-level boundaries and aligns with Graph invitation patterns.

