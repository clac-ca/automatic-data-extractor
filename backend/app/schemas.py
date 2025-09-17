"""Pydantic schemas for API responses and payloads."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _normalise_non_empty_string(value: Any, field_name: str) -> str:
    """Return a trimmed string, raising if the result is empty."""

    if value is None:
        msg = f"{field_name} must not be empty or whitespace"
        raise ValueError(msg)

    if not isinstance(value, str):
        value = str(value)

    result = value.strip()
    if not result:
        msg = f"{field_name} must not be empty or whitespace"
        raise ValueError(msg)
    return result


class HealthResponse(BaseModel):
    """Response model for the health endpoint."""

    status: str


class SnapshotBase(BaseModel):
    """Shared fields for snapshot payloads."""

    document_type: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    payload: dict[str, Any] = Field(default_factory=dict)
    is_published: bool = False

    @field_validator("title", mode="before")
    @classmethod
    def _trim_title(cls, value: Any) -> str:
        return _normalise_non_empty_string(value, "title")

    @field_validator("document_type", mode="before")
    @classmethod
    def _trim_document_type(cls, value: Any) -> str:
        return _normalise_non_empty_string(value, "document_type")


class SnapshotCreate(SnapshotBase):
    """Payload for creating snapshots."""


class SnapshotUpdate(BaseModel):
    """Payload for updating snapshots."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    payload: dict[str, Any] | None = None
    is_published: bool | None = None

    @field_validator("title", mode="before")
    @classmethod
    def _trim_title(cls, value: Any) -> Any:
        if value is None:
            return value
        return _normalise_non_empty_string(value, "title")

    @field_validator("payload", mode="before")
    @classmethod
    def _reject_null_payload(cls, value: Any) -> Any:
        if value is None:
            msg = "payload cannot be null"
            raise ValueError(msg)
        return value

    @field_validator("is_published", mode="before")
    @classmethod
    def _reject_null_is_published(cls, value: Any) -> Any:
        if value is None:
            msg = "is_published cannot be null"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _ensure_updates(self) -> "SnapshotUpdate":
        if not self.model_fields_set:
            msg = "At least one field must be provided"
            raise ValueError(msg)
        return self


class SnapshotResponse(BaseModel):
    """API response model for snapshot resources."""

    model_config = ConfigDict(from_attributes=True)

    snapshot_id: str
    document_type: str
    title: str
    payload: dict[str, Any]
    is_published: bool
    created_at: str
    updated_at: str


__all__ = [
    "HealthResponse",
    "SnapshotCreate",
    "SnapshotUpdate",
    "SnapshotResponse",
]
