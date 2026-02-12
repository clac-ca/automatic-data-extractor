# JIT Sign-In Membership-Only Impact Analysis

## Decision Under Analysis

In `jit` provisioning mode:

1. Do not run background tenant-wide membership sync that creates users.
2. Reconcile IdP group membership only for the user who successfully signs in.
3. Auto-create missing provider groups as metadata containers when first observed.

## Problem Solved

Scenario:

- IdP Group A = `User_A`, `User_B`, `User_C`
- ADE has only `User_A`, `User_B`

With this model:

1. Background processing does not create `User_C`.
2. If `User_C` later signs in (and JIT policy allows), ADE creates/links `User_C` and hydrates Group A membership immediately.

This directly removes implicit provisioning from directory group data.

## Security and Governance Effects

### Positive

1. Clear separation of provisioning authority (invite/JIT/SCIM) from group reconciliation.
2. Reduced risk of accidental account creation due to stale or broad IdP directory scope.
3. Better audit interpretation: user creation events are tied to invitation, JIT login, or SCIM events.

### Watchouts

1. Membership removals for users who do not sign in will not reconcile in JIT mode until next login.
2. Existing sessions may retain effective access until normal session expiration unless explicit revocation is added.

## Performance and Reliability Effects

### Positive

1. Eliminates large periodic tenant crawls in JIT mode.
2. Makes sign-in update scope bounded to one user.

### Risks

1. Sign-in path can be slower when membership fetch is required.
2. Directory API transient failures can delay membership freshness.

### Required mitigations

1. Best-effort hydration inline; do not block login on transient failures.
2. Queue one async retry after login failure path.
3. Emit latency/failure metrics for hydration.

## Standards Alignment

1. OIDC tokens may not reliably carry full group sets in large tenants.
2. Microsoft guidance indicates fallback to Graph calls for group membership when token overage occurs.

References:

- [Group claims and app roles in Microsoft Entra](https://learn.microsoft.com/en-us/security/zero-trust/develop/configure-tokens-group-claims-app-roles)
- [Microsoft Graph user memberOf](https://learn.microsoft.com/en-us/graph/api/user-list-memberof?view=graph-rest-1.0)

## Operational Fit by Provisioning Mode

1. `disabled`: no JIT creation; sign-in allowed only for existing linked users.
2. `jit`: JIT create/link + per-user membership hydration on sign-in.
3. `scim`: SCIM manages membership; sign-in-time hydration is optional and off by default.

## Conclusion

JIT sign-in hydration only is the simplest design that preserves immediate access correctness for the user who logs in while preventing unwanted background identity creation.
