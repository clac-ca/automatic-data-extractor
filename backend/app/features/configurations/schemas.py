"""Pydantic schemas for configuration responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from backend.app.platform.schema import BaseSchema


class ConfigurationRecord(BaseSchema):
    """Serialised representation of a configuration version."""

    configuration_id: str = Field(alias="id", serialization_alias="configuration_id")
    workspace_id: str
    title: str
    version: int
    is_active: bool
    activated_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ConfigurationCreate(BaseSchema):
    """Payload for creating a configuration version."""

    title: str = Field(..., max_length=255)
    payload: dict[str, Any] = Field(default_factory=dict)
    clone_from_configuration_id: str | None = Field(
        default=None,
        description=(
            "Optional configuration identifier to clone. The source must belong "
            "to the same workspace."
        ),
    )
    clone_from_active: bool = Field(
        default=False,
        description=(
            "Clone the active configuration for the workspace when no explicit "
            "identifier is provided."
        ),
    )

    @model_validator(mode="after")
    def _validate_clone_configuration(self) -> "ConfigurationCreate":
        """Ensure clone arguments are not contradictory."""

        if self.clone_from_configuration_id and self.clone_from_active:
            raise ValueError(
                "Provide either clone_from_configuration_id or set "
                "clone_from_active, not both."
            )
        return self


class ConfigurationUpdate(BaseSchema):
    """Payload for replacing mutable configuration fields."""

    title: str = Field(..., max_length=255)
    payload: dict[str, Any] = Field(default_factory=dict)


class ConfigurationOptions(BaseSchema):
    """Tunable options that describe how a configuration behaves at runtime."""

    unknown_policy: str | None = None
    output: dict[str, Any] = Field(default_factory=dict)
    sheet_detection: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class ConfigurationScriptVersionIn(BaseSchema):
    """Input payload for uploading a new configuration script version."""

    canonical_key: str = Field(..., min_length=1, max_length=255)
    language: str = Field(default="python", max_length=50)
    code: str = Field(..., min_length=1)


class ConfigurationScriptVersionOut(BaseSchema):
    """Serialised representation of a configuration script version."""

    script_version_id: str = Field(alias="id", serialization_alias="script_version_id")
    configuration_id: str
    canonical_key: str
    version: int
    language: str
    code: str | None = None
    code_sha256: str
    doc_name: str | None = None
    doc_description: str | None = None
    doc_declared_version: int | None = None
    validated_at: datetime | None = None
    validation_errors: dict[str, Any] | None = None
    created_by_user_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ConfigurationColumnIn(BaseSchema):
    """Input payload describing a configuration column."""

    canonical_key: str = Field(..., min_length=1, max_length=255)
    ordinal: int = Field(..., ge=0)
    display_label: str = Field(..., max_length=255)
    header_color: str | None = Field(default=None, max_length=20)
    width: int | None = Field(default=None, ge=0)
    required: bool = False
    enabled: bool = True
    script_version_id: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class ConfigurationColumnOut(ConfigurationColumnIn):
    """Serialised representation of a configuration column."""

    configuration_id: str
    script_version: ConfigurationScriptVersionOut | None = None
    created_at: datetime
    updated_at: datetime


class ConfigurationColumnBindingUpdate(BaseSchema):
    """Payload for updating column binding metadata."""

    script_version_id: str | None = Field(default=None)
    params: dict[str, Any] | None = None
    enabled: bool | None = None
    required: bool | None = None


ConfigurationRecord.model_rebuild()
ConfigurationCreate.model_rebuild()
ConfigurationUpdate.model_rebuild()
ConfigurationOptions.model_rebuild()
ConfigurationScriptVersionIn.model_rebuild()
ConfigurationScriptVersionOut.model_rebuild()
ConfigurationColumnIn.model_rebuild()
ConfigurationColumnOut.model_rebuild()
ConfigurationColumnBindingUpdate.model_rebuild()


__all__ = [
    "ConfigurationCreate",
    "ConfigurationRecord",
    "ConfigurationUpdate",
    "ConfigurationColumnIn",
    "ConfigurationColumnOut",
    "ConfigurationColumnBindingUpdate",
    "ConfigurationOptions",
    "ConfigurationScriptVersionIn",
    "ConfigurationScriptVersionOut",
]
