"""Schemas for workspace responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from ade_api.common.cursor_listing import CursorPage
from ade_api.common.ids import UUIDStr
from ade_api.common.schema import BaseSchema


class WorkspaceOut(BaseSchema):
    """Workspace information decorated with membership metadata."""

    id: UUIDStr
    name: str
    slug: str
    roles: list[str]
    permissions: list[str]
    is_default: bool
    processing_paused: bool = Field(
        default=False,
        description="Whether document processing is paused for the workspace.",
    )


class WorkspaceCreate(BaseSchema):
    """Payload for creating a workspace."""

    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=100)
    owner_user_id: UUIDStr | None = Field(default=None, alias="owner_user_id")
    settings: dict[str, Any] | None = None
    processing_paused: bool | None = Field(
        default=None,
        description="Optional processing pause state for the workspace.",
    )


class WorkspaceUpdate(BaseSchema):
    """Payload for updating workspace metadata."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=100)
    settings: dict[str, Any] | None = None
    processing_paused: bool | None = Field(
        default=None,
        description="Optional processing pause state for the workspace.",
    )


class WorkspaceDefaultSelectionOut(BaseSchema):
    """Response indicating the caller's default workspace selection."""

    workspace_id: UUIDStr
    is_default: bool


class WorkspacePage(CursorPage[WorkspaceOut]):
    """Cursor-based workspace listing."""


class WorkspaceMemberOut(BaseSchema):
    """Workspace member with their role IDs and slugs."""

    user_id: UUIDStr
    role_ids: list[UUIDStr]
    role_slugs: list[str]
    created_at: datetime


class WorkspaceMemberCreate(BaseSchema):
    """Payload for adding a new workspace member with roles."""

    user_id: UUIDStr
    role_ids: list[UUIDStr]


class WorkspaceMemberUpdate(BaseSchema):
    """Payload for updating workspace member roles."""

    role_ids: list[UUIDStr]


class WorkspaceMemberPage(CursorPage[WorkspaceMemberOut]):
    """Cursor-based collection of workspace members."""


__all__ = [
    "WorkspaceCreate",
    "WorkspaceDefaultSelectionOut",
    "WorkspaceMemberCreate",
    "WorkspaceMemberOut",
    "WorkspaceMemberPage",
    "WorkspaceMemberUpdate",
    "WorkspaceOut",
    "WorkspaceUpdate",
    "WorkspacePage",
]
