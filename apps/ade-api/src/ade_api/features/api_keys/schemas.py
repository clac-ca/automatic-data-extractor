"""Pydantic schemas for API key management."""

from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field, field_validator, model_validator

from ade_api.common.ids import UUIDStr
from ade_api.common.pagination import Page
from ade_api.common.schema import BaseSchema
from ade_api.core.rbac.types import ScopeType


class ApiKeyCreateRequest(BaseSchema):
    """Request payload to create a new API key."""

    label: str | None = Field(
        default=None,
        max_length=100,
        description="Optional human-friendly label (e.g. 'CLI on laptop').",
    )
    expires_in_days: int | None = Field(
        default=None,
        ge=1,
        le=3650,
        description="Optional TTL in days; omit for a non-expiring key.",
    )
    scope_type: ScopeType = Field(
        default=ScopeType.GLOBAL,
        description="Scope of the key: global or workspace.",
    )
    scope_id: UUIDStr | None = Field(
        default=None,
        description=(
            "Workspace identifier when scope_type=workspace. "
            "Must be null for global keys."
        ),
    )

    @field_validator("label")
    @classmethod
    def _clean_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def _validate_scope(self) -> ApiKeyCreateRequest:
        if self.scope_type == ScopeType.GLOBAL and self.scope_id is not None:
            raise ValueError("scope_id must be null when scope_type=global")
        if self.scope_type == ScopeType.WORKSPACE and self.scope_id is None:
            raise ValueError("scope_id is required when scope_type=workspace")
        return self


class ApiKeyIssueRequest(ApiKeyCreateRequest):
    """Admin payload to issue a key by user id or email."""

    user_id: UUIDStr | None = Field(
        default=None,
        description="Target user id; provide exactly one of user_id or email.",
    )
    email: EmailStr | None = Field(
        default=None,
        description="Target user email; provide exactly one of user_id or email.",
    )

    @model_validator(mode="after")
    def _validate_principal(self) -> ApiKeyIssueRequest:
        provided = [self.user_id, self.email]
        if sum(value is not None for value in provided) != 1:
            raise ValueError("Provide exactly one of user_id or email")
        return self


class ApiKeyCreateResponse(BaseSchema):
    """Response returned when a new API key is created."""

    id: UUIDStr
    owner_user_id: UUIDStr = Field(description="User that this key authenticates as.")
    created_by_user_id: UUIDStr | None = Field(
        default=None,
        description="User who created the key (may equal owner for self-service).",
    )

    secret: str = Field(
        description="Full API key secret, returned once at creation time.",
    )
    token_prefix: str = Field(
        description="Prefix used for identification in logs/UI.",
    )

    label: str | None = None
    scope_type: ScopeType
    scope_id: UUIDStr | None = None

    created_at: datetime
    expires_at: datetime | None = None


class ApiKeySummary(BaseSchema):
    """Metadata describing an API key without exposing the secret."""

    id: UUIDStr
    owner_user_id: UUIDStr
    created_by_user_id: UUIDStr | None = None

    token_prefix: str
    label: str | None = None

    scope_type: ScopeType
    scope_id: UUIDStr | None = None

    created_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None


class ApiKeyPage(Page[ApiKeySummary]):
    """Paginated collection of API keys."""


__all__ = [
    "ApiKeyCreateRequest",
    "ApiKeyIssueRequest",
    "ApiKeyCreateResponse",
    "ApiKeySummary",
    "ApiKeyPage",
]
