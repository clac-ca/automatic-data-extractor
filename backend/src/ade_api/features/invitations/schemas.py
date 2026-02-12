from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field

from ade_api.common.schema import BaseSchema
from ade_db.models import InvitationStatus


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


class InvitationOut(BaseSchema):
    id: UUID
    email_normalized: str
    invited_user_id: UUID | None
    invited_by_user_id: UUID
    status: InvitationStatus
    expires_at: datetime | None
    redeemed_at: datetime | None
    metadata: dict[str, object] | None
    created_at: datetime
    updated_at: datetime | None


class InvitationListResponse(BaseSchema):
    items: list[InvitationOut]


__all__ = [
    "InvitationCreate",
    "InvitationListResponse",
    "InvitationOut",
    "InvitationRoleAssignmentSeed",
    "InvitationWorkspaceContext",
]
