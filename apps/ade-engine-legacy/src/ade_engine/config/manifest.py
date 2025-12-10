"""Manifest helpers used by the config runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ade_engine.schemas.manifest import FieldConfig, HookCollection, ManifestV1, WriterConfig


@dataclass(frozen=True)
class ManifestContext:
    """Convenience wrapper for manifest data."""

    raw: dict[str, Any]
    model: ManifestV1

    @property
    def columns(self) -> list[FieldConfig]:
        return self.model.columns

    @property
    def writer(self) -> WriterConfig:
        return self.model.writer

    @property
    def hooks(self) -> HookCollection:
        return self.model.hooks

    @property
    def column_names(self) -> list[str]:
        return [col.name for col in self.model.columns]
