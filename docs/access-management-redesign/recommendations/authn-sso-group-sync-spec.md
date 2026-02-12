# AuthN, SSO, Provisioning, and Membership Hydration Spec

## Current Baseline

- ADE supports OIDC SSO provider config and JIT provisioning toggle.
- Entra subject normalization (`tid:oid`) and identity linking already exist.
- Login-time per-user membership hydration is already available.
- Scheduled full group sync path also exists today.

Code references:

- `backend/src/ade_api/features/auth/sso_router.py:170`
- `backend/src/ade_api/features/sso/group_sync.py:251`
- `backend/src/ade_api/features/sso/group_sync.py:292`
- `backend/src/ade_db/models/sso.py:144`

## Target Objectives

1. Make provisioning behavior explicit by mode: `disabled | jit | scim`.
2. Keep invitations as explicit provisioning path.
3. In JIT mode, update group membership on sign-in for that user only.
4. Add SCIM as standards-based provisioning channel for enterprise orgs.
5. Keep provider-managed groups read-only in ADE manual membership APIs.

## Provisioning-Mode Contract

## Mode: `disabled`

- No auto-provision on SSO callback.
- Login requires pre-existing linked user.
- Invitations/admin create remain valid onboarding paths.

## Mode: `jit`

- SSO callback can create user (subject to domain/policy checks).
- Resolve/persist identity link (`sso_identities` + user external metadata).
- Run best-effort membership hydration for that user:
  - fetch groups from provider (`memberOf` for user)
  - upsert provider groups if missing
  - reconcile this user’s provider-sourced memberships
- On hydration failure, login still succeeds and an async retry is queued.

## Mode: `scim`

- SCIM endpoints are enabled and authoritative for automated user/group lifecycle.
- SSO callback does not JIT-create unknown users.
- Login primarily links/authenticates existing users provisioned via SCIM/invite.
- Group membership mutations come from SCIM group operations.

## Identity Source Strategy

### Users

- `source=internal` for ADE-created/invite-created users.
- `source=idp` for JIT-linked users.
- `source=scim` for SCIM-provisioned users.
- `external_id` stores provider/SCIM stable correlation ID.

### Groups

- `source=internal` for ADE-managed groups.
- `source=idp` for provider-managed groups (JIT-hydrated or SCIM-managed).
- Provider-managed groups are read-only for manual membership edits.

## Group Membership Ownership Rules

1. `membership_source=internal` rows are app-managed.
2. `membership_source=idp` rows are provider-managed.
3. Manual membership write endpoints reject provider-managed group mutations with `409`.
4. Effective access always uses union of direct assignments and group-derived assignments.

## Standards Alignment Rationale

1. Group claims in tokens can be incomplete at scale; user-specific Graph lookup is standard fallback.
2. SCIM is the interoperable provisioning channel for enterprise IdPs.
3. Provisioning and authorization reconciliation must remain distinct concerns.

References:

- [Microsoft group claims overage guidance](https://learn.microsoft.com/en-us/security/zero-trust/develop/configure-tokens-group-claims-app-roles)
- [Microsoft Graph user memberOf](https://learn.microsoft.com/en-us/graph/api/user-list-memberof?view=graph-rest-1.0)
- [RFC 7644](https://datatracker.ietf.org/doc/html/rfc7644)
- [Entra SCIM guidance](https://learn.microsoft.com/en-us/entra/identity/app-provisioning/use-scim-to-provision-users-and-groups)

## Failure Handling

1. SSO authn failure blocks login.
2. JIT membership hydration failure does not block login; emit error telemetry + schedule retry.
3. SCIM write validation/auth failures return SCIM-compliant errors and do not partially mutate state.
4. Inactive users remain denied regardless of direct/group grants.

## Observability Requirements

1. `sso.callback.success|failure`
2. `sso.jit.provision.success|failure`
3. `sso.group_hydration.success|failure|latency`
4. `scim.request.success|failure|latency`
5. audit events include channel (`invite|jit|scim`) and correlation identifiers.
