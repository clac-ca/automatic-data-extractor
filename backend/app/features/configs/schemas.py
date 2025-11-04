"""Pydantic schemas for config API responses."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConfigActivationMetadata(BaseModel):
    """Metadata describing activation environment state."""

    model_config = ConfigDict(from_attributes=True)

    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    venv_path: str | None = None
    python_executable: str | None = None
    packages_uri: str | None = None
    install_log_uri: str | None = None
    hooks_uri: str | None = None
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    annotations: list[dict[str, Any]] = Field(default_factory=list)


class ConfigVersionRecord(BaseModel):
    """Serializable representation of a config version."""

    model_config = ConfigDict(from_attributes=True)

    config_version_id: str
    sequence: int
    label: str | None
    manifest: dict[str, Any]
    manifest_sha256: str
    package_sha256: str
    package_path: str
    config_script_api_version: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    activation: ConfigActivationMetadata | None = None


class ConfigSummary(BaseModel):
    """Lightweight config representation for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    config_id: str
    workspace_id: str
    slug: str
    title: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    active_version: ConfigVersionRecord | None = None


class ConfigRecord(ConfigSummary):
    """Detailed config representation including version history."""

    versions: list[ConfigVersionRecord] = Field(default_factory=list)


class ValidationDiagnostic(BaseModel):
    """Represents a validation diagnostic entry."""

    level: Literal["error", "warning"]
    code: str
    path: str
    message: str
    hint: str | None = None


class ConfigValidationResponse(BaseModel):
    """Response envelope for config validation."""

    diagnostics: list[ValidationDiagnostic] = Field(default_factory=list)


class ConfigPackageEntry(BaseModel):
    """Represents a single file or directory inside a config package."""

    path: str
    type: Literal["file", "directory"]
    size: int | None = None
    sha256: str | None = None


class ConfigFileContent(BaseModel):
    """Represents the contents of a package file."""

    path: str
    encoding: str = "utf-8"
    content: str
    sha256: str


class ConfigFileUpdate(BaseModel):
    """Request payload for updating draft files."""

    content: str
    encoding: str = "utf-8"
    expected_sha256: str | None = None


class ConfigDraftRecord(BaseModel):
    """Metadata describing a config editing draft."""

    draft_id: str
    config_id: str
    workspace_id: str
    base_config_version_id: str | None = None
    base_sequence: int | None = None
    manifest_sha256: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by_user_id: str | None = None
    updated_by_user_id: str | None = None
    last_published_version_id: str | None = None


class ConfigDraftCreateRequest(BaseModel):
    """Request payload for creating a new draft."""

    base_config_version_id: str


class ConfigDraftPublishRequest(BaseModel):
    """Request payload when publishing a draft to a new version."""

    label: str | None = Field(default=None, max_length=50)


__all__ = [
    "ConfigDraftCreateRequest",
    "ConfigDraftPublishRequest",
    "ConfigDraftRecord",
    "ConfigActivationMetadata",
    "ConfigFileContent",
    "ConfigFileUpdate",
    "ConfigPackageEntry",
    "ConfigRecord",
    "ConfigSummary",
    "ConfigValidationResponse",
    "ConfigVersionRecord",
    "ValidationDiagnostic",
]
