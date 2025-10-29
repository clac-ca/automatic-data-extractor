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
    """Configuration package summary with active version pointer."""

    config_id: str
    workspace_id: str
    slug: str
    title: str
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    active_version: "ConfigVersionRecord | None" = None
    versions_count: int


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
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    activated_at: datetime | None = None
    manifest: dict[str, Any] = Field(default_factory=dict)


class ConfigVersionCreateRequest(BaseSchema):
    """Payload used to create a new configuration version."""

    semver: str = Field(min_length=1, max_length=64)
    message: str | None = Field(default=None, max_length=1000)
    source_version_id: str | None = None
    seed_defaults: bool = False


class ConfigVersionValidateResponse(BaseSchema):
    """Result of a version validation pass."""

    files_hash: str
    ready: bool
    problems: list[str]


class ConfigVersionTestRequest(BaseSchema):
    """Request body when executing a version test."""

    document_id: str
    notes: str | None = Field(default=None, max_length=1000)


class ConfigVersionTestResponse(BaseSchema):
    """Result envelope for a version test execution."""

    files_hash: str
    document_id: str
    findings: list[str]
    summary: str | None = None


class ConfigScriptSummary(BaseSchema):
    """Metadata about a configuration version script."""

    config_script_id: str
    config_version_id: str
    path: str
    language: str
    sha256: str
    created_at: datetime
    updated_at: datetime


class ConfigScriptContent(ConfigScriptSummary):
    """Full script payload including source code."""

    code: str


class ConfigScriptCreateRequest(BaseSchema):
    """Request payload to create a new version script."""

    path: str = Field(min_length=1, max_length=512)
    template: str | None = None
    language: str | None = Field(default=None, max_length=50)


class ConfigScriptUpdateRequest(BaseSchema):
    """Request payload to update an existing version script."""

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
    "ConfigVersionCreateRequest",
    "ConfigVersionTestRequest",
    "ConfigVersionTestResponse",
    "ConfigVersionValidateResponse",
    "ConfigScriptContent",
    "ConfigScriptCreateRequest",
    "ConfigScriptSummary",
    "ConfigScriptUpdateRequest",
    "ConfigVersionRecord",
    "ConfigRecord",
    "ManifestPatchRequest",
    "ManifestResponse",
]
