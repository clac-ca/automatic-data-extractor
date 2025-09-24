"""Pydantic schemas for configuration responses."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ...core.schema import BaseSchema


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


__all__ = ["ConfigurationRecord"]
