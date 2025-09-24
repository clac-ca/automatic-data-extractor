"""Schemas for workspace responses."""

from __future__ import annotations

from pydantic import Field

from ...core.schema import BaseSchema
from ..users.schemas import UserProfile
from .models import WorkspaceRole


class WorkspaceProfile(BaseSchema):
    """Workspace information decorated with membership metadata."""

    workspace_id: str = Field(serialization_alias="workspace_id", validation_alias="id")
    name: str
    slug: str
    role: WorkspaceRole
    permissions: list[str]
    is_default: bool


class WorkspaceContext(BaseSchema):
    """Resolved workspace context for the current request."""

    workspace: WorkspaceProfile


class WorkspaceMemberCreate(BaseSchema):
    """Payload for adding a member to a workspace."""

    user_id: str
    role: WorkspaceRole = WorkspaceRole.MEMBER


class WorkspaceMember(BaseSchema):
    """Representation of a workspace membership."""

    workspace_membership_id: str = Field(
        serialization_alias="workspace_membership_id",
        validation_alias="id",
    )
    workspace_id: str
    role: WorkspaceRole
    permissions: list[str]
    is_default: bool
    user: UserProfile


__all__ = [
    "WorkspaceContext",
    "WorkspaceMember",
    "WorkspaceMemberCreate",
    "WorkspaceProfile",
]
