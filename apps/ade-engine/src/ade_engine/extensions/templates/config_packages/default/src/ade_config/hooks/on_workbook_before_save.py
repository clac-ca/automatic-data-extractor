from __future__ import annotations

from ade_engine.models import HookContext, HookName


def register(registry):
    registry.register_hook(on_workbook_before_save, hook_name=HookName.ON_WORKBOOK_BEFORE_SAVE, priority=0)


def on_workbook_before_save(
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
    """Example finalization hook."""

    if logger:
        logger.info("Config hook: workbook before save (%s)", metadata.get("output_file", ""))
