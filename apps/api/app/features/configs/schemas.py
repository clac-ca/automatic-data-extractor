"""Pydantic schemas for configuration APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, field_validator

from apps.api.app.shared.core.ids import ULIDStr
from apps.api.app.shared.core.schema import BaseSchema
from .models import ConfigurationStatus


class ConfigSourceTemplate(BaseSchema):
    """Reference to a bundled template."""

    type: Literal["template"]
    template_id: str = Field(min_length=1, max_length=100)

    @field_validator("template_id", mode="before")
    @classmethod
    def _clean_template_id(cls, value: str) -> str:
        return value.strip()


class ConfigSourceClone(BaseSchema):
    """Reference to an existing workspace config."""

    type: Literal["clone"]
    config_id: ULIDStr

    @field_validator("config_id", mode="before")
    @classmethod
    def _clean_config_id(cls, value: str) -> str:
        return value.strip()


ConfigSource = Annotated[
    ConfigSourceTemplate | ConfigSourceClone,
    Field(discriminator="type"),
]


class ConfigurationCreate(BaseSchema):
    """Payload for creating a configuration."""

    display_name: str = Field(min_length=1, max_length=255)
    source: ConfigSource

    @field_validator("display_name", mode="before")
    @classmethod
    def _clean_display_name(cls, value: str) -> str:
        return value.strip()


class ConfigurationRecord(BaseSchema):
    """Serialized configuration metadata."""

    workspace_id: ULIDStr
    config_id: ULIDStr
    display_name: str
    status: ConfigurationStatus
    config_version: int
    content_digest: str | None = None
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None = None


class ConfigValidationIssue(BaseSchema):
    """Description of a validation issue found on disk."""

    path: str
    message: str


class ConfigurationValidateResponse(BaseSchema):
    """Result of running validation."""

    workspace_id: ULIDStr
    config_id: ULIDStr
    status: ConfigurationStatus
    content_digest: str | None = None
    issues: list[ConfigValidationIssue]


class ConfigurationActivateRequest(BaseSchema):
    """Activation control flags."""

    ensure_build: bool = False


class FileCapabilities(BaseSchema):
    editable: bool
    can_create: bool
    can_delete: bool
    can_rename: bool


class FileSizeLimits(BaseSchema):
    code_max_bytes: int
    asset_max_bytes: int


class FileListingSummary(BaseSchema):
    files: int
    directories: int


class FileEntry(BaseSchema):
    path: str
    name: str
    parent: str
    kind: Literal["file", "dir"]
    depth: int
    size: int | None = None
    mtime: datetime | None = None
    etag: str | None = None
    content_type: str | None = None
    has_children: bool | None = None


class FileListing(BaseSchema):
    workspace_id: ULIDStr
    config_id: ULIDStr
    status: ConfigurationStatus
    capabilities: FileCapabilities
    root: str
    prefix: str
    depth: Literal["0", "1", "infinity"]
    generated_at: datetime
    fileset_hash: str
    summary: FileListingSummary
    limits: FileSizeLimits
    count: int
    next_token: str | None = None
    entries: list[FileEntry]


class FileReadJson(BaseSchema):
    path: str
    encoding: Literal["utf-8", "base64"]
    content: str
    size: int
    mtime: datetime
    etag: str
    content_type: str


class FileWriteResponse(BaseSchema):
    path: str
    created: bool
    size: int
    mtime: datetime
    etag: str


class FileRenameRequest(BaseSchema):
    op: Literal["move"] = "move"
    to: str
    overwrite: bool = False
    dest_if_match: str | None = None


class FileRenameResponse(BaseSchema):
    src: str = Field(alias="from")
    dest: str = Field(alias="to")
    size: int
    mtime: datetime
    etag: str


__all__ = [
    "ConfigSource",
    "ConfigSourceClone",
    "ConfigSourceTemplate",
    "ConfigValidationIssue",
    "ConfigurationCreate",
    "ConfigurationActivateRequest",
    "ConfigurationRecord",
    "ConfigurationValidateResponse",
    "FileCapabilities",
    "FileSizeLimits",
    "FileListingSummary",
    "FileEntry",
    "FileListing",
    "FileReadJson",
    "FileWriteResponse",
    "FileRenameRequest",
    "FileRenameResponse",
]
