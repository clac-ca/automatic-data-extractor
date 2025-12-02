"""Static RBAC policy definitions (implication rules, etc.)."""

from __future__ import annotations

# Global-scope permission implications
GLOBAL_IMPLICATIONS: dict[str, tuple[str, ...]] = {
    "roles.manage_all": ("roles.read_all",),
    "system.settings.manage": ("system.settings.read",),
    "workspaces.manage_all": ("workspaces.read_all",),
    "api_keys.manage_all": ("api_keys.read_all",),
    "users.manage_all": ("users.read_all",),
}

# Workspace-scope permission implications
WORKSPACE_IMPLICATIONS: dict[str, tuple[str, ...]] = {
    "workspace.settings.manage": ("workspace.read",),
    "workspace.members.manage": ("workspace.members.read", "workspace.read"),
    "workspace.documents.manage": ("workspace.documents.read", "workspace.read"),
    "workspace.configurations.manage": ("workspace.configurations.read", "workspace.read"),
    "workspace.runs.manage": ("workspace.runs.read", "workspace.read"),
    "workspace.roles.manage": ("workspace.roles.read", "workspace.read"),
}

__all__ = ["GLOBAL_IMPLICATIONS", "WORKSPACE_IMPLICATIONS"]
