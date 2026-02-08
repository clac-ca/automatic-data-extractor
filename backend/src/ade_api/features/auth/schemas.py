"""Request/response contracts for authentication endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import EmailStr, Field, SecretStr

from ade_api.common.schema import BaseSchema


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

    id: str = Field(..., description="Provider identifier, e.g. 'password' or 'oidc'.")
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
    password_reset_enabled: bool = Field(
        default=True,
        description="When true, public password reset flows should be offered.",
    )


class AuthSetupStatusResponse(BaseSchema):
    """Setup status response returned by /auth/setup."""

    setup_required: bool
    registration_mode: Literal["setup-only", "closed", "open"]
    oidc_configured: bool
    providers: list[AuthProvider]


__all__ = [
    "AuthProvider",
    "AuthProviderListResponse",
    "AuthSetupRequest",
    "AuthSetupStatusResponse",
]
