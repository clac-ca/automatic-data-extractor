"""Schemas exposed by the auth module."""

from __future__ import annotations

from pydantic import EmailStr, Field, model_validator

from ...core.schema import BaseSchema
from .service import APIKeyPrincipalType


class TokenResponse(BaseSchema):
    """Issued bearer token."""

    access_token: str
    token_type: str = "bearer"


class APIKeyIssueRequest(BaseSchema):
    """Payload for issuing a new API key."""

    principal_type: APIKeyPrincipalType
    email: EmailStr | None = None
    service_account_id: str | None = Field(default=None, min_length=1)
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)

    @model_validator(mode="after")
    def _validate_principal(self) -> "APIKeyIssueRequest":
        principal = APIKeyPrincipalType(self.principal_type)
        self.principal_type = principal
        if principal is APIKeyPrincipalType.USER:
            if not self.email:
                raise ValueError("email is required when principal_type is 'user'")
            self.service_account_id = None
        else:
            if not self.service_account_id:
                raise ValueError(
                    "service_account_id is required when principal_type is 'service_account'",
                )
            self.email = None
        return self


class APIKeyIssueResponse(BaseSchema):
    """Representation of a freshly issued API key secret."""

    api_key: str
    principal_type: APIKeyPrincipalType
    principal_id: str
    principal_label: str
    expires_at: str | None = None


class APIKeySummary(BaseSchema):
    """Metadata describing an issued API key."""

    api_key_id: str
    principal_type: APIKeyPrincipalType
    principal_id: str
    principal_label: str
    token_prefix: str
    created_at: str
    expires_at: str | None = None
    last_seen_at: str | None = None
    last_seen_ip: str | None = None
    last_seen_user_agent: str | None = None


__all__ = [
    "APIKeyIssueRequest",
    "APIKeyIssueResponse",
    "APIKeySummary",
    "TokenResponse",
]
