"""Request/response contracts for authentication endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field, SecretStr

from ade_api.common.schema import BaseSchema


class AuthLoginRequest(BaseSchema):
    """Credentials submitted when performing a password login."""

    email: EmailStr = Field(..., description="User email address.")
    password: SecretStr = Field(..., description="User password.")


class AuthRefreshRequest(BaseSchema):
    """Optional payload for refresh / logout.

    Browser clients typically rely on the refresh cookie; API clients can
    supply the token in the request body instead.
    """

    refresh_token: str | None = Field(
        default=None,
        description="Refresh token to rotate. Optional when using the refresh cookie.",
    )


class AuthSetupStatusResponse(BaseSchema):
    """Describes whether initial administrator setup is required."""

    requires_setup: bool = Field(
        ...,
        description="True when no users exist and an initial admin must be created.",
    )
    has_users: bool = Field(
        ...,
        description="True when at least one user already exists.",
    )


class AuthSetupRequest(BaseSchema):
    """Payload used to create the first administrator account."""

    email: EmailStr = Field(..., description="Administrator email.")
    password: SecretStr = Field(..., description="Administrator password.")
    display_name: str | None = Field(
        default=None,
        max_length=255,
        description="Optional display name for the administrator.",
    )


class SessionTokens(BaseSchema):
    """Session token pair issued to a client."""

    access_token: str = Field(..., description="JWT access token.")
    refresh_token: str | None = Field(
        default=None,
        description="Refresh token, if one is issued.",
    )
    token_type: str = Field(
        default="bearer",
        description="Token type, usually 'bearer'.",
    )
    expires_at: datetime = Field(
        ...,
        description="When the access token expires (UTC).",
    )
    refresh_expires_at: datetime | None = Field(
        default=None,
        description="When the refresh token expires (UTC), if applicable.",
    )
    expires_in: int = Field(
        ...,
        ge=0,
        description="Seconds until the access token expires.",
    )
    refresh_expires_in: int | None = Field(
        default=None,
        ge=0,
        description="Seconds until the refresh token expires, if applicable.",
    )


class SessionEnvelope(BaseSchema):
    """Wrapper around issued session tokens."""

    session: SessionTokens = Field(..., description="Issued session token pair.")
    csrf_token: str | None = Field(
        default=None,
        description="CSRF token mirrored in the ade_csrf cookie for double-submit.",
    )


class SessionSnapshot(BaseSchema):
    """Minimal view of the current session."""

    user_id: UUID = Field(..., description="Subject of the session.")
    principal_type: Literal["user", "service_account"] = Field(
        ...,
        description="Type of principal represented by the session.",
    )
    issued_at: datetime | None = Field(
        default=None,
        description="When the session was issued (UTC), if known.",
    )
    expires_at: datetime = Field(..., description="When the session expires (UTC).")


class SessionStatusResponse(BaseSchema):
    """Snapshot response for GET /auth/session."""

    session: SessionSnapshot = Field(
        ...,
        description="Details about the currently authenticated session.",
    )


class AuthProvider(BaseSchema):
    """Describes an interactive authentication provider option."""

    id: str = Field(..., description="Provider identifier, e.g. 'password' or 'sso'.")
    label: str = Field(..., description="Human-friendly label for the provider.")
    type: Literal["password", "oidc"] = Field(
        ...,
        description="Provider type: 'password' or 'oidc' (for SSO/OIDC providers).",
    )
    start_url: str | None = Field(
        default=None,
        description="URL to initiate login for this provider, if applicable.",
    )
    icon_url: str | None = Field(
        default=None,
        description="Optional icon URL for UI rendering.",
    )


class AuthProviderListResponse(BaseSchema):
    """Response payload returned by /auth/providers."""

    providers: list[AuthProvider]
    force_sso: bool = Field(
        default=False,
        description="When true, the frontend should offer only SSO.",
    )


__all__ = [
    "AuthLoginRequest",
    "AuthRefreshRequest",
    "AuthSetupStatusResponse",
    "AuthSetupRequest",
    "SessionEnvelope",
    "SessionSnapshot",
    "SessionStatusResponse",
    "SessionTokens",
    "AuthProvider",
    "AuthProviderListResponse",
]
