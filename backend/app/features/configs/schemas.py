"""Pydantic schemas for config API responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConfigPackageUpload(BaseModel):
    """Represents a base64 encoded config package zip archive."""

    filename: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)


class ConfigCreateRequest(BaseModel):
    """Payload for creating a config and its initial version."""

    slug: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    manifest: dict[str, Any]
    package: ConfigPackageUpload


class ConfigVersionCreateRequest(BaseModel):
    """Payload for creating a new config version."""

    label: str | None = Field(default=None, max_length=50)
    manifest: dict[str, Any]
    package: ConfigPackageUpload


class ConfigVersionRecord(BaseModel):
    """Serializable representation of a config version."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    config_version_id: str = Field(alias="id", serialization_alias="config_version_id")
    sequence: int
    label: str | None
    manifest: dict[str, Any]
    manifest_sha256: str
    package_sha256: str
    package_uri: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class ConfigSummary(BaseModel):
    """Lightweight config representation for list endpoints."""

    config_id: str = Field(alias="id", serialization_alias="config_id")
    workspace_id: str
    slug: str
    title: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    active_version: ConfigVersionRecord | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ConfigRecord(ConfigSummary):
    """Detailed config representation including version history."""

    versions: list[ConfigVersionRecord] = Field(default_factory=list)


__all__ = [
    "ConfigCreateRequest",
    "ConfigPackageUpload",
    "ConfigRecord",
    "ConfigSummary",
    "ConfigVersionCreateRequest",
    "ConfigVersionRecord",
]
