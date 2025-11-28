"""Pydantic models for the ade_config manifest."""
from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class FieldConfig(BaseModel):
    """Column metadata for a canonical field."""

    label: str
    module: str
    required: bool = False
    synonyms: list[str] = Field(default_factory=list)
    type: str | None = None

    model_config = ConfigDict(extra="forbid")


class ColumnsConfig(BaseModel):
    """Column ordering and field definitions."""

    order: list[str]
    fields: dict[str, FieldConfig]

    model_config = ConfigDict(extra="forbid")


class HookCollection(BaseModel):
    """Lifecycle hook modules keyed by stage."""

    on_run_start: list[str] = Field(default_factory=list)
    on_after_extract: list[str] = Field(default_factory=list)
    on_after_mapping: list[str] = Field(default_factory=list)
    on_before_save: list[str] = Field(default_factory=list)
    on_run_end: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class WriterConfig(BaseModel):
    """Writer behavior toggles from the manifest."""

    append_unmapped_columns: bool = True
    unmapped_prefix: str = "raw_"
    output_sheet: str | None = "Normalized"

    model_config = ConfigDict(extra="forbid")


class ManifestV1(BaseModel):
    """Top-level manifest model."""

    schema_id: str = Field(
        alias="schema",
        validation_alias=AliasChoices("schema", "schema_id"),
    )
    version: str
    name: str | None = None
    description: str | None = None
    script_api_version: int
    columns: ColumnsConfig
    hooks: HookCollection
    writer: WriterConfig
    extra: dict[str, Any] | None = Field(default=None, description="Reserved for future extensions")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @property
    def schema(self) -> str:
        return self.schema_id
