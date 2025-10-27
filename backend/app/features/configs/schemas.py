"""Pydantic schemas for configuration versioning APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from backend.app.shared.core.schema import BaseSchema


class ConfigCreateRequest(BaseSchema):
    """Payload accepted when creating a new configuration package."""

    slug: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=255)


class ConfigRecord(BaseSchema):
    """Configuration package with draft/published summaries."""

    config_id: str
    workspace_id: str
    slug: str
    title: str
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None
    draft: "ConfigVersionRecord | None" = None
    published: "ConfigVersionRecord | None" = None


class ConfigVersionRecord(BaseSchema):
    """Snapshot metadata for a configuration version."""

    config_version_id: str
    config_id: str
    semver: str
    status: str
    message: str | None = None
    files_hash: str
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None
    published_at: datetime | None = None
    manifest: dict[str, Any] = Field(default_factory=dict)


class ConfigFileSummary(BaseSchema):
    """Metadata about a draft file."""

    config_file_id: str
    config_version_id: str
    path: str
    language: str
    sha256: str
    created_at: datetime
    updated_at: datetime


class ConfigFileContent(ConfigFileSummary):
    """Full draft file payload including source code."""

    code: str


class ConfigPublishRequest(BaseSchema):
    """Request payload when publishing the current draft."""

    semver: str = Field(min_length=1, max_length=64)
    message: str | None = Field(default=None, max_length=1000)


class ConfigRevertRequest(BaseSchema):
    """Request payload to revert to the most recent previous version."""

    message: str | None = Field(default=None, max_length=1000)


class ConfigFileCreateRequest(BaseSchema):
    """Request payload to create a new draft file."""

    path: str = Field(min_length=1, max_length=512)
    template: str | None = None
    language: str | None = Field(default=None, max_length=50)


class ConfigFileUpdateRequest(BaseSchema):
    """Request payload to update an existing draft file."""

    code: str


class ManifestPatchRequest(BaseSchema):
    """Partial manifest update payload."""

    manifest: dict[str, Any]


class ManifestResponse(BaseSchema):
    """Wrapper for manifest retrieval."""

    manifest: dict[str, Any]


ConfigRecord.model_rebuild()


__all__ = [
    "ConfigCreateRequest",
    "ConfigFileContent",
    "ConfigFileCreateRequest",
    "ConfigFileSummary",
    "ConfigFileUpdateRequest",
    "ConfigPublishRequest",
    "ConfigRecord",
    "ConfigRevertRequest",
    "ConfigVersionRecord",
    "ManifestPatchRequest",
    "ManifestResponse",
]

