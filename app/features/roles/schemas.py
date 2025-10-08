"""Pydantic schemas for role definitions."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.core.schema import BaseSchema


class PermissionRead(BaseSchema):
    """Serialized permission registry entry."""

    key: str
    scope: Literal["global", "workspace"]
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
    scope: Literal["global", "workspace"]
    workspace_id: str | None = Field(default=None, serialization_alias="workspace_id")
    permissions: list[str]
    is_system: bool
    editable: bool


__all__ = ["PermissionRead", "RoleCreate", "RoleRead", "RoleUpdate"]
