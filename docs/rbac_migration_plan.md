# ADE RBAC Migration Plan

> Reimagining ADE's permissions to be **SIMPLE, SCALABLE, and MAINTAINABLE**
> using a Microsoft Graph–style RBAC model.

This plan captures the current inventory, the target RBAC shape, rollout steps,
and the test strategy required to finish the redesign safely. The registry and
helpers now live under `app/features/roles`, while workspace routes consume the
Graph-style permission keys directly.

---

## 1. Current-state inventory

### API & session contract
- Session payload returns the authenticated user plus the active workspace
  profile. `WorkspaceProfile.permissions` contains Graph-style keys such as
  `Workspace.Documents.Read`.
- Route protection relies on `require_workspace_access`, which checks Graph keys
  against the resolved `WorkspaceProfile` and raises `403` when any are
  missing. Global routes consume the matching `require_global_access`
  dependency that now enforces `Workspaces.Create`, `Roles.ReadWrite.All`, etc.
- Global administrators shadow as workspace owners; other users receive the
  permission lists derived from their workspace role defaults.

### Persistence
- Alembic migration `0002_graph_rbac_scaffold.py` introduces the `permissions`,
  `roles`, `role_permissions`, and `user_global_roles` tables and adds a
  nullable `role_id` column to `workspace_memberships`.
- Application startup calls `sync_permission_registry` to seed the registry and
  immutable system roles (`Admin`, `User`, `WorkspaceOwner`, `WorkspaceMember`).
- `WorkspaceMembership.permissions` has been removed; runtime permission lists
  are computed from the registry-backed role defaults.

### Permission vocabulary
- The canonical registry lives in
  `app/features/roles/registry.py` and the public catalog in
  `docs/permission_catalog.md` mirrors the same keys.
- Feature tests, fixtures, and docs reference the Graph names directly—there is
  no remaining dependency on the legacy colon-scoped aliases.

---

## 2. Target RBAC model

### Permission registry (Graph-style)
- Keys follow `{Resource}.{Operation}[.All]` naming with `.All` representing
  tenant-wide scope.
- Registry entries carry: `key` (PK), `scope` (`global` or `workspace`),
  `label`, `description`.
- Starting set:
  - **Global:** `Workspaces.Read.All`, `Workspaces.ReadWrite.All`,
    `Workspaces.Create`, `Roles.Read.All`, `Roles.ReadWrite.All`,
    `Users.Read.All`, `Users.Invite`, `System.Settings.Read`,
    `System.Settings.ReadWrite`.
  - **Workspace:** `Workspace.Read`, `Workspace.Settings.ReadWrite`,
    `Workspace.Delete`, `Workspace.Members.Read`,
    `Workspace.Members.ReadWrite`, `Workspace.Documents.Read`,
    `Workspace.Documents.ReadWrite`, `Workspace.Configurations.Read`,
    `Workspace.Configurations.ReadWrite`, `Workspace.Jobs.Read`,
    `Workspace.Jobs.ReadWrite`.
- Optional extensions (delete/purge/export granularities) stay out of the
  registry until a concrete need emerges.

### Roles
- `roles` table stores metadata (`slug`, `name`, `description`, `scope`,
  `is_system`, `editable`, audit columns).
- Join tables: `role_permissions`, `user_global_roles`, and
  `workspace_memberships.role_id` (future pivot `membership_roles` can extend
  workspace assignments).
- System seeds (immutable): `Admin` (global), `User` (global baseline),
  `WorkspaceOwner`, `WorkspaceMember`. Owners include `Workspace.Delete`.

### Authorization helpers
- `authorize_global` and `authorize_workspace` validate required keys against
  the registry and enforce default deny. `get_global_permissions_for_user`
  collapses assigned global roles (with an admin shortcut).
- `sync_permission_registry` keeps the database representation aligned with the
  registry constants, ensuring the helpers always validate against the same
  source of truth.

---

## 3. Migration & rollout strategy

### Phase 0 – foundations (landed)
- Registry, models, migrations, helpers, and documentation checked in under
  `app/features/roles`.
- Workspace and global routes reference Graph keys via
  `require_workspace_access` and `require_global_access`.
- Startup seeding ensures permissions and immutable roles exist.

### Phase 1 – global role assignments
- Model admin APIs (or CLI flows) to assign global roles via
  `user_global_roles`.
- Update the session payload to surface the caller's global permission list for
  debugging and UI purposes (workspace permissions remain per-request).
- Extend tests to cover global role assignment flows.

### Phase 2 – workspace role administration
- Build the role editor UI/API for cloning system roles and toggling
  permissions.
- Decide whether to allow multiple roles per membership (`membership_roles`)
  or stick with the single `role_id` column.
- Add service methods and routes for workspace role CRUD guarded by
  `Roles.ReadWrite.All`.

### Phase 3 – telemetry & hardening
- Add audit logging around role and permission changes.
- Publish documentation for customers (catalog + role matrix).
- Monitor adoption and introduce optional extension keys when required.

---

## 4. Testing strategy

- **Unit tests:** cover authorization helpers (`default deny`, unknown key
  rejection, global permission aggregation) under
  `app/features/roles/tests/`.
- **Integration tests:** workspace router specs exercise success/failure paths
  for Graph keys (`Workspace.Delete`, member management). Global creation route
  ensures only the correct keys succeed.
- **Migration smoke tests:** Alembic fixtures run upgrade/downgrade to verify
  registry tables create cleanly; startup seeding runs in tests via the
  application lifespan.
- **Docs alignment:** `docs/permission_catalog.md` is kept in sync with the
  registry constants; future automation can lint this relationship.

---

## 5. Rollout checklist

1. Finalise global role assignment APIs and tests.
2. Ship the role management UI (clone/edit system roles).
3. Implement workspace role assignment flows once the admin UI lands.
4. Add observability (audit logging, metrics) around permission changes.
5. Revisit optional permission extensions after customer feedback.

---

## 6. Open questions & follow-ups

- How should service accounts inherit workspace permissions? (Possible future
  `Workspace.Members.ReadWrite.All` global key.)
- Do we need per-workspace custom roles at launch? Schema supports it via
  additional data once requirements arrive.
- Should we expose permission categories for UI grouping? Derivable from the
  resource prefix if needed later.

Prepared by: ADE Automation Agent
Date: 2024-03-01
