"""RBAC models exposed under ``ade_api.infra.db.models`` for feature modules."""

from ade_api.core.models.rbac import Permission, Role, RolePermission, ScopeType, UserRoleAssignment

__all__ = ["Permission", "Role", "RolePermission", "ScopeType", "UserRoleAssignment"]
