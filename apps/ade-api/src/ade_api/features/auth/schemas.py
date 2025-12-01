"""Schemas exposed by the auth module."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from email_validator import EmailNotValidError, validate_email
from pydantic import EmailStr, Field, SecretStr, field_validator, model_validator

from ade_api.shared.core.ids import UUIDStr
from ade_api.shared.core.schema import BaseSchema
from ade_api.shared.pagination import Page

from ..system_settings.schemas import SafeModeStatus
from ..users.schemas import UserProfile
from ..workspaces.schemas import WorkspacePage
from .utils import normalise_email


def _validate_email(value: EmailStr | str, *, allow_reserved: bool = False) -> str:
    candidate = normalise_email(str(value))
    try:
        validated = validate_email(candidate)
    except EmailNotValidError as exc:
        message = str(exc)
        if allow_reserved and candidate.endswith((".local", ".localhost", ".test")):
            if "special-use or reserved" in message:
                return candidate
        raise ValueError(message) from exc
    return validated.normalized


class SetupStatus(BaseSchema):
    """Response payload describing the initial setup state."""

    requires_setup: bool
    completed_at: datetime | None = None
    force_sso: bool = False


class SetupRequest(BaseSchema):
    """Payload submitted when creating the first administrator."""

    email: str
    password: SecretStr
    display_name: str | None = Field(default=None, max_length=255)

    @field_validator("email", mode="plain")
    @classmethod
    def _normalise_email(cls, value: EmailStr | str) -> str:
        return _validate_email(value, allow_reserved=True)

    @field_validator("password", mode="before")
    @classmethod
    def _validate_password(cls, value: SecretStr | str) -> str:
        if isinstance(value, SecretStr):
            raw = value.get_secret_value()
        else:
            raw = str(value)
        candidate = raw.strip()
        if not candidate:
            msg = "Password must not be empty"
            raise ValueError(msg)
        return candidate

    @field_validator("display_name", mode="before")
    @classmethod
    def _clean_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class LoginRequest(BaseSchema):
    """Credentials submitted when performing a password login."""

    email: str
    password: SecretStr

    @field_validator("email", mode="plain")
    @classmethod
    def _normalise_email(cls, value: EmailStr | str) -> str:
        """Lowercase, trim, and lightly validate the submitted email."""

        return _validate_email(value, allow_reserved=True)

    @field_validator("password", mode="before")
    @classmethod
    def _validate_password(cls, value: SecretStr | str) -> str:
        """Ensure passwords are present after trimming whitespace."""

        if isinstance(value, SecretStr):
            raw = value.get_secret_value()
        else:
            raw = str(value)
        candidate = raw.strip()
        if not candidate:
            msg = "Password must not be empty"
            raise ValueError(msg)
        return candidate


class SessionEnvelope(BaseSchema):
    """Envelope returned when a session is established or refreshed."""

    user: UserProfile
    expires_at: datetime | None = None
    refresh_expires_at: datetime | None = None
    return_to: str | None = None


class BootstrapEnvelope(BaseSchema):
    """Consolidated bootstrap payload for SPA initialization."""

    user: UserProfile
    global_roles: list[str]
    global_permissions: list[str]
    workspaces: WorkspacePage
    safe_mode: SafeModeStatus


class AuthProvider(BaseSchema):
    """Representation of an interactive authentication provider."""

    id: str
    label: str
    start_url: str
    icon_url: str | None = None


class ProviderDiscoveryResponse(BaseSchema):
    """Response payload returned by `/auth/providers`."""

    providers: list[AuthProvider]
    force_sso: bool


class APIKeyIssueRequest(BaseSchema):
    """Payload for issuing a new API key."""

    user_id: UUIDStr | None = Field(default=None)
    email: str | None = None
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)
    label: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _validate_target(self) -> APIKeyIssueRequest:
        if self.user_id and self.email:
            raise ValueError("specify either user_id or email, not both")
        if not self.user_id and not self.email:
            raise ValueError("user_id or email is required")
        return self

    @field_validator("email", mode="before")
    @classmethod
    def _normalise_optional_email(
        cls, value: EmailStr | str | None
    ) -> EmailStr | str | None:
        if value is None:
            return None
        return _validate_email(value, allow_reserved=True)


class APIKeyIssueResponse(BaseSchema):
    """Representation of a freshly issued API key secret."""

    api_key: str
    principal_type: Literal["user", "service_account"]
    principal_id: UUIDStr
    principal_label: str
    expires_at: datetime | None = None
    label: str | None = None


class APIKeySummary(BaseSchema):
    """Metadata describing an issued API key."""

    id: UUIDStr
    principal_type: Literal["user", "service_account"]
    principal_id: UUIDStr
    principal_label: str
    token_prefix: str
    label: str | None = None
    created_at: datetime
    expires_at: datetime | None = None
    last_seen_at: datetime | None = None
    last_seen_ip: str | None = None
    last_seen_user_agent: str | None = None
    revoked_at: datetime | None = None


class APIKeyPage(Page[APIKeySummary]):
    """Paginated collection of API keys."""


__all__ = [
    "SetupStatus",
    "SetupRequest",
    "LoginRequest",
    "SessionEnvelope",
    "AuthProvider",
    "ProviderDiscoveryResponse",
    "APIKeyIssueRequest",
    "APIKeyIssueResponse",
    "APIKeyPage",
    "APIKeySummary",
]
