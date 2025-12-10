from __future__ import annotations

from ade_engine.registry.models import HookName


def register(registry):
    registry.register_hook(on_table_detected, hook_name=HookName.ON_TABLE_DETECTED, priority=0)


def on_table_detected(
    *,
    hook_name,
    metadata,
    state,
    workbook,
    sheet,
    table,
    input_file_name,
    logger,
) -> None:
    """Log table detection details."""

    if logger and table:
        logger.info(
            "Config hook: table detected (sheet=%s, header_row=%s, mapped=%d)",
            getattr(table, "sheet_name", ""),
            getattr(table, "header_row_index", None),
            len(getattr(table, "mapped_columns", []) or []),
        )
