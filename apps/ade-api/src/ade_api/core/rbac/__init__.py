"""RBAC contracts and registries shared across features."""

from .policy import GLOBAL_IMPLICATIONS, WORKSPACE_IMPLICATIONS
from .registry import (
    PERMISSION_REGISTRY,
    PERMISSIONS,
    SYSTEM_ROLE_BY_SLUG,
    SYSTEM_ROLES,
)
from .service_interface import RbacService
from .types import PermissionDef, ScopeType, SystemRoleDef

__all__ = [
    "PERMISSION_REGISTRY",
    "PERMISSIONS",
    "SYSTEM_ROLE_BY_SLUG",
    "SYSTEM_ROLES",
    "RbacService",
    "ScopeType",
    "PermissionDef",
    "SystemRoleDef",
    "GLOBAL_IMPLICATIONS",
    "WORKSPACE_IMPLICATIONS",
]
