"""Schemas for workspace responses."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from backend.app.shared.core.schema import BaseSchema

from ..users.schemas import UserProfile


class WorkspaceProfile(BaseSchema):
    """Workspace information decorated with membership metadata."""

    workspace_id: str = Field(serialization_alias="workspace_id", validation_alias="id")
    name: str
    slug: str
    roles: list[str]
    permissions: list[str]
    is_default: bool


class WorkspaceCreate(BaseSchema):
    """Payload for creating a workspace."""

    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=100)
    owner_user_id: str | None = Field(default=None, alias="owner_user_id")
    settings: dict[str, Any] | None = None


class WorkspaceUpdate(BaseSchema):
    """Payload for updating workspace metadata."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=100)
    settings: dict[str, Any] | None = None


class WorkspaceMemberCreate(BaseSchema):
    """Payload for adding a member to a workspace."""

    user_id: str
    role_ids: list[str] | None = Field(default=None, min_length=0)


class WorkspaceMemberRolesUpdate(BaseSchema):
    """Payload used to replace the set of roles for a membership."""

    role_ids: list[str] = Field(default_factory=list)


class WorkspaceMember(BaseSchema):
    """Representation of a workspace membership."""

    workspace_membership_id: str = Field(
        serialization_alias="workspace_membership_id",
        validation_alias="id",
    )
    workspace_id: str
    roles: list[str]
    permissions: list[str]
    is_default: bool
    user: UserProfile


class WorkspaceDefaultSelection(BaseSchema):
    """Response indicating the caller's default workspace selection."""

    workspace_id: str
    is_default: bool


__all__ = [
    "WorkspaceCreate",
    "WorkspaceDefaultSelection",
    "WorkspaceMember",
    "WorkspaceMemberCreate",
    "WorkspaceMemberRolesUpdate",
    "WorkspaceProfile",
    "WorkspaceUpdate",
]
