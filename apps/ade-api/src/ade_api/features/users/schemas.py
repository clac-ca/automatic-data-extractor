"""Pydantic schemas for user payloads."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from ade_api.common.ids import UUIDStr
from ade_api.common.pagination import Page
from ade_api.common.schema import BaseSchema


class UserProfile(BaseSchema):
    """Minimal view of the authenticated user."""

    id: UUIDStr
    email: str
    is_active: bool
    is_service_account: bool
    display_name: str | None = None
    preferred_workspace_id: UUIDStr | None = Field(
        default=None,
        validation_alias="preferred_workspace_id",
    )
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class UserOut(UserProfile):
    """Extended representation with activation metadata."""

    created_at: datetime
    updated_at: datetime


class UserPage(Page[UserOut]):
    """Paginated collection of users."""


__all__ = ["UserOut", "UserPage", "UserProfile"]
