# Graph-style Permission Catalog (Draft)

This catalog mirrors the registry that will live in the database. Each permission includes a human label and description so that admin tooling and documentation can rely on a single source of truth.

| Key | Scope | Label | Description |
| --- | --- | --- | --- |
| `Workspaces.Read.All` | global | Read all workspaces | Enumerate and inspect every workspace in the tenant. |
| `Workspaces.ReadWrite.All` | global | Manage all workspaces | Create, update, delete, archive, or restore any workspace. |
| `Workspaces.Create` | global | Create workspaces | Provision a new workspace within the tenant. |
| `Roles.Read.All` | global | Read roles | View any global or workspace role definition. |
| `Roles.ReadWrite.All` | global | Manage roles | Create, edit, or archive role definitions. |
| `Users.Read.All` | global | Read users | View user profiles, status, and assignments. |
| `Users.Invite` | global | Invite users | Send invitations or reinstate deactivated accounts. |
| `System.Settings.Read` | global | Read system settings | Inspect ADE global configuration. |
| `System.Settings.ReadWrite` | global | Manage system settings | Modify ADE global configuration and feature toggles. |
| `Workspace.Read` | workspace | Read workspace | Access basic workspace metadata and dashboards. |
| `Workspace.Settings.ReadWrite` | workspace | Manage workspace settings | Update workspace metadata and feature toggles. |
| `Workspace.Delete` | workspace | Delete workspace | Delete the workspace after verifying guardrails. |
| `Workspace.Members.Read` | workspace | Read workspace members | View the membership roster and roles. |
| `Workspace.Members.ReadWrite` | workspace | Manage workspace members | Invite, remove, or change member roles. |
| `Workspace.Documents.Read` | workspace | Read documents | List and download workspace documents. |
| `Workspace.Documents.ReadWrite` | workspace | Manage documents | Upload, update, delete, or restore workspace documents. |
| `Workspace.Configs.Read` | workspace | Read configs | View configuration packages, drafts, and published versions. |
| `Workspace.Configs.ReadWrite` | workspace | Manage configs | Create, edit, publish, revert, or delete configuration packages. |
| `Workspace.Runs.Read` | workspace | Read runs | Inspect run history and status. |
| `Workspace.Runs.ReadWrite` | workspace | Manage runs | Submit, cancel, retry, or reprioritise runs within the workspace. |

## Admin UI sketch

- **Role browser:** list roles grouped by scope. Display badge if a role is system-managed (`is_system=True`, `editable=False`).
- **Role detail:** show label/description, permission checklist with registry-driven tooltips, and an audit trail of changes.
- **Clone flow:** `Clone role` button available for system roles; pre-populates name/description with suffix "(Clone)" and allows toggling permissions before saving.
- **Assignment views:**
  - *Global:* assign roles to users/service accounts with search + filter by permission.
  - *Workspace:* embed within workspace members tab, supporting multi-role assignments when `membership_roles` pivot ships.
- **Change log:** document registry revisions so support teams can explain new capabilities when keys are added.

All UI copy should reference the labels from this catalog to guarantee consistency between docs and implementation.
