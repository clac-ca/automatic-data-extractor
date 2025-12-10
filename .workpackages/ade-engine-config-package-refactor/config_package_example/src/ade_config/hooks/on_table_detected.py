from __future__ import annotations

from ade_engine.registry.models import HookContext, HookName


def register(registry):
    registry.register_hook(on_table_detected, hook_name=HookName.ON_TABLE_DETECTED, priority=0)


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
