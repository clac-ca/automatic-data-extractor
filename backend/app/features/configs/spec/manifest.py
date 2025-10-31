"""Pydantic models representing config manifest structures."""

from __future__ import annotations

import re
from typing import Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "ColumnMeta",
    "ColumnsConfig",
    "EngineConfig",
    "EngineDefaults",
    "EngineWriter",
    "HookRef",
    "HooksConfig",
    "ManifestInfo",
    "ManifestV1",
]

TARGET_FIELD_RE = re.compile(r"^[a-z][a-z0-9_]*$")
TargetFieldId = str


class ManifestInfo(BaseModel):
    """Metadata about the manifest document."""

    model_config = ConfigDict(populate_by_name=True)

    schema_: Literal["ade.manifest/v1.0"] = Field(alias="schema")
    title: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=2000)


class EngineDefaults(BaseModel):
    """Execution defaults enforced by the job runner."""

    timeout_ms: int = Field(default=120_000, ge=1000)
    memory_mb: int = Field(default=512, ge=64)
    allow_net: bool = False
    min_mapping_confidence: float = Field(default=0.0, ge=0.0)


class EngineWriter(BaseModel):
    """Normalized workbook writer settings."""

    mode: Literal["row_streaming", "in_memory"] = "row_streaming"
    append_unmapped_columns: bool = True
    unmapped_prefix: str = Field(default="raw_", min_length=1)
    output_sheet: str = Field(default="Normalized", min_length=1, max_length=31)


class EngineConfig(BaseModel):
    """Top-level engine section of the manifest."""

    defaults: EngineDefaults = Field(default_factory=EngineDefaults)
    writer: EngineWriter = Field(default_factory=EngineWriter)


class HookRef(BaseModel):
    """A hook script reference."""

    script: str = Field(pattern=r"^(hooks/)?[A-Za-z0-9_.\-/]+\.py$")
    enabled: bool = True


class HooksConfig(BaseModel):
    """Hook entrypoints that wrap the job lifecycle."""

    on_activate: List[HookRef] = Field(default_factory=list)
    on_job_start: List[HookRef] = Field(default_factory=list)
    on_after_extract: List[HookRef] = Field(default_factory=list)
    on_job_end: List[HookRef] = Field(default_factory=list)


class ColumnMeta(BaseModel):
    """Metadata for a normalized output column."""

    label: str = Field(min_length=1, max_length=255)
    required: bool = False
    enabled: bool = True
    script: str = Field(pattern=r"^columns/[A-Za-z0-9_.\-/]+\.py$")
    synonyms: List[str] = Field(default_factory=list)
    type_hint: str | None = Field(default=None, max_length=64)


class ColumnsConfig(BaseModel):
    """Column ordering and per-field metadata."""

    order: List[TargetFieldId] = Field(min_length=1)
    meta: Dict[TargetFieldId, ColumnMeta]

    @field_validator("order")
    @classmethod
    def ensure_unique_order(cls, value: List[TargetFieldId]) -> List[TargetFieldId]:
        seen: set[str] = set()
        duplicates: list[str] = []
        for item in value:
            if not TARGET_FIELD_RE.match(item):
                raise ValueError(
                    f"Invalid column id {item!r}; expected lowercase snake_case"
                )
            if item in seen:
                duplicates.append(item)
            seen.add(item)
        if duplicates:
            raise ValueError(
                "Duplicate column ids in columns.order: "
                + ", ".join(sorted(set(duplicates)))
            )
        return value

    @model_validator(mode="after")
    def validate_meta_keys(self) -> "ColumnsConfig":
        missing = set(self.order) - set(self.meta.keys())
        if missing:
            raise ValueError(
                "columns.meta is missing entries for: " + ", ".join(sorted(missing))
            )
        extra = set(self.meta.keys()) - set(self.order)
        if extra:
            raise ValueError(
                "columns.meta contains keys not listed in columns.order: "
                + ", ".join(sorted(extra))
            )
        return self


class ManifestV1(BaseModel):
    """Normalized representation of ``ade.manifest/v1.0``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    info: ManifestInfo
    config_script_api_version: Literal["1"] = Field(alias="config_script_api_version")
    engine: EngineConfig = Field(default_factory=EngineConfig)
    env: Dict[str, str] = Field(default_factory=dict)
    hooks: HooksConfig = Field(default_factory=HooksConfig)
    columns: ColumnsConfig

    @field_validator("env")
    @classmethod
    def ensure_env_strings(cls, value: Dict[str, str]) -> Dict[str, str]:
        for key, val in value.items():
            if not isinstance(val, str):
                raise ValueError(f"Env value for {key!r} must be a string")
        return value
