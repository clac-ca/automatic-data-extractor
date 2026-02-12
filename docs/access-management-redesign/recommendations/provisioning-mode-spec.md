# Provisioning Mode Spec (Recommended)

## Goal

Provide one explicit admin-selected provisioning mode per organization to keep identity lifecycle behavior predictable.

## Mode Enum

`auth.identityProvider.provisioningMode`:

1. `disabled`
2. `jit`
3. `scim`

## Normative Behavior by Mode

### 1. `disabled`

- No automatic user creation at SSO login.
- No SCIM processing.
- Users must be created via invitation/admin APIs.
- Sign-in allowed only for already-linked active users.

### 2. `jit`

- SSO callback may create user when domain/policy checks pass.
- Group membership reconciliation occurs on sign-in for that user only.
- Unknown users from background directory/group data are never created.
- Group records observed during hydration can be upserted as `source=idp`.

### 3. `scim`

- SCIM endpoints are enabled and authoritative for automated user/group lifecycle.
- SSO callback does not auto-create unknown users.
- Group membership is updated by SCIM group operations.
- Invitations remain available for explicit exceptions (if org policy allows).

## Shared Rules

1. User `is_active=false` always suppresses effective access.
2. Provider-managed groups are read-only from ADE manual membership endpoints.
3. Audit events must include provisioning channel: `invite`, `jit`, or `scim`.

## Settings and Admin UX

Expose provisioning mode in Organization Settings > Authentication/SSO policy.

Required helper text:

- `disabled`: "Only invited/admin-created users can access this organization."
- `jit`: "Users can be created at first sign-in; memberships update when they sign in."
- `scim`: "Users/groups are provisioned by your identity provider via SCIM."

## Mode Transition Rules

1. `disabled -> jit`: allow immediately.
2. `jit -> disabled`: stop auto-create at login immediately.
3. `jit -> scim`: enable SCIM credentials first, then switch mode.
4. `scim -> jit`: keep existing provisioned users; stop accepting SCIM mutations after switch.

## Failure Semantics

1. JIT membership hydration failure must not block successful login.
2. SCIM authentication/validation failures must return SCIM-compliant errors and not mutate data.
3. Mode mismatch calls (for disabled paths) return explicit policy error responses.

## Observability Requirements

1. `auth.provisioning.mode.current` gauge.
2. `auth.jit.hydration.success|failure|latency` metrics.
3. `auth.scim.request.count|error.count|latency` metrics.
4. Audit trail for mode changes including actor and timestamp.
