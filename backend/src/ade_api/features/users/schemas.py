"""Pydantic schemas for user payloads."""

from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field, field_validator, model_validator

from ade_api.common.ids import UUIDStr
from ade_api.common.cursor_listing import CursorPage
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
    )
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class UserOut(UserProfile):
    """Extended representation with activation metadata."""

    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseSchema):
    """Fields administrators can update for a user."""

    display_name: str | None = Field(
        default=None,
        description="Human-friendly display name for the user.",
        max_length=255,
    )
    is_active: bool | None = Field(
        default=None,
        description="Whether the account is active and allowed to authenticate.",
    )

    @field_validator("display_name")
    @classmethod
    def _normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def _ensure_changes_present(self) -> UserUpdate:
        if not self.model_fields_set:
            msg = "Provide at least one field to update."
            raise ValueError(msg)
        return self


class UserCreate(BaseSchema):
    """Payload for pre-provisioning a user account."""

    email: EmailStr = Field(
        ...,
        description="User email.",
    )
    display_name: str | None = Field(
        default=None,
        description="Optional display name for the user.",
        max_length=255,
    )

    @field_validator("display_name")
    @classmethod
    def _normalize_create_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class UserPage(CursorPage[UserOut]):
    """Cursor-based collection of users."""


__all__ = ["UserCreate", "UserOut", "UserPage", "UserProfile", "UserUpdate"]
