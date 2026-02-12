# Access Permission Matrix

## Purpose

Define canonical permissions and boundary behavior for access-management operations.

## Permission Catalog

### Organization scope

- `users.read_all`
- `users.manage_all`
- `groups.read_all`
- `groups.manage_all`
- `groups.members.read_all`
- `groups.members.manage_all`
- `roles.read_all`
- `roles.manage_all`
- `invitations.read_all`
- `invitations.manage_all`
- `identity.provisioning.read`
- `identity.provisioning.manage`

### Workspace scope

- `workspace.read`
- `workspace.members.read`
- `workspace.members.manage`
- `workspace.roles.read`
- `workspace.roles.manage`
- `workspace.invitations.read`
- `workspace.invitations.manage`

## Capability Matrix

| Capability | Global Admin | Global User | Workspace Owner | Workspace Member |
| --- | --- | --- | --- | --- |
| View organization users | yes | no | no | no |
| Create/update organization users | yes | no | no | no |
| Run user lifecycle batch (`POST /$batch`) | yes | no | no | no |
| Manage groups in organization scope | yes | no | no | no |
| Manage provisioning mode and SCIM settings | yes | no | no | no |
| Create org role assignments | yes | no | no | no |
| View workspace principals | yes | member-only | yes | granted only |
| Invite user into workspace | yes | no | yes | no |
| Assign workspace roles | yes | no | yes | no |
| Manage organization role definitions | yes | no | no | no |
| Manage workspace role definitions | yes | no | granted only | no |

## Boundary Rules

1. `workspace.members.manage` authorizes workspace-scoped invites and assignments only.
2. `users.manage_all` is required for global user lifecycle operations.
3. `groups.members.manage_all` does not authorize workspace role assignment mutations.
4. `identity.provisioning.manage` governs provisioning mode and SCIM token lifecycle.
5. Batch authz is evaluated per subrequest with no privilege aggregation.

## Group-Derived Access Rules

1. Effective permissions are union of direct grants and group-derived grants.
2. Deactivated users have no effective access even if assignments remain.
3. Provider-managed group memberships are read-only from ADE manual mutation endpoints.

## Policy Extensions (Optional)

1. Invite-approval gate for restricted organizations.
2. Sensitive-role assignment approval for high-risk workspace roles.
