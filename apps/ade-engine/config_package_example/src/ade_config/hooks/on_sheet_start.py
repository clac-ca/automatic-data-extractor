from __future__ import annotations

from ade_engine.registry.models import HookName


def register(registry):
    registry.register_hook(on_sheet_start, hook_name=HookName.ON_SHEET_START, priority=0)


def on_sheet_start(
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
    """Example sheet-start hook."""

    sheet_name = getattr(sheet, "title", getattr(sheet, "name", ""))
    if logger:
        logger.info("Config hook: sheet start (%s)", sheet_name)
