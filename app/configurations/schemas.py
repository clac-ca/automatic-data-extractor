"""Pydantic schemas for configuration responses."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.core.schema import BaseSchema


class ConfigurationRecord(BaseSchema):
    """Serialised representation of a configuration version."""

    configuration_id: str = Field(alias="id", serialization_alias="configuration_id")
    document_type: str
    title: str
    version: int
    is_active: bool
    activated_at: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class ConfigurationCreate(BaseSchema):
    """Payload for creating a configuration version."""

    document_type: str = Field(..., max_length=100)
    title: str = Field(..., max_length=255)
    payload: dict[str, Any] = Field(default_factory=dict)


class ConfigurationUpdate(BaseSchema):
    """Payload for replacing mutable configuration fields."""

    title: str = Field(..., max_length=255)
    payload: dict[str, Any] = Field(default_factory=dict)


ConfigurationRecord.model_rebuild()
ConfigurationCreate.model_rebuild()
ConfigurationUpdate.model_rebuild()


__all__ = [
    "ConfigurationCreate",
    "ConfigurationRecord",
    "ConfigurationUpdate",
]
