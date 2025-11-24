"""on_after_mapping hook.

Runs after MappedTable objects have been produced, before normalization.
"""

from __future__ import annotations

from typing import Any


def run(ctx: Any) -> None:
    """
    Emit a compact summary of mapped vs extra columns per table.

    This is intentionally simple and defensive so it's safe to copy as a
    starting point.
    """
    logger = getattr(ctx, "logger", None)
    tables = getattr(ctx, "tables", None) or []

    if logger is None:
        return

    for mapped_table in tables:
        raw = getattr(mapped_table, "raw", None)
        source_file = getattr(getattr(raw, "source_file", None), "name", None)
        source_sheet = getattr(raw, "source_sheet", None)
        mapping = getattr(mapped_table, "mapping", []) or []
        extras = getattr(mapped_table, "extras", []) or []

        logger.note(
            "Mapped table",
            file=source_file,
            sheet=source_sheet,
            mapped_columns=len(mapping),
            extra_columns=len(extras),
            stage=getattr(ctx, "stage", None),
        )
