"""Pydantic schemas for role definitions."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from ade.core.schema import BaseSchema


class PermissionRead(BaseSchema):
    """Serialized permission registry entry."""

    key: str
    resource: str
    action: str
    scope_type: Literal["global", "workspace"]
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


class RoleRead(BaseSchema):
    """Serialized representation of a role definition."""

    role_id: str = Field(serialization_alias="role_id", validation_alias="id")
    slug: str
    name: str
    description: str | None = None
    scope_type: Literal["global", "workspace"]
    scope_id: str | None = None
    permissions: list[str]
    built_in: bool
    editable: bool


class RoleAssignmentCreate(BaseSchema):
    """Payload for creating a role assignment."""

    role_id: str = Field(min_length=1)
    principal_id: str | None = Field(default=None, min_length=1)
    user_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _ensure_identifier(self) -> "RoleAssignmentCreate":
        if not self.principal_id and not self.user_id:
            raise ValueError("principal_id or user_id is required")
        if self.principal_id and self.user_id:
            raise ValueError("Provide only one of principal_id or user_id")
        return self


class RoleAssignmentRead(BaseSchema):
    """Serialized representation of a role assignment."""

    assignment_id: str = Field(
        serialization_alias="assignment_id", validation_alias="id"
    )
    principal_id: str
    principal_type: Literal["user"]
    user_id: str | None = None
    user_email: str | None = None
    user_display_name: str | None = None
    role_id: str
    role_slug: str
    scope_type: Literal["global", "workspace"]
    scope_id: str | None = None
    created_at: datetime


class EffectivePermissionsResponse(BaseSchema):
    """Effective permissions for the authenticated principal."""

    global_permissions: list[str] = Field(default_factory=list)
    workspace_id: str | None = None
    workspace_permissions: list[str] = Field(default_factory=list)


class PermissionCheckRequest(BaseSchema):
    """Batch permission check payload."""

    permissions: list[str] = Field(min_length=1)
    workspace_id: str | None = None


class PermissionCheckResponse(BaseSchema):
    """Result map produced by the batch permission check."""

    results: dict[str, bool] = Field(default_factory=dict)


__all__ = [
    "EffectivePermissionsResponse",
    "PermissionCheckRequest",
    "PermissionCheckResponse",
    "PermissionRead",
    "RoleAssignmentCreate",
    "RoleAssignmentRead",
    "RoleCreate",
    "RoleRead",
    "RoleUpdate",
]
