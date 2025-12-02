"""Canonical permission and system role registry.

Populate these constants with the authoritative catalog; keep the structure
stable so feature teams can seed and reference permissions consistently.
"""

from __future__ import annotations

from ade_api.core.rbac.types import PermissionDef, ScopeType, SystemRoleDef


def _permission(
    *,
    key: str,
    scope: ScopeType,
    label: str,
    description: str,
    resource: str | None = None,
    action: str | None = None,
) -> PermissionDef:
    if resource is None or action is None:
        parts = key.split(".")
        derived_action = parts[-1] if len(parts) > 1 else key
        derived_resource = ".".join(parts[:-1]) or key
        resource = resource or derived_resource
        action = action or derived_action
    return PermissionDef(
        key=key,
        resource=resource,
        action=action,
        scope_type=scope,
        label=label,
        description=description,
    )


PERMISSIONS: tuple[PermissionDef, ...] = (
    # Global permissions -------------------------------------------------
    _permission(
        key="workspaces.read_all",
        scope=ScopeType.GLOBAL,
        label="Read all workspaces",
        description="Enumerate and inspect every workspace in the tenant.",
    ),
    _permission(
        key="workspaces.manage_all",
        scope=ScopeType.GLOBAL,
        label="Manage all workspaces",
        description="Create, update, archive, or restore any workspace in the tenant.",
    ),
    _permission(
        key="workspaces.create",
        scope=ScopeType.GLOBAL,
        label="Create workspaces",
        description="Provision a new workspace within the tenant.",
    ),
    _permission(
        key="roles.read_all",
        scope=ScopeType.GLOBAL,
        label="Read roles",
        description="Inspect global role definitions and assignments.",
    ),
    _permission(
        key="roles.manage_all",
        scope=ScopeType.GLOBAL,
        label="Manage roles",
        description="Create, edit, or delete global roles and assignments.",
    ),
    _permission(
        key="api_keys.read_all",
        scope=ScopeType.GLOBAL,
        label="Read API keys",
        description="List and inspect API keys across the tenant.",
    ),
    _permission(
        key="api_keys.manage_all",
        scope=ScopeType.GLOBAL,
        label="Manage API keys",
        description="Create, rotate, and revoke API keys for any principal.",
    ),
    _permission(
        key="users.read_all",
        scope=ScopeType.GLOBAL,
        label="Read users",
        description="Inspect user profiles, status, and assignments across the tenant.",
    ),
    _permission(
        key="users.invite",
        scope=ScopeType.GLOBAL,
        label="Invite users",
        description="Invite new users or reinstate deactivated accounts.",
    ),
    _permission(
        key="system.settings.read",
        scope=ScopeType.GLOBAL,
        label="Read system settings",
        description="Inspect ADE tenant-wide configuration.",
    ),
    _permission(
        key="system.settings.manage",
        scope=ScopeType.GLOBAL,
        label="Manage system settings",
        description="Modify ADE tenant-wide configuration and feature toggles.",
    ),
    # Workspace permissions ---------------------------------------------
    _permission(
        key="workspace.read",
        scope=ScopeType.WORKSPACE,
        label="Read workspace",
        description="Access workspace dashboards and metadata.",
    ),
    _permission(
        key="workspace.settings.manage",
        scope=ScopeType.WORKSPACE,
        label="Manage workspace settings",
        description="Update workspace metadata and feature toggles.",
    ),
    _permission(
        key="workspace.delete",
        scope=ScopeType.WORKSPACE,
        label="Delete workspace",
        description="Delete the workspace after ensuring business guardrails.",
    ),
    _permission(
        key="workspace.members.read",
        scope=ScopeType.WORKSPACE,
        label="Read workspace members",
        description="List workspace members and their roles.",
    ),
    _permission(
        key="workspace.members.manage",
        scope=ScopeType.WORKSPACE,
        label="Manage workspace members",
        description="Invite, remove, or change member roles within the workspace.",
    ),
    _permission(
        key="workspace.documents.read",
        scope=ScopeType.WORKSPACE,
        label="Read documents",
        description="List and download workspace documents.",
    ),
    _permission(
        key="workspace.documents.manage",
        scope=ScopeType.WORKSPACE,
        label="Manage documents",
        description="Upload, update, delete, or restore workspace documents.",
    ),
    _permission(
        key="workspace.configurations.read",
        scope=ScopeType.WORKSPACE,
        label="Read configurations",
        description="View workspace configurations and version history.",
    ),
    _permission(
        key="workspace.configurations.manage",
        scope=ScopeType.WORKSPACE,
        label="Manage configurations",
        description="Create, update, archive, or restore workspace configurations.",
    ),
    _permission(
        key="workspace.runs.read",
        scope=ScopeType.WORKSPACE,
        label="Read runs",
        description="Inspect workspace runs and their artifacts.",
    ),
    _permission(
        key="workspace.runs.manage",
        scope=ScopeType.WORKSPACE,
        label="Manage runs",
        description="Submit runs and manage their lifecycle within the workspace.",
    ),
    _permission(
        key="workspace.roles.read",
        scope=ScopeType.WORKSPACE,
        label="Read workspace roles",
        description="View role definitions and assignments within the workspace.",
    ),
    _permission(
        key="workspace.roles.manage",
        scope=ScopeType.WORKSPACE,
        label="Manage workspace roles",
        description="Create, edit, delete, and assign roles within the workspace.",
    ),
)

PERMISSION_REGISTRY: dict[str, PermissionDef] = {
    definition.key: definition for definition in PERMISSIONS
}

SYSTEM_ROLES: tuple[SystemRoleDef, ...] = (
    SystemRoleDef(
        slug="global-admin",
        name="Global Admin",
        description="Tenant-wide administrator with access to all global permissions.",
        permissions=tuple(defn.key for defn in PERMISSIONS if defn.scope_type == ScopeType.GLOBAL),
        allowed_scopes=(ScopeType.GLOBAL,),
    ),
    SystemRoleDef(
        slug="global-user",
        name="Global User",
        description="Baseline global role with no administrative permissions.",
        permissions=(),
        allowed_scopes=(ScopeType.GLOBAL,),
    ),
    SystemRoleDef(
        slug="workspace-owner",
        name="Workspace Owner",
        description="Workspace owner with full management capabilities.",
        permissions=tuple(
            defn.key for defn in PERMISSIONS if defn.scope_type == ScopeType.WORKSPACE
        ),
        allowed_scopes=(ScopeType.WORKSPACE,),
    ),
    SystemRoleDef(
        slug="workspace-member",
        name="Workspace Member",
        description="Standard workspace member with common read/write capabilities.",
        permissions=(
            "workspace.read",
            "workspace.documents.read",
            "workspace.documents.manage",
            "workspace.configurations.read",
            "workspace.runs.read",
            "workspace.runs.manage",
        ),
        allowed_scopes=(ScopeType.WORKSPACE,),
    ),
)

SYSTEM_ROLE_BY_SLUG: dict[str, SystemRoleDef] = {
    definition.slug: definition for definition in SYSTEM_ROLES
}

__all__ = [
    "PERMISSION_REGISTRY",
    "PERMISSIONS",
    "PermissionDef",
    "ScopeType",
    "SYSTEM_ROLE_BY_SLUG",
    "SYSTEM_ROLES",
    "SystemRoleDef",
]
