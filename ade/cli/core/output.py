"""Output helpers for ADE CLI commands."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

__all__ = ["ColumnSpec", "print_rows", "print_json"]

ColumnAccessor = str | Callable[[Any], Any]
ColumnSpec = tuple[str, ColumnAccessor]


def _resolve_value(row: Any, accessor: ColumnAccessor) -> Any:
    if callable(accessor):
        return accessor(row)
    if isinstance(row, Mapping):
        return row.get(accessor)
    return getattr(row, accessor, None)


def print_rows(rows: Iterable[Any], columns: Sequence[ColumnSpec]) -> None:
    """Render ``rows`` using a simple left-aligned table."""

    materialised = list(rows)
    if not materialised:
        print("No results.")
        return

    resolved: list[list[str]] = []
    widths = [len(header) for header, _ in columns]

    for row in materialised:
        rendered: list[str] = []
        for index, (_header, accessor) in enumerate(columns):
            value = _resolve_value(row, accessor)
            text = "-" if value in (None, "") else str(value)
            rendered.append(text)
            widths[index] = max(widths[index], len(text))
        resolved.append(rendered)

    header_line = "  ".join(
        header.ljust(widths[index]) for index, (header, _accessor) in enumerate(columns)
    )
    print(header_line)
    for row_values in resolved:
        row_line = "  ".join(value.ljust(widths[index]) for index, value in enumerate(row_values))
        print(row_line)


def print_json(data: Any) -> None:
    """Emit ``data`` as formatted JSON for scripting."""

    print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))
