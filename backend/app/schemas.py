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

    @model_validator(mode="before")
    @classmethod
    def _normalise_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        if not data:
            msg = "At least one field must be provided"
            raise ValueError(msg)

        if "title" in data:
            data["title"] = _normalise_non_empty_string(data["title"], "title")

        if "payload" in data and data["payload"] is None:
            msg = "payload cannot be null"
            raise ValueError(msg)

        if "is_published" in data and data["is_published"] is None:
            msg = "is_published cannot be null"
            raise ValueError(msg)

        return data


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
