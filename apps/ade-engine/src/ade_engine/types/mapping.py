"""Mapping patch dataclass for hook-driven overrides."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnMappingPatch:
    """Change-set applied after initial mapping, before normalization.

    - ``assign`` maps canonical field -> source column index (0-based)
    - ``rename_passthrough`` maps source column index -> output header name
    - ``drop_passthrough`` lists passthrough source columns to omit from output
    """

    assign: dict[str, int] | None = None
    rename_passthrough: dict[int, str] | None = None
    drop_passthrough: set[int] | None = None


__all__ = ["ColumnMappingPatch"]
