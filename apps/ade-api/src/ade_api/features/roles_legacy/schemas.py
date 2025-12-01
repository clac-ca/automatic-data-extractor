"""Pydantic schemas for RBAC routes."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from ade_api.shared.core.ids import UUIDStr
from ade_api.shared.core.schema import BaseSchema
from ade_api.shared.pagination import Page

from .models import ScopeType


class PermissionOut(BaseSchema):
    id: UUIDStr
    key: str
    resource: str
    action: str
    scope_type: ScopeType
    label: str
    description: str


class RoleCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=150)
    slug: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)


class RoleUpdate(BaseSchema):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)


class RoleOut(BaseSchema):
    id: UUIDStr
    slug: str
    name: str
    description: str | None = None
    permissions: list[str]
    is_system: bool
    is_editable: bool
    created_at: datetime
    updated_at: datetime


class RoleAssignmentCreate(BaseSchema):
    role_id: UUIDStr
    user_id: UUIDStr


class RoleAssignmentOut(BaseSchema):
    id: UUIDStr
    user_id: UUIDStr
    role_id: UUIDStr
    role_slug: str
    scope_type: ScopeType
    scope_id: UUIDStr | None = None
    created_at: datetime


class EffectivePermissionsResponse(BaseSchema):
    global_permissions: list[str] = Field(default_factory=list)
    workspace_id: UUIDStr | None = None
    workspace_permissions: list[str] = Field(default_factory=list)


class PermissionCheckRequest(BaseSchema):
    permissions: list[str] = Field(min_length=1)
    workspace_id: UUIDStr | None = None


class PermissionCheckResponse(BaseSchema):
    results: dict[str, bool] = Field(default_factory=dict)


class RolePage(Page[RoleOut]):
    """Paginated role collection."""


class RoleAssignmentPage(Page[RoleAssignmentOut]):
    """Paginated role assignment collection."""


class PermissionPage(Page[PermissionOut]):
    """Paginated permission registry response."""


__all__ = [
    "EffectivePermissionsResponse",
    "PermissionCheckRequest",
    "PermissionCheckResponse",
    "PermissionOut",
    "PermissionPage",
    "RoleAssignmentCreate",
    "RoleAssignmentOut",
    "RoleAssignmentPage",
    "RoleCreate",
    "RoleOut",
    "RolePage",
    "RoleUpdate",
    "ScopeType",
]
