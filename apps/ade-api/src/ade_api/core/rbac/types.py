"""RBAC type definitions used across the stack."""

from __future__ import annotations

import enum
from dataclasses import dataclass


class ScopeType(str, enum.Enum):
    """Scopes supported by RBAC-aware resources."""

    GLOBAL = "global"
    WORKSPACE = "workspace"


@dataclass(frozen=True)
class PermissionDef:
    """Static permission definition."""

    key: str
    scope_type: ScopeType
    resource: str
    action: str
    label: str
    description: str


@dataclass(frozen=True)
class SystemRoleDef:
    """Static system role definition seeded at startup."""

    slug: str
    name: str
    description: str
    permissions: tuple[str, ...]
    allowed_scopes: tuple[ScopeType, ...]
    is_system: bool = True
    is_editable: bool = False
