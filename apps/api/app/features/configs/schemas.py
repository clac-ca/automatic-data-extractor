"""Pydantic schemas for configuration APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConfigSourceTemplate(BaseModel):
    """Reference to a bundled template."""

    type: Literal["template"]
    template_id: str = Field(min_length=1, max_length=100)

    @field_validator("template_id", mode="before")
    @classmethod
    def _clean_template_id(cls, value: str) -> str:
        return value.strip()


class ConfigSourceClone(BaseModel):
    """Reference to an existing workspace config."""

    type: Literal["clone"]
    config_id: str = Field(min_length=1, max_length=26)

    @field_validator("config_id", mode="before")
    @classmethod
    def _clean_config_id(cls, value: str) -> str:
        return value.strip()


ConfigSource = Annotated[
    ConfigSourceTemplate | ConfigSourceClone,
    Field(discriminator="type"),
]


class ConfigurationCreate(BaseModel):
    """Payload for creating a configuration."""

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=255)
    source: ConfigSource

    @field_validator("display_name", mode="before")
    @classmethod
    def _clean_display_name(cls, value: str) -> str:
        return value.strip()


class ConfigurationRecord(BaseModel):
    """Serialized configuration metadata."""

    model_config = ConfigDict(from_attributes=True)

    workspace_id: str
    config_id: str
    display_name: str
    status: str
    config_version: int
    content_digest: str | None = None
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None = None


class ConfigValidationIssue(BaseModel):
    """Description of a validation issue found on disk."""

    path: str
    message: str


class ConfigurationValidateResponse(BaseModel):
    """Result of running validation."""

    workspace_id: str
    config_id: str
    status: str
    content_digest: str | None = None
    issues: list[ConfigValidationIssue]


class ConfigurationActivateRequest(BaseModel):
    """Activation control flags."""

    ensure_build: bool = False


__all__ = [
    "ConfigSource",
    "ConfigSourceClone",
    "ConfigSourceTemplate",
    "ConfigValidationIssue",
    "ConfigurationCreate",
    "ConfigurationActivateRequest",
    "ConfigurationRecord",
    "ConfigurationValidateResponse",
]
