from __future__ import annotations

from typing import Any

from ade_engine.registry import HookContext, HookName, hook


@hook(HookName.ON_TABLE_DETECTED)
def on_table_detected(ctx: HookContext) -> None:
    """Log table detection details."""

    table = ctx.table
    if ctx.logger and table:
        ctx.logger.info(
            "Config hook: table detected (sheet=%s, header_row=%s, mapped=%d)",
            getattr(table, "sheet_name", ""),
            getattr(table, "header_row_index", None),
            len(getattr(table, "mapped_columns", []) or []),
        )
