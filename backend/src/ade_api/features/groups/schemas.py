from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from ade_api.common.schema import BaseSchema
from ade_db.models import GroupMembershipMode, GroupSource


class GroupCreate(BaseSchema):
    display_name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    membership_mode: GroupMembershipMode = Field(default=GroupMembershipMode.ASSIGNED)
    source: GroupSource = Field(default=GroupSource.INTERNAL)
    external_id: str | None = None


class GroupUpdate(BaseSchema):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    membership_mode: GroupMembershipMode | None = None
    is_active: bool | None = None
    external_id: str | None = None


class GroupOut(BaseSchema):
    id: UUID
    display_name: str
    slug: str
    description: str | None
    membership_mode: GroupMembershipMode
    source: GroupSource
    external_id: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None


class GroupListResponse(BaseSchema):
    items: list[GroupOut]


class GroupMembershipRefCreate(BaseSchema):
    member_id: UUID = Field(alias="memberId")


class GroupMemberOut(BaseSchema):
    user_id: UUID
    email: str
    display_name: str | None


class GroupMembersResponse(BaseSchema):
    items: list[GroupMemberOut]


class GroupOwnerRefCreate(BaseSchema):
    owner_id: UUID = Field(alias="ownerId")


class GroupOwnerOut(BaseSchema):
    user_id: UUID
    email: str
    display_name: str | None


class GroupOwnersResponse(BaseSchema):
    items: list[GroupOwnerOut]


__all__ = [
    "GroupCreate",
    "GroupListResponse",
    "GroupMemberOut",
    "GroupMembershipRefCreate",
    "GroupMembersResponse",
    "GroupOwnerOut",
    "GroupOwnerRefCreate",
    "GroupOwnersResponse",
    "GroupOut",
    "GroupUpdate",
]
