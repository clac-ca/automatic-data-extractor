"""Manifest helpers used by the config runtime.

This module provides a small wrapper around :class:`ManifestV1` to expose
typed accessors for the rest of the engine and script API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ade_engine.schemas.manifest import ColumnsConfig, HookCollection, ManifestV1, WriterConfig


@dataclass(frozen=True)
class ManifestContext:
    """Convenience wrapper for manifest data.

    Attributes
    ----------
    raw_json:
        The original manifest dictionary loaded from disk.
    model:
        The validated :class:`ManifestV1` instance.
    """

    raw_json: dict[str, Any]
    model: ManifestV1

    @property
    def columns(self) -> ColumnsConfig:
        """Shortcut to the manifest columns section."""

        return self.model.columns

    @property
    def writer(self) -> WriterConfig:
        """Shortcut to writer configuration."""

        return self.model.writer

    @property
    def hooks(self) -> HookCollection:
        """Shortcut to configured hooks."""

        return self.model.hooks
