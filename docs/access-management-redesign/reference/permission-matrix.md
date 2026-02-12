# Permission Matrix (Recommended)

## Permission Catalog (Proposed)

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

### Workspace scope

- `workspace.read`
- `workspace.members.read`
- `workspace.members.manage`
- `workspace.roles.read`
- `workspace.roles.manage`
- `workspace.invitations.read`
- `workspace.invitations.manage`

## Actor Capability Matrix

| Capability | Global Admin | Global User | Workspace Owner | Workspace Member |
|---|---|---|---|---|
| View organization users | Yes | No | No | No |
| Create/update org users | Yes | No | No | No |
| View/manage groups (org) | Yes | No | No | No |
| Create org role assignments | Yes | No | No | No |
| View workspace principals | Yes | If member and has read role | Yes | If granted |
| Invite user into workspace | Yes | No | Yes | No |
| Assign workspace roles | Yes | No | Yes | No |
| Manage org roles | Yes | No | No | No |
| Manage workspace roles | Yes | No | Yes (if granted) | No |

## Boundary Rules

1. `workspace.members.manage` allows workspace-scoped invitation and role assignment only.
2. `users.manage_all` is required for global user lifecycle operations.
3. `groups.members.manage_all` does not imply workspace role assignment permission.
4. `roles.manage_all` does not imply unrestricted workspace membership edits unless paired with workspace authority (or explicit global override policy).

## Group-Derived Access Rules

1. Effective permissions are union of direct principal grants and group grants.
2. User deactivation suppresses all effective permissions.
3. Dynamic group memberships are read-only from ADE mutation endpoints.

## Special Policy Hooks (Recommended)

1. Optional approval policy for assigning sensitive roles (for example `workspace-owner`).
2. Optional invite-approval mode for high-regulation organizations.

