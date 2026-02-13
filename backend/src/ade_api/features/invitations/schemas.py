from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import EmailStr, Field

from ade_api.common.cursor_listing import CursorPage
from ade_api.common.schema import BaseSchema


class InvitationRoleAssignmentSeed(BaseSchema):
    role_id: UUID = Field(alias="roleId")


class InvitationWorkspaceContext(BaseSchema):
    workspace_id: UUID = Field(alias="workspaceId")
    role_assignments: list[InvitationRoleAssignmentSeed] = Field(
        default_factory=list,
        alias="roleAssignments",
    )


class InvitationCreate(BaseSchema):
    invited_user_email: EmailStr = Field(alias="invitedUserEmail")
    display_name: str | None = Field(default=None, alias="displayName")
    workspace_context: InvitationWorkspaceContext | None = Field(
        default=None,
        alias="workspaceContext",
    )


class InvitationLifecycleStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class InvitationRoleAssignmentOut(BaseSchema):
    role_id: UUID = Field(alias="roleId")


class InvitationWorkspaceContextOut(BaseSchema):
    workspace_id: UUID = Field(alias="workspaceId")
    role_assignments: list[InvitationRoleAssignmentOut] = Field(
        default_factory=list,
        alias="roleAssignments",
    )


class InvitationOut(BaseSchema):
    id: UUID
    email_normalized: str
    invited_user_id: UUID | None
    invited_by_user_id: UUID
    workspace_id: UUID | None
    status: InvitationLifecycleStatus
    expires_at: datetime | None
    redeemed_at: datetime | None
    workspace_context: InvitationWorkspaceContextOut | None = Field(
        default=None,
        alias="workspaceContext",
    )
    created_at: datetime
    updated_at: datetime | None


class InvitationPage(CursorPage[InvitationOut]):
    """Cursor-based invitation collection."""


__all__ = [
    "InvitationCreate",
    "InvitationLifecycleStatus",
    "InvitationOut",
    "InvitationPage",
    "InvitationRoleAssignmentSeed",
    "InvitationRoleAssignmentOut",
    "InvitationWorkspaceContext",
    "InvitationWorkspaceContextOut",
]
