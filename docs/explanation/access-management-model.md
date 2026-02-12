# Access Management Model

## Purpose

Explain ADE's access model across organization and workspace scopes, including
principals, role assignments, invitations, provisioning modes, and SCIM.

## Core Concepts

- **Principal**: entity that can receive role assignments (`user` or `group`)
- **Role**: permission bundle scoped to organization or workspace
- **Role assignment**: binding of `principal + role + scope`
- **Invitation**: explicit provisioning workflow to create or onboard users
- **Provisioning mode**: policy controlling automatic identity provisioning behavior

## Scope Model

### Organization scope

Used for tenant-wide administration:

1. organization roles
2. user and group lifecycle
3. provisioning mode and SCIM controls

### Workspace scope

Used for delegated access administration:

1. principal assignment in one workspace
2. workspace role definitions and grants
3. workspace invitation lifecycle

## Access Resolution

Effective permissions are computed as:

1. direct user assignments in scope
2. union with assignments granted through group membership
3. user status guardrail (`inactive` users always denied)

## Provisioning Modes

`auth.identityProvider.provisioningMode`:

1. `disabled`: no automatic unknown-user provisioning; invite/admin create only
2. `jit`: unknown user can be created at sign-in based on policy; memberships hydrated for signed-in user
3. `scim`: SCIM is authoritative provisioning path; unknown-user JIT create is blocked

## Group Model

- `source=internal`: ADE-managed groups
- `source=idp`: provider-managed groups
- provider-managed memberships are read-only in ADE manual membership APIs

## Why This Model

1. clear org/workspace permission boundaries
2. standard enterprise alignment (Graph-style resources, SCIM provisioning)
3. scalable grants through group principals
4. explicit provisioning controls for security and operations

## Related

- [Access Reference](../reference/access/README.md)
- [Access Management API Reference](../reference/api/access-management.md)
- [Manage Users and Access](../how-to/manage-users-and-access.md)
- [Auth Operations](../how-to/auth-operations.md)
