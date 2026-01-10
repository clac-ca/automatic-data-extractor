"""Pydantic schemas for API key management."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from ade_api.common.ids import UUIDStr
from ade_api.common.listing import ListPage
from ade_api.common.schema import BaseSchema


class ApiKeyCreateRequest(BaseSchema):
    """Request payload to create a new API key."""

    name: str | None = Field(
        default=None,
        max_length=100,
        description="Optional human-friendly name (e.g. 'CLI on laptop').",
    )
    expires_in_days: int | None = Field(
        default=None,
        ge=1,
        le=3650,
        description="Optional TTL in days; omit for a non-expiring key.",
    )

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ApiKeyCreateResponse(BaseSchema):
    """Response returned when a new API key is created."""

    id: UUIDStr
    user_id: UUIDStr = Field(description="User that this key authenticates as.")

    secret: str = Field(
        description="Full API key secret, returned once at creation time.",
    )
    prefix: str = Field(
        description="Prefix used for identification in logs/UI.",
    )
    name: str | None = None

    created_at: datetime
    expires_at: datetime | None = None


class ApiKeySummary(BaseSchema):
    """Metadata describing an API key without exposing the secret."""

    id: UUIDStr
    user_id: UUIDStr
    prefix: str
    name: str | None = None

    created_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None


class ApiKeyPage(ListPage[ApiKeySummary]):
    """Paginated collection of API keys."""


__all__ = [
    "ApiKeyCreateRequest",
    "ApiKeyCreateResponse",
    "ApiKeySummary",
    "ApiKeyPage",
]
