"""Schemas for workspace responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from ade_api.common.cursor_listing import CursorPage
from ade_api.common.ids import UUIDStr
from ade_api.common.schema import BaseSchema
from ade_db.models import PrincipalType


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


class WorkspaceMemberUserOut(BaseSchema):
    """Renderable user identity for a workspace member."""

    id: UUIDStr
    email: str
    display_name: str | None = None


class WorkspaceMemberSourceOut(BaseSchema):
    """A direct or indirect grant source contributing to effective access."""

    principal_type: PrincipalType
    principal_id: UUIDStr
    principal_display_name: str | None = None
    principal_email: str | None = None
    principal_slug: str | None = None
    role_ids: list[UUIDStr]
    role_slugs: list[str]
    created_at: datetime


class WorkspaceMemberOut(BaseSchema):
    """Effective workspace member with identity and access source metadata."""

    user_id: UUIDStr
    role_ids: list[UUIDStr]
    role_slugs: list[str]
    created_at: datetime
    user: WorkspaceMemberUserOut
    access_mode: Literal["direct", "indirect", "mixed"]
    is_directly_managed: bool
    sources: list[WorkspaceMemberSourceOut] = Field(default_factory=list)


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
    "WorkspaceMemberSourceOut",
    "WorkspaceMemberUpdate",
    "WorkspaceMemberUserOut",
    "WorkspaceOut",
    "WorkspaceUpdate",
    "WorkspacePage",
]
