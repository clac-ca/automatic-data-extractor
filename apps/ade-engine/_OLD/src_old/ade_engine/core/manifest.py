"""Typed manifest models and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field


class ScriptRef(BaseModel):
    """Reference to a hook script."""

    model_config = ConfigDict(extra="forbid")

    script: str
    enabled: bool = True


class HookCollection(BaseModel):
    """Collection of hook definitions grouped by lifecycle stage."""

    model_config = ConfigDict(extra="forbid")

    on_activate: tuple[ScriptRef, ...] = ()
    on_job_start: tuple[ScriptRef, ...] = ()
    on_after_extract: tuple[ScriptRef, ...] = ()
    on_before_save: tuple[ScriptRef, ...] = ()
    on_job_end: tuple[ScriptRef, ...] = ()


class ColumnMeta(BaseModel):
    """Metadata describing an output column."""

    model_config = ConfigDict(extra="forbid")

    label: str
    script: str
    required: bool = False
    enabled: bool = True
    synonyms: tuple[str, ...] = ()
    type_hint: str | None = None


class ColumnSection(BaseModel):
    """Manifest ``columns`` section."""

    model_config = ConfigDict(extra="forbid")

    order: list[str]
    meta: dict[str, ColumnMeta]


class EngineDefaults(BaseModel):
    """Defaults that influence pipeline behaviour."""

    model_config = ConfigDict(extra="forbid")

    timeout_ms: int | None = Field(default=None, ge=1000)
    memory_mb: int | None = Field(default=None, ge=64)
    runtime_network_access: bool = False
    mapping_score_threshold: float | None = Field(default=None, ge=0.0)
    detector_sample_size: int | None = Field(default=None, ge=1)


class EngineWriter(BaseModel):
    """Output writer configuration."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["row_streaming", "in_memory"] = Field(default="row_streaming")
    append_unmapped_columns: bool = True
    unmapped_prefix: str = Field(default="raw_", min_length=1)
    output_sheet: str = Field(default="Normalized", min_length=1, max_length=31)


class EngineSection(BaseModel):
    """Manifest ``engine`` section."""

    model_config = ConfigDict(extra="forbid")

    defaults: EngineDefaults = Field(default_factory=EngineDefaults)
    writer: EngineWriter = Field(default_factory=EngineWriter)


class ManifestInfo(BaseModel):
    """Metadata describing the config package itself."""

    model_config = ConfigDict(extra="forbid")

    schema: Literal["ade.manifest/v1.0"]
    title: str
    version: str
    description: str | None = None


class ManifestV1(BaseModel):
    """Typed representation of a v1 manifest."""

    model_config = ConfigDict(extra="forbid")

    config_script_api_version: Literal["1"]
    info: ManifestInfo
    engine: EngineSection
    hooks: HookCollection = Field(default_factory=HookCollection)
    columns: ColumnSection
    env: dict[str, str] = Field(default_factory=dict)


@dataclass(slots=True)
class ManifestContext:
    """Single manifest representation for the engine."""

    raw: dict[str, object]
    version: str | None = None
    model: ManifestV1 | None = None

    @property
    def column_order(self) -> list[str]:
        if self.model is not None:
            return list(self.model.columns.order)
        columns = (self.raw.get("columns") or {})
        if isinstance(columns, Mapping):
            order = columns.get("order", [])
            if isinstance(order, Iterable):
                return [str(item) for item in order]
        return []

    @property
    def column_meta_models(self) -> dict[str, ColumnMeta]:
        if self.model is not None:
            return dict(self.model.columns.meta)

        columns = self.raw.get("columns") or {}
        result: dict[str, ColumnMeta] = {}
        if isinstance(columns, Mapping):
            meta = columns.get("meta", {})
            if isinstance(meta, Mapping):
                for field, value in meta.items():
                    if isinstance(value, Mapping):
                        try:
                            result[str(field)] = ColumnMeta.model_validate(value)
                        except Exception:  # pragma: no cover - validation fallback
                            continue
        return result

    @property
    def defaults(self) -> EngineDefaults:
        if self.model is not None:
            return self.model.engine.defaults
        engine = self.raw.get("engine") or {}
        if isinstance(engine, Mapping):
            defaults = engine.get("defaults", {})
            if isinstance(defaults, Mapping):
                try:
                    return EngineDefaults.model_validate(defaults)
                except Exception:  # pragma: no cover - validation fallback
                    pass
        return EngineDefaults()

    @property
    def writer(self) -> EngineWriter:
        if self.model is not None:
            return self.model.engine.writer
        engine = self.raw.get("engine") or {}
        if isinstance(engine, Mapping):
            writer = engine.get("writer", {})
            if isinstance(writer, Mapping):
                try:
                    return EngineWriter.model_validate(writer)
                except Exception:  # pragma: no cover - validation fallback
                    pass
        return EngineWriter()

    # Compatibility helpers to ease migration away from dict-based accessors.
    @property
    def column_meta(self) -> dict[str, dict[str, object]]:
        if self.model is not None:
            return {
                field: meta.model_dump()
                for field, meta in self.model.columns.meta.items()
            }
        columns = self.raw.get("columns") or {}
        if isinstance(columns, Mapping):
            meta = columns.get("meta", {})
            if isinstance(meta, Mapping):
                return {
                    str(field): dict(value) if isinstance(value, Mapping) else {}
                    for field, value in meta.items()
                }
        return {}

    @property
    def column_models(self) -> dict[str, ColumnMeta]:
        return self.column_meta_models


__all__ = [
    "ColumnMeta",
    "ColumnSection",
    "EngineDefaults",
    "EngineSection",
    "EngineWriter",
    "HookCollection",
    "ManifestContext",
    "ManifestInfo",
    "ManifestV1",
    "ScriptRef",
]
