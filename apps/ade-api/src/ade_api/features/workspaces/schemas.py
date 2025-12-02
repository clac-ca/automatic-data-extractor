"""Schemas for workspace responses."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ade_api.common.ids import UUIDStr
from ade_api.common.pagination import Page
from ade_api.common.schema import BaseSchema


class WorkspaceOut(BaseSchema):
    """Workspace information decorated with membership metadata."""

    id: UUIDStr
    name: str
    slug: str
    roles: list[str]
    permissions: list[str]
    is_default: bool


class WorkspaceCreate(BaseSchema):
    """Payload for creating a workspace."""

    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=100)
    owner_user_id: UUIDStr | None = Field(default=None, alias="owner_user_id")
    settings: dict[str, Any] | None = None


class WorkspaceUpdate(BaseSchema):
    """Payload for updating workspace metadata."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=100)
    settings: dict[str, Any] | None = None


class WorkspaceDefaultSelectionOut(BaseSchema):
    """Response indicating the caller's default workspace selection."""

    workspace_id: UUIDStr
    is_default: bool


class WorkspacePage(Page[WorkspaceOut]):
    """Paginated workspace listing."""


__all__ = [
    "WorkspaceCreate",
    "WorkspaceDefaultSelectionOut",
    "WorkspaceOut",
    "WorkspaceUpdate",
    "WorkspacePage",
]
