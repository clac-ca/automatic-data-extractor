# Provisioning Mode Patterns

## Purpose

Document common identity provisioning operating modes and map them to ADE design choices.

## Mode Pattern 1: Provisioning Disabled (Manual/Invite-Only)

### Industry pattern

Organizations without enterprise IdP automation often rely on invites/manual account lifecycle.

Reference:

- [GitHub organization invitations](https://docs.github.com/en/organizations/managing-membership-in-your-organization/inviting-users-to-join-your-organization)

### ADE fit

- No automatic IdP user creation at login.
- No SCIM writes.
- Users enter ADE through invitation/admin create path only.

## Mode Pattern 2: JIT Provisioning (On Sign-In)

### Industry pattern

JIT creates or links user identity during successful SSO login.

Reference:

- [Atlassian JIT provisioning](https://support.atlassian.com/atlassian-cloud/kb/what-is-just-in-time-provisioning-and-how-to-set-it-up/)

### ADE fit

- Unknown users can be created at login when domain/policy checks pass.
- Group membership should be hydrated per-user on sign-in (not via full tenant polling).
- If token group claims are incomplete/overage, call directory API for that user’s memberships.

Reference:

- [Microsoft group claims and overage guidance](https://learn.microsoft.com/en-us/security/zero-trust/develop/configure-tokens-group-claims-app-roles)
- [Microsoft Graph: list user memberOf](https://learn.microsoft.com/en-us/graph/api/user-list-memberof?view=graph-rest-1.0)

## Mode Pattern 3: SCIM Provisioning (Directory Push)

### Industry pattern

SCIM provides standardized user/group lifecycle pushes from IdP to app.

References:

- [RFC 7644: SCIM protocol](https://datatracker.ietf.org/doc/html/rfc7644)
- [Microsoft Entra SCIM provisioning guidance](https://learn.microsoft.com/en-us/entra/identity/app-provisioning/use-scim-to-provision-users-and-groups)
- [Okta SCIM provisioning integration](https://developer.okta.com/docs/guides/scim-provisioning-integration-overview/main/)

### ADE fit

- IdP is source of truth for provisioned users/groups.
- Login should link identity and enforce access; it should not become fallback bulk-provision path.
- Group membership changes arrive through SCIM group operations.

## Common Industry Rule: Separate Provisioning from Authorization Reconciliation

Observed across vendors:

1. Provisioning channel controls who exists in app (`invite`, `jit`, `scim`).
2. Authorization channel controls what access they get (role assignments from user/group).
3. Group membership updates do not justify silent identity creation outside selected provisioning mode.

## ADE Design Consequences

1. Admins choose a single provisioning mode per organization: `disabled | jit | scim`.
2. Invitations remain available in every mode for explicit admin-driven onboarding.
3. Background group polling should not create users.
4. JIT mode should only hydrate memberships for the user signing in.
5. SCIM mode should use `/scim/v2` as the integration surface and become the primary automated provisioning path.
