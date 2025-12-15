from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class TableView:
    """Read-only canonical table view for transforms/validators."""

    _columns: Mapping[str, list[Any]]
    mapping: Mapping[str, int | None]
    row_count: int

    def get(self, field: str) -> list[Any] | None:
        col = self._columns.get(field)
        if col is None:
            return None
        # Copy to prevent mutation of the underlying engine vectors.
        return list(col)

    def fields(self) -> list[str]:
        return list(self._columns.keys())


__all__ = ["TableView"]

