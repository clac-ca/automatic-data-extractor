"""Pydantic schemas for role definitions."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.core.schema import BaseSchema


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


__all__ = ["RoleRead"]
