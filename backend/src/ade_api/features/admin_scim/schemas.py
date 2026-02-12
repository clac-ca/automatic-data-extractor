from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from ade_api.common.schema import BaseSchema


class ScimTokenOut(BaseSchema):
    id: UUID
    name: str
    prefix: str
    created_by_user_id: UUID = Field(alias="createdByUserId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    last_used_at: datetime | None = Field(default=None, alias="lastUsedAt")
    revoked_at: datetime | None = Field(default=None, alias="revokedAt")


class ScimTokenCreateRequest(BaseSchema):
    name: str = Field(min_length=1, max_length=120)


class ScimTokenCreateResponse(BaseSchema):
    token: str
    item: ScimTokenOut


class ScimTokenListResponse(BaseSchema):
    items: list[ScimTokenOut]


__all__ = [
    "ScimTokenCreateRequest",
    "ScimTokenCreateResponse",
    "ScimTokenListResponse",
    "ScimTokenOut",
]
