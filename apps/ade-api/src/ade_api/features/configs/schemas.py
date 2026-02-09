"""Pydantic schemas for configuration APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ade_api.common.ids import UUIDStr
from ade_api.common.cursor_listing import CursorPage
from ade_api.common.schema import BaseSchema
from ade_api.models import ConfigurationStatus


class ConfigSourceTemplate(BaseSchema):
    """Request to scaffold a config from the engine's built-in template."""

    type: Literal["template"]


class ConfigSourceClone(BaseSchema):
    """Reference to an existing workspace config."""

    type: Literal["clone"]
    configuration_id: UUIDStr

    @field_validator("configuration_id", mode="before")
    @classmethod
    def _clean_configuration_id(cls, value: object) -> object:
        if value is None:
            return value
        if isinstance(value, UUID):
            return value
        return str(value).strip()


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

    id: UUIDStr
    workspace_id: UUIDStr
    display_name: str
    status: ConfigurationStatus
    content_digest: str | None = None
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None = None


class ConfigValidationIssue(BaseSchema):
    """Description of a validation issue found on disk."""

    path: str
    message: str


class ConfigurationPage(CursorPage[ConfigurationRecord]):
    """Cursor-based configuration listing."""


class ConfigurationValidateResponse(BaseSchema):
    """Result of running validation."""

    id: UUIDStr
    workspace_id: UUIDStr
    status: ConfigurationStatus
    content_digest: str | None = None
    issues: list[ConfigValidationIssue]


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
    mtime: datetime
    etag: str
    content_type: str
    has_children: bool

    @model_validator(mode="after")
    def _validate_directory_constraints(self) -> FileEntry:
        if self.kind == "dir":
            if self.size not in (None, 0):
                raise ValueError("Directory entries must omit size or set it to null")
            if self.content_type != "inode/directory":
                raise ValueError('Directory entries must use content_type="inode/directory"')
        else:
            if self.size is None:
                raise ValueError("File entries must include a size value")
        return self


class FileListing(BaseSchema):
    workspace_id: UUIDStr
    configuration_id: UUIDStr
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
    next_cursor: str | None = Field(default=None, alias="nextCursor")
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
    from_path: str = Field(alias="from")
    to_path: str = Field(alias="to")
    size: int
    mtime: datetime
    etag: str


class DirectoryWriteResponse(BaseSchema):
    path: str
    created: bool


__all__ = [
    "ConfigSource",
    "ConfigSourceClone",
    "ConfigSourceTemplate",
    "ConfigValidationIssue",
    "ConfigurationPage",
    "ConfigurationCreate",
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
    "DirectoryWriteResponse",
]
