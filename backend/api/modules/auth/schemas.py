"""Schemas exposed by the auth module."""

from __future__ import annotations

from typing import Literal

from email_validator import EmailNotValidError, validate_email
from pydantic import EmailStr, Field, SecretStr, field_validator, model_validator

from ...core.schema import BaseSchema
from .service import normalise_email


class TokenRequest(BaseSchema):
    """Credentials submitted to the token endpoint."""

    username: EmailStr
    password: SecretStr

    @field_validator("username", mode="plain")
    @classmethod
    def _normalise_username(cls, value: EmailStr | str) -> str:
        """Lowercase, trim, and lightly validate the submitted email."""

        candidate = normalise_email(str(value))
        try:
            validated = validate_email(candidate)
        except EmailNotValidError as exc:
            message = str(exc)
            if candidate.endswith((".local", ".localhost", ".test")) and (
                "special-use or reserved" in message
            ):
                return candidate
            raise ValueError(message) from exc
        return validated.normalized

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


class TokenResponse(BaseSchema):
    """Issued bearer token."""

    access_token: str
    token_type: str = "bearer"


class APIKeyIssueRequest(BaseSchema):
    """Payload for issuing a new API key."""

    user_id: str | None = Field(default=None, min_length=1)
    email: EmailStr | None = None
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)

    @model_validator(mode="after")
    def _validate_target(self) -> APIKeyIssueRequest:
        if self.user_id and self.email:
            raise ValueError("specify either user_id or email, not both")
        if not self.user_id and not self.email:
            raise ValueError("user_id or email is required")
        return self


class APIKeyIssueResponse(BaseSchema):
    """Representation of a freshly issued API key secret."""

    api_key: str
    principal_type: Literal["user", "service_account"]
    principal_id: str
    principal_label: str
    expires_at: str | None = None


class APIKeySummary(BaseSchema):
    """Metadata describing an issued API key."""

    api_key_id: str
    principal_type: Literal["user", "service_account"]
    principal_id: str
    principal_label: str
    token_prefix: str
    created_at: str
    expires_at: str | None = None
    last_seen_at: str | None = None
    last_seen_ip: str | None = None
    last_seen_user_agent: str | None = None


__all__ = [
    "TokenRequest",
    "APIKeyIssueRequest",
    "APIKeyIssueResponse",
    "APIKeySummary",
    "TokenResponse",
]
