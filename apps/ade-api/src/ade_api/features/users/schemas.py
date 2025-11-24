"""Pydantic schemas for user payloads."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from ade_api.shared.core.ids import ULIDStr
from ade_api.shared.core.schema import BaseSchema
from ade_api.shared.pagination import Page


class UserProfile(BaseSchema):
    """Minimal view of the authenticated user."""

    id: ULIDStr
    email: str
    is_active: bool
    is_service_account: bool
    display_name: str | None = None
    preferred_workspace_id: ULIDStr | None = Field(
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
