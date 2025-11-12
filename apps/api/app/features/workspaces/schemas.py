"""Schemas for workspace responses."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from apps.api.app.shared.core.ids import ULIDStr
from apps.api.app.shared.core.schema import BaseSchema
from apps.api.app.shared.pagination import Page

from ..users.schemas import UserOut


class WorkspaceOut(BaseSchema):
    """Workspace information decorated with membership metadata."""

    id: ULIDStr
    name: str
    slug: str
    roles: list[str]
    permissions: list[str]
    is_default: bool


class WorkspaceCreate(BaseSchema):
    """Payload for creating a workspace."""

    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=100)
    owner_user_id: ULIDStr | None = Field(default=None, alias="owner_user_id")
    settings: dict[str, Any] | None = None


class WorkspaceUpdate(BaseSchema):
    """Payload for updating workspace metadata."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=100)
    settings: dict[str, Any] | None = None


class WorkspaceMemberCreate(BaseSchema):
    """Payload for adding a member to a workspace."""

    user_id: ULIDStr
    role_ids: list[ULIDStr] | None = Field(default=None, min_length=0)


class WorkspaceMemberRolesUpdate(BaseSchema):
    """Payload used to replace the set of roles for a membership."""

    role_ids: list[ULIDStr] = Field(default_factory=list)


class WorkspaceMemberOut(BaseSchema):
    """Representation of a workspace membership."""

    id: ULIDStr
    workspace_id: ULIDStr
    roles: list[str]
    permissions: list[str]
    is_default: bool
    user: UserOut


class WorkspaceDefaultSelectionOut(BaseSchema):
    """Response indicating the caller's default workspace selection."""

    workspace_id: ULIDStr
    is_default: bool


class WorkspacePage(Page[WorkspaceOut]):
    """Paginated workspace listing."""


class WorkspaceMemberPage(Page[WorkspaceMemberOut]):
    """Paginated workspace member listing."""


__all__ = [
    "WorkspaceCreate",
    "WorkspaceDefaultSelectionOut",
    "WorkspaceMemberOut",
    "WorkspaceMemberCreate",
    "WorkspaceMemberRolesUpdate",
    "WorkspaceOut",
    "WorkspaceUpdate",
    "WorkspacePage",
    "WorkspaceMemberPage",
]
