"""Pydantic schemas for user payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field, SecretStr, field_validator, model_validator

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


class UserPasswordProfile(BaseSchema):
    """Password provisioning mode for user creation."""

    mode: Literal["auto_generate", "explicit"]
    password: SecretStr | None = None
    force_change_on_next_sign_in: bool = Field(
        default=False,
        alias="forceChangeOnNextSignIn",
    )

    @model_validator(mode="after")
    def _validate_profile(self) -> UserPasswordProfile:
        if self.mode == "explicit":
            if self.password is None or not self.password.get_secret_value().strip():
                msg = "password is required when mode is explicit."
                raise ValueError(msg)
        elif self.password is not None:
            msg = "password must not be provided when mode is auto_generate."
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
        alias="displayName",
    )
    password_profile: UserPasswordProfile = Field(
        description="Password provisioning mode for the user account.",
        alias="passwordProfile",
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


class UserPasswordProvisioning(BaseSchema):
    """Password provisioning result for created users."""

    mode: Literal["auto_generate", "explicit"]
    initial_password: str | None = Field(default=None, alias="initialPassword")
    force_change_on_next_sign_in: bool = Field(alias="forceChangeOnNextSignIn")


class UserCreateResponse(BaseSchema):
    """Create-user response including one-time password provisioning payload."""

    user: UserOut
    password_provisioning: UserPasswordProvisioning = Field(alias="passwordProvisioning")


__all__ = [
    "UserCreate",
    "UserCreateResponse",
    "UserOut",
    "UserPage",
    "UserPasswordProfile",
    "UserPasswordProvisioning",
    "UserProfile",
    "UserUpdate",
]
