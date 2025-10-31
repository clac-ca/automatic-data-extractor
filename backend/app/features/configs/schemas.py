"""Pydantic schemas for configuration engine v0.5."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ManifestInfo(BaseModel):
    """Metadata describing the manifest bundle."""

    model_config = ConfigDict(extra="forbid")

    schema: str = Field(alias="schema", serialization_alias="schema")
    title: str
    version: str

    @field_validator("schema")
    @classmethod
    def _validate_schema(cls, value: str) -> str:
        expected = "ade.manifest/v0.5"
        if value != expected:
            raise ValueError(f"Manifest schema must be '{expected}'")
        return value


class HookLimits(BaseModel):
    """Execution constraints attached to hook scripts."""

    model_config = ConfigDict(extra="forbid")

    timeout_ms: int | None = Field(default=None, ge=1, le=300_000)


class HookEntry(BaseModel):
    """Definition of an executable hook script."""

    model_config = ConfigDict(extra="forbid")

    script: str
    limits: HookLimits | None = None


class ManifestHooks(BaseModel):
    """Collection of manifest hook configurations."""

    model_config = ConfigDict(extra="forbid")

    on_activate: list[HookEntry] = Field(default_factory=list)
    on_job_start: list[HookEntry] = Field(default_factory=list)
    on_after_extract: list[HookEntry] = Field(default_factory=list)
    on_job_end: list[HookEntry] = Field(default_factory=list)


class ManifestEngineDefaults(BaseModel):
    """Runtime limits applied to sandbox execution."""

    model_config = ConfigDict(extra="forbid")

    timeout_ms: int = Field(1_000, ge=1)
    memory_mb: int = Field(512, ge=1)
    allow_net: bool = False


class ManifestEngine(BaseModel):
    """Engine configuration for the sandbox runtime."""

    model_config = ConfigDict(extra="forbid")

    defaults: ManifestEngineDefaults = Field(default_factory=ManifestEngineDefaults)


class ManifestColumnMeta(BaseModel):
    """Metadata describing a canonical output column."""

    model_config = ConfigDict(extra="forbid")

    label: str
    required: bool = False
    enabled: bool = True
    script: str


class ManifestColumns(BaseModel):
    """Collection of canonical columns available to the engine."""

    model_config = ConfigDict(extra="forbid")

    order: list[str]
    meta: dict[str, ManifestColumnMeta]

    @model_validator(mode="after")
    def _validate_order(self) -> "ManifestColumns":
        unique = set(self.order)
        if len(unique) != len(self.order):
            raise ValueError("columns.order must not contain duplicate keys")
        meta_keys = set(self.meta)
        missing = unique - meta_keys
        if missing:
            raise ValueError(
                "columns.order references undefined keys: " + ", ".join(sorted(missing))
            )
        extra = meta_keys - unique
        if extra:
            raise ValueError(
                "columns.meta defines keys that are not present in columns.order: "
                + ", ".join(sorted(extra))
            )
        return self


class ManifestSecretCipher(BaseModel):
    """Encrypted secret payload stored inside the manifest."""

    model_config = ConfigDict(extra="forbid")

    alg: str = Field(default="AES-256-GCM", frozen=True)
    kdf: str = Field(default="HKDF-SHA256", frozen=True)
    key_id: str = Field(default="default")
    nonce: str
    salt: str
    ciphertext: str
    created_at: datetime


class Manifest(BaseModel):
    """Complete manifest definition for a configuration bundle."""

    model_config = ConfigDict(extra="forbid")

    info: ManifestInfo
    env: dict[str, str] = Field(default_factory=dict)
    secrets: dict[str, ManifestSecretCipher] = Field(default_factory=dict)
    engine: ManifestEngine = Field(default_factory=ManifestEngine)
    hooks: ManifestHooks = Field(default_factory=ManifestHooks)
    columns: ManifestColumns

    @classmethod
    def from_json(cls, payload: Dict[str, Any]) -> "Manifest":
        """Validate a raw JSON payload into a :class:`Manifest` instance."""

        return cls.model_validate(payload)


class ValidationIssueLevel(StrEnum):
    """Severity of a validation diagnostic."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ValidationIssue(BaseModel):
    """Diagnostic result produced by config validation routines."""

    model_config = ConfigDict(extra="forbid")

    path: str
    code: str
    message: str
    level: ValidationIssueLevel = ValidationIssueLevel.ERROR


class FileItem(BaseModel):
    """Metadata describing an individual file inside a config bundle."""

    model_config = ConfigDict(extra="forbid")

    path: str
    byte_size: int
    sha256: str


class ConfigRecord(BaseModel):
    """Serialised representation of a config database row."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    config_id: str
    workspace_id: str
    title: str
    note: str | None = None
    status: str
    version: str
    files_hash: str | None = None
    package_sha256: str | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None = None
    activated_by: str | None = None
    archived_at: datetime | None = None
    archived_by: str | None = None


class ConfigCreateRequest(BaseModel):
    """Payload for creating a new configuration bundle."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None)
    from_config_id: str | None = Field(default=None, min_length=1)

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("title must not be empty if provided")
        return trimmed

    @field_validator("note")
    @classmethod
    def _normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class ConfigUpdateRequest(BaseModel):
    """Payload for updating configuration metadata."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None)
    version: str | None = Field(default=None, max_length=32)
    status: str | None = Field(default=None, max_length=16)

    @field_validator("title", "note", "version", "status")
    @classmethod
    def _strip_values(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class ConfigCloneRequest(BaseModel):
    """Payload for cloning an existing configuration bundle."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(max_length=255)
    note: str | None = Field(default=None)

    @field_validator("title")
    @classmethod
    def _validate_clone_title(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("title must not be empty")
        return trimmed

    @field_validator("note")
    @classmethod
    def _normalize_clone_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class RenameColumnRequest(BaseModel):
    """Payload for renaming a canonical column key."""

    model_config = ConfigDict(extra="forbid")

    from_key: str = Field(min_length=1)
    to_key: str = Field(min_length=1)

    @field_validator("from_key", "to_key")
    @classmethod
    def _normalize_column_keys(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("column keys must not be empty")
        return trimmed


class ConfigSecretCreateRequest(BaseModel):
    """Payload for creating or updating a manifest secret."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    value: str = Field(min_length=1)
    key_id: str | None = Field(default="default", min_length=1)

    @field_validator("name", "value", "key_id")
    @classmethod
    def _normalize_secret_fields(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("value is required")
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("fields must not be empty")
        return trimmed


class ConfigSecretMetadata(BaseModel):
    """Metadata describing an encrypted secret stored within the manifest."""

    model_config = ConfigDict(extra="forbid")

    name: str
    key_id: str
    created_at: datetime


class ConfigValidationResponse(BaseModel):
    """Response payload for validation results."""

    model_config = ConfigDict(extra="forbid")

    manifest: Manifest | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)


__all__ = [
    "ConfigRecord",
    "ConfigCloneRequest",
    "ConfigCreateRequest",
    "ConfigSecretCreateRequest",
    "ConfigSecretMetadata",
    "ConfigUpdateRequest",
    "ConfigValidationResponse",
    "FileItem",
    "HookEntry",
    "HookLimits",
    "Manifest",
    "ManifestColumnMeta",
    "ManifestColumns",
    "ManifestEngine",
    "ManifestEngineDefaults",
    "ManifestHooks",
    "ManifestInfo",
    "ManifestSecretCipher",
    "RenameColumnRequest",
    "ValidationIssue",
    "ValidationIssueLevel",
]
