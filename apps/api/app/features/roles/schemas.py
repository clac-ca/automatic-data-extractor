"""Pydantic schemas for role definitions."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from apps.api.app.shared.core.ids import ULIDStr
from apps.api.app.shared.core.schema import BaseSchema
from apps.api.app.shared.pagination import Page

from .models import PrincipalType, ScopeType


class PermissionOut(BaseSchema):
    """Serialized permission registry entry."""

    id: ULIDStr
    key: str
    resource: str
    action: str
    scope_type: ScopeType
    label: str
    description: str


class RoleCreate(BaseSchema):
    """Payload for creating a workspace or global role."""

    name: str = Field(min_length=1, max_length=150)
    slug: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)


class RoleUpdate(BaseSchema):
    """Payload for updating an existing role."""

    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)


class RoleOut(BaseSchema):
    """Serialized representation of a role definition."""

    id: ULIDStr
    slug: str
    name: str
    description: str | None = None
    scope_type: ScopeType
    scope_id: ULIDStr | None = None
    permissions: list[str]
    built_in: bool
    editable: bool


class RoleAssignmentCreate(BaseSchema):
    """Payload for creating a role assignment."""

    role_id: ULIDStr
    principal_id: ULIDStr | None = None
    user_id: ULIDStr | None = None

    @model_validator(mode="after")
    def _ensure_identifier(self) -> RoleAssignmentCreate:
        if not self.principal_id and not self.user_id:
            raise ValueError("principal_id or user_id is required")
        if self.principal_id and self.user_id:
            raise ValueError("Provide only one of principal_id or user_id")
        return self


class RoleAssignmentOut(BaseSchema):
    """Serialized representation of a role assignment."""

    id: ULIDStr
    principal_id: ULIDStr
    principal_type: PrincipalType
    user_id: ULIDStr | None = None
    user_email: str | None = None
    user_display_name: str | None = None
    role_id: ULIDStr
    role_slug: str
    scope_type: ScopeType
    scope_id: ULIDStr | None = None
    created_at: datetime


class EffectivePermissionsResponse(BaseSchema):
    """Effective permissions for the authenticated principal."""

    global_permissions: list[str] = Field(default_factory=list)
    workspace_id: ULIDStr | None = None
    workspace_permissions: list[str] = Field(default_factory=list)


class PermissionCheckRequest(BaseSchema):
    """Batch permission check payload."""

    permissions: list[str] = Field(min_length=1)
    workspace_id: ULIDStr | None = None


class PermissionCheckResponse(BaseSchema):
    """Result map produced by the batch permission check."""

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
    "PermissionPage",
    "PermissionOut",
    "RoleAssignmentCreate",
    "RoleAssignmentOut",
    "RoleAssignmentPage",
    "RoleCreate",
    "RoleOut",
    "RolePage",
    "RoleUpdate",
]
