"""Canonical permission registry for ADE's Graph-style RBAC."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

PermissionScope = Literal["global", "workspace"]


@dataclass(frozen=True)
class PermissionDefinition:
    """Describes a permission entry in the registry."""

    key: str
    resource: str
    action: str
    scope: PermissionScope
    label: str
    description: str


@dataclass(frozen=True)
class SystemRoleDefinition:
    """Seed data for immutable system roles."""

    slug: str
    name: str
    scope_type: PermissionScope
    description: str
    permissions: tuple[str, ...]
    built_in: bool = True
    editable: bool = False


def _definition(
    *, key: str, scope: PermissionScope, label: str, description: str
) -> PermissionDefinition:
    parts = key.split(".")
    resource = parts[0] if parts else key
    action = ".".join(parts[1:]) if len(parts) > 1 else "*"
    return PermissionDefinition(
        key=key,
        resource=resource,
        action=action,
        scope=scope,
        label=label,
        description=description,
    )


PERMISSIONS: tuple[PermissionDefinition, ...] = (
    # Global permissions -------------------------------------------------
    _definition(
        key="Workspaces.Read.All",
        scope="global",
        label="Read all workspaces",
        description="Enumerate and inspect every workspace in the tenant.",
    ),
    _definition(
        key="Workspaces.ReadWrite.All",
        scope="global",
        label="Manage all workspaces",
        description="Create, update, delete, archive, or restore any workspace.",
    ),
    _definition(
        key="Workspaces.Create",
        scope="global",
        label="Create workspaces",
        description="Provision a new workspace within the tenant.",
    ),
    _definition(
        key="Roles.Read.All",
        scope="global",
        label="Read roles",
        description="View any global or workspace role definition.",
    ),
    _definition(
        key="Roles.ReadWrite.All",
        scope="global",
        label="Manage roles",
        description="Create, edit, or archive role definitions across the tenant.",
    ),
    _definition(
        key="Users.Read.All",
        scope="global",
        label="Read users",
        description="Inspect user profiles, status, and assignments across the tenant.",
    ),
    _definition(
        key="Users.Invite",
        scope="global",
        label="Invite users",
        description="Invite new users or reinstate deactivated accounts.",
    ),
    _definition(
        key="System.Settings.Read",
        scope="global",
        label="Read system settings",
        description="Inspect ADE's tenant-wide configuration.",
    ),
    _definition(
        key="System.Settings.ReadWrite",
        scope="global",
        label="Manage system settings",
        description="Modify ADE's tenant-wide configuration and feature toggles.",
    ),
    # Workspace permissions ---------------------------------------------
    _definition(
        key="Workspace.Read",
        scope="workspace",
        label="Read workspace",
        description="Access workspace dashboards and metadata.",
    ),
    _definition(
        key="Workspace.Settings.ReadWrite",
        scope="workspace",
        label="Manage workspace settings",
        description="Update workspace metadata and feature toggles.",
    ),
    _definition(
        key="Workspace.Delete",
        scope="workspace",
        label="Delete workspace",
        description="Delete the workspace after ensuring business guardrails.",
    ),
    _definition(
        key="Workspace.Members.Read",
        scope="workspace",
        label="Read workspace members",
        description="List workspace members and their roles.",
    ),
    _definition(
        key="Workspace.Members.ReadWrite",
        scope="workspace",
        label="Manage workspace members",
        description="Invite, remove, or change member roles within the workspace.",
    ),
    _definition(
        key="Workspace.Documents.Read",
        scope="workspace",
        label="Read documents",
        description="List and download workspace documents.",
    ),
    _definition(
        key="Workspace.Documents.ReadWrite",
        scope="workspace",
        label="Manage documents",
        description="Upload, update, delete, or restore workspace documents.",
    ),
    _definition(
        key="Workspace.Configurations.Read",
        scope="workspace",
        label="Read configurations",
        description="Inspect configuration versions for document processing.",
    ),
    _definition(
        key="Workspace.Configurations.ReadWrite",
        scope="workspace",
        label="Manage configurations",
        description="Create, edit, activate, or delete configuration versions.",
    ),
    _definition(
        key="Workspace.Roles.Read",
        scope="workspace",
        label="Read workspace roles",
        description="View role definitions and assignments within the workspace.",
    ),
    _definition(
        key="Workspace.Roles.ReadWrite",
        scope="workspace",
        label="Manage workspace roles",
        description="Create, edit, delete, and assign roles within the workspace.",
    ),
    _definition(
        key="Workspace.Jobs.Read",
        scope="workspace",
        label="Read jobs",
        description="Inspect job history and run details within the workspace.",
    ),
    _definition(
        key="Workspace.Jobs.ReadWrite",
        scope="workspace",
        label="Manage jobs",
        description="Submit, cancel, retry, or reprioritise jobs within the workspace.",
    ),
)

PERMISSION_REGISTRY: Mapping[str, PermissionDefinition] = {
    definition.key: definition for definition in PERMISSIONS
}


SYSTEM_ROLES: tuple[SystemRoleDefinition, ...] = (
    SystemRoleDefinition(
        slug="global-administrator",
        name="Global Administrator",
        scope_type="global",
        description="Tenant-wide administrator with access to all global permissions.",
        permissions=tuple(
            definition.key for definition in PERMISSIONS if definition.scope == "global"
        ),
    ),
    SystemRoleDefinition(
        slug="global-user",
        name="Global User",
        scope_type="global",
        description="Baseline global role with no administrative permissions.",
        permissions=(),
    ),
    SystemRoleDefinition(
        slug="workspace-owner",
        name="Workspace Owner",
        scope_type="workspace",
        description="Workspace owner with full management capabilities.",
        permissions=(
            "Workspace.Read",
            "Workspace.Settings.ReadWrite",
            "Workspace.Delete",
            "Workspace.Members.Read",
            "Workspace.Members.ReadWrite",
            "Workspace.Documents.Read",
            "Workspace.Documents.ReadWrite",
            "Workspace.Configurations.Read",
            "Workspace.Configurations.ReadWrite",
            "Workspace.Roles.Read",
            "Workspace.Roles.ReadWrite",
            "Workspace.Jobs.Read",
            "Workspace.Jobs.ReadWrite",
        ),
    ),
    SystemRoleDefinition(
        slug="workspace-member",
        name="Workspace Member",
        scope_type="workspace",
        description="Standard workspace member with common read/write capabilities.",
        permissions=(
            "Workspace.Read",
            "Workspace.Documents.Read",
            "Workspace.Documents.ReadWrite",
            "Workspace.Configurations.Read",
            "Workspace.Jobs.Read",
        ),
    ),
)


__all__ = [
    "PERMISSION_REGISTRY",
    "PERMISSIONS",
    "PermissionDefinition",
    "PermissionScope",
    "SYSTEM_ROLES",
    "SystemRoleDefinition",
]
