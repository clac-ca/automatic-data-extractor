"""Request/response contracts for authentication endpoints."""

from __future__ import annotations

from typing import Literal

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


class AuthTokensResponse(BaseSchema):
    """Response payload containing a freshly issued session token pair."""

    access_token: str = Field(..., description="JWT access token.")
    refresh_token: str | None = Field(
        default=None,
        description="Refresh token, if one is issued.",
    )
    token_type: str = Field(
        default="bearer",
        description="Token type, usually 'bearer'.",
    )
    expires_in: int = Field(
        ...,
        description="Seconds until the access token expires.",
    )
    refresh_expires_in: int | None = Field(
        default=None,
        description="Seconds until the refresh token expires, if applicable.",
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
    "AuthTokensResponse",
    "AuthSetupStatusResponse",
    "AuthSetupRequest",
    "AuthProvider",
    "AuthProviderListResponse",
]
